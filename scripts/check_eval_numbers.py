"""Verify deterministic and final locked-holdout numbers on public surfaces.

The README keeps the authored deterministic regression-case count. The landing
and Markdown case study expose only the final 600-listing locked-holdout result:
four aggregate metrics, seven field results, the final decision, and one bounded
inference-cost scenario. Calibration and historical result numbers stay out of
the public case study.

Usage: .venv/bin/python -m scripts.check_eval_numbers
Exit code 0 when every public occurrence matches the canonical artifacts.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REGRESSION_COUNT_TARGETS = (
    PROJECT_ROOT / "README.md",
)
SCORECARD_TARGETS = (
    PROJECT_ROOT / "CASE_STUDY.md",
    PROJECT_ROOT / "docs" / "case-study.html",
)
SCORECARD_PATH = (
    PROJECT_ROOT
    / "eval"
    / "runs"
    / "terra-high-locked-holdout"
    / "product-scorecard"
    / "product_scorecard.json"
)
REPORT_PATH = (
    PROJECT_ROOT
    / "eval"
    / "runs"
    / "terra-high-locked-holdout"
    / "reports"
    / "report.json"
)
MANIFEST_PATH = (
    PROJECT_ROOT
    / "eval"
    / "runs"
    / "terra-high-locked-holdout"
    / "run_manifest.json"
)
PUBLIC_EVIDENCE_LABEL = (
    "Offline AI QA evaluation · synthetic data · 600 listings"
)
ANNUAL_CHECK_SCENARIO = 15_000
OFFICIAL_RELETTING_PROXY = 12_398
FINAL_STOPPING_RATIONALE = (
    "The final run provided enough evidence for this prototype: it showed that "
    "the approach was promising and identified a specific weakness in rooms "
    "detection. Because the evaluation used synthetic data, the next meaningful "
    "step is not further tuning on the same benchmark, but recalibration and "
    "validation on permitted real listings."
)
HISTORICAL_PUBLIC_MARKERS = (
    "Synthetic frozen validation",
    "99.3%",
    "139/140",
    "280/280",
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


def main() -> int:
    expected_count = int(_run_eval_json()["listing_count"])
    errors: list[str] = []

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

    artifacts: dict[str, dict] = {}
    for label, path in (
        ("Product Scorecard", SCORECARD_PATH),
        ("final report", REPORT_PATH),
        ("run manifest", MANIFEST_PATH),
    ):
        try:
            artifacts[label] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read {label}: {exc}")
            artifacts[label] = {}

    scorecard = artifacts["Product Scorecard"]
    report = artifacts["final report"]
    manifest = artifacts["run manifest"]
    decision = scorecard.get("decision", {})
    expected_decision = {
        "overall_status": "fail",
        "simple_metrics_status": "pass",
        "matching_critical_guardrails_status": "fail",
        "positive_landing_claim_allowed": False,
    }
    for key, expected in expected_decision.items():
        if decision.get(key) != expected:
            errors.append(
                f"Product Scorecard decision {key}={decision.get(key)!r}, "
                f"expected {expected!r}"
            )

    metrics = scorecard.get("metrics", {})
    expected_public_metrics: list[tuple[str, str, str]] = []
    for key in (
        "parser_error_detection_rate",
        "false_alert_rate",
        "correct_field_detection_rate",
        "successful_check_rate",
    ):
        entry = metrics.get(key)
        if not isinstance(entry, dict):
            errors.append(f"Product Scorecard metric is missing: {key}")
            continue
        result = entry.get("result", {})
        value = result.get("value")
        numerator = result.get("numerator")
        denominator = result.get("denominator")
        if not isinstance(value, (int, float)):
            errors.append(f"Product Scorecard metric has invalid value: {key}")
            continue
        expected_public_metrics.append(
            (
                str(entry.get("label")),
                f"{value:.1%}",
                f"{numerator}/{denominator}",
            )
        )

    fields = scorecard.get("fields", {})
    expected_public_fields: list[tuple[str, str, str]] = []
    for key in (
        "wbs",
        "district",
        "rent_kalt",
        "rooms",
        "address_postal_code",
        "floor",
        "rent_warm",
    ):
        entry = fields.get(key)
        if not isinstance(entry, dict):
            errors.append(f"Product Scorecard field is missing: {key}")
            continue
        result = entry.get("result", {})
        value = result.get("value")
        numerator = result.get("numerator")
        denominator = result.get("denominator")
        if not isinstance(value, (int, float)):
            errors.append(f"Product Scorecard field has invalid value: {key}")
            continue
        expected_public_fields.append(
            (
                str(entry.get("label")),
                f"{value:.1%}",
                f"{numerator}/{denominator}",
            )
        )

    operational = report.get("operational", {})
    recorded_cost = operational.get("cost", {})
    token_usage = operational.get("token_usage", {})
    budget = manifest.get("budget", {})
    pricing_date_parts = str(budget.get("pricing_observed_date", "")).split("-")
    if len(pricing_date_parts) == 3:
        year, month, day = (int(part) for part in pricing_date_parts)
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
        pricing_date_display = f"{day} {month_names[month]} {year}"
    else:
        pricing_date_display = ""
        errors.append("run manifest has an invalid pricing_observed_date")
    completed_cases = int(recorded_cost.get("records_with_cost", 0))
    total_cost = float(recorded_cost.get("total_usd", 0))
    observed_per_check = total_cost / completed_cases if completed_cases else 0
    observed_annual = observed_per_check * ANNUAL_CHECK_SCENARIO
    observed_monthly = observed_annual / 12

    input_tokens = int(token_usage.get("input_tokens", 0))
    output_tokens = int(token_usage.get("output_tokens", 0))
    input_price = float(budget.get("input_price_per_1m", 0))
    output_price = float(budget.get("output_price_per_1m", 0))
    conservative_run_cost = (
        input_tokens * input_price + output_tokens * output_price
    ) / 1_000_000
    conservative_per_check = (
        conservative_run_cost / completed_cases if completed_cases else 0
    )
    conservative_annual = conservative_per_check * ANNUAL_CHECK_SCENARIO
    conservative_monthly = conservative_annual / 12

    expected_cost_strings = (
        f"${total_cost:.6f}",
        f"${observed_per_check:.5f}",
        f"${observed_annual:.0f}",
        f"${observed_monthly:.2f}",
        f"${conservative_per_check:.5f}",
        f"${conservative_annual:.0f}",
        f"${conservative_monthly:.2f}",
        f"{OFFICIAL_RELETTING_PROXY:,}",
        f"{ANNUAL_CHECK_SCENARIO:,}",
        pricing_date_display,
    )

    for path in SCORECARD_TARGETS:
        text = path.read_text(encoding="utf-8")
        if PUBLIC_EVIDENCE_LABEL not in text:
            errors.append(
                f"{path.relative_to(PROJECT_ROOT)}: evidence label is missing"
            )
        if "configuration not accepted" not in text.lower():
            errors.append(
                f"{path.relative_to(PROJECT_ROOT)}: final rejection is missing"
            )
        if FINAL_STOPPING_RATIONALE not in text:
            errors.append(
                f"{path.relative_to(PROJECT_ROOT)}: "
                "approved stopping rationale is missing or changed"
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
            expected_label = (
                "Address / postal code"
                if label == "address/postal code"
                else label.capitalize()
                if label in {"district", "rooms", "floor"}
                else label
            )
            for expected in (expected_label, percentage, count):
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
        "600-listing locked holdout, field results, decision, and cost scenario."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
