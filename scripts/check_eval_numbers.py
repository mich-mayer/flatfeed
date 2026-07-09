"""Verify eval result numbers quoted in CASE_STUDY.md and docs/case-study.html
match a fresh `eval.run_eval --json` run.

Implements the §27 "Eval sync search" as an automated check instead of a
manual grep: every hardcoded occurrence of a result number is compared
against ground truth, not just located.

Usage: .venv/bin/python -m scripts.check_eval_numbers
Exit code 0 if every quoted number matches; 1 if any is stale or an
expected anchor phrase is missing (the prose changed and the check needs
updating, or a number changed without updating the prose).
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


def _run_eval_json() -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "eval.run_eval", "--json"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _pct(value: float) -> str:
    return f"{value:.1%}"


def _pct_close(actual: str, expected: float, tolerance: float = 0.05) -> bool:
    return abs(float(actual) - expected * 100) < tolerance


def _cost(value: float) -> str:
    return f"{value:.6f}"


class Check:
    def __init__(self, label: str, pattern: str, verify) -> None:
        self.label = label
        self.regex = re.compile(pattern)
        self.verify = verify

    def run(self, text: str, expected: dict) -> list[str]:
        matches = list(self.regex.finditer(text))
        if not matches:
            return [f"NOT FOUND: {self.label} — anchor phrase missing (prose changed?)"]
        errors = []
        for match in matches:
            problem = self.verify(match.groupdict(), expected)
            if problem:
                errors.append(f"MISMATCH: {self.label} — {problem}")
        return errors


def _check_result_prose(groups: dict, expected: dict) -> str | None:
    if int(groups["listing_count"]) != expected["listing_count"]:
        return f"listing count {groups['listing_count']} != {expected['listing_count']}"
    if not _pct_close(groups["field_pct"], expected["field_accuracy"]):
        return f"field accuracy {groups['field_pct']}% != {_pct(expected['field_accuracy'])}"
    if not _pct_close(groups["exact_pct"], expected["exact_listing_accuracy"]):
        return f"exact listing accuracy {groups['exact_pct']}% != {_pct(expected['exact_listing_accuracy'])}"
    return None


def _check_qa_prose(groups: dict, expected: dict) -> str | None:
    if int(groups["false_alert"]) != expected["false_alert_fields"]:
        return f"false alert fields {groups['false_alert']} != {expected['false_alert_fields']}"
    if groups["cost"] != _cost(expected["total_cost_usd"]):
        return f"QA cost ${groups['cost']} != ${_cost(expected['total_cost_usd'])}"
    return None


def _check_bare_pct(groups: dict, expected: dict) -> str | None:
    if not _pct_close(groups["bare_pct"], expected["field_accuracy"]):
        return f"headline {groups['bare_pct']}% != {_pct(expected['field_accuracy'])}"
    if int(groups["listing_count"]) != expected["listing_count"]:
        return f"listing count {groups['listing_count']} != {expected['listing_count']}"
    if expected["field_accuracy"] < 1.0:
        return (
            "field accuracy is below 100% — the sentence 'means the parser covers "
            "every case I designed for it' is now a factual overclaim and needs a "
            "human rewrite, not just a number swap"
        )
    return None


def _check_golden_set_intro(groups: dict, expected: dict) -> str | None:
    if int(groups["listing_count"]) != expected["listing_count"]:
        return f"listing count {groups['listing_count']} != {expected['listing_count']}"
    return None


def _make_common_checks() -> list[Check]:
    return [
        Check(
            "results prose (parses N listings / field / exact accuracy)",
            r"parses (?P<listing_count>\d+) synthetic listings\s+with\s+"
            r"(?P<field_pct>\d+(?:\.\d+)?)%\s+parser field accuracy and\s*"
            r"(?P<exact_pct>\d+(?:\.\d+)?)% exact listing accuracy",
            _check_result_prose,
        ),
        Check(
            "results prose (false alert fields / QA cost)",
            r"produced\s+(?P<false_alert>\d+)\s+false alert fields and\s*"
            r"\$(?P<cost>\d+\.\d+)\s+total QA cost",
            _check_qa_prose,
        ),
        Check(
            "headline (\"N% on a M-listing golden set\")",
            r"(?P<bare_pct>\d+(?:\.\d+)?)%\s+on a\s+(?P<listing_count>\d+)-listing synthetic golden set",
            _check_bare_pct,
        ),
        Check(
            "approach prose (\"an N-listing synthetic golden set\")",
            r"a\s+(?P<listing_count>\d+)-listing synthetic golden set with hidden ground",
            _check_golden_set_intro,
        ),
    ]


def _make_html_only_checks() -> list[Check]:
    def field(label: str, group: str, cast=int):
        def verify(groups: dict, expected: dict) -> str | None:
            actual = groups[group]
            expect = expected[label]
            ok = _pct_close(actual, expect) if cast is float else cast(actual) == expect
            if not ok:
                return f"{group} {actual} != {expect}"
            return None

        return verify

    return [
        Check(
            "dashboard panel (Golden listings)",
            r'<strong>(?P<count>\d+)</strong><span>Golden listings</span>',
            field("listing_count", "count"),
        ),
        Check(
            "dashboard panel (Field accuracy)",
            r'<strong>(?P<pct>\d+(?:\.\d+)?)%</strong><span>Field accuracy</span>',
            field("field_accuracy", "pct", cast=float),
        ),
        Check(
            "dashboard panel (Parser misses by tag)",
            r'<strong>(?P<misses>\d+)</strong><span>Parser misses by tag</span>',
            field("misses_total", "misses"),
        ),
        Check(
            "dashboard panel (Mock QA cost)",
            r'<strong>\$(?P<cost>\d+\.\d+)</strong><span>Mock QA cost</span>',
            lambda groups, expected: (
                None
                if groups["cost"] == _cost(expected["total_cost_usd"])
                else f"cost ${groups['cost']} != ${_cost(expected['total_cost_usd'])}"
            ),
        ),
        Check(
            "scope figures (golden-set listings with hidden ground truth)",
            r'<strong>(?P<count>\d+)</strong><span>golden-set listings with hidden ground truth</span>',
            field("listing_count", "count"),
        ),
        Check(
            "results table (Golden-set listings row)",
            r'<th scope="row">Golden-set listings</th>\s*<td class="case-results-value">(?P<count>\d+)</td>',
            field("listing_count", "count"),
        ),
        Check(
            "results table (Parser field accuracy row)",
            r'<th scope="row">Parser field accuracy</th>\s*<td class="case-results-value">(?P<pct>\d+(?:\.\d+)?)%</td>',
            field("field_accuracy", "pct", cast=float),
        ),
        Check(
            "results table (Exact listing accuracy row)",
            r'<th scope="row">Exact listing accuracy</th>\s*<td class="case-results-value">(?P<pct>\d+(?:\.\d+)?)%</td>',
            field("exact_listing_accuracy", "pct", cast=float),
        ),
        Check(
            "results table (Parser misses by tag row)",
            r'<th scope="row">Parser misses by tag</th>\s*<td class="case-results-value">(?P<misses>\d+)</td>',
            field("misses_total", "misses"),
        ),
        Check(
            "results table (Mock QA cost row)",
            r'<th scope="row">Mock QA cost</th>\s*<td class="case-results-value">\$(?P<cost>\d+\.\d+)</td>',
            lambda groups, expected: (
                None
                if groups["cost"] == _cost(expected["total_cost_usd"])
                else f"cost ${groups['cost']} != ${_cost(expected['total_cost_usd'])}"
            ),
        ),
    ]


def main() -> int:
    report = _run_eval_json()
    expected = {
        "listing_count": report["listing_count"],
        "field_accuracy": report["parser"]["field_accuracy"],
        "exact_listing_accuracy": report["parser"]["exact_listing_accuracy"],
        "misses_total": sum(report["parser"]["misses_by_tag"].values()),
        "false_alert_fields": report["qa"]["false_alert_fields"],
        "total_cost_usd": report["total_cost_usd"],
    }

    targets = {
        PROJECT_ROOT / "CASE_STUDY.md": _make_common_checks(),
        PROJECT_ROOT / "docs" / "case-study.html": _make_common_checks() + _make_html_only_checks(),
    }

    all_errors: list[str] = []
    for path, checks in targets.items():
        text = path.read_text(encoding="utf-8")
        for check in checks:
            for problem in check.run(text, expected):
                all_errors.append(f"{path.relative_to(PROJECT_ROOT)}: {problem}")

    if all_errors:
        print("Eval number sync check FAILED:\n")
        for error in all_errors:
            print(f"  - {error}")
        print(
            "\nGround truth (current eval run):\n"
            f"  listing_count={expected['listing_count']} "
            f"field_accuracy={_pct(expected['field_accuracy'])} "
            f"exact_listing_accuracy={_pct(expected['exact_listing_accuracy'])} "
            f"misses_total={expected['misses_total']} "
            f"false_alert_fields={expected['false_alert_fields']} "
            f"total_cost_usd=${_cost(expected['total_cost_usd'])}"
        )
        print(
            "\nUpdate every occurrence in CASE_STUDY.md and docs/case-study.html "
            "in the same change (DESIGN_CONTENT_SYSTEM.md §27)."
        )
        return 1

    print("Eval number sync check passed — all quoted numbers match the current eval run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
