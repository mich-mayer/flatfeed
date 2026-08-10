from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from eval.ai_qa_scorer import (
    ERROR_FIELD_LABELS,
    EXPERIMENT_LABEL,
    wilson_95_interval,
)


SCORECARD_SCHEMA_VERSION = "1.0"
SCORECARD_CONTRACT_VERSION = "product-scorecard-v1"

PRODUCT_METRIC_TARGETS = {
    "parser_error_detection_rate": ("min", 0.95),
    "false_alert_rate": ("max", 0.03),
    "correct_field_detection_rate": ("min", 0.90),
    "successful_check_rate": ("min", 0.995),
}
PRODUCT_METRIC_LABELS = {
    "parser_error_detection_rate": "Parser Error Detection Rate",
    "false_alert_rate": "False Alert Rate",
    "correct_field_detection_rate": "Correct Field Detection Rate",
    "successful_check_rate": "Successful Check Rate",
}
PRODUCT_METRIC_DEFINITIONS = {
    "parser_error_detection_rate": (
        "Alerted corrupted listings divided by all corrupted listings."
    ),
    "false_alert_rate": (
        "Alerted clean listings divided by all clean listings."
    ),
    "correct_field_detection_rate": (
        "Corrupted listings with the correct field named divided by all "
        "corrupted listings."
    ),
    "successful_check_rate": (
        "Schema-conforming model responses divided by all attempted checks."
    ),
}

FIELD_ORDER = (
    "wbs",
    "district",
    "rent_kalt",
    "rooms",
    "address_postal_code",
    "floor",
    "rent_warm",
)
MATCHING_CRITICAL_FIELDS = (
    "wbs",
    "district",
    "rent_kalt",
    "rooms",
)
MATCHING_CRITICAL_TARGET = 0.90

SCORECARD_FILENAMES = {
    "json": "product_scorecard.json",
    "markdown": "product_scorecard.md",
}
FROZEN_VALIDATION_SPLITS = (
    "terra_validation",
    "terra_high_validation",
)
LOCKED_HOLDOUT_SPLIT = "locked_holdout"

REAL_WORLD_LIMITATIONS = (
    (
        "This scorecard measures a synthetic challenge set, not performance "
        "on live housing-provider listings or real parser-error prevalence."
    ),
    (
        "A real product would need human review of every AI alert and an "
        "independent random sample of listings that received no alert so "
        "missed parser errors can be measured."
    ),
    (
        "FlatFeed does not currently use housing-provider data without "
        "permission, so that real-world audit workflow is planned rather "
        "than implemented in this prototype."
    ),
    (
        "The checker can evaluate only listings and raw text that the "
        "collection layer obtained; missing listings require a separate "
        "source-coverage control."
    ),
)


class ProductScorecardError(ValueError):
    """Raised when source artifacts do not satisfy the scorecard contract."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductScorecardError(f"cannot read JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise ProductScorecardError(f"JSON artifact must be an object: {path}")
    return value


def _require_nonnegative_int(
    mapping: Mapping[str, object],
    key: str,
) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProductScorecardError(f"invalid report count: {key}")
    return value


def _proportion(numerator: int, denominator: int) -> dict[str, object]:
    if numerator > denominator:
        raise ProductScorecardError("metric numerator exceeds denominator")
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
        "wilson_95_ci": wilson_95_interval(numerator, denominator),
    }


def _gate(
    metric: Mapping[str, object],
    *,
    comparison: str,
    threshold: float,
) -> dict[str, object]:
    value = metric.get("value")
    if value is None:
        status = "not_evaluable"
    elif not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ProductScorecardError("metric value must be numeric or null")
    elif comparison == "min":
        status = "pass" if value >= threshold else "fail"
    elif comparison == "max":
        status = "pass" if value <= threshold else "fail"
    else:
        raise ProductScorecardError("unsupported gate comparison")
    return {
        "comparison": comparison,
        "threshold": threshold,
        "status": status,
    }


def _validate_report(report: Mapping[str, Any]) -> None:
    if report.get("report_schema_version") != "1.0":
        raise ProductScorecardError("unsupported scorer report schema")
    if report.get("experiment") != EXPERIMENT_LABEL:
        raise ProductScorecardError("unexpected experiment label")
    split = report.get("split")
    if not isinstance(split, str) or not split:
        raise ProductScorecardError("report split must be a non-empty string")

    counts = report.get("counts")
    if not isinstance(counts, Mapping):
        raise ProductScorecardError("report counts are missing")
    total = _require_nonnegative_int(counts, "total_cases")
    clean = _require_nonnegative_int(counts, "clean_cases")
    corrupted = _require_nonnegative_int(counts, "corrupted_cases")
    covered = _require_nonnegative_int(counts, "valid_structured_outputs")
    alerted_corrupted = _require_nonnegative_int(
        counts,
        "alerted_corrupted_cases",
    )
    false_positives = _require_nonnegative_int(counts, "false_positives")
    correctly_localized = _require_nonnegative_int(
        counts,
        "correctly_localized_alerts",
    )
    if clean + corrupted != total:
        raise ProductScorecardError("clean and corrupted counts do not sum to total")
    if covered > total:
        raise ProductScorecardError("covered count exceeds total cases")
    if alerted_corrupted > corrupted:
        raise ProductScorecardError("alerted corrupted count exceeds total")
    if false_positives > clean:
        raise ProductScorecardError("false positives exceed clean cases")
    if correctly_localized > alerted_corrupted:
        raise ProductScorecardError("correct field count exceeds detected errors")

    field_breakdown = report.get("field_breakdown")
    if not isinstance(field_breakdown, Mapping):
        raise ProductScorecardError("field breakdown is missing")
    field_total_sum = 0
    field_correct_sum = 0
    for field in FIELD_ORDER:
        row = field_breakdown.get(field)
        if not isinstance(row, Mapping):
            raise ProductScorecardError(f"field breakdown is missing: {field}")
        field_total = _require_nonnegative_int(row, "total_corrupted")
        field_correct = _require_nonnegative_int(row, "correctly_localized")
        if field_correct > field_total:
            raise ProductScorecardError(
                f"correct field count exceeds field total: {field}"
            )
        field_total_sum += field_total
        field_correct_sum += field_correct
    if field_total_sum != corrupted:
        raise ProductScorecardError(
            "field corrupted counts do not sum to corrupted cases"
        )
    if field_correct_sum != correctly_localized:
        raise ProductScorecardError(
            "field correct counts do not sum to correct-field cases"
        )

    acceptance_gates = report.get("acceptance_gates")
    if not isinstance(acceptance_gates, Mapping) or acceptance_gates.get(
        "overall_status"
    ) not in {"pass", "fail", "not_evaluable"}:
        raise ProductScorecardError("engineering acceptance status is invalid")


def _validate_run_manifest(
    report: Mapping[str, Any],
    run_manifest: Mapping[str, Any],
) -> None:
    if run_manifest.get("schema_version") != "1.0":
        raise ProductScorecardError("unsupported run-manifest schema")
    if run_manifest.get("experiment") != EXPERIMENT_LABEL:
        raise ProductScorecardError("run manifest has unexpected experiment")
    if run_manifest.get("status") != "completed":
        raise ProductScorecardError("run manifest is not completed")
    if run_manifest.get("split") != report.get("split"):
        raise ProductScorecardError("report and run-manifest splits differ")
    counts = report["counts"]
    if run_manifest.get("case_count") != counts["total_cases"]:
        raise ProductScorecardError("report and run-manifest case counts differ")
    configuration = run_manifest.get("configuration")
    if not isinstance(configuration, Mapping):
        raise ProductScorecardError("run-manifest configuration is missing")


def _validate_frozen_validation(
    report: Mapping[str, Any],
    run_manifest: Mapping[str, Any],
    freeze: Mapping[str, Any],
) -> None:
    report_split = report.get("split")
    if report_split not in FROZEN_VALIDATION_SPLITS:
        raise ProductScorecardError(
            "a frozen-validation scorecard requires an approved validation split"
        )
    if freeze.get("schema_version") != "1.0":
        raise ProductScorecardError("unsupported configuration-freeze schema")
    if freeze.get("status") != "validation_authorized_once":
        raise ProductScorecardError("configuration freeze does not authorize validation")
    boundaries = freeze.get("boundaries")
    locked_holdout_authorized = (
        boundaries.get("locked_holdout_authorized")
        if isinstance(boundaries, Mapping)
        else freeze.get("locked_holdout_authorized")
    )
    if locked_holdout_authorized is not False:
        raise ProductScorecardError("locked holdout boundary is not preserved")

    frozen_configuration = freeze.get("configuration")
    actual_configuration = run_manifest.get("configuration")
    if not isinstance(frozen_configuration, Mapping) or not isinstance(
        actual_configuration,
        Mapping,
    ):
        raise ProductScorecardError("configuration data is missing")
    for key, frozen_value in frozen_configuration.items():
        actual_value = (
            run_manifest.get("runner_version")
            if key == "runner_version"
            else actual_configuration.get(key)
        )
        if actual_value != frozen_value:
            raise ProductScorecardError(
                f"validation configuration differs from freeze: {key}"
            )

    frozen_validation = freeze.get("validation")
    actual_input = run_manifest.get("input")
    actual_budget = run_manifest.get("budget")
    if not isinstance(frozen_validation, Mapping):
        raise ProductScorecardError("frozen validation data is missing")
    if not isinstance(actual_input, Mapping) or not isinstance(
        actual_budget,
        Mapping,
    ):
        raise ProductScorecardError("validation manifest data is missing")
    checks = (
        (
            actual_input.get("sha256"),
            frozen_validation.get("model_inputs_sha256"),
            "input hash",
        ),
        (
            run_manifest.get("case_count"),
            frozen_validation.get("case_count"),
            "case count",
        ),
        (
            actual_budget.get("hard_limit_usd"),
            frozen_validation.get("hard_budget_limit_usd"),
            "hard budget",
        ),
        (
            run_manifest.get("split"),
            frozen_validation.get("split"),
            "split",
        ),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise ProductScorecardError(
                f"validation {label} differs from configuration freeze"
            )


def _validate_locked_holdout(
    report: Mapping[str, Any],
    run_manifest: Mapping[str, Any],
    freeze: Mapping[str, Any],
) -> None:
    if report.get("split") != LOCKED_HOLDOUT_SPLIT:
        raise ProductScorecardError("unexpected locked-holdout split")
    if freeze.get("schema_version") != "1.0":
        raise ProductScorecardError("unsupported holdout-freeze schema")
    if freeze.get("status") != "holdout_authorized_once":
        raise ProductScorecardError(
            "configuration freeze does not authorize the locked holdout"
        )
    boundaries = freeze.get("boundaries")
    if (
        not isinstance(boundaries, Mapping)
        or boundaries.get("locked_holdout_authorized") is not True
        or boundaries.get("holdout_authorized_once") is not True
        or boundaries.get("product_runtime_modified") is not False
    ):
        raise ProductScorecardError(
            "locked holdout boundary is not correctly frozen"
        )

    frozen_configuration = freeze.get("configuration")
    actual_configuration = run_manifest.get("configuration")
    if not isinstance(frozen_configuration, Mapping) or not isinstance(
        actual_configuration,
        Mapping,
    ):
        raise ProductScorecardError("configuration data is missing")
    for key, frozen_value in frozen_configuration.items():
        actual_value = (
            run_manifest.get("runner_version")
            if key == "runner_version"
            else actual_configuration.get(key)
        )
        if actual_value != frozen_value:
            raise ProductScorecardError(
                f"holdout configuration differs from freeze: {key}"
            )

    frozen_holdout = freeze.get("holdout")
    actual_input = run_manifest.get("input")
    actual_budget = run_manifest.get("budget")
    if not isinstance(frozen_holdout, Mapping):
        raise ProductScorecardError("frozen holdout data is missing")
    if not isinstance(actual_input, Mapping) or not isinstance(
        actual_budget,
        Mapping,
    ):
        raise ProductScorecardError("holdout manifest data is missing")
    checks = (
        (
            actual_input.get("sha256"),
            frozen_holdout.get("model_inputs_sha256"),
            "input hash",
        ),
        (
            run_manifest.get("case_count"),
            frozen_holdout.get("case_count"),
            "case count",
        ),
        (
            actual_budget.get("hard_limit_usd"),
            frozen_holdout.get("hard_budget_limit_usd"),
            "hard budget",
        ),
        (
            run_manifest.get("split"),
            frozen_holdout.get("split"),
            "split",
        ),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise ProductScorecardError(
                f"holdout {label} differs from configuration freeze"
            )


def _metric_entry(
    *,
    key: str,
    metric: Mapping[str, object],
) -> dict[str, object]:
    comparison, threshold = PRODUCT_METRIC_TARGETS[key]
    return {
        "label": PRODUCT_METRIC_LABELS[key],
        "definition": PRODUCT_METRIC_DEFINITIONS[key],
        "result": dict(metric),
        "gate": _gate(
            metric,
            comparison=comparison,
            threshold=threshold,
        ),
    }


def build_product_scorecard(
    report: Mapping[str, Any],
    *,
    run_manifest: Mapping[str, Any],
    freeze: Mapping[str, Any] | None = None,
    source_report_sha256: str | None = None,
    source_run_manifest_sha256: str | None = None,
    source_freeze_sha256: str | None = None,
) -> dict[str, Any]:
    """Build the product-facing metric layer from a frozen scorer report."""

    _validate_report(report)
    _validate_run_manifest(report, run_manifest)
    split = str(report["split"])
    is_frozen_validation = split in FROZEN_VALIDATION_SPLITS
    is_locked_holdout = split == LOCKED_HOLDOUT_SPLIT
    is_frozen_evaluation = is_frozen_validation or is_locked_holdout
    if is_frozen_evaluation:
        if freeze is None:
            raise ProductScorecardError(
                f"{split} requires the configuration freeze"
            )
        if is_locked_holdout:
            _validate_locked_holdout(report, run_manifest, freeze)
        else:
            _validate_frozen_validation(report, run_manifest, freeze)
    elif freeze is not None:
        raise ProductScorecardError(
            "configuration freeze is accepted only for an approved validation split"
        )

    counts = report["counts"]
    detection = _proportion(
        counts["alerted_corrupted_cases"],
        counts["corrupted_cases"],
    )
    false_alert = _proportion(
        counts["false_positives"],
        counts["clean_cases"],
    )
    correct_field = _proportion(
        counts["correctly_localized_alerts"],
        counts["corrupted_cases"],
    )
    successful_check = _proportion(
        counts["valid_structured_outputs"],
        counts["total_cases"],
    )
    metric_results = {
        "parser_error_detection_rate": _metric_entry(
            key="parser_error_detection_rate",
            metric=detection,
        ),
        "false_alert_rate": _metric_entry(
            key="false_alert_rate",
            metric=false_alert,
        ),
        "correct_field_detection_rate": _metric_entry(
            key="correct_field_detection_rate",
            metric=correct_field,
        ),
        "successful_check_rate": _metric_entry(
            key="successful_check_rate",
            metric=successful_check,
        ),
    }

    field_results: dict[str, dict[str, object]] = {}
    for field in FIELD_ORDER:
        row = report["field_breakdown"][field]
        result = _proportion(
            row["correctly_localized"],
            row["total_corrupted"],
        )
        is_critical = field in MATCHING_CRITICAL_FIELDS
        field_results[field] = {
            "label": ERROR_FIELD_LABELS[field],
            "matching_critical": is_critical,
            "result": result,
            "guardrail": (
                _gate(
                    result,
                    comparison="min",
                    threshold=MATCHING_CRITICAL_TARGET,
                )
                if is_critical
                else None
            ),
        }

    metric_statuses = {
        entry["gate"]["status"]
        for entry in metric_results.values()
    }
    critical_statuses = {
        field_results[field]["guardrail"]["status"]
        for field in MATCHING_CRITICAL_FIELDS
    }
    frozen_contract_status = report["acceptance_gates"]["overall_status"]
    all_statuses = (
        metric_statuses
        | critical_statuses
        | {frozen_contract_status}
    )
    if "not_evaluable" in all_statuses:
        overall_status = "not_evaluable"
    elif "fail" in all_statuses:
        overall_status = "fail"
    else:
        overall_status = "pass"

    configuration = run_manifest["configuration"]
    return {
        "scorecard_schema_version": SCORECARD_SCHEMA_VERSION,
        "contract_version": SCORECARD_CONTRACT_VERSION,
        "experiment": EXPERIMENT_LABEL,
        "evidence_label": (
            "Synthetic locked holdout"
            if is_locked_holdout
            else (
                "Synthetic frozen validation"
                if is_frozen_validation
                else "Synthetic calibration preview"
            )
        ),
        "evidence_scope": (
            "Synthetic offline parser-QA evidence only; not live-source, "
            "production-prevalence, or user-outcome evidence."
        ),
        "publication_state": (
            "final_test_result_ready_for_evidence_review"
            if is_locked_holdout
            else (
                "result_ready_for_evidence_review"
                if is_frozen_validation
                else "not_public_calibration_preview"
            )
        ),
        "source": {
            "split": split,
            "run_label": report.get("run_label"),
            "report_sha256": source_report_sha256,
            "run_manifest_sha256": source_run_manifest_sha256,
            "configuration_freeze_sha256": source_freeze_sha256,
        },
        "configuration": {
            "model": configuration.get("model"),
            "reasoning_effort": configuration.get("reasoning_effort"),
            "prompt_version": configuration.get("prompt_version"),
            "max_output_tokens": configuration.get("max_output_tokens"),
            "retries": configuration.get("retries"),
            "strict_structured_outputs": configuration.get(
                "strict_structured_outputs"
            ),
        },
        "case_counts": {
            "total": counts["total_cases"],
            "clean": counts["clean_cases"],
            "corrupted": counts["corrupted_cases"],
        },
        "metrics": metric_results,
        "fields": field_results,
        "decision": {
            "overall_status": overall_status,
            "simple_metrics_status": (
                "pass" if metric_statuses == {"pass"} else "fail"
            ),
            "matching_critical_guardrails_status": (
                "pass" if critical_statuses == {"pass"} else "fail"
            ),
            "frozen_engineering_contract_status": frozen_contract_status,
            "positive_landing_claim_allowed": (
                is_frozen_validation and overall_status == "pass"
            ),
            "public_copy_change_requires_separate_review": is_locked_holdout,
        },
        "real_world_limitations": list(REAL_WORLD_LIMITATIONS),
    }


def _format_percentage(value: object) -> str:
    if value is None:
        return "n/a"
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ProductScorecardError("percentage value must be numeric or null")
    return f"{value:.1%}"


def format_product_scorecard_markdown(
    scorecard: Mapping[str, Any],
) -> str:
    if scorecard["evidence_label"] == "Synthetic locked holdout":
        decision_label = "Final-test decision"
    elif scorecard["evidence_label"] == "Synthetic frozen validation":
        decision_label = "Product decision"
    else:
        decision_label = "Preview gate status"
    lines = [
        "# AI QA Product Scorecard",
        "",
        f"**Evidence:** {scorecard['evidence_label']}",
        "",
        str(scorecard["evidence_scope"]),
        "",
        (
            f"- Model: `{scorecard['configuration']['model']}` "
            f"with `reasoning_effort="
            f"{scorecard['configuration']['reasoning_effort']}`"
        ),
        f"- Prompt: `{scorecard['configuration']['prompt_version']}`",
        (
            f"- Cases: {scorecard['case_counts']['total']} "
            f"({scorecard['case_counts']['clean']} clean, "
            f"{scorecard['case_counts']['corrupted']} corrupted)"
        ),
        f"- {decision_label}: `{scorecard['decision']['overall_status']}`",
        "",
        "## Four simple metrics",
        "",
        "| Metric | Result | Target | Count | Status |",
        "|---|---:|---:|---:|---:|",
    ]
    for entry in scorecard["metrics"].values():
        result = entry["result"]
        gate = entry["gate"]
        operator = ">=" if gate["comparison"] == "min" else "<="
        lines.append(
            f"| {entry['label']} | {_format_percentage(result['value'])} | "
            f"{operator} {_format_percentage(gate['threshold'])} | "
            f"{result['numerator']}/{result['denominator']} | "
            f"{gate['status']} |"
        )

    lines.extend(
        [
            "",
            "## Checked fields",
            "",
            "| Field | Correct field | Role | Guardrail |",
            "|---|---:|---|---:|",
        ]
    )
    for entry in scorecard["fields"].values():
        result = entry["result"]
        guardrail = entry["guardrail"]
        role = "matching-critical" if entry["matching_critical"] else "diagnostic"
        guardrail_text = (
            "n/a"
            if guardrail is None
            else (
                f">= {_format_percentage(guardrail['threshold'])} "
                f"({guardrail['status']})"
            )
        )
        lines.append(
            f"| {entry['label']} | {_format_percentage(result['value'])} "
            f"({result['numerator']}/{result['denominator']}) | "
            f"{role} | {guardrail_text} |"
        )

    lines.extend(
        [
            "",
            "## Real-world boundary",
            "",
        ]
    )
    for limitation in scorecard["real_world_limitations"]:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)


def write_product_scorecard(
    scorecard: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        key: output_dir / filename
        for key, filename in SCORECARD_FILENAMES.items()
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise ProductScorecardError(
            "refusing to overwrite product scorecard artifacts: "
            + ", ".join(str(path) for path in existing)
        )
    paths["json"].write_text(
        json.dumps(
            scorecard,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["markdown"].write_text(
        format_product_scorecard_markdown(scorecard),
        encoding="utf-8",
    )
    return paths


def build_product_scorecard_from_files(
    *,
    report_path: Path,
    run_manifest_path: Path,
    freeze_path: Path | None = None,
) -> dict[str, Any]:
    report = _read_json_object(report_path)
    run_manifest = _read_json_object(run_manifest_path)
    freeze = _read_json_object(freeze_path) if freeze_path is not None else None
    return build_product_scorecard(
        report,
        run_manifest=run_manifest,
        freeze=freeze,
        source_report_sha256=_sha256_file(report_path),
        source_run_manifest_sha256=_sha256_file(run_manifest_path),
        source_freeze_sha256=(
            _sha256_file(freeze_path)
            if freeze_path is not None
            else None
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the separate AI QA Product Scorecard."
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--configuration-freeze", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    scorecard = build_product_scorecard_from_files(
        report_path=args.report,
        run_manifest_path=args.run_manifest,
        freeze_path=args.configuration_freeze,
    )
    paths = write_product_scorecard(scorecard, args.output_dir)
    print(
        json.dumps(
            {
                "decision": scorecard["decision"],
                "evidence_label": scorecard["evidence_label"],
                "outputs": {
                    key: str(path)
                    for key, path in paths.items()
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
