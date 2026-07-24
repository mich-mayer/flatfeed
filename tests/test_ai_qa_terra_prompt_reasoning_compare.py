from __future__ import annotations

import json
import unittest

from eval.ai_qa_terra_prompt_reasoning_compare import OUTPUT_DIR


class TerraPromptReasoningComparisonTests(unittest.TestCase):
    def test_committed_comparison_matches_predeclared_decision(self) -> None:
        result = json.loads((OUTPUT_DIR / "comparison.json").read_text(encoding="utf-8"))
        self.assertEqual(result["profiles"]["terra-v1-low"]["total_correct"], 48)
        self.assertEqual(result["profiles"]["terra-v1-medium"]["total_correct"], 48)
        self.assertEqual(result["profiles"]["luna-v5-medium"]["total_correct"], 45)
        self.assertEqual(result["profiles"]["luna-v5-low"]["technical_failures"], 1)
        self.assertEqual(result["decision"]["selected_profile"], "terra-v1-medium")
        self.assertEqual(
            result["paired_comparisons"]["reasoning_effect_terra_v1_left_low_right_medium"],
            {"both_correct": 48, "both_wrong": 0, "left_only_correct": 0, "right_only_correct": 0},
        )
        self.assertFalse(result["locked_holdout_used"])
        self.assertFalse(result["sol_used"])


if __name__ == "__main__":
    unittest.main()
