from __future__ import annotations

import unittest
from collections import Counter
from decimal import Decimal

from eval.ai_qa_extraction_final import (
    COUNTS,
    ERROR_DISTRIBUTION,
    FIELD_MINIMUMS,
    FREEZE_PATH,
    build_configuration_freeze,
    build_final_dataset_rows,
    build_final_gate,
    calculate_cost_usd,
    verify_configuration_freeze,
    verify_final_dataset,
)


class AIQAExtractionFinalTests(unittest.TestCase):
    def test_final_dataset_is_reproducible_and_balanced(self) -> None:
        inputs, truth = build_final_dataset_rows()

        self.assertEqual(len(inputs), 600)
        self.assertEqual(len(truth), 600)
        self.assertEqual(
            sum(row["case_type"] == "clean" for row in truth),
            COUNTS["clean"],
        )
        self.assertEqual(
            sum(row["case_type"] == "corrupted" for row in truth),
            COUNTS["corrupted"],
        )
        self.assertEqual(
            Counter(
                {
                    "display_wbs": "wbs",
                    "address": "address_postal_code",
                    "postal_code": "address_postal_code",
                }.get(
                    str(row["corrupted_field"]),
                    str(row["corrupted_field"]),
                )
                for row in truth
                if row["case_type"] == "corrupted"
            ),
            Counter(ERROR_DISTRIBUTION),
        )

    def test_committed_dataset_and_freeze_match_code(self) -> None:
        manifest = verify_final_dataset()
        freeze = verify_configuration_freeze(FREEZE_PATH)

        self.assertEqual(manifest["counts"]["total"], 600)
        self.assertEqual(freeze, build_configuration_freeze())
        self.assertTrue(
            freeze["dataset"]["zero_overlap_with_prior_inputs"]
        )
        self.assertEqual(freeze["authorization"]["final_runs"], 1)
        self.assertFalse(
            freeze["authorization"]["post_run_tuning_or_rescore"]
        )

    def test_current_pricing_accounts_for_all_input_classes(self) -> None:
        usage = {
            "input_tokens": 100,
            "cached_input_tokens": 20,
            "cache_write_tokens": 30,
            "output_tokens": 10,
        }
        expected = (
            Decimal(50) * Decimal("2.00")
            + Decimal(20) * Decimal("0.20")
            + Decimal(30) * Decimal("2.50")
            + Decimal(10) * Decimal("12.00")
        ) / Decimal(1_000_000)

        self.assertEqual(calculate_cost_usd(usage), expected)

    def test_final_gate_requires_every_strict_field_minimum(self) -> None:
        report = {
            "metrics": {
                "successful_check_rate": {"numerator": 600},
                "parser_error_detection_rate": {"numerator": 300},
                "correct_field_detection_rate": {"numerator": 300},
                "false_alert_rate": {"numerator": 0},
            },
            "per_field": {
                field: {"correct_field": minimum}
                for field, minimum in FIELD_MINIMUMS.items()
            },
        }

        passing = build_final_gate(report)
        self.assertTrue(passing["all_gates_passed"])

        report["per_field"]["rooms"]["correct_field"] -= 1
        failing = build_final_gate(report)
        self.assertFalse(failing["all_gates_passed"])
        self.assertFalse(
            failing["gates"]["rooms_at_least_49_of_50"]
        )


if __name__ == "__main__":
    unittest.main()
