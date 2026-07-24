from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from eval.ai_qa_runner import (
    TERRA_EFFORT_SCREEN_HARD_BUDGET_USD,
    OfflineRunnerError,
    RunnerConfig,
    build_run_plan,
    dry_run_summary,
    execute_run_plan,
)
from eval.ai_qa_terra_effort_screen import (
    DEFAULT_TERRA_EFFORT_SCREEN_DIR,
    SCREEN_COUNTS,
    SCREEN_ERROR_DISTRIBUTION,
    build_terra_effort_screen_rows,
    verify_terra_effort_screen,
    write_terra_effort_screen,
)


class TerraEffortScreenTests(unittest.TestCase):
    def test_screen_is_reproducible_and_matches_contract(self) -> None:
        first = build_terra_effort_screen_rows()
        second = build_terra_effort_screen_rows()
        self.assertEqual(first, second)
        self.assertEqual(SCREEN_COUNTS, {"clean": 16, "corrupted": 32})
        self.assertEqual(SCREEN_ERROR_DISTRIBUTION["wbs"], 20)
        self.assertEqual(len(first[0]), 48)

    def test_committed_screen_has_no_leakage_or_overlap(self) -> None:
        manifest = verify_terra_effort_screen(DEFAULT_TERRA_EFFORT_SCREEN_DIR)
        self.assertTrue(
            all(value == 0 for value in manifest["isolation"]["overlaps"].values())
        )
        self.assertIn(
            "luna_low_cycle_calibration_model_inputs",
            manifest["isolation"]["overlaps"],
        )
        input_path = DEFAULT_TERRA_EFFORT_SCREEN_DIR / manifest["model_inputs"][
            "file"
        ]
        for line in input_path.read_text(encoding="utf-8").splitlines():
            self.assertEqual(
                set(json.loads(line)),
                {"case_id", "raw_text", "parser_snapshot"},
            )

    def test_write_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            self.assertEqual(
                write_terra_effort_screen(first),
                write_terra_effort_screen(second),
            )
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )

    def test_runner_allows_only_exact_terra_profiles(self) -> None:
        for effort in ("none", "low"):
            plan = build_run_plan(
                split="terra_effort_screen",
                config=RunnerConfig(
                    model="gpt-5.6-terra",
                    reasoning_effort=effort,
                    max_output_tokens=256,
                    retries=0,
                    prompt_version="luna-v5",
                ),
            )
            summary = dry_run_summary(
                plan,
                budget_limit_usd=TERRA_EFFORT_SCREEN_HARD_BUDGET_USD,
            )
            self.assertEqual(plan.case_count, 48)
            self.assertTrue(summary["budget_sufficient"])
        with self.assertRaisesRegex(OfflineRunnerError, "differs from contract"):
            build_run_plan(
                split="terra_effort_screen",
                config=RunnerConfig(
                    model="gpt-5.6-luna",
                    reasoning_effort="low",
                    max_output_tokens=256,
                    retries=0,
                    prompt_version="luna-v5",
                ),
            )

    def test_execute_rejects_wrong_budget_before_loading_credential(self) -> None:
        plan = build_run_plan(
            split="terra_effort_screen",
            config=RunnerConfig(
                model="gpt-5.6-terra",
                reasoning_effort="none",
                max_output_tokens=256,
                retries=0,
                prompt_version="luna-v5",
            ),
        )
        with self.assertRaisesRegex(OfflineRunnerError, "budget differs"):
            execute_run_plan(
                plan,
                output_dir=Path("eval/runs/terra-effort-screen-none"),
                budget_limit_usd=Decimal("0.81"),
                api_key_loader=lambda: self.fail("credential must not be read"),
            )


if __name__ == "__main__":
    unittest.main()
