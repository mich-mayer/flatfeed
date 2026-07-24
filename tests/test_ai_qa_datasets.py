from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from eval.ai_qa_datasets import (
    ARTIFACT_FILENAMES,
    DATASET_SEED,
    DEVELOPMENT_ERROR_DISTRIBUTION,
    LOCKED_HOLDOUT_ERROR_DISTRIBUTION,
    build_ai_qa_dataset_rows,
    verify_ai_qa_dataset,
    verify_dataset_reproducibility,
    write_ai_qa_datasets,
)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _input_signature(row: dict[str, object]) -> str:
    return json.dumps(
        {
            "raw_text": row["raw_text"],
            "parser_snapshot": row["parser_snapshot"],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class AIQADatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.output_dir = Path(self._temporary_directory.name)
        self.manifest = write_ai_qa_datasets(self.output_dir)

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _inputs(self, split: str) -> list[dict[str, object]]:
        key = (
            "development_model_inputs"
            if split == "development"
            else "locked_holdout_model_inputs"
        )
        return _read_jsonl(self.output_dir / ARTIFACT_FILENAMES[key])

    def _truth(self, split: str) -> list[dict[str, object]]:
        key = (
            "development_truth"
            if split == "development"
            else "locked_holdout_truth"
        )
        return _read_jsonl(self.output_dir / ARTIFACT_FILENAMES[key])

    def test_contract_counts_and_holdout_distribution_are_exact(self) -> None:
        development_truth = self._truth("development")
        holdout_truth = self._truth("locked_holdout")

        self.assertEqual(len(development_truth), 100)
        self.assertEqual(
            sum(row["case_type"] == "clean" for row in development_truth),
            50,
        )
        self.assertEqual(
            sum(row["case_type"] == "corrupted" for row in development_truth),
            50,
        )
        self.assertEqual(len(holdout_truth), 600)
        self.assertEqual(
            sum(row["case_type"] == "clean" for row in holdout_truth),
            300,
        )
        self.assertEqual(
            sum(row["case_type"] == "corrupted" for row in holdout_truth),
            300,
        )

        field_to_category = {
            "display_wbs": "wbs",
            "rent_kalt": "rent_kalt",
            "rooms": "rooms",
            "address": "address_postal_code",
            "postal_code": "address_postal_code",
            "district": "district",
            "floor": "floor",
            "rent_warm": "rent_warm",
        }
        for truth_rows, expected in (
            (development_truth, DEVELOPMENT_ERROR_DISTRIBUTION),
            (holdout_truth, LOCKED_HOLDOUT_ERROR_DISTRIBUTION),
        ):
            actual = {field: 0 for field in expected}
            for row in truth_rows:
                if row["case_type"] == "corrupted":
                    actual[field_to_category[row["corrupted_field"]]] += 1
            self.assertEqual(actual, expected)

    def test_inputs_are_unique_and_splits_are_disjoint(self) -> None:
        development_inputs = self._inputs("development")
        holdout_inputs = self._inputs("locked_holdout")
        all_inputs = [*development_inputs, *holdout_inputs]

        self.assertEqual(len({row["case_id"] for row in all_inputs}), 700)
        self.assertEqual(len({row["raw_text"] for row in all_inputs}), 700)
        self.assertEqual(len({_input_signature(row) for row in all_inputs}), 700)
        self.assertTrue(
            {row["case_id"] for row in development_inputs}.isdisjoint(
                {row["case_id"] for row in holdout_inputs}
            )
        )
        self.assertTrue(
            {row["raw_text"] for row in development_inputs}.isdisjoint(
                {row["raw_text"] for row in holdout_inputs}
            )
        )

    def test_model_input_envelopes_have_no_answer_key_leakage(self) -> None:
        forbidden_keys = {
            "answer_key",
            "case_type",
            "clean",
            "corrupted",
            "corrupted_field",
            "corrupted_value",
            "corruption_type",
            "error_category",
            "expected_value",
            "format_variant",
            "generation_seed",
            "label",
            "required_wbs",
            "seed",
            "split",
            "title",
            "truth",
        }

        for row in [
            *self._inputs("development"),
            *self._inputs("locked_holdout"),
        ]:
            with self.subTest(case_id=row["case_id"]):
                self.assertEqual(
                    set(row),
                    {"case_id", "raw_text", "parser_snapshot"},
                )
                self.assertRegex(row["case_id"], r"^aqa-[0-9a-f]{20}$")
                self.assertTrue(
                    forbidden_keys.isdisjoint(row["parser_snapshot"])
                )
                serialized = json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                for forbidden_key in forbidden_keys - {"required_wbs"}:
                    self.assertNotIn(f'"{forbidden_key}"', serialized)

    def test_manifest_hashes_match_every_jsonl_artifact(self) -> None:
        for split_name in ("development", "locked_holdout"):
            artifacts = self.manifest["splits"][split_name]["artifacts"]
            for artifact in artifacts.values():
                path = self.output_dir / artifact["file"]
                self.assertEqual(artifact["sha256"], _sha256(path))
                self.assertEqual(
                    artifact["lines"],
                    len(path.read_text(encoding="utf-8").splitlines()),
                )

    def test_same_seed_is_byte_for_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as second_directory:
            second_path = Path(second_directory)
            write_ai_qa_datasets(second_path, seed=DATASET_SEED)
            for filename in ARTIFACT_FILENAMES.values():
                self.assertEqual(
                    (self.output_dir / filename).read_bytes(),
                    (second_path / filename).read_bytes(),
                )

        verify_dataset_reproducibility(self.output_dir)

    def test_different_seed_changes_generated_rows(self) -> None:
        default_rows = build_ai_qa_dataset_rows(seed=DATASET_SEED)
        alternate_rows = build_ai_qa_dataset_rows(seed=DATASET_SEED + 1)

        self.assertNotEqual(default_rows, alternate_rows)

    def test_hash_verification_detects_artifact_tampering(self) -> None:
        path = self.output_dir / ARTIFACT_FILENAMES["development_model_inputs"]
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        first_row = json.loads(lines[0])
        lines[0] = (
            json.dumps(
                {
                    "raw_text": first_row["raw_text"],
                    "parser_snapshot": first_row["parser_snapshot"],
                    "case_id": first_row["case_id"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        path.write_text("".join(lines), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "SHA-256"):
            verify_ai_qa_dataset(self.output_dir)

    def test_invalid_seed_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "seed must be an integer"):
            build_ai_qa_dataset_rows(seed=True)


if __name__ == "__main__":
    unittest.main()
