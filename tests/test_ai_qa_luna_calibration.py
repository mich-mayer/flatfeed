from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from eval.ai_qa_datasets import ARTIFACT_FILENAMES, DEFAULT_DATASET_DIR
from eval.ai_qa_luna_calibration import (
    DEFAULT_LUNA_DATASET_DIR,
    LUNA_SPLITS,
    build_luna_calibration_rows,
    verify_luna_calibration_datasets,
    write_luna_calibration_datasets,
)
from eval.ai_qa_prompt import (
    EVAL_PROMPT_VERSION,
    LUNA_PROMPT_VERSION,
    LUNA_V2_PROMPT_VERSION,
    LUNA_SYSTEM_INSTRUCTIONS,
    LUNA_V2_SYSTEM_INSTRUCTIONS,
    SYSTEM_INSTRUCTIONS,
    get_system_instructions,
)
from eval.ai_qa_runner import (
    RunnerConfig,
    _request_case,
    build_run_plan,
    dry_run_summary,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            status="completed",
            model="gpt-5.6-luna",
            output_text='{"has_error":false,"error_field":null}',
            output=[],
            usage=None,
        )


class _FakeClient:
    def __init__(self) -> None:
        self.responses = _FakeResponses()


class LunaCalibrationDatasetTests(unittest.TestCase):
    def test_two_fresh_splits_are_valid_and_disjoint(self) -> None:
        datasets = build_luna_calibration_rows()

        self.assertEqual(set(datasets), set(LUNA_SPLITS))
        signatures: dict[str, set[str]] = {}
        for split_name, (inputs, truth) in datasets.items():
            self.assertEqual(len(inputs), 100)
            self.assertEqual(len(truth), 100)
            self.assertEqual(
                [row["case_id"] for row in inputs],
                [row["case_id"] for row in truth],
            )
            signatures[split_name] = {
                json.dumps(row, ensure_ascii=False, sort_keys=True)
                for row in inputs
            }
        self.assertFalse(
            signatures["luna_calibration"]
            & signatures["luna_validation"]
        )

    def test_write_is_byte_reproducible_and_preserves_original_dataset(self) -> None:
        protected_paths = [
            DEFAULT_DATASET_DIR / filename
            for filename in ARTIFACT_FILENAMES.values()
        ]
        protected_hashes = {
            path.name: _sha256(path)
            for path in protected_paths
        }
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            first_manifest = write_luna_calibration_datasets(first)
            second_manifest = write_luna_calibration_datasets(second)

            self.assertEqual(first_manifest, second_manifest)
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )
        self.assertEqual(
            protected_hashes,
            {path.name: _sha256(path) for path in protected_paths},
        )

    def test_committed_artifacts_verify_without_answer_key_leakage(self) -> None:
        manifest = verify_luna_calibration_datasets(DEFAULT_LUNA_DATASET_DIR)

        self.assertTrue(
            all(value == 0 for value in manifest["isolation"]["overlaps"].values())
        )
        for split in manifest["splits"].values():
            input_path = DEFAULT_LUNA_DATASET_DIR / split["artifacts"][
                "model_inputs"
            ]["file"]
            for line in input_path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.assertEqual(
                    set(row),
                    {"case_id", "raw_text", "parser_snapshot"},
                )


class LunaPromptAndRunnerTests(unittest.TestCase):
    def test_prompt_profiles_are_explicit_and_versioned(self) -> None:
        self.assertEqual(get_system_instructions(EVAL_PROMPT_VERSION), SYSTEM_INSTRUCTIONS)
        self.assertEqual(
            get_system_instructions(LUNA_PROMPT_VERSION),
            LUNA_SYSTEM_INSTRUCTIONS,
        )
        self.assertIn('"WBS 141-220" means 160, 180, 220', LUNA_SYSTEM_INSTRUCTIONS)
        self.assertIn('first compare an explicit "Bezirk"', LUNA_SYSTEM_INSTRUCTIONS)
        self.assertEqual(
            get_system_instructions(LUNA_V2_PROMPT_VERSION),
            LUNA_V2_SYSTEM_INSTRUCTIONS,
        )
        self.assertIn('"WBS 100" means only 100', LUNA_V2_SYSTEM_INSTRUCTIONS)
        self.assertIn(
            "generic WBS requirement with no number means type unknown",
            LUNA_V2_SYSTEM_INSTRUCTIONS,
        )
        self.assertIn("Hochparterre", LUNA_V2_SYSTEM_INSTRUCTIONS)
        with self.assertRaisesRegex(ValueError, "unknown prompt version"):
            get_system_instructions("missing")

    def test_runner_uses_luna_split_and_luna_prompt(self) -> None:
        config = RunnerConfig(
            model="gpt-5.6-luna",
            reasoning_effort="none",
            retries=0,
            prompt_version=LUNA_PROMPT_VERSION,
        )
        plan = build_run_plan(
            split="luna_calibration",
            limit=1,
            config=config,
        )
        summary = dry_run_summary(plan)

        self.assertEqual(summary["split"], "luna_calibration")
        self.assertEqual(summary["prompt"]["version"], LUNA_PROMPT_VERSION)
        self.assertEqual(
            summary["prompt"]["system_instructions"],
            LUNA_SYSTEM_INSTRUCTIONS,
        )

        client = _FakeClient()
        prediction = _request_case(
            client=client,
            case=plan.cases[0],
            config=config,
            sleep_fn=lambda _seconds: None,
            monotonic_fn=iter((0.0, 0.1)).__next__,
        )
        self.assertEqual(prediction["status"], "completed")
        self.assertEqual(
            client.responses.calls[0]["instructions"],
            LUNA_SYSTEM_INSTRUCTIONS,
        )
        self.assertEqual(
            client.responses.calls[0]["reasoning"],
            {"effort": "none"},
        )


if __name__ == "__main__":
    unittest.main()
