from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.ai_qa_luna_effort_screen import (
    DEFAULT_LUNA_EFFORT_SCREEN_DIR,
    SCREEN_COUNTS,
    SCREEN_ERROR_DISTRIBUTION,
    build_luna_effort_screen_rows,
    verify_luna_effort_screen,
    write_luna_effort_screen,
)
from eval.ai_qa_runner import OfflineRunnerError, RunnerConfig, build_run_plan


class LunaEffortScreenTests(unittest.TestCase):
    def test_screen_is_reproducible_and_matches_diagnostic_contract(self) -> None:
        first = build_luna_effort_screen_rows()
        second = build_luna_effort_screen_rows()
        self.assertEqual(first, second)
        self.assertEqual(SCREEN_COUNTS, {"clean": 8, "corrupted": 16})
        self.assertEqual(SCREEN_ERROR_DISTRIBUTION["wbs"], 10)
        self.assertEqual(len(first[0]), 24)

    def test_committed_screen_has_no_leakage_or_overlap(self) -> None:
        manifest = verify_luna_effort_screen(DEFAULT_LUNA_EFFORT_SCREEN_DIR)
        self.assertTrue(
            all(value == 0 for value in manifest["isolation"]["overlaps"].values())
        )
        input_path = DEFAULT_LUNA_EFFORT_SCREEN_DIR / manifest["model_inputs"]["file"]
        for line in input_path.read_text(encoding="utf-8").splitlines():
            self.assertEqual(
                set(json.loads(line)),
                {"case_id", "raw_text", "parser_snapshot"},
            )

    def test_write_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            self.assertEqual(write_luna_effort_screen(first), write_luna_effort_screen(second))
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )

    def test_runner_allows_only_exact_none_or_low_profiles(self) -> None:
        for effort in ("none", "low"):
            plan = build_run_plan(
                split="luna_effort_screen",
                config=RunnerConfig(
                    model="gpt-5.6-luna",
                    reasoning_effort=effort,
                    max_output_tokens=256,
                    retries=0,
                    prompt_version="luna-v5",
                ),
            )
            self.assertEqual(plan.case_count, 24)
        with self.assertRaisesRegex(OfflineRunnerError, "differs from contract"):
            build_run_plan(
                split="luna_effort_screen",
                config=RunnerConfig(
                    model="gpt-5.6-luna",
                    reasoning_effort="low",
                    max_output_tokens=128,
                    retries=0,
                    prompt_version="luna-v5",
                ),
            )


if __name__ == "__main__":
    unittest.main()
