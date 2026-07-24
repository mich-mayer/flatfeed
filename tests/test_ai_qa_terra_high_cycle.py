from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from eval.ai_qa_runner import (
    OfflineRunnerError,
    RunnerConfig,
    TERRA_HIGH_CALIBRATION_HARD_BUDGET_USD,
    TERRA_HIGH_FREEZE_PATH,
    build_run_plan,
    dry_run_summary,
    execute_run_plan,
    write_terra_high_calibration_freeze,
)
from eval.ai_qa_terra_high_cycle import (
    COUNTS,
    DEFAULT_TERRA_HIGH_DATASET_DIR,
    ERROR_DISTRIBUTION,
    build_terra_high_cycle_rows,
    verify_terra_high_cycle,
    write_terra_high_cycle,
)


class TerraHighCycleTests(unittest.TestCase):
    def test_rows_are_reproducible_and_balanced(self) -> None:
        first = build_terra_high_cycle_rows()
        second = build_terra_high_cycle_rows()
        self.assertEqual(first, second)
        self.assertEqual(set(first), {
            "terra_high_calibration",
            "terra_high_validation",
        })
        for inputs, truth in first.values():
            self.assertEqual(len(inputs), 280)
            self.assertEqual(len(truth), 280)
        self.assertEqual(COUNTS, {"clean": 140, "corrupted": 140})
        self.assertEqual(ERROR_DISTRIBUTION["wbs"], 56)
        self.assertEqual(ERROR_DISTRIBUTION["rooms"], 21)
        self.assertEqual(ERROR_DISTRIBUTION["district"], 10)

    def test_committed_data_has_no_leakage_or_overlap(self) -> None:
        manifest = verify_terra_high_cycle()
        self.assertTrue(
            all(value == 0 for value in manifest["isolation"]["overlaps"].values())
        )
        self.assertIn(
            "calibration_ai_qa_locked_holdout_model_inputs",
            manifest["isolation"]["overlaps"],
        )
        self.assertIn(
            "calibration_terra_high_reasoning_screen",
            manifest["isolation"]["overlaps"],
        )
        for split in ("terra_high_calibration", "terra_high_validation"):
            artifact = manifest["splits"][split]["artifacts"]["model_inputs"]
            input_path = DEFAULT_TERRA_HIGH_DATASET_DIR / artifact["file"]
            for line in input_path.read_text(encoding="utf-8").splitlines():
                self.assertEqual(
                    set(json.loads(line)),
                    {"case_id", "raw_text", "parser_snapshot"},
                )

    def test_write_is_byte_reproducible_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first, second = Path(first_dir), Path(second_dir)
            self.assertEqual(
                write_terra_high_cycle(first),
                write_terra_high_cycle(second),
            )
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )
            with self.assertRaises(FileExistsError):
                write_terra_high_cycle(first)

    def test_runner_allows_only_exact_high_calibration(self) -> None:
        plan = build_run_plan(
            split="terra_high_calibration",
            config=RunnerConfig(
                model="gpt-5.6-terra",
                reasoning_effort="high",
                max_output_tokens=256,
                retries=0,
                prompt_version="terra-v1",
            ),
        )
        self.assertEqual(plan.case_count, 280)
        summary = dry_run_summary(
            plan,
            budget_limit_usd=TERRA_HIGH_CALIBRATION_HARD_BUDGET_USD,
            output_dir=Path("eval/runs/terra-high-calibration"),
        )
        self.assertTrue(summary["budget_sufficient"])
        self.assertFalse(summary["credential_read"])
        self.assertEqual(summary["network_calls"], 0)

        with self.assertRaisesRegex(OfflineRunnerError, "differs from contract"):
            build_run_plan(
                split="terra_high_calibration",
                config=RunnerConfig(
                    model="gpt-5.6-terra",
                    reasoning_effort="medium",
                    max_output_tokens=256,
                    retries=0,
                    prompt_version="terra-v1",
                ),
            )

    def test_passing_freeze_authorizes_only_exact_validation(self) -> None:
        freeze = json.loads(TERRA_HIGH_FREEZE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(freeze["status"], "validation_authorized_once")
        self.assertFalse(freeze["boundaries"]["locked_holdout_authorized"])
        self.assertFalse(freeze["boundaries"]["landing_claim_authorized"])
        plan = build_run_plan(
            split="terra_high_validation",
            config=RunnerConfig(
                model="gpt-5.6-terra",
                reasoning_effort="high",
                max_output_tokens=256,
                retries=0,
                prompt_version="terra-v1",
            ),
        )
        self.assertEqual(plan.case_count, 280)
        self.assertEqual(
            plan.input_sha256,
            "fb26a15e4e4489c82dec342449f44dc8df18daed7bf6c71f5d6d3a8c3c6a4f65",
        )
        with self.assertRaises(FileExistsError):
            write_terra_high_calibration_freeze()

        with self.assertRaisesRegex(OfflineRunnerError, "differs from contract"):
            build_run_plan(
                split="terra_high_validation",
                config=RunnerConfig(
                    model="gpt-5.6-terra",
                    reasoning_effort="medium",
                    max_output_tokens=256,
                    retries=0,
                    prompt_version="terra-v1",
                ),
            )

    def test_execute_rejects_wrong_budget_before_credential(self) -> None:
        plan = build_run_plan(
            split="terra_high_calibration",
            config=RunnerConfig(
                model="gpt-5.6-terra",
                reasoning_effort="high",
                max_output_tokens=256,
                retries=0,
                prompt_version="terra-v1",
            ),
        )
        with self.assertRaisesRegex(OfflineRunnerError, "budget differs"):
            execute_run_plan(
                plan,
                output_dir=Path("eval/runs/terra-high-calibration"),
                budget_limit_usd=Decimal("4.99"),
                api_key_loader=lambda: self.fail("credential must not be read"),
            )


if __name__ == "__main__":
    unittest.main()
