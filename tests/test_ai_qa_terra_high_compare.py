from __future__ import annotations

import json
import unittest

from eval.ai_qa_scorer import TRUTH_FIELD_TO_ERROR_FIELD
from eval.ai_qa_terra_high_compare import OUTPUT_DIR, compare_terra_high_profiles
from eval.ai_qa_terra_high_screen import build_terra_high_screen_rows


def _prediction(
    truth: dict[str, object],
    *,
    correct: bool = True,
) -> dict[str, object]:
    if truth["case_type"] == "clean":
        result = (
            {"has_error": False, "error_field": None}
            if correct
            else {"has_error": True, "error_field": "wbs"}
        )
    else:
        expected = TRUTH_FIELD_TO_ERROR_FIELD[str(truth["corrupted_field"])]
        result = (
            {"has_error": True, "error_field": expected}
            if correct
            else {"has_error": False, "error_field": None}
        )
    return {
        "case_id": truth["case_id"],
        "status": "completed",
        "raw_output": json.dumps(result, separators=(",", ":")),
    }


class TerraHighComparisonTests(unittest.TestCase):
    def test_committed_comparison_matches_advance_decision(self) -> None:
        result = json.loads(
            (OUTPUT_DIR / "comparison.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            result["profiles"]["terra-v1-medium"]["total_correct"],
            46,
        )
        self.assertEqual(
            result["profiles"]["terra-v1-high"]["total_correct"],
            48,
        )
        self.assertEqual(
            result["profiles"]["terra-v1-high"]["correct_rooms"],
            14,
        )
        self.assertEqual(
            result["profiles"]["terra-v1-high"]["correct_wbs"],
            14,
        )
        self.assertTrue(result["advancement"]["all_criteria_pass"])
        self.assertEqual(
            result["decision"]["action"],
            "advance_terra_high_to_fresh_calibration_contract",
        )
        self.assertFalse(result["consumed_validation_reused"])
        self.assertFalse(result["locked_holdout_used"])
        self.assertFalse(result["sol_used"])

    def test_high_advances_only_with_targeted_gain_and_no_regressions(self) -> None:
        _inputs, truth = build_terra_high_screen_rows()
        first_rooms = next(
            row for row in truth if row["corrupted_field"] == "rooms"
        )
        medium = [
            _prediction(row, correct=row["case_id"] != first_rooms["case_id"])
            for row in truth
        ]
        high = [_prediction(row) for row in truth]

        result = compare_terra_high_profiles(
            truth_rows=truth,
            medium_rows=medium,
            high_rows=high,
        )

        self.assertTrue(result["advancement"]["all_criteria_pass"])
        self.assertEqual(
            result["decision"]["action"],
            "advance_terra_high_to_fresh_calibration_contract",
        )
        self.assertEqual(
            result["paired_comparison"]["high_only_correct"],
            1,
        )

    def test_equal_results_do_not_justify_higher_reasoning(self) -> None:
        _inputs, truth = build_terra_high_screen_rows()
        predictions = [_prediction(row) for row in truth]

        result = compare_terra_high_profiles(
            truth_rows=truth,
            medium_rows=predictions,
            high_rows=predictions,
        )

        self.assertFalse(result["advancement"]["all_criteria_pass"])
        self.assertEqual(
            result["decision"]["action"],
            "stop_terra_reasoning_escalation",
        )

    def test_high_cannot_trade_a_wbs_regression_for_a_rooms_gain(self) -> None:
        _inputs, truth = build_terra_high_screen_rows()
        first_rooms = next(
            row for row in truth if row["corrupted_field"] == "rooms"
        )
        first_wbs = next(
            row
            for row in truth
            if row["corrupted_field"] is not None
            and TRUTH_FIELD_TO_ERROR_FIELD[str(row["corrupted_field"])] == "wbs"
        )
        medium = [
            _prediction(row, correct=row["case_id"] != first_rooms["case_id"])
            for row in truth
        ]
        high = [
            _prediction(row, correct=row["case_id"] != first_wbs["case_id"])
            for row in truth
        ]

        result = compare_terra_high_profiles(
            truth_rows=truth,
            medium_rows=medium,
            high_rows=high,
        )

        self.assertFalse(result["advancement"]["all_criteria_pass"])
        self.assertFalse(
            result["advancement"]["comparative"]["no_wbs_regression"]
        )


if __name__ == "__main__":
    unittest.main()
