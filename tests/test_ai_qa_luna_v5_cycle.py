from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.ai_qa_luna_v5_cycle import (
    DEFAULT_LUNA_V5_DATASET_DIR,
    LUNA_V5_COUNTS,
    LUNA_V5_ERROR_DISTRIBUTION,
    LUNA_V5_SPLITS,
    LUNA_V5_WBS_PHRASES,
    build_luna_v5_cycle_rows,
    verify_luna_v5_cycle_datasets,
    write_luna_v5_cycle_datasets,
)
from eval.ai_qa_prompt import (
    LUNA_V5_PROMPT_VERSION,
    LUNA_V5_SYSTEM_INSTRUCTIONS,
    get_system_instructions,
)
from eval.ai_qa_runner import (
    OfflineRunnerError,
    RunnerConfig,
    build_run_plan,
    dry_run_summary,
)


class LunaV5CycleTests(unittest.TestCase):
    def test_contract_is_balanced_and_reproducible(self) -> None:
        self.assertEqual(LUNA_V5_COUNTS, {"clean": 140, "corrupted": 140})
        self.assertEqual(sum(LUNA_V5_ERROR_DISTRIBUTION.values()), 140)
        self.assertEqual(LUNA_V5_ERROR_DISTRIBUTION["wbs"], 56)
        first = build_luna_v5_cycle_rows()
        second = build_luna_v5_cycle_rows()
        self.assertEqual(first, second)
        self.assertEqual(set(first), set(LUNA_V5_SPLITS))
        first_ids = {row["case_id"] for row in first["luna_v5_calibration"][0]}
        second_ids = {row["case_id"] for row in first["luna_v5_validation"][0]}
        self.assertEqual(len(first_ids), 280)
        self.assertEqual(len(second_ids), 280)
        self.assertFalse(first_ids & second_ids)

    def test_manifest_has_exact_semantic_balance_and_no_leakage(self) -> None:
        manifest = verify_luna_v5_cycle_datasets(DEFAULT_LUNA_V5_DATASET_DIR)
        self.assertTrue(
            all(count == 0 for count in manifest["isolation"]["overlaps"].values())
        )
        expected = {"clean": 20, "wbs_corrupted": 8, "non_wbs_corrupted": 12}
        for split in manifest["splits"].values():
            self.assertEqual(
                set(split["wbs_semantic_balance"]),
                set(LUNA_V5_WBS_PHRASES),
            )
            for balance in split["wbs_semantic_balance"].values():
                self.assertEqual(balance, expected)
            input_path = DEFAULT_LUNA_V5_DATASET_DIR / split["artifacts"][
                "model_inputs"
            ]["file"]
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
                write_luna_v5_cycle_datasets(first),
                write_luna_v5_cycle_datasets(second),
            )
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )

    def test_prompt_reduces_wbs_salience_and_runner_selects_it(self) -> None:
        prompt = get_system_instructions(LUNA_V5_PROMPT_VERSION)
        self.assertEqual(prompt, LUNA_V5_SYSTEM_INSTRUCTIONS)
        self.assertIn("normalized set of supported tiers", prompt)
        self.assertIn("141-220 with display_wbs 160, 180, 220 is correct", prompt)
        self.assertIn("Compare every field independently", prompt)
        self.assertNotIn("This WBS check is mandatory", prompt)
        config = RunnerConfig(
            model="gpt-5.6-luna",
            reasoning_effort="none",
            retries=0,
            max_output_tokens=64,
            prompt_version=LUNA_V5_PROMPT_VERSION,
        )
        plan = build_run_plan(
            split="luna_v5_calibration",
            limit=2,
            config=config,
        )
        summary = dry_run_summary(plan)
        self.assertEqual(summary["prompt"]["version"], "luna-v5")
        self.assertEqual(summary["request_plan"]["maximum_responses_api_requests"], 2)
        self.assertEqual(summary["answer_key_leakage_check"]["status"], "passed")

    def test_validation_is_closed_before_passing_calibration_freeze(self) -> None:
        with self.assertRaisesRegex(
            OfflineRunnerError,
            "disabled until passing calibration freeze",
        ):
            build_run_plan(
                split="luna_v5_validation",
                config=RunnerConfig(
                    model="gpt-5.6-luna",
                    reasoning_effort="none",
                    retries=0,
                    max_output_tokens=64,
                    prompt_version=LUNA_V5_PROMPT_VERSION,
                ),
            )


if __name__ == "__main__":
    unittest.main()
