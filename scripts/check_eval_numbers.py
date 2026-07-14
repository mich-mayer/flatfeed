"""Verify the one eval number quoted on public portfolio surfaces.

The public story intentionally exposes only the authored regression-case count.
Field accuracy, exact-listing accuracy, mock-provider cost, and quiet/caught
counts stay in the runnable eval report because they are engineering diagnostics,
not product outcomes.

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

PUBLIC_TARGETS = (
    PROJECT_ROOT / "CASE_STUDY.md",
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "docs" / "case-study.html",
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

    for path in PUBLIC_TARGETS:
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

    if errors:
        print("Eval number sync check FAILED:\n")
        for error in errors:
            print(f"  - {error}")
        print(f"\nCurrent eval listing_count={expected_count}")
        return 1

    print(
        "Eval number sync check passed — the public authored-case count "
        f"matches the current eval run ({expected_count})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
