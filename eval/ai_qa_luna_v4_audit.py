from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from eval.ai_qa_luna_v4_cycle import (
    DEFAULT_LUNA_V4_DATASET_DIR,
    WBS_SEMANTIC_DRIFT_PHRASES,
)
from eval.ai_qa_scorer import TRUTH_FIELD_TO_ERROR_FIELD, load_jsonl


DEFAULT_RUN_DIR = Path(__file__).with_name("runs") / "luna-v4-calibration"
DEFAULT_INPUT_PATH = DEFAULT_LUNA_V4_DATASET_DIR / "calibration_model_inputs.jsonl"
DEFAULT_TRUTH_PATH = DEFAULT_LUNA_V4_DATASET_DIR / "calibration_truth.jsonl"
DEFAULT_PREDICTIONS_PATH = DEFAULT_RUN_DIR / "predictions.jsonl"


def _phrase_catalog(
    wbs_phrases: Mapping[str, Sequence[str]],
) -> dict[str, str]:
    return {
        phrase: expected_wbs
        for expected_wbs, phrases in wbs_phrases.items()
        for phrase in phrases
    }


def _find_wbs_phrase(
    raw_text: str,
    *,
    wbs_phrases: Mapping[str, Sequence[str]],
) -> tuple[str, str]:
    matches = [
        (phrase, expected_wbs)
        for phrase, expected_wbs in _phrase_catalog(wbs_phrases).items()
        if raw_text.endswith(phrase)
    ]
    if len(matches) != 1:
        raise ValueError("listing must end in exactly one registered WBS phrase")
    return matches[0]


def _prediction_value(row: Mapping[str, object]) -> tuple[bool, str | None]:
    if row.get("status") != "completed":
        raise ValueError("audit requires a technically complete calibration run")
    raw_output = row.get("raw_output")
    if not isinstance(raw_output, str):
        raise ValueError("prediction lacks raw_output")
    parsed = json.loads(raw_output)
    has_error = parsed.get("has_error")
    error_field = parsed.get("error_field")
    if not isinstance(has_error, bool):
        raise ValueError("prediction has invalid has_error")
    if error_field is not None and not isinstance(error_field, str):
        raise ValueError("prediction has invalid error_field")
    return has_error, error_field


def build_failure_audit(
    *,
    input_rows: Sequence[Mapping[str, object]],
    truth_rows: Sequence[Mapping[str, object]],
    prediction_rows: Sequence[Mapping[str, object]],
    wbs_phrases: Mapping[str, Sequence[str]] = WBS_SEMANTIC_DRIFT_PHRASES,
    cycle_label: str = "Luna-v4",
) -> dict[str, object]:
    truth_by_id = {str(row["case_id"]): row for row in truth_rows}
    prediction_by_id = {str(row["case_id"]): row for row in prediction_rows}
    if len(truth_by_id) != len(truth_rows):
        raise ValueError("truth contains duplicate case IDs")
    if len(prediction_by_id) != len(prediction_rows):
        raise ValueError("predictions contain duplicate case IDs")
    input_ids = {str(row["case_id"]) for row in input_rows}
    if input_ids != set(truth_by_id) or input_ids != set(prediction_by_id):
        raise ValueError("input, truth, and prediction case IDs differ")

    totals: Counter[str] = Counter()
    by_phrase: dict[str, Counter[str]] = defaultdict(Counter)
    phrase_expected_wbs: dict[str, str] = {}
    wrong_routes: Counter[str] = Counter()

    for input_row in input_rows:
        case_id = str(input_row["case_id"])
        truth = truth_by_id[case_id]
        has_error, predicted_field = _prediction_value(
            prediction_by_id[case_id]
        )
        phrase, expected_wbs = _find_wbs_phrase(
            str(input_row["raw_text"]),
            wbs_phrases=wbs_phrases,
        )
        phrase_expected_wbs[phrase] = expected_wbs
        stats = by_phrase[phrase]
        stats["exposures"] += 1

        case_type = truth.get("case_type")
        corrupted_field = truth.get("corrupted_field")
        if case_type == "clean":
            totals["clean_cases"] += 1
            stats["clean_exposures"] += 1
            if has_error:
                totals["false_alerts"] += 1
                stats["clean_false_alerts"] += 1
                if predicted_field == "wbs":
                    totals["clean_false_alerts_wbs"] += 1
                    stats["clean_false_alerts_wbs"] += 1
            continue

        if case_type != "corrupted" or not isinstance(corrupted_field, str):
            raise ValueError("truth case has invalid type or corrupted field")
        try:
            expected_field = TRUTH_FIELD_TO_ERROR_FIELD[corrupted_field]
        except KeyError:
            raise ValueError("truth case has an unsupported corrupted field") from None
        totals["corrupted_cases"] += 1
        stats["corrupted_exposures"] += 1
        if not has_error:
            totals["false_negatives"] += 1
            stats["false_negatives"] += 1
        elif predicted_field != expected_field:
            route = f"{expected_field}->{predicted_field}"
            wrong_routes[route] += 1
            totals["wrong_field_localizations"] += 1
            stats["wrong_field_localizations"] += 1
            if predicted_field == "wbs":
                totals["wrongly_localized_to_wbs"] += 1
                stats["wrongly_localized_to_wbs"] += 1

        if expected_field == "wbs":
            stats["wbs_corrupted_exposures"] += 1
            if not has_error or predicted_field != "wbs":
                totals["wbs_localized_misses"] += 1
                stats["wbs_localized_misses"] += 1
        else:
            stats["non_wbs_corrupted_exposures"] += 1

    phrase_rows: list[dict[str, Any]] = []
    for phrase, stats in by_phrase.items():
        clean_exposures = stats["clean_exposures"]
        non_wbs_exposures = stats["non_wbs_corrupted_exposures"]
        phrase_rows.append(
            {
                "phrase": phrase,
                "expected_wbs": phrase_expected_wbs[phrase],
                **dict(stats),
                "clean_false_alert_rate": (
                    stats["clean_false_alerts"] / clean_exposures
                    if clean_exposures
                    else None
                ),
                "non_wbs_error_diversion_rate": (
                    stats["wrongly_localized_to_wbs"] / non_wbs_exposures
                    if non_wbs_exposures
                    else None
                ),
            }
        )
    phrase_rows.sort(
        key=lambda row: (
            int(row.get("clean_false_alerts_wbs", 0))
            + int(row.get("wrongly_localized_to_wbs", 0)),
            int(row.get("wbs_localized_misses", 0)),
            str(row["phrase"]),
        ),
        reverse=True,
    )
    return {
        "experiment": f"synthetic offline AI QA {cycle_label} failure audit",
        "cycle_label": cycle_label,
        "scope": "aggregate calibration diagnostics; no locked holdout data",
        "totals": dict(totals),
        "wrong_field_routes": dict(sorted(wrong_routes.items())),
        "phrases": phrase_rows,
    }


def render_markdown(audit: Mapping[str, object]) -> str:
    totals = audit["totals"]
    phrases = audit["phrases"]
    rows = [
        f"# {audit.get('cycle_label', 'Luna-v4')} Failure Audit",
        "",
        "Synthetic offline calibration diagnostics. The locked holdout was not used.",
        "",
        "## Aggregate finding",
        "",
        f"- Clean false alerts: {totals.get('false_alerts', 0)}; "
        f"WBS predictions: {totals.get('clean_false_alerts_wbs', 0)}.",
        f"- Wrong field localizations: {totals.get('wrong_field_localizations', 0)}; "
        f"diverted to WBS: {totals.get('wrongly_localized_to_wbs', 0)}.",
        f"- WBS localized misses: {totals.get('wbs_localized_misses', 0)}.",
        "",
        "## Highest-risk WBS wording variants",
        "",
        "| Expected WBS | Wording | Clean FP | Non-WBS diverted to WBS | WBS misses |",
        "|---|---|---:|---:|---:|",
    ]
    for row in phrases:
        risk_count = int(row.get("clean_false_alerts_wbs", 0)) + int(
            row.get("wrongly_localized_to_wbs", 0)
        ) + int(row.get("wbs_localized_misses", 0))
        if not risk_count:
            continue
        wording = str(row["phrase"]).replace("|", "\\|")
        rows.append(
            f"| {row['expected_wbs']} | {wording} | "
            f"{row.get('clean_false_alerts_wbs', 0)} | "
            f"{row.get('wrongly_localized_to_wbs', 0)} | "
            f"{row.get('wbs_localized_misses', 0)} |"
        )
    rows.extend(
        [
            "",
            "## Decision",
            "",
            "The dominant failure is WBS salience: the checker treats semantically "
            "unusual but correct WBS wording as a contradiction and can stop before "
            "localizing the actual non-WBS error. The next cycle must audit wording "
            "validity, add clean negative controls, and reduce field-order bias before "
            "another paid calibration.",
            "",
        ]
    )
    return "\n".join(rows)


def write_failure_audit(
    *,
    input_path: Path = DEFAULT_INPUT_PATH,
    truth_path: Path = DEFAULT_TRUTH_PATH,
    predictions_path: Path = DEFAULT_PREDICTIONS_PATH,
    output_dir: Path = DEFAULT_RUN_DIR,
) -> dict[str, Path]:
    audit = build_failure_audit(
        input_rows=load_jsonl(input_path),
        truth_rows=load_jsonl(truth_path),
        prediction_rows=load_jsonl(predictions_path),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "failure_audit.json"
    markdown_path = output_dir / "failure_audit.md"
    json_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(audit), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Luna-v4 WBS failure clusters.")
    parser.add_argument("--inputs", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--truth", type=Path, default=DEFAULT_TRUTH_PATH)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    written = write_failure_audit(
        input_path=args.inputs,
        truth_path=args.truth,
        predictions_path=args.predictions,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {name: str(path) for name, path in written.items()},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
