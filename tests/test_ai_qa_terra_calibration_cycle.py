from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.ai_qa_runner import (
    TERRA_CALIBRATION_HARD_BUDGET_USD,
    OfflineRunnerError,
    RunnerConfig,
    build_run_plan,
    dry_run_summary,
    write_terra_calibration_freeze,
)
from eval.ai_qa_terra_calibration_cycle import (
    DEFAULT_TERRA_CALIBRATION_DATASET_DIR,
    build_terra_calibration_cycle_rows,
    verify_terra_calibration_cycle,
    write_terra_calibration_cycle,
)


class TerraCalibrationCycleTests(unittest.TestCase):
    def test_datasets_are_fresh_balanced_and_reproducible(self) -> None:
        first = build_terra_calibration_cycle_rows()
        self.assertEqual(first, build_terra_calibration_cycle_rows())
        self.assertEqual(set(first), {"terra_calibration", "terra_validation"})
        self.assertTrue(all(len(rows[0]) == 280 for rows in first.values()))
        self.assertFalse(
            {row["case_id"] for row in first["terra_calibration"][0]}
            & {row["case_id"] for row in first["terra_validation"][0]}
        )

    def test_manifest_proves_zero_overlap_and_no_truth_leakage(self) -> None:
        manifest = verify_terra_calibration_cycle()
        self.assertTrue(all(value == 0 for value in manifest["isolation"]["overlaps"].values()))
        self.assertIn("calibration_terra_prompt_reasoning_screen", manifest["isolation"]["overlaps"])
        for split in manifest["splits"].values():
            path = DEFAULT_TERRA_CALIBRATION_DATASET_DIR / split["artifacts"]["model_inputs"]["file"]
            for line in path.read_text(encoding="utf-8").splitlines():
                self.assertEqual(set(json.loads(line)), {"case_id", "raw_text", "parser_snapshot"})

    def test_write_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first, second = Path(first_dir), Path(second_dir)
            self.assertEqual(write_terra_calibration_cycle(first), write_terra_calibration_cycle(second))
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )

    def test_runner_enforces_exact_profile_and_budget(self) -> None:
        config = RunnerConfig(
            model="gpt-5.6-terra",
            reasoning_effort="medium",
            max_output_tokens=256,
            retries=0,
            prompt_version="terra-v1",
        )
        plan = build_run_plan(split="terra_calibration", config=config)
        summary = dry_run_summary(plan, budget_limit_usd=TERRA_CALIBRATION_HARD_BUDGET_USD)
        self.assertEqual(plan.case_count, 280)
        self.assertTrue(summary["budget_sufficient"])
        with self.assertRaisesRegex(OfflineRunnerError, "differs from contract"):
            build_run_plan(
                split="terra_calibration",
                config=RunnerConfig(
                    model="gpt-5.6-terra",
                    reasoning_effort="low",
                    max_output_tokens=256,
                    retries=0,
                    prompt_version="terra-v1",
                ),
            )

    def test_validation_requires_and_matches_committed_freeze(self) -> None:
        plan = build_run_plan(
            split="terra_validation",
            config=RunnerConfig(
                model="gpt-5.6-terra",
                reasoning_effort="medium",
                max_output_tokens=256,
                retries=0,
                prompt_version="terra-v1",
            ),
        )
        self.assertEqual(plan.case_count, 280)
        self.assertEqual(
            plan.input_sha256,
            "1b6dabc602067d571adf42b6a0e467293503ac4802eb4910974dcba0663f58e2",
        )
        with self.assertRaisesRegex(OfflineRunnerError, "differs from contract"):
            build_run_plan(
                split="terra_validation",
                config=RunnerConfig(
                    model="gpt-5.6-terra",
                    reasoning_effort="low",
                    max_output_tokens=256,
                    retries=0,
                    prompt_version="terra-v1",
                ),
            )

    def test_freeze_is_reproducible_from_passing_calibration(self) -> None:
        with tempfile.TemporaryDirectory(dir="eval/runs") as output_dir:
            path = write_terra_calibration_freeze(
                output_path=Path(output_dir) / "freeze.json"
            )
            generated = json.loads(path.read_text(encoding="utf-8"))
            committed = json.loads(
                Path("eval/runs/terra-calibration-configuration-freeze.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(generated, committed)


if __name__ == "__main__":
    unittest.main()
