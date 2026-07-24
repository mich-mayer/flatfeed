from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.ai_qa_luna_low_audit import (
    RUN_DIR,
    build_luna_low_failure_audit,
    render_markdown,
    write_luna_low_failure_audit,
)
from eval.ai_qa_luna_v5_cycle import LUNA_V5_WBS_PHRASES


def _input(case_id: str, family: str = "100, 140") -> dict[str, object]:
    return {
        "case_id": case_id,
        "raw_text": f"Wohnung\n{LUNA_V5_WBS_PHRASES[family][0]}",
        "parser_snapshot": {},
    }


def _truth(
    case_id: str,
    *,
    field: str | None,
    expected: object = None,
    corrupted: object = None,
    corruption_type: str | None = None,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "case_type": "clean" if field is None else "corrupted",
        "corrupted_field": field,
        "expected_value": expected,
        "corrupted_value": corrupted,
        "corruption_type": corruption_type,
    }


def _prediction(
    case_id: str,
    *,
    has_error: bool,
    error_field: str | None,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "status": "completed",
        "raw_output": json.dumps(
            {"has_error": has_error, "error_field": error_field}
        ),
    }


class LunaLowFailureAuditTests(unittest.TestCase):
    def test_aggregates_failures_without_case_level_artifacts(self) -> None:
        inputs = [
            _input("clean"),
            _input("wbs-miss"),
            _input("wbs-hit"),
            _input("district-miss"),
        ]
        truth = [
            _truth("clean", field=None),
            _truth(
                "wbs-miss",
                field="display_wbs",
                expected="100, 140",
                corrupted="100",
                corruption_type="wbs_range_boundary_shift",
            ),
            _truth(
                "wbs-hit",
                field="display_wbs",
                expected="100, 140",
                corrupted="160, 180, 220",
                corruption_type="wbs_range_boundary_shift",
            ),
            _truth(
                "district-miss",
                field="district",
                expected="Mitte",
                corrupted="Pankow",
                corruption_type="district_substitution",
            ),
        ]
        predictions = [
            _prediction("clean", has_error=False, error_field=None),
            _prediction("wbs-miss", has_error=False, error_field=None),
            _prediction("wbs-hit", has_error=True, error_field="wbs"),
            _prediction("district-miss", has_error=False, error_field=None),
        ]
        audit = build_luna_low_failure_audit(
            input_rows=inputs,
            truth_rows=truth,
            prediction_rows=predictions,
        )

        self.assertEqual(audit["totals"]["false_negatives"], 2)
        family = audit["wbs_by_semantic_family"][0]
        self.assertEqual(family["exposures"], 2)
        self.assertEqual(family["misses"], 1)
        serialized = json.dumps(audit)
        for case_id in ("clean", "wbs-miss", "wbs-hit", "district-miss"):
            self.assertNotIn(f'"{case_id}"', serialized)
        self.assertNotIn('"raw_text"', serialized)
        self.assertNotIn('"parser_snapshot"', serialized)
        self.assertIn("Do not freeze", render_markdown(audit))

    def test_committed_audit_matches_calibration_result(self) -> None:
        audit = json.loads(
            (RUN_DIR / "failure_audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual(audit["totals"]["false_negatives"], 8)
        self.assertEqual(audit["totals"].get("false_alerts", 0), 0)
        self.assertEqual(audit["wbs_gate"]["correctly_localized"], 50)
        self.assertEqual(audit["wbs_gate"]["minimum_correct_to_pass"], 51)
        self.assertEqual(audit["wbs_gate"]["status"], "fail")
        serialized = json.dumps(audit)
        self.assertNotIn("aqa-", serialized)
        self.assertFalse(audit["boundaries"]["new_model_calls"])

    def test_write_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = write_luna_low_failure_audit(output_dir=Path(first_dir))
            second = write_luna_low_failure_audit(output_dir=Path(second_dir))
            self.assertEqual(
                {name: path.read_bytes() for name, path in first.items()},
                {name: path.read_bytes() for name, path in second.items()},
            )


if __name__ == "__main__":
    unittest.main()
