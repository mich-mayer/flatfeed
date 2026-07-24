from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any


SCORER_VERSION = "1.0"
MODEL_OUTPUT_SCHEMA_VERSION = "1.0"
EXPERIMENT_LABEL = "synthetic offline AI QA evaluation"

ERROR_FIELDS = (
    "wbs",
    "rent_kalt",
    "rooms",
    "address_postal_code",
    "district",
    "floor",
    "rent_warm",
)
ERROR_FIELD_LABELS = {
    "wbs": "WBS",
    "rent_kalt": "Kaltmiete",
    "rooms": "rooms",
    "address_postal_code": "address/postal code",
    "district": "district",
    "floor": "floor",
    "rent_warm": "Warmmiete",
}
TRUTH_FIELD_TO_ERROR_FIELD = {
    "display_wbs": "wbs",
    "rent_kalt": "rent_kalt",
    "rooms": "rooms",
    "address": "address_postal_code",
    "postal_code": "address_postal_code",
    "district": "district",
    "floor": "floor",
    "rent_warm": "rent_warm",
}

_TRUTH_KEYS = {
    "case_id",
    "case_type",
    "corrupted_field",
    "expected_value",
    "corrupted_value",
    "corruption_type",
}
_PREDICTION_KEYS = {
    "case_id",
    "status",
    "raw_output",
    "failure",
    "usage",
    "cost_usd",
    "latency_ms",
    "latency_mode",
    "retry_count",
}
_USAGE_KEYS = {
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
}
_MODEL_OUTPUT_KEYS = {"has_error", "error_field"}
_Z_95 = 1.959963984540054
_FAILURE_TYPE_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")

_ACCEPTANCE_GATES = (
    ("structured_output_coverage", "min", 0.995),
    ("error_recall", "min", 0.90),
    ("false_alert_rate", "max", 0.08),
    ("challenge_set_precision", "min", 0.85),
    ("field_localization_accuracy", "min", 0.90),
)
_PER_FIELD_ACCEPTANCE_GATES = (
    ("wbs", 0.90),
    ("rent_kalt", 0.90),
    ("rooms", 0.90),
)


@dataclass(frozen=True)
class ParsedPrediction:
    case_id: str
    outcome: str
    covered: bool
    has_error: bool
    error_field: str | None
    technical_failure_type: str | None = None


def _is_nonnegative_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 0
    )


def _is_nonnegative_integer(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL envelope.

    Invalid model JSON belongs in the valid outer envelope's ``raw_output``
    string. An invalid outer JSONL line is an artifact-integrity error because
    it cannot be joined safely to a case ID.
    """

    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as artifact:
        for line_number, line in enumerate(artifact, start=1):
            if not line.strip():
                raise ValueError(f"{path.name}:{line_number} is blank")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path.name}:{line_number} is not valid envelope JSON"
                ) from exc
            if not isinstance(row, dict):
                raise ValueError(
                    f"{path.name}:{line_number} must be a JSON object"
                )
            rows.append(row)
    return rows


def _validate_truth_rows(
    truth_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    if not truth_rows:
        raise ValueError("truth artifact must contain at least one case")
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in truth_rows:
        if set(row) != _TRUTH_KEYS:
            raise ValueError("truth rows do not match the answer-key schema")
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("truth case_id must be a non-empty string")
        if case_id in indexed:
            raise ValueError(f"duplicate truth case_id: {case_id}")

        case_type = row.get("case_type")
        if case_type not in {"clean", "corrupted"}:
            raise ValueError(f"invalid truth case_type for {case_id}")
        if case_type == "clean":
            hidden_values = (
                row.get("corrupted_field"),
                row.get("expected_value"),
                row.get("corrupted_value"),
                row.get("corruption_type"),
            )
            if any(value is not None for value in hidden_values):
                raise ValueError(f"clean truth contains corruption data: {case_id}")
        else:
            corrupted_field = row.get("corrupted_field")
            if corrupted_field not in TRUTH_FIELD_TO_ERROR_FIELD:
                raise ValueError(f"unsupported truth field for {case_id}")
            if row.get("expected_value") == row.get("corrupted_value"):
                raise ValueError(f"truth corruption did not change {case_id}")
            if not isinstance(row.get("corruption_type"), str) or not row[
                "corruption_type"
            ].strip():
                raise ValueError(f"truth corruption_type is missing for {case_id}")
        indexed[case_id] = row
    return indexed


def _validate_prediction_envelope(row: Mapping[str, Any]) -> None:
    extra_keys = set(row) - _PREDICTION_KEYS
    if extra_keys:
        raise ValueError(
            f"prediction envelope contains unsupported keys: {sorted(extra_keys)}"
        )
    case_id = row.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("prediction case_id must be a non-empty string")
    status = row.get("status")
    if status not in {"completed", "technical_failure"}:
        raise ValueError(f"invalid prediction status for {case_id}")

    if status == "technical_failure":
        failure = row.get("failure")
        if (
            not isinstance(failure, dict)
            or set(failure) != {"type"}
            or not isinstance(failure.get("type"), str)
            or not _FAILURE_TYPE_PATTERN.fullmatch(failure["type"])
        ):
            raise ValueError(
                f"technical failure needs a safe category for {case_id}"
            )
    elif row.get("failure") is not None:
        raise ValueError(f"completed prediction cannot contain failure for {case_id}")

    usage = row.get("usage")
    if usage is not None:
        if not isinstance(usage, dict) or set(usage) != _USAGE_KEYS:
            raise ValueError(f"invalid usage schema for {case_id}")
        if not all(_is_nonnegative_integer(value) for value in usage.values()):
            raise ValueError(f"usage values must be non-negative integers: {case_id}")

    for key in ("cost_usd", "latency_ms"):
        if row.get(key) is not None and not _is_nonnegative_number(row[key]):
            raise ValueError(f"{key} must be a non-negative number: {case_id}")
    if row.get("retry_count") is not None and not _is_nonnegative_integer(
        row["retry_count"]
    ):
        raise ValueError(f"retry_count must be a non-negative integer: {case_id}")
    if row.get("latency_mode") is not None and (
        not isinstance(row["latency_mode"], str)
        or not row["latency_mode"].strip()
    ):
        raise ValueError(f"latency_mode must be a non-empty string: {case_id}")
    if row.get("latency_mode") is not None and row.get("latency_ms") is None:
        raise ValueError(f"latency_mode requires latency_ms: {case_id}")


def _index_prediction_rows(
    prediction_rows: Sequence[Mapping[str, Any]],
    *,
    truth_ids: set[str],
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in prediction_rows:
        _validate_prediction_envelope(row)
        case_id = row["case_id"]
        if case_id not in truth_ids:
            raise ValueError(f"prediction has unknown case_id: {case_id}")
        if case_id in indexed:
            raise ValueError(f"duplicate prediction case_id: {case_id}")
        indexed[case_id] = row
    missing_ids = sorted(truth_ids - set(indexed))
    if missing_ids:
        preview = ", ".join(missing_ids[:3])
        suffix = "..." if len(missing_ids) > 3 else ""
        raise ValueError(
            "prediction artifact is incomplete; missing case_id values: "
            f"{preview}{suffix}"
        )
    return indexed


def _parse_prediction(row: Mapping[str, Any]) -> ParsedPrediction:
    case_id = str(row["case_id"])
    if row["status"] == "technical_failure":
        return ParsedPrediction(
            case_id=case_id,
            outcome="technical_failure",
            covered=False,
            has_error=False,
            error_field=None,
            technical_failure_type=str(row["failure"]["type"]),
        )

    raw_output = row.get("raw_output")
    if not isinstance(raw_output, str):
        return ParsedPrediction(
            case_id=case_id,
            outcome="invalid_schema",
            covered=False,
            has_error=False,
            error_field=None,
        )
    try:
        output = json.loads(raw_output)
    except json.JSONDecodeError:
        return ParsedPrediction(
            case_id=case_id,
            outcome="invalid_json",
            covered=False,
            has_error=False,
            error_field=None,
        )
    if not isinstance(output, dict) or set(output) != _MODEL_OUTPUT_KEYS:
        return ParsedPrediction(
            case_id=case_id,
            outcome="invalid_schema",
            covered=False,
            has_error=False,
            error_field=None,
        )

    has_error = output.get("has_error")
    error_field = output.get("error_field")
    valid = isinstance(has_error, bool) and (
        (has_error is False and error_field is None)
        or (
            has_error is True
            and isinstance(error_field, str)
            and error_field in ERROR_FIELDS
        )
    )
    if not valid:
        return ParsedPrediction(
            case_id=case_id,
            outcome="invalid_schema",
            covered=False,
            has_error=False,
            error_field=None,
        )
    return ParsedPrediction(
        case_id=case_id,
        outcome="valid",
        covered=True,
        has_error=has_error,
        error_field=error_field,
    )


def wilson_95_interval(
    numerator: int,
    denominator: int,
) -> dict[str, float | None]:
    if denominator < 0 or numerator < 0 or numerator > denominator:
        raise ValueError("invalid proportion counts")
    if denominator == 0:
        return {"low": None, "high": None}

    proportion = numerator / denominator
    z_squared = _Z_95**2
    scale = 1 + z_squared / denominator
    center = (proportion + z_squared / (2 * denominator)) / scale
    margin = (
        _Z_95
        * math.sqrt(
            proportion * (1 - proportion) / denominator
            + z_squared / (4 * denominator**2)
        )
        / scale
    )
    return {
        "low": max(0.0, center - margin),
        "high": min(1.0, center + margin),
    }


def _proportion(numerator: int, denominator: int) -> dict[str, object]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
        "wilson_95_ci": wilson_95_interval(numerator, denominator),
    }


def _percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return ordered[lower_index]
    weight = position - lower_index
    return ordered[lower_index] + (
        ordered[upper_index] - ordered[lower_index]
    ) * weight


def _aggregate_operational(
    prediction_rows: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    token_totals = {key: 0 for key in _USAGE_KEYS}
    usage_records = 0
    cost_total = Decimal("0")
    cost_records = 0
    retry_total = 0
    latency_by_mode: dict[str, list[float]] = {}
    completed_cases = 0

    for row in prediction_rows:
        if row["status"] == "completed":
            completed_cases += 1
        usage = row.get("usage")
        if usage is not None:
            usage_records += 1
            for key in _USAGE_KEYS:
                token_totals[key] += int(usage[key])
        if row.get("cost_usd") is not None:
            cost_records += 1
            cost_total += Decimal(str(row["cost_usd"]))
        retry_total += int(row.get("retry_count", 0))
        if row.get("latency_ms") is not None:
            mode = str(row.get("latency_mode") or "unspecified")
            latency_by_mode.setdefault(mode, []).append(float(row["latency_ms"]))

    usage_report: dict[str, object] | None = None
    if usage_records:
        usage_report = {
            **token_totals,
            "total_tokens": (
                token_totals["input_tokens"]
                + token_totals["output_tokens"]
            ),
            "records_with_usage": usage_records,
            "total_case_records": len(prediction_rows),
            "is_partial": usage_records != len(prediction_rows),
        }

    cost_report: dict[str, object] | None = None
    if cost_records:
        total_cost = float(cost_total)
        cost_report = {
            "total_usd": total_cost,
            "records_with_cost": cost_records,
            "total_case_records": len(prediction_rows),
            "is_partial": cost_records != len(prediction_rows),
            "cost_per_completed_case_usd": (
                total_cost / completed_cases
                if completed_cases and cost_records == len(prediction_rows)
                else None
            ),
        }

    latency_report = {
        mode: {
            "sample_count": len(values),
            "total_case_records": len(prediction_rows),
            "is_partial": len(values) != len(prediction_rows),
            "p50_ms": _percentile(values, 0.50),
            "p95_ms": _percentile(values, 0.95),
        }
        for mode, values in sorted(latency_by_mode.items())
    }
    return {
        "case_result_records": len(prediction_rows),
        "completed_cases": completed_cases,
        "request_count": len(prediction_rows) + retry_total,
        "retry_count": retry_total,
        "token_usage": usage_report,
        "cost": cost_report,
        "latency_by_mode": latency_report or None,
    }


def _evaluate_acceptance_gates(
    metrics: Mapping[str, Mapping[str, object]],
    per_field_recall: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    gates: dict[str, dict[str, object]] = {}
    for metric_name, comparison, threshold in _ACCEPTANCE_GATES:
        value = metrics[metric_name]["value"]
        if value is None:
            status = "not_evaluable"
        elif comparison == "min":
            status = "pass" if value >= threshold else "fail"
        else:
            status = "pass" if value <= threshold else "fail"
        gates[metric_name] = {
            "comparison": comparison,
            "threshold": threshold,
            "value": value,
            "status": status,
        }
    for field, threshold in _PER_FIELD_ACCEPTANCE_GATES:
        value = per_field_recall[field]["value"]
        gate_name = f"{field}_per_field_recall"
        gates[gate_name] = {
            "comparison": "min",
            "threshold": threshold,
            "value": value,
            "status": (
                "not_evaluable"
                if value is None
                else ("pass" if value >= threshold else "fail")
            ),
        }
    statuses = {gate["status"] for gate in gates.values()}
    if "not_evaluable" in statuses:
        overall_status = "not_evaluable"
    elif "fail" in statuses:
        overall_status = "fail"
    else:
        overall_status = "pass"
    return {
        "overall_status": overall_status,
        "gates": gates,
        "note": "Targets from the eval contract; not achieved results until scored.",
    }


def score_predictions(
    truth_rows: Sequence[Mapping[str, Any]],
    prediction_rows: Sequence[Mapping[str, Any]],
    *,
    split: str,
    run_label: str | None = None,
) -> dict[str, Any]:
    """Score offline model predictions against a separate answer key."""

    if not isinstance(split, str) or not split.strip():
        raise ValueError("split must be a non-empty string")
    truth_by_id = _validate_truth_rows(truth_rows)
    predictions_by_id = _index_prediction_rows(
        prediction_rows,
        truth_ids=set(truth_by_id),
    )

    clean_count = sum(
        truth["case_type"] == "clean"
        for truth in truth_by_id.values()
    )
    corrupted_count = len(truth_by_id) - clean_count
    counts = Counter(
        {
            "total_cases": len(truth_by_id),
            "clean_cases": clean_count,
            "corrupted_cases": corrupted_count,
            "valid_structured_outputs": 0,
            "uncovered_cases": 0,
            "invalid_structured_outputs": 0,
            "technical_failures": 0,
            "alerts": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "alerted_corrupted_cases": 0,
            "correctly_localized_alerts": 0,
            "wrong_field_localizations": 0,
            "outcome_valid": 0,
            "outcome_invalid_json": 0,
            "outcome_invalid_schema": 0,
            "outcome_technical_failure": 0,
        }
    )
    technical_failure_categories: Counter[str] = Counter()
    false_positives: list[dict[str, object]] = []
    false_negatives: list[dict[str, object]] = []
    wrong_localizations: list[dict[str, object]] = []
    invalid_outputs: list[dict[str, object]] = []
    field_counts = {
        field: Counter(
            {
                "total_corrupted": 0,
                "alerted": 0,
                "correctly_localized": 0,
                "wrong_localization": 0,
                "missed": 0,
            }
        )
        for field in ERROR_FIELDS
    }
    field_miss_reasons = {
        field: Counter()
        for field in ERROR_FIELDS
    }

    for case_id, truth in truth_by_id.items():
        parsed = _parse_prediction(predictions_by_id[case_id])

        counts[f"outcome_{parsed.outcome}"] += 1
        if parsed.covered:
            counts["valid_structured_outputs"] += 1
        else:
            counts["uncovered_cases"] += 1
        if parsed.outcome in {"invalid_json", "invalid_schema"}:
            counts["invalid_structured_outputs"] += 1
            invalid_outputs.append(
                {
                    "case_id": case_id,
                    "reason": parsed.outcome,
                }
            )
        if parsed.technical_failure_type is not None:
            counts["technical_failures"] += 1
            technical_failure_categories[parsed.technical_failure_type] += 1

        is_corrupted = truth["case_type"] == "corrupted"
        is_alert = parsed.covered and parsed.has_error
        if is_alert:
            counts["alerts"] += 1

        if not is_corrupted:
            if is_alert:
                counts["false_positives"] += 1
                false_positives.append(
                    {
                        "case_id": case_id,
                        "predicted_field": parsed.error_field,
                    }
                )
            continue

        expected_field = TRUTH_FIELD_TO_ERROR_FIELD[truth["corrupted_field"]]
        field_count = field_counts[expected_field]
        field_count["total_corrupted"] += 1
        if not is_alert:
            miss_reason = (
                "model_no_alert"
                if parsed.outcome == "valid"
                else parsed.outcome
            )
            counts["false_negatives"] += 1
            field_count["missed"] += 1
            field_miss_reasons[expected_field][miss_reason] += 1
            false_negatives.append(
                {
                    "case_id": case_id,
                    "expected_field": expected_field,
                    "reason": miss_reason,
                }
            )
            continue

        counts["alerted_corrupted_cases"] += 1
        field_count["alerted"] += 1
        if parsed.error_field == expected_field:
            counts["correctly_localized_alerts"] += 1
            field_count["correctly_localized"] += 1
        else:
            counts["wrong_field_localizations"] += 1
            field_count["wrong_localization"] += 1
            wrong_localizations.append(
                {
                    "case_id": case_id,
                    "expected_field": expected_field,
                    "predicted_field": parsed.error_field,
                }
            )

    metrics = {
        "error_recall": _proportion(
            counts["alerted_corrupted_cases"],
            corrupted_count,
        ),
        "missed_error_rate": _proportion(
            counts["false_negatives"],
            corrupted_count,
        ),
        "false_alert_rate": _proportion(
            counts["false_positives"],
            clean_count,
        ),
        "challenge_set_precision": _proportion(
            counts["alerted_corrupted_cases"],
            counts["alerts"],
        ),
        "field_localization_accuracy": _proportion(
            counts["correctly_localized_alerts"],
            counts["alerted_corrupted_cases"],
        ),
        "structured_output_coverage": _proportion(
            counts["valid_structured_outputs"],
            len(truth_by_id),
        ),
        "technical_failure_rate": _proportion(
            counts["technical_failures"],
            len(truth_by_id),
        ),
    }

    field_breakdown: dict[str, dict[str, object]] = {}
    per_field_recall: dict[str, dict[str, object]] = {}
    for field in ERROR_FIELDS:
        field_count = field_counts[field]
        localized_recall = _proportion(
            field_count["correctly_localized"],
            field_count["total_corrupted"],
        )
        per_field_recall[field] = localized_recall
        field_breakdown[field] = {
            "label": ERROR_FIELD_LABELS[field],
            **dict(field_count),
            "missed_by_reason": dict(
                sorted(field_miss_reasons[field].items())
            ),
            "error_alert_recall": _proportion(
                field_count["alerted"],
                field_count["total_corrupted"],
            ),
            "localized_recall": localized_recall,
        }

    acceptance_gates = _evaluate_acceptance_gates(
        metrics,
        per_field_recall,
    )
    return {
        "report_schema_version": "1.0",
        "scorer_version": SCORER_VERSION,
        "model_output_schema_version": MODEL_OUTPUT_SCHEMA_VERSION,
        "experiment": EXPERIMENT_LABEL,
        "evidence_scope": (
            "Synthetic challenge-set engineering artifact; "
            "not production precision or user-impact evidence."
        ),
        "split": split,
        "run_label": run_label,
        "counts": dict(counts),
        "metrics": metrics,
        "per_field_recall": per_field_recall,
        "field_breakdown": field_breakdown,
        "acceptance_gates": acceptance_gates,
        "operational": _aggregate_operational(prediction_rows),
        "diagnostics": {
            "technical_failure_categories": dict(
                sorted(technical_failure_categories.items())
            ),
            "false_positives": sorted(
                false_positives,
                key=lambda row: str(row["case_id"]),
            ),
            "false_negatives": sorted(
                false_negatives,
                key=lambda row: str(row["case_id"]),
            ),
            "wrong_field_localizations": sorted(
                wrong_localizations,
                key=lambda row: str(row["case_id"]),
            ),
            "invalid_outputs": sorted(
                invalid_outputs,
                key=lambda row: str(row["case_id"]),
            ),
        },
    }


def score_prediction_files(
    *,
    truth_path: Path,
    predictions_path: Path,
    split: str,
    run_label: str | None = None,
) -> dict[str, Any]:
    truth_rows = load_jsonl(truth_path)
    prediction_rows = load_jsonl(predictions_path)
    report = score_predictions(
        truth_rows,
        prediction_rows,
        split=split,
        run_label=run_label,
    )
    report["provenance"] = {
        "truth_file": truth_path.name,
        "truth_sha256": _sha256_file(truth_path),
        "predictions_file": predictions_path.name,
        "predictions_sha256": _sha256_file(predictions_path),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score offline AI QA prediction envelopes.",
    )
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--run-label")
    args = parser.parse_args()

    report = score_prediction_files(
        truth_path=args.truth,
        predictions_path=args.predictions,
        split=args.split,
        run_label=args.run_label,
    )
    from eval.ai_qa_reports import write_report_bundle

    written = write_report_bundle(report, args.output_dir)
    print(
        json.dumps(
            {
                "experiment": report["experiment"],
                "split": report["split"],
                "total_cases": report["counts"]["total_cases"],
                "artifacts": {
                    name: str(path)
                    for name, path in written.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
