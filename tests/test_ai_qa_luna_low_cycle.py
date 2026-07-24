from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.ai_qa_luna_low_cycle import (
    DEFAULT_LUNA_LOW_DATASET_DIR,
    LUNA_LOW_COUNTS,
    LUNA_LOW_ERROR_DISTRIBUTION,
    LUNA_LOW_SPLITS,
    build_luna_low_cycle_rows,
    verify_luna_low_cycle_datasets,
    write_luna_low_cycle_datasets,
)
from eval.ai_qa_runner import (
    LUNA_LOW_CALIBRATION_HARD_BUDGET_USD,
    OfflineRunnerError,
    RunnerConfig,
    build_run_plan,
    dry_run_summary,
)


class LunaLowCycleTests(unittest.TestCase):
    def test_contract_is_balanced_fresh_and_reproducible(self) -> None:
        self.assertEqual(LUNA_LOW_COUNTS, {"clean": 140, "corrupted": 140})
        self.assertEqual(sum(LUNA_LOW_ERROR_DISTRIBUTION.values()), 140)
        self.assertEqual(LUNA_LOW_ERROR_DISTRIBUTION["wbs"], 56)
        first = build_luna_low_cycle_rows()
        second = build_luna_low_cycle_rows()
        self.assertEqual(first, second)
        self.assertEqual(set(first), set(LUNA_LOW_SPLITS))
        calibration_ids = {
            row["case_id"] for row in first["luna_low_calibration"][0]
        }
        validation_ids = {
            row["case_id"] for row in first["luna_low_validation"][0]
        }
        self.assertEqual(len(calibration_ids), 280)
        self.assertEqual(len(validation_ids), 280)
        self.assertFalse(calibration_ids & validation_ids)

    def test_manifest_proves_isolation_and_model_input_leakage_boundary(self) -> None:
        manifest = verify_luna_low_cycle_datasets(
            DEFAULT_LUNA_LOW_DATASET_DIR
        )
        overlaps = manifest["isolation"]["overlaps"]
        self.assertTrue(all(count == 0 for count in overlaps.values()))
        self.assertIn("calibration_luna_effort_screen", overlaps)
        self.assertIn("validation_luna_effort_screen", overlaps)
        for split in manifest["splits"].values():
            input_path = DEFAULT_LUNA_LOW_DATASET_DIR / split["artifacts"][
                "model_inputs"
            ]["file"]
            for line in input_path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.assertEqual(
                    set(row),
                    {"case_id", "raw_text", "parser_snapshot"},
                )

    def test_write_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            self.assertEqual(
                write_luna_low_cycle_datasets(first),
                write_luna_low_cycle_datasets(second),
            )
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )

    def test_runner_enforces_frozen_calibration_profile_and_budget(self) -> None:
        config = RunnerConfig(
            model="gpt-5.6-luna",
            reasoning_effort="low",
            max_output_tokens=256,
            retries=0,
            prompt_version="luna-v5",
        )
        plan = build_run_plan(split="luna_low_calibration", config=config)
        summary = dry_run_summary(
            plan,
            budget_limit_usd=LUNA_LOW_CALIBRATION_HARD_BUDGET_USD,
        )
        self.assertEqual(plan.case_count, 280)
        self.assertTrue(summary["budget_sufficient"])
        self.assertEqual(summary["reasoning_effort"], "low")
        self.assertEqual(summary["prompt"]["version"], "luna-v5")
        self.assertEqual(
            summary["request_plan"]["maximum_responses_api_requests"],
            280,
        )
        self.assertEqual(summary["hard_budget_limit_usd"], 1.72)
        with self.assertRaisesRegex(OfflineRunnerError, "differs from contract"):
            build_run_plan(
                split="luna_low_calibration",
                config=RunnerConfig(
                    model="gpt-5.6-luna",
                    reasoning_effort="none",
                    max_output_tokens=256,
                    retries=0,
                    prompt_version="luna-v5",
                ),
            )

    def test_validation_is_closed_before_passing_calibration_freeze(self) -> None:
        with self.assertRaisesRegex(
            OfflineRunnerError,
            "disabled until passing calibration freeze",
        ):
            build_run_plan(
                split="luna_low_validation",
                config=RunnerConfig(
                    model="gpt-5.6-luna",
                    reasoning_effort="low",
                    max_output_tokens=256,
                    retries=0,
                    prompt_version="luna-v5",
                ),
            )


if __name__ == "__main__":
    unittest.main()
