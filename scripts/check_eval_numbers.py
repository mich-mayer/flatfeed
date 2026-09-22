"""Verify deterministic and final extraction-v1 numbers on public surfaces.

The README keeps the authored deterministic regression-case count. The landing
and Markdown case study expose only the final fresh 600-listing synthetic
result: four aggregate metrics, seven field results, a visible synthetic-data
qualifier, and one bounded AI API cost scenario.

Usage: .venv/bin/python -m scripts.check_eval_numbers
Exit code 0 when every public occurrence matches the canonical artifacts.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REGRESSION_COUNT_TARGETS = (PROJECT_ROOT / "README.md",)
SCORECARD_TARGETS = (
    PROJECT_ROOT / "CASE_STUDY.md",
    PROJECT_ROOT / "docs" / "case-study.html",
)
RUN_DIR = PROJECT_ROOT / "eval" / "runs" / "extraction-v1-final-600"
REPORT_PATH = RUN_DIR / "report.json"
MANIFEST_PATH = RUN_DIR / "run_manifest.json"
FREEZE_PATH = (
    PROJECT_ROOT
    / "eval"
    / "runs"
    / "extraction-v1-final-600-configuration-freeze.json"
)
PUBLIC_SYNTHETIC_QUALIFIER = "600 synthetic listing pairs"
ANNUAL_CHECK_SCENARIO = 15_000
OFFICIAL_RELETTING_PROXY = 12_398
PLANNING_BUFFER = 1.25
FINAL_EVIDENCE_CONTEXT_PARTS = (
    "defined the metric targets",
    "compared model setups on separate development data",
    "froze the setup before running it once on the locked 600-listing evaluation",
    "admin-only AI check",
    "300 clean and 300 with one planted parser error",
    "no retries or tuning after the run",
)
HISTORICAL_PUBLIC_MARKERS = (
    "Synthetic frozen validation",
    "291/300",
    "43/50",
    "$1.011304",
    "configuration not accepted",
    "critical rooms weakness",
)
METRIC_LABELS = {
    "parser_error_detection_rate": "Errors detected",
    "false_alert_rate": "Unnecessary review flags",
    "correct_field_detection_rate": "Correct field identified",
    "successful_check_rate": "Usable results",
}
FIELD_KEYS = (
    "wbs",
    "district",
    "rent_kalt",
    "rooms",
    "address_postal_code",
    "floor",
    "rent_warm",
)

CASE_COUNT_PATTERN = re.compile(
    r"(?P<count>\d+) (?:"
    r"authored synthetic cases currently pass the parser regression check|"
    r"synthetic test cases pass the regression check"
    r")",
    re.IGNORECASE,
)


def _run_eval_json() -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "eval.run_eval", "--json"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _read_json(path: Path, label: str, errors: list[str]) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read {label}: {exc}")
        return {}


def _display_date(raw_date: str, errors: list[str]) -> str:
    parts = raw_date.split("-")
    if len(parts) != 3:
        errors.append("configuration freeze has an invalid pricing date")
        return ""
    year, month, day = (int(part) for part in parts)
    month_names = (
        "",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    return f"{day} {month_names[month]} {year}"


def main() -> int:
    errors: list[str] = []
    expected_count = int(_run_eval_json()["listing_count"])

    for path in REGRESSION_COUNT_TARGETS:
        text = path.read_text(encoding="utf-8")
        matches = list(CASE_COUNT_PATTERN.finditer(text))
        if not matches:
            errors.append(
                f"{path.relative_to(PROJECT_ROOT)}: regression-case count not found"
            )
            continue
        for match in matches:
            actual_count = int(match.group("count"))
            if actual_count != expected_count:
                errors.append(
                    f"{path.relative_to(PROJECT_ROOT)}: {actual_count} authored cases "
                    f"!= eval listing_count {expected_count}"
                )

    report = _read_json(REPORT_PATH, "final report", errors)
    manifest = _read_json(MANIFEST_PATH, "run manifest", errors)
    freeze = _read_json(FREEZE_PATH, "configuration freeze", errors)

    decision = report.get("gate_decision", {})
    expected_decision = {
        "status": "pass",
        "all_gates_passed": True,
        "final_synthetic_result_accepted": True,
        "product_runtime_integration_authorized": False,
    }
    for key, expected in expected_decision.items():
        if decision.get(key) != expected:
            errors.append(
                f"final report decision {key}={decision.get(key)!r}, "
                f"expected {expected!r}"
            )

    expected_public_metrics: list[tuple[str, str, str]] = []
    metrics = report.get("metrics", {})
    for key, label in METRIC_LABELS.items():
        entry = metrics.get(key)
        if not isinstance(entry, dict):
            errors.append(f"final report metric is missing: {key}")
            continue
        value = entry.get("value")
        numerator = entry.get("numerator")
        denominator = entry.get("denominator")
        if not isinstance(value, (int, float)):
            errors.append(f"final report metric has invalid value: {key}")
            continue
        expected_public_metrics.append(
            (label, f"{value:.1%}", f"{numerator}/{denominator}")
        )

    expected_public_fields: list[tuple[str, str, str]] = []
    fields = report.get("per_field", {})
    for key in FIELD_KEYS:
        entry = fields.get(key)
        result = entry.get("correct_field_rate", {}) if isinstance(entry, dict) else {}
        value = result.get("value")
        if not isinstance(value, (int, float)):
            errors.append(f"final report field has invalid value: {key}")
            continue
        label = str(entry.get("label"))
        public_label = (
            "Address / postal code"
            if label == "address/postal code"
            else label.capitalize()
            if label in {"district", "rooms", "floor"}
            else label
        )
        expected_public_fields.append(
            (
                public_label,
                f"{value:.1%}",
                f"{result.get('numerator')}/{result.get('denominator')}",
            )
        )

    counts = report.get("counts", {})
    completed_cases = int(counts.get("attempted", 0))
    operations = report.get("operations", {})
    total_cost = float(operations.get("recorded_cost_usd", 0))
    observed_per_check = total_cost / completed_cases if completed_cases else 0
    observed_annual = observed_per_check * ANNUAL_CHECK_SCENARIO
    observed_monthly = observed_annual / 12
    planning_per_check = observed_per_check * PLANNING_BUFFER
    planning_annual = planning_per_check * ANNUAL_CHECK_SCENARIO
    planning_monthly = planning_annual / 12
    pricing_date_display = _display_date(
        str(freeze.get("pricing", {}).get("observed_date", "")), errors
    )

    expected_cost_strings = (
        f"${total_cost:.6f}",
        f"${observed_per_check:.5f}",
        f"${observed_annual:.0f}",
        f"${observed_monthly:.2f}",
        f"${planning_per_check:.5f}",
        f"${math.ceil(planning_annual):.0f}",
        f"${planning_monthly:.2f}",
        f"{OFFICIAL_RELETTING_PROXY:,}",
        f"{ANNUAL_CHECK_SCENARIO:,}",
        pricing_date_display,
    )

    manifest_configuration = manifest.get("configuration", {})
    freeze_configuration = freeze.get("configuration", {})
    if manifest_configuration != freeze_configuration:
        errors.append("run manifest configuration does not match the freeze")
    manifest_result = manifest.get("result", {})
    manifest_attempted = int(manifest_result.get("completed_cases", 0)) + int(
        manifest_result.get("invalid_outputs", 0)
    )
    if manifest_attempted != completed_cases:
        errors.append("run manifest attempted count does not match the report")

    for path in SCORECARD_TARGETS:
        text = path.read_text(encoding="utf-8")
        normalized_text = " ".join(text.split())
        if PUBLIC_SYNTHETIC_QUALIFIER not in normalized_text:
            errors.append(
                f"{path.relative_to(PROJECT_ROOT)}: synthetic qualifier is missing"
            )
        for context_part in FINAL_EVIDENCE_CONTEXT_PARTS:
            if context_part not in normalized_text:
                errors.append(
                    f"{path.relative_to(PROJECT_ROOT)}: "
                    "approved evaluation context is missing or changed: "
                    f"{context_part}"
                )
        for label, percentage, count in expected_public_metrics:
            for expected, alternatives in (
                (label, (label,)),
                (percentage, (percentage,)),
                (count, (count, count.replace("/", " of "))),
            ):
                if not any(alternative in text for alternative in alternatives):
                    errors.append(
                        f"{path.relative_to(PROJECT_ROOT)}: "
                        f"scorecard value is missing: {expected}"
                    )
        for label, percentage, count in expected_public_fields:
            for expected in (label, percentage, count):
                if expected not in text:
                    errors.append(
                        f"{path.relative_to(PROJECT_ROOT)}: "
                        f"field value is missing: {expected}"
                    )
        for expected in expected_cost_strings:
            if expected not in text:
                errors.append(
                    f"{path.relative_to(PROJECT_ROOT)}: "
                    f"cost-scenario value is missing: {expected}"
                )
        for marker in HISTORICAL_PUBLIC_MARKERS:
            if marker in text:
                errors.append(
                    f"{path.relative_to(PROJECT_ROOT)}: "
                    f"historical public marker must be removed: {marker}"
                )

    if errors:
        print("Eval number sync check FAILED:\n")
        for error in errors:
            print(f"  - {error}")
        print(f"\nCurrent eval listing_count={expected_count}")
        return 1

    print(
        "Eval number sync check passed — the README regression count is "
        f"{expected_count}, and both case-study surfaces match the final "
        "extraction-v1 600-case result, field results, evidence boundary, and "
        "cost scenario."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
