from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from eval.ai_qa_luna_v4_cycle import (
    DEFAULT_LUNA_V4_DATASET_DIR,
    LUNA_V4_COUNTS,
    LUNA_V4_ERROR_DISTRIBUTION,
    LUNA_V4_SPLITS,
    build_luna_v4_cycle_rows,
    verify_luna_v4_cycle_datasets,
    write_luna_v4_cycle_datasets,
)
from eval.ai_qa_prompt import (
    LUNA_V4_PROMPT_VERSION,
    LUNA_V4_SYSTEM_INSTRUCTIONS,
    MODEL_OUTPUT_JSON_SCHEMA,
    get_system_instructions,
)
from eval.ai_qa_runner import (
    EVAL_ROOT,
    OfflineRunnerError,
    RUNNER_VERSION,
    RunnerConfig,
    build_run_plan,
    dry_run_summary,
    write_luna_v4_configuration_freeze,
)


class LunaV4CycleTests(unittest.TestCase):
    def test_contract_emphasizes_wbs_and_is_reproducible(self) -> None:
        self.assertEqual(LUNA_V4_COUNTS, {"clean": 120, "corrupted": 120})
        self.assertEqual(sum(LUNA_V4_ERROR_DISTRIBUTION.values()), 120)
        self.assertEqual(LUNA_V4_ERROR_DISTRIBUTION["wbs"], 50)

        first = build_luna_v4_cycle_rows()
        second = build_luna_v4_cycle_rows()
        self.assertEqual(first, second)
        self.assertEqual(set(first), set(LUNA_V4_SPLITS))
        calibration_ids = {
            row["case_id"] for row in first["luna_v4_calibration"][0]
        }
        validation_ids = {
            row["case_id"] for row in first["luna_v4_validation"][0]
        }
        self.assertEqual(len(calibration_ids), 240)
        self.assertEqual(len(validation_ids), 240)
        self.assertFalse(calibration_ids & validation_ids)

    def test_committed_datasets_are_isolated_and_have_no_truth_leakage(self) -> None:
        manifest = verify_luna_v4_cycle_datasets(DEFAULT_LUNA_V4_DATASET_DIR)
        self.assertTrue(
            all(count == 0 for count in manifest["isolation"]["overlaps"].values())
        )
        for split in manifest["splits"].values():
            input_path = DEFAULT_LUNA_V4_DATASET_DIR / split["artifacts"][
                "model_inputs"
            ]["file"]
            for line in input_path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.assertEqual(
                    set(row),
                    {"case_id", "raw_text", "parser_snapshot"},
                )
        all_inputs = "\n".join(
            (DEFAULT_LUNA_V4_DATASET_DIR / split["artifacts"]["model_inputs"]["file"])
            .read_text(encoding="utf-8")
            for split in manifest["splits"].values()
        )
        self.assertIn("141 % bis 220 %", all_inputs)
        self.assertIn("oberhalb von 140 %", all_inputs)

    def test_write_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            self.assertEqual(
                write_luna_v4_cycle_datasets(first),
                write_luna_v4_cycle_datasets(second),
            )
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )

    def test_prompt_and_runner_use_literal_wbs_boundaries(self) -> None:
        prompt_text = get_system_instructions(LUNA_V4_PROMPT_VERSION)
        self.assertEqual(prompt_text, LUNA_V4_SYSTEM_INSTRUCTIONS)
        self.assertIn("never round or snap", prompt_text)
        self.assertIn("141-220 or greater than 140", prompt_text)
        config = RunnerConfig(
            model="gpt-5.6-luna",
            reasoning_effort="none",
            retries=0,
            prompt_version=LUNA_V4_PROMPT_VERSION,
        )
        plan = build_run_plan(
            split="luna_v4_calibration",
            limit=2,
            config=config,
        )
        summary = dry_run_summary(plan)
        self.assertEqual(summary["prompt"]["version"], "luna-v4")
        self.assertEqual(summary["request_plan"]["maximum_responses_api_requests"], 2)
        self.assertEqual(summary["answer_key_leakage_check"]["status"], "passed")

    def test_validation_requires_passing_calibration_and_exact_freeze(self) -> None:
        config = RunnerConfig(
            model="gpt-5.6-luna",
            reasoning_effort="none",
            retries=0,
            max_output_tokens=64,
            prompt_version=LUNA_V4_PROMPT_VERSION,
        )
        with patch(
            "eval.ai_qa_runner.LUNA_V4_FREEZE_PATH",
            EVAL_ROOT / "runs" / "missing-v4-freeze.json",
        ):
            with self.assertRaisesRegex(OfflineRunnerError, "freeze is invalid"):
                build_run_plan(split="luna_v4_validation", config=config)

        runs_dir = EVAL_ROOT / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runs_dir) as temp_dir:
            temp = Path(temp_dir)
            report_path = temp / "report.json"
            manifest_path = temp / "run_manifest.json"
            freeze_path = temp / "freeze.json"
            report_path.write_text(
                json.dumps(
                    {
                        "split": "luna_v4_calibration",
                        "acceptance_gates": {"overall_status": "pass"},
                    }
                ),
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "runner_version": RUNNER_VERSION,
                        "configuration": {
                            "model": "gpt-5.6-luna",
                            "reasoning_effort": "none",
                            "max_output_tokens": 64,
                            "retries": 0,
                            "timeout_seconds": 60.0,
                            "prompt_version": "luna-v4",
                            "prompt_sha256": hashlib.sha256(
                                LUNA_V4_SYSTEM_INSTRUCTIONS.encode("utf-8")
                            ).hexdigest(),
                            "output_schema_sha256": hashlib.sha256(
                                json.dumps(
                                    MODEL_OUTPUT_JSON_SCHEMA,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                ).encode("utf-8")
                            ).hexdigest(),
                            "strict_structured_outputs": True,
                            "responses_api": True,
                            "store": False,
                        },
                        "split": "luna_v4_calibration",
                        "case_count": 240,
                    }
                ),
                encoding="utf-8",
            )
            write_luna_v4_configuration_freeze(
                calibration_report_path=report_path,
                calibration_run_manifest_path=manifest_path,
                validation_budget_limit_usd=Decimal("2.0"),
                output_path=freeze_path,
            )
            with patch("eval.ai_qa_runner.LUNA_V4_FREEZE_PATH", freeze_path):
                plan = build_run_plan(split="luna_v4_validation", config=config)
                self.assertEqual(plan.case_count, 240)


if __name__ == "__main__":
    unittest.main()
