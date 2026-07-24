from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.ai_qa_datasets import (
    ARTIFACT_FILENAMES,
    write_ai_qa_datasets,
)
from eval.ai_qa_holdout_readiness import (
    HoldoutReadinessError,
    audit_locked_holdout_readiness,
)


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key
            for nested in value.values()
            for key in _all_keys(nested)
        }
    if isinstance(value, list):
        return {
            key
            for nested in value
            for key in _all_keys(nested)
        }
    return set()


class LockedHoldoutReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.dataset_dir = Path(self._temporary_directory.name) / "ai_qa"
        write_ai_qa_datasets(self.dataset_dir)

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def test_frozen_dataset_is_ready_with_declared_limitations(self) -> None:
        audit = audit_locked_holdout_readiness(
            self.dataset_dir,
            comparison_input_paths=[
                self.dataset_dir
                / ARTIFACT_FILENAMES["development_model_inputs"]
            ],
        )

        self.assertEqual(audit["status"], "ready_with_declared_limitations")
        self.assertTrue(all(audit["checks"].values()))
        self.assertEqual(
            audit["composition"]["case_types"],
            {"clean": 300, "corrupted": 300},
        )
        self.assertEqual(audit["composition"]["unique_exact_inputs"], 600)
        self.assertEqual(
            audit["composition"]["format_families"],
            {
                "compact_block": 100,
                "costs_first": 100,
                "label_table": 99,
                "portal_lines": 99,
                "prose_first": 101,
                "sectioned": 101,
            },
        )
        self.assertEqual(
            audit["release_gates"]["product_scorecard"],
            {
                "parser_error_detection_rate": {
                    "target": ">= 95%",
                    "minimum_count": 285,
                    "denominator": 300,
                },
                "false_alert_rate": {
                    "target": "<= 3%",
                    "maximum_count": 9,
                    "denominator": 300,
                },
                "correct_field_detection_rate": {
                    "target": ">= 90%",
                    "minimum_count": 270,
                    "denominator": 300,
                },
                "successful_check_rate": {
                    "target": ">= 99.5%",
                    "minimum_count": 597,
                    "denominator": 600,
                },
            },
        )
        self.assertEqual(
            audit["release_gates"]["matching_critical_fields"],
            {
                "WBS": {
                    "target": ">= 90%",
                    "minimum_count": 68,
                    "denominator": 75,
                },
                "district": {
                    "target": ">= 90%",
                    "minimum_count": 27,
                    "denominator": 30,
                },
                "Kaltmiete": {
                    "target": ">= 90%",
                    "minimum_count": 54,
                    "denominator": 60,
                },
                "rooms": {
                    "target": ">= 90%",
                    "minimum_count": 45,
                    "denominator": 50,
                },
            },
        )

    def test_audit_output_contains_no_case_level_content(self) -> None:
        audit = audit_locked_holdout_readiness(
            self.dataset_dir,
            comparison_input_paths=[],
        )

        forbidden = {
            "case_id",
            "raw_text",
            "parser_snapshot",
            "expected_value",
            "corrupted_value",
        }
        self.assertTrue(forbidden.isdisjoint(_all_keys(audit)))

    def test_exact_input_overlap_fails_closed(self) -> None:
        holdout_path = (
            self.dataset_dir
            / ARTIFACT_FILENAMES["locked_holdout_model_inputs"]
        )
        first_row = holdout_path.read_text(encoding="utf-8").splitlines()[0]
        overlap_path = (
            Path(self._temporary_directory.name)
            / "comparison_model_inputs.jsonl"
        )
        overlap_path.write_text(first_row + "\n", encoding="utf-8")

        with self.assertRaisesRegex(
            HoldoutReadinessError,
            "zero_overlap_with_prior_inputs",
        ):
            audit_locked_holdout_readiness(
                self.dataset_dir,
                comparison_input_paths=[overlap_path],
            )

    def test_manifest_hash_mismatch_fails_before_audit(self) -> None:
        holdout_path = (
            self.dataset_dir
            / ARTIFACT_FILENAMES["locked_holdout_model_inputs"]
        )
        rows = holdout_path.read_text(encoding="utf-8").splitlines()
        first = json.loads(rows[0])
        first["raw_text"] = str(first["raw_text"]) + " "
        rows[0] = json.dumps(first, ensure_ascii=False, sort_keys=True)
        holdout_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "case_id does not match"):
            audit_locked_holdout_readiness(
                self.dataset_dir,
                comparison_input_paths=[],
            )


if __name__ == "__main__":
    unittest.main()
