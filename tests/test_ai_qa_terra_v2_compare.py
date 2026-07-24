from __future__ import annotations

import json
import unittest

from eval.ai_qa_terra_v2_compare import OUTPUT_DIR, compare_terra_v2_profiles
from eval.ai_qa_terra_v2_screen import build_terra_v2_screen_rows
from eval.ai_qa_scorer import TRUTH_FIELD_TO_ERROR_FIELD


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


class TerraV2ComparisonTests(unittest.TestCase):
    def test_committed_comparison_matches_stop_decision(self) -> None:
        result = json.loads(
            (OUTPUT_DIR / "comparison.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            result["profiles"]["terra-v1-medium"]["total_correct"],
            62,
        )
        self.assertEqual(
            result["profiles"]["terra-v2-medium"]["total_correct"],
            59,
        )
        self.assertEqual(
            result["profiles"]["terra-v2-medium"]["correct_rooms"],
            20,
        )
        self.assertEqual(
            result["profiles"]["terra-v2-medium"]["correct_wbs"],
            17,
        )
        self.assertFalse(result["advancement"]["all_criteria_pass"])
        self.assertEqual(
            result["decision"]["action"],
            "stop_terra_v2_prompt_change",
        )
        self.assertFalse(result["consumed_validation_reused"])
        self.assertFalse(result["locked_holdout_used"])
        self.assertFalse(result["sol_used"])

    def test_v2_advances_only_with_rooms_gain_and_no_regressions(self) -> None:
        _inputs, truth = build_terra_v2_screen_rows()
        first_rooms = next(
            row for row in truth if row["corrupted_field"] == "rooms"
        )
        v1 = [
            _prediction(row, correct=row["case_id"] != first_rooms["case_id"])
            for row in truth
        ]
        v2 = [_prediction(row) for row in truth]

        result = compare_terra_v2_profiles(
            truth_rows=truth,
            v1_rows=v1,
            v2_rows=v2,
        )

        self.assertTrue(result["advancement"]["all_criteria_pass"])
        self.assertEqual(
            result["decision"]["action"],
            "advance_terra_v2_to_fresh_calibration_contract",
        )
        self.assertEqual(
            result["paired_comparison"]["v2_only_correct"],
            1,
        )

    def test_equal_prompts_do_not_justify_prompt_change(self) -> None:
        _inputs, truth = build_terra_v2_screen_rows()
        predictions = [_prediction(row) for row in truth]

        result = compare_terra_v2_profiles(
            truth_rows=truth,
            v1_rows=predictions,
            v2_rows=predictions,
        )

        self.assertFalse(result["advancement"]["all_criteria_pass"])
        self.assertEqual(
            result["decision"]["action"],
            "stop_terra_v2_prompt_change",
        )


if __name__ == "__main__":
    unittest.main()
