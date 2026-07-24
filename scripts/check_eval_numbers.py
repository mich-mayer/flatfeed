"""Verify deterministic and frozen-validation numbers on public surfaces.

The README keeps the authored deterministic regression-case count. After a
passing publication gate, the landing and Markdown case study expose the four
simple Product Scorecard metrics from the aggregate frozen-validation artifact.
Calibration, historical, cost, latency, and mock-provider diagnostics stay out
of the landing.

Usage: .venv/bin/python -m scripts.check_eval_numbers
Exit code 0 when every public occurrence matches a fresh eval run.
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
    / "terra-high-validation"
    / "product-scorecard"
    / "product_scorecard.json"
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

    try:
        scorecard = json.loads(SCORECARD_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read Product Scorecard: {exc}")
        scorecard = {}

    decision = scorecard.get("decision", {})
    if decision.get("positive_landing_claim_allowed") is not True:
        errors.append("Product Scorecard does not authorize a landing claim")

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

    for path in SCORECARD_TARGETS:
        text = path.read_text(encoding="utf-8")
        if "Synthetic frozen validation" not in text:
            errors.append(
                f"{path.relative_to(PROJECT_ROOT)}: evidence label is missing"
            )
        for label, percentage, count in expected_public_metrics:
            for expected in (label, percentage, count):
                if expected not in text:
                    errors.append(
                        f"{path.relative_to(PROJECT_ROOT)}: "
                        f"scorecard value is missing: {expected}"
                    )

    if errors:
        print("Eval number sync check FAILED:\n")
        for error in errors:
            print(f"  - {error}")
        print(f"\nCurrent eval listing_count={expected_count}")
        return 1

    print(
        "Eval number sync check passed — the README regression count is "
        f"{expected_count}, and both case-study surfaces match the frozen "
        "four-metric Product Scorecard."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
