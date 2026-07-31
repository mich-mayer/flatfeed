from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from eval.ai_qa_review_contract import (
    ReviewOutputError,
    parse_review_output,
)
from eval.ai_qa_scorer import (
    ERROR_FIELDS,
    ERROR_FIELD_LABELS,
    TRUTH_FIELD_TO_ERROR_FIELD,
)


SCORER_VERSION = "review-v1"
Profile = Literal["baseline", "candidate"]

_MODEL_INPUT_KEYS = {"case_id", "raw_text", "parser_snapshot"}
_TRUTH_KEYS = {
    "case_id",
    "case_type",
    "corrupted_field",
    "expected_value",
    "corrupted_value",
    "corruption_type",
}
_BASELINE_OUTPUT_KEYS = {"has_error", "error_field"}


@dataclass(frozen=True)
class NormalizedDecision:
    covered: bool
    review_required: bool
    error_field: str | None
    review_reason: str | None
    failure_type: str | None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line:
            raise ValueError(f"{path.name}:{line_number} is blank")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path.name}:{line_number} is not valid envelope JSON"
            ) from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path.name}:{line_number} must be an object")
        rows.append(row)
    return rows


def _index_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    required_keys: set[str],
    label: str,
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if set(row) != required_keys:
            raise ValueError(f"{label} row does not match its schema")
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{label} case_id must be a non-empty string")
        if case_id in indexed:
            raise ValueError(f"duplicate {label} case_id: {case_id}")
        indexed[case_id] = row
    return indexed


def _index_predictions(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_ids: set[str],
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("prediction case_id must be a non-empty string")
        if case_id not in expected_ids:
            raise ValueError(f"prediction has unknown case_id: {case_id}")
        if case_id in indexed:
            raise ValueError(f"duplicate prediction case_id: {case_id}")
        status = row.get("status")
        if status not in {"completed", "technical_failure"}:
            raise ValueError(f"invalid prediction status for {case_id}")
        indexed[case_id] = row

    missing = expected_ids - set(indexed)
    if missing:
        raise ValueError(
            f"prediction artifact is incomplete; missing {len(missing)} cases"
        )
    return indexed


def _parse_baseline_output(raw_output: object) -> NormalizedDecision:
    if not isinstance(raw_output, str):
        return NormalizedDecision(False, False, None, None, "invalid_schema")
    try:
        output = json.loads(raw_output)
    except json.JSONDecodeError:
        return NormalizedDecision(False, False, None, None, "invalid_json")
    if not isinstance(output, dict) or set(output) != _BASELINE_OUTPUT_KEYS:
        return NormalizedDecision(False, False, None, None, "invalid_schema")

    has_error = output["has_error"]
    error_field = output["error_field"]
    valid = isinstance(has_error, bool) and (
        (has_error is False and error_field is None)
        or (
            has_error is True
            and isinstance(error_field, str)
            and error_field in ERROR_FIELDS
        )
    )
    if not valid:
        return NormalizedDecision(False, False, None, None, "invalid_schema")
    return NormalizedDecision(
        covered=True,
        review_required=has_error,
        error_field=error_field,
        review_reason=None,
        failure_type=None,
    )


def _parse_candidate_output(
    raw_output: object,
    *,
    input_row: Mapping[str, Any],
) -> NormalizedDecision:
    if not isinstance(raw_output, str):
        return NormalizedDecision(False, False, None, None, "invalid_schema")
    try:
        decision = parse_review_output(
            raw_output,
            raw_text=str(input_row["raw_text"]),
            parser_snapshot=input_row["parser_snapshot"],
        )
    except ReviewOutputError as exc:
        return NormalizedDecision(
            False,
            False,
            None,
            None,
            str(exc),
        )
    return NormalizedDecision(
        covered=True,
        review_required=decision.review_required,
        error_field=decision.error_field,
        review_reason=decision.review_reason,
        failure_type=None,
    )


def _parse_prediction(
    row: Mapping[str, Any],
    *,
    profile: Profile,
    input_row: Mapping[str, Any],
) -> NormalizedDecision:
    if row["status"] == "technical_failure":
        failure = row.get("failure")
        failure_type = (
            str(failure.get("type"))
            if isinstance(failure, dict) and failure.get("type")
            else "technical_failure"
        )
        return NormalizedDecision(
            False,
            False,
            None,
            None,
            failure_type,
        )
    if profile == "baseline":
        return _parse_baseline_output(row.get("raw_output"))
    return _parse_candidate_output(
        row.get("raw_output"),
        input_row=input_row,
    )


def _ratio(numerator: int, denominator: int) -> dict[str, object]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def score_review_predictions(
    *,
    profile: Profile,
    input_rows: Sequence[Mapping[str, Any]],
    truth_rows: Sequence[Mapping[str, Any]],
    prediction_rows: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    """Score either output format against the same hidden truth."""

    if profile not in {"baseline", "candidate"}:
        raise ValueError("profile must be baseline or candidate")

    inputs = _index_rows(
        input_rows,
        required_keys=_MODEL_INPUT_KEYS,
        label="model input",
    )
    truth = _index_rows(
        truth_rows,
        required_keys=_TRUTH_KEYS,
        label="truth",
    )
    if set(inputs) != set(truth):
        raise ValueError("model inputs and truth contain different case IDs")
    predictions = _index_predictions(
        prediction_rows,
        expected_ids=set(truth),
    )

    clean_total = 0
    corrupted_total = 0
    covered = 0
    detected = 0
    correct_field = 0
    false_alerts = 0
    correct_cases = 0
    review_reasons: Counter[str] = Counter()
    failure_types: Counter[str] = Counter()
    per_field: dict[str, Counter[str]] = {
        field: Counter()
        for field in ERROR_FIELDS
    }
    false_negatives: list[dict[str, object]] = []
    false_positives: list[dict[str, object]] = []
    wrong_fields: list[dict[str, object]] = []

    for case_id, truth_row in truth.items():
        input_row = inputs[case_id]
        prediction = _parse_prediction(
            predictions[case_id],
            profile=profile,
            input_row=input_row,
        )
        if prediction.covered:
            covered += 1
        elif prediction.failure_type:
            failure_types[prediction.failure_type] += 1

        if prediction.review_reason:
            review_reasons[prediction.review_reason] += 1

        if truth_row["case_type"] == "clean":
            clean_total += 1
            if prediction.review_required:
                false_alerts += 1
                false_positives.append(
                    {
                        "case_id": case_id,
                        "error_field": prediction.error_field,
                        "review_reason": prediction.review_reason,
                    }
                )
            elif prediction.covered:
                correct_cases += 1
            continue

        corrupted_total += 1
        expected_field = TRUTH_FIELD_TO_ERROR_FIELD[
            str(truth_row["corrupted_field"])
        ]
        field_counts = per_field[expected_field]
        field_counts["total"] += 1

        if prediction.review_required:
            detected += 1
            field_counts["detected"] += 1
            if prediction.error_field == expected_field:
                correct_field += 1
                correct_cases += 1
                field_counts["correct_field"] += 1
            else:
                wrong_fields.append(
                    {
                        "case_id": case_id,
                        "expected_field": expected_field,
                        "predicted_field": prediction.error_field,
                        "review_reason": prediction.review_reason,
                    }
                )
        else:
            false_negatives.append(
                {
                    "case_id": case_id,
                    "expected_field": expected_field,
                    "covered": prediction.covered,
                    "failure_type": prediction.failure_type,
                }
            )

    field_report = {
        field: {
            "label": ERROR_FIELD_LABELS[field],
            "total": per_field[field]["total"],
            "detected": per_field[field]["detected"],
            "correct_field": per_field[field]["correct_field"],
            "correct_field_rate": _ratio(
                per_field[field]["correct_field"],
                per_field[field]["total"],
            ),
        }
        for field in ERROR_FIELDS
    }
    return {
        "scorer_version": SCORER_VERSION,
        "profile": profile,
        "counts": {
            "attempted": len(truth),
            "clean": clean_total,
            "corrupted": corrupted_total,
        },
        "metrics": {
            "successful_check_rate": _ratio(covered, len(truth)),
            "parser_error_detection_rate": _ratio(
                detected,
                corrupted_total,
            ),
            "false_alert_rate": _ratio(false_alerts, clean_total),
            "correct_field_detection_rate": _ratio(
                correct_field,
                corrupted_total,
            ),
            "case_accuracy": _ratio(correct_cases, len(truth)),
        },
        "per_field": field_report,
        "review_reasons": dict(sorted(review_reasons.items())),
        "failure_types": dict(sorted(failure_types.items())),
        "diagnostics": {
            "false_negatives": false_negatives,
            "false_positives": false_positives,
            "wrong_fields": wrong_fields,
        },
    }


def score_review_prediction_files(
    *,
    profile: Profile,
    model_inputs_path: Path,
    truth_path: Path,
    predictions_path: Path,
) -> dict[str, object]:
    return score_review_predictions(
        profile=profile,
        input_rows=_read_jsonl(model_inputs_path),
        truth_rows=_read_jsonl(truth_path),
        prediction_rows=_read_jsonl(predictions_path),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score a review-v1 development prediction artifact.",
    )
    parser.add_argument(
        "--profile",
        choices=("baseline", "candidate"),
        required=True,
    )
    parser.add_argument("--model-inputs", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = score_review_prediction_files(
        profile=args.profile,
        model_inputs_path=args.model_inputs,
        truth_path=args.truth,
        predictions_path=args.predictions,
    )
    rendered = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
