from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from eval.ai_qa_review_development import (
    COUNTS,
    DEFAULT_OUTPUT_DIR,
    ERROR_DISTRIBUTION,
    MANIFEST_FILE,
    MODEL_INPUTS_FILE,
    TRUTH_FILE,
    build_review_development_rows,
    verify_review_development,
    write_review_development,
)
from eval.ai_qa_scorer import TRUTH_FIELD_TO_ERROR_FIELD


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


class AIQAReviewDevelopmentTests(unittest.TestCase):
    def test_rows_are_reproducible_and_match_predeclared_counts(self) -> None:
        first = build_review_development_rows()
        second = build_review_development_rows()

        self.assertEqual(first, second)
        inputs, truth, _ = first
        self.assertEqual(len(inputs), 120)
        self.assertEqual(len(truth), 120)
        self.assertEqual(
            Counter(row["case_type"] for row in truth),
            Counter(COUNTS),
        )

        distribution = Counter(
            TRUTH_FIELD_TO_ERROR_FIELD[str(row["corrupted_field"])]
            for row in truth
            if row["case_type"] == "corrupted"
        )
        self.assertEqual(distribution, Counter(ERROR_DISTRIBUTION))

    def test_composition_keeps_extra_rooms_and_postal_cases(self) -> None:
        _, _, composition = build_review_development_rows()
        corruption_types = composition["corruption_types"]

        self.assertEqual(corruption_types["rooms_neighbor_value"], 20)
        self.assertEqual(corruption_types["postal_code_substitution"], 6)
        self.assertEqual(corruption_types["address_house_number_shift"], 4)
        self.assertEqual(
            sum(composition["source"]["format_variants"].values()),
            120,
        )
        self.assertEqual(
            len(composition["source"]["format_variants"]),
            6,
        )

    def test_model_inputs_do_not_contain_hidden_truth(self) -> None:
        input_rows, _, _ = build_review_development_rows()
        forbidden = {
            "case_type",
            "corrupted_field",
            "expected_value",
            "corrupted_value",
            "corruption_type",
            "truth",
            "seed",
        }

        for row in input_rows:
            self.assertEqual(
                set(row),
                {"case_id", "raw_text", "parser_snapshot"},
            )
            rendered = json.dumps(row, ensure_ascii=False, sort_keys=True)
            for key in forbidden:
                self.assertNotIn(f'"{key}"', rendered)

    def test_write_is_byte_reproducible_and_refuses_overwrite(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first_dir,
            tempfile.TemporaryDirectory() as second_dir,
            tempfile.TemporaryDirectory() as prior_dir,
            patch(
                "eval.ai_qa_review_development.DATASETS_ROOT",
                Path(prior_dir),
            ),
        ):
            first = Path(first_dir)
            second = Path(second_dir)

            write_review_development(first)
            write_review_development(second)

            self.assertEqual(
                {
                    path.name: path.read_bytes()
                    for path in first.iterdir()
                },
                {
                    path.name: path.read_bytes()
                    for path in second.iterdir()
                },
            )
            with self.assertRaises(FileExistsError):
                write_review_development(first)

    def test_committed_artifacts_are_verified_and_isolated(self) -> None:
        manifest = verify_review_development()

        self.assertEqual(manifest["counts"]["total"], 120)
        self.assertEqual(
            manifest["model_inputs"]["lines"],
            120,
        )
        self.assertEqual(manifest["truth"]["lines"], 120)
        self.assertGreater(
            manifest["isolation"]["prior_artifact_count"],
            0,
        )
        for overlap in manifest["isolation"]["overlaps"].values():
            self.assertEqual(
                overlap,
                {"model_input": 0, "raw_text": 0, "case_id": 0},
            )
        self.assertFalse(
            manifest["boundaries"]["openai_called_during_generation"]
        )
        self.assertFalse(
            manifest["boundaries"]["api_execution_authorized_by_manifest"]
        )

    def test_committed_model_inputs_exclude_consumed_miss_ids(self) -> None:
        current_ids = {
            row["case_id"]
            for row in _read_jsonl(DEFAULT_OUTPUT_DIR / MODEL_INPUTS_FILE)
        }
        missed_ids = {
            row["case_id"]
            for row in _read_jsonl(
                Path("eval/runs/terra-high-locked-holdout/reports")
                / "false_negatives.jsonl"
            )
        }

        self.assertFalse(current_ids & missed_ids)

    def test_expected_artifact_names_are_stable(self) -> None:
        self.assertEqual(MODEL_INPUTS_FILE, "model_inputs.jsonl")
        self.assertEqual(TRUTH_FILE, "truth.jsonl")
        self.assertEqual(MANIFEST_FILE, "dataset_manifest.json")


if __name__ == "__main__":
    unittest.main()
