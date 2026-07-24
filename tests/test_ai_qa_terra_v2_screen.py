from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from eval.ai_qa_prompt import get_system_instructions
from eval.ai_qa_runner import (
    OfflineRunnerError,
    RunnerConfig,
    TERRA_V2_SCREEN_HARD_BUDGET_USD,
    build_run_plan,
    dry_run_summary,
    execute_run_plan,
)
from eval.ai_qa_terra_v2_screen import (
    COUNTS,
    DEFAULT_TERRA_V2_SCREEN_DIR,
    ERROR_DISTRIBUTION,
    build_terra_v2_screen_rows,
    verify_terra_v2_screen,
    write_terra_v2_screen,
)


class TerraV2ScreenTests(unittest.TestCase):
    def test_terra_v2_is_task_general_and_adds_comparison_veto(self) -> None:
        prompt = get_system_instructions("terra-v2")
        self.assertIn("source equality ledger", prompt)
        self.assertIn("contradiction veto", prompt)
        self.assertIn("rooms", prompt)
        self.assertIn("wbs", prompt)
        for leaked_value in ("Tempelhofer Damm 25a", "Lipschitzallee 74"):
            self.assertNotIn(leaked_value, prompt)

    def test_rows_are_reproducible_and_match_composition(self) -> None:
        first = build_terra_v2_screen_rows()
        second = build_terra_v2_screen_rows()
        self.assertEqual(first, second)
        self.assertEqual(len(first[0]), 64)
        self.assertEqual(COUNTS, {"clean": 16, "corrupted": 48})
        self.assertEqual(ERROR_DISTRIBUTION["rooms"], 20)
        self.assertEqual(ERROR_DISTRIBUTION["wbs"], 20)

    def test_committed_data_has_no_leakage_or_prior_overlap(self) -> None:
        manifest = verify_terra_v2_screen()
        self.assertTrue(
            all(value == 0 for value in manifest["isolation"]["overlaps"].values())
        )
        self.assertIn(
            "terra_calibration_cycle_validation_model_inputs",
            manifest["isolation"]["overlaps"],
        )
        input_path = (
            DEFAULT_TERRA_V2_SCREEN_DIR / manifest["model_inputs"]["file"]
        )
        for line in input_path.read_text(encoding="utf-8").splitlines():
            self.assertEqual(
                set(json.loads(line)),
                {"case_id", "raw_text", "parser_snapshot"},
            )

    def test_write_is_byte_reproducible_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first, second = Path(first_dir), Path(second_dir)
            self.assertEqual(
                write_terra_v2_screen(first),
                write_terra_v2_screen(second),
            )
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )
            with self.assertRaises(FileExistsError):
                write_terra_v2_screen(first)

    def test_runner_allows_only_two_medium_profiles(self) -> None:
        for prompt in ("terra-v1", "terra-v2"):
            plan = build_run_plan(
                split="terra_v2_prompt_screen",
                config=RunnerConfig(
                    model="gpt-5.6-terra",
                    reasoning_effort="medium",
                    max_output_tokens=256,
                    retries=0,
                    prompt_version=prompt,
                ),
            )
            self.assertEqual(plan.case_count, 64)
            self.assertTrue(
                dry_run_summary(
                    plan,
                    budget_limit_usd=TERRA_V2_SCREEN_HARD_BUDGET_USD,
                )["budget_sufficient"]
            )
        with self.assertRaisesRegex(OfflineRunnerError, "medium reasoning"):
            build_run_plan(
                split="terra_v2_prompt_screen",
                config=RunnerConfig(
                    model="gpt-5.6-terra",
                    reasoning_effort="low",
                    max_output_tokens=256,
                    retries=0,
                    prompt_version="terra-v2",
                ),
            )

    def test_execute_rejects_wrong_budget_before_credential(self) -> None:
        plan = build_run_plan(
            split="terra_v2_prompt_screen",
            config=RunnerConfig(
                model="gpt-5.6-terra",
                reasoning_effort="medium",
                max_output_tokens=256,
                retries=0,
                prompt_version="terra-v2",
            ),
        )
        with self.assertRaisesRegex(OfflineRunnerError, "budget differs"):
            execute_run_plan(
                plan,
                output_dir=Path("eval/runs/terra-v2-screen-terra-v2-medium"),
                budget_limit_usd=Decimal("1.49"),
                api_key_loader=lambda: self.fail("credential must not be read"),
            )


if __name__ == "__main__":
    unittest.main()
