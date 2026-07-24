from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from eval.ai_qa_datasets import ARTIFACT_FILENAMES, DEFAULT_DATASET_DIR
from eval.ai_qa_luna_calibration import DEFAULT_LUNA_DATASET_DIR
from eval.ai_qa_luna_v3_cycle import (
    DEFAULT_LUNA_V3_DATASET_DIR,
    LUNA_V3_COUNTS,
    LUNA_V3_ERROR_DISTRIBUTION,
    LUNA_V3_SPLITS,
    build_luna_v3_cycle_rows,
    verify_luna_v3_cycle_datasets,
    write_luna_v3_cycle_datasets,
)
from eval.ai_qa_prompt import (
    LUNA_V3_PROMPT_VERSION,
    LUNA_V3_SYSTEM_INSTRUCTIONS,
    get_system_instructions,
)
from eval.ai_qa_runner import (
    OfflineRunnerError,
    RunnerConfig,
    build_run_plan,
    dry_run_summary,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LunaV3CycleTests(unittest.TestCase):
    def test_contract_is_predeclared_and_emphasizes_critical_fields(self) -> None:
        self.assertEqual(LUNA_V3_COUNTS, {"clean": 100, "corrupted": 100})
        self.assertEqual(sum(LUNA_V3_ERROR_DISTRIBUTION.values()), 100)
        self.assertEqual(LUNA_V3_ERROR_DISTRIBUTION["rent_kalt"], 25)
        self.assertEqual(LUNA_V3_ERROR_DISTRIBUTION["wbs"], 20)
        self.assertEqual(LUNA_V3_ERROR_DISTRIBUTION["rooms"], 15)
        self.assertEqual(LUNA_V3_ERROR_DISTRIBUTION["floor"], 15)

    def test_splits_are_reproducible_and_disjoint(self) -> None:
        first = build_luna_v3_cycle_rows()
        second = build_luna_v3_cycle_rows()
        self.assertEqual(first, second)
        self.assertEqual(set(first), set(LUNA_V3_SPLITS))

        calibration_ids = {
            row["case_id"] for row in first["luna_v3_calibration"][0]
        }
        validation_ids = {
            row["case_id"] for row in first["luna_v3_validation"][0]
        }
        self.assertEqual(len(calibration_ids), 200)
        self.assertEqual(len(validation_ids), 200)
        self.assertFalse(calibration_ids & validation_ids)

    def test_write_is_byte_reproducible_and_preserves_prior_artifacts(self) -> None:
        protected_paths = [
            *(DEFAULT_DATASET_DIR / name for name in ARTIFACT_FILENAMES.values()),
            *(path for path in DEFAULT_LUNA_DATASET_DIR.iterdir() if path.is_file()),
        ]
        protected_hashes = {str(path): _sha256(path) for path in protected_paths}

        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            first_manifest = write_luna_v3_cycle_datasets(first)
            second_manifest = write_luna_v3_cycle_datasets(second)
            self.assertEqual(first_manifest, second_manifest)
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )

        self.assertEqual(
            protected_hashes,
            {str(path): _sha256(path) for path in protected_paths},
        )

    def test_committed_inputs_have_no_answer_key_leakage(self) -> None:
        manifest = verify_luna_v3_cycle_datasets(DEFAULT_LUNA_V3_DATASET_DIR)
        self.assertTrue(
            all(
                count == 0
                for count in manifest["isolation"]["overlaps"].values()
            )
        )
        for split in manifest["splits"].values():
            path = DEFAULT_LUNA_V3_DATASET_DIR / split["artifacts"][
                "model_inputs"
            ]["file"]
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.assertEqual(
                    set(row),
                    {"case_id", "raw_text", "parser_snapshot"},
                )

    def test_luna_v3_prompt_is_surgical_and_runner_selects_it(self) -> None:
        prompt = get_system_instructions(LUNA_V3_PROMPT_VERSION)
        self.assertEqual(prompt, LUNA_V3_SYSTEM_INSTRUCTIONS)
        self.assertIn("map only to rent_kalt", prompt)
        self.assertIn("map only to rent_warm", prompt)
        self.assertIn("compare an explicit \"Bezirk\"", prompt)
        self.assertIn('"WBS 100" means only 100', prompt)

        config = RunnerConfig(
            model="gpt-5.6-luna",
            reasoning_effort="none",
            retries=0,
            prompt_version=LUNA_V3_PROMPT_VERSION,
        )
        plan = build_run_plan(
            split="luna_v3_calibration",
            limit=2,
            config=config,
        )
        summary = dry_run_summary(plan)
        self.assertEqual(summary["prompt"]["version"], "luna-v3")
        self.assertEqual(summary["prompt"]["system_instructions"], prompt)
        self.assertEqual(summary["answer_key_leakage_check"]["status"], "passed")
        self.assertEqual(summary["request_plan"]["maximum_responses_api_requests"], 2)

    def test_validation_requires_exact_frozen_configuration(self) -> None:
        frozen = RunnerConfig(
            model="gpt-5.6-luna",
            reasoning_effort="none",
            retries=0,
            max_output_tokens=64,
            prompt_version=LUNA_V3_PROMPT_VERSION,
        )
        plan = build_run_plan(split="luna_v3_validation", config=frozen)
        self.assertEqual(plan.case_count, 200)

        with self.assertRaisesRegex(
            OfflineRunnerError,
            "differs from freeze",
        ):
            build_run_plan(
                split="luna_v3_validation",
                config=RunnerConfig(
                    model="gpt-5.6-luna",
                    reasoning_effort="none",
                    retries=0,
                    max_output_tokens=65,
                    prompt_version=LUNA_V3_PROMPT_VERSION,
                ),
            )


if __name__ == "__main__":
    unittest.main()
