from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from eval.ai_qa_prompt import get_system_instructions
from eval.ai_qa_runner import (
    TERRA_PROMPT_REASONING_SCREEN_HARD_BUDGET_USD,
    OfflineRunnerError,
    RunnerConfig,
    build_run_plan,
    dry_run_summary,
    execute_run_plan,
)
from eval.ai_qa_terra_prompt_reasoning_screen import (
    DEFAULT_TERRA_PROMPT_REASONING_SCREEN_DIR,
    build_terra_prompt_reasoning_screen_rows,
    verify_terra_prompt_reasoning_screen,
    write_terra_prompt_reasoning_screen,
)


class TerraPromptReasoningScreenTests(unittest.TestCase):
    def test_terra_v1_is_task_general_and_explicit(self) -> None:
        prompt = get_system_instructions("terra-v1")
        self.assertIn("mandatory seven-field inspection pass", prompt)
        self.assertIn("code independently", prompt)
        self.assertIn("three independent checks", prompt)
        self.assertNotIn("13435", prompt)
        self.assertNotIn("12043", prompt)

    def test_screen_is_reproducible_and_matches_contract(self) -> None:
        first = build_terra_prompt_reasoning_screen_rows()
        second = build_terra_prompt_reasoning_screen_rows()
        self.assertEqual(first, second)
        self.assertEqual(len(first[0]), 48)

    def test_committed_screen_has_zero_overlap_and_no_truth_leakage(self) -> None:
        manifest = verify_terra_prompt_reasoning_screen()
        self.assertTrue(all(value == 0 for value in manifest["isolation"]["overlaps"].values()))
        self.assertIn("terra_effort_screen_model_inputs", manifest["isolation"]["overlaps"])
        path = DEFAULT_TERRA_PROMPT_REASONING_SCREEN_DIR / manifest["model_inputs"]["file"]
        for line in path.read_text(encoding="utf-8").splitlines():
            self.assertEqual(set(json.loads(line)), {"case_id", "raw_text", "parser_snapshot"})

    def test_write_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first, second = Path(first_dir), Path(second_dir)
            self.assertEqual(write_terra_prompt_reasoning_screen(first), write_terra_prompt_reasoning_screen(second))
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )

    def test_runner_allows_only_four_exact_profiles(self) -> None:
        for prompt in ("luna-v5", "terra-v1"):
            for effort in ("low", "medium"):
                plan = build_run_plan(
                    split="terra_prompt_reasoning_screen",
                    config=RunnerConfig(
                        model="gpt-5.6-terra",
                        reasoning_effort=effort,
                        max_output_tokens=256,
                        retries=0,
                        prompt_version=prompt,
                    ),
                )
                self.assertEqual(plan.case_count, 48)
                self.assertTrue(dry_run_summary(
                    plan,
                    budget_limit_usd=TERRA_PROMPT_REASONING_SCREEN_HARD_BUDGET_USD,
                )["budget_sufficient"])
        with self.assertRaisesRegex(OfflineRunnerError, "supports only low and medium"):
            build_run_plan(
                split="terra_prompt_reasoning_screen",
                config=RunnerConfig(
                    model="gpt-5.6-terra",
                    reasoning_effort="none",
                    max_output_tokens=256,
                    retries=0,
                    prompt_version="luna-v5",
                ),
            )

    def test_execute_rejects_wrong_budget_before_credential(self) -> None:
        plan = build_run_plan(
            split="terra_prompt_reasoning_screen",
            config=RunnerConfig(
                model="gpt-5.6-terra",
                reasoning_effort="low",
                max_output_tokens=256,
                retries=0,
                prompt_version="terra-v1",
            ),
        )
        with self.assertRaisesRegex(OfflineRunnerError, "budget differs"):
            execute_run_plan(
                plan,
                output_dir=Path("eval/runs/terra-2x2-terra-v1-low"),
                budget_limit_usd=Decimal("0.91"),
                api_key_loader=lambda: self.fail("credential must not be read"),
            )


if __name__ == "__main__":
    unittest.main()
