from __future__ import annotations

import json
import unittest

from eval.ai_qa_review_scorer import score_review_predictions


def _input(case_id: str, *, raw_text: str, **snapshot: object) -> dict[str, object]:
    base_snapshot = {
        "display_wbs": "100, 140",
        "rooms": 2.0,
        "floor": "2",
        "address": "Teststraße 10",
        "postal_code": "12043",
        "district": "Neukölln",
        "rent_kalt": "600,00 EUR",
        "rent_warm": "800,00 EUR",
    }
    base_snapshot.update(snapshot)
    return {
        "case_id": case_id,
        "raw_text": raw_text,
        "parser_snapshot": base_snapshot,
    }


def _truth(
    case_id: str,
    *,
    corrupted_field: str | None = None,
    expected_value: object | None = None,
    corrupted_value: object | None = None,
    corruption_type: str | None = None,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "case_type": "corrupted" if corrupted_field else "clean",
        "corrupted_field": corrupted_field,
        "expected_value": expected_value,
        "corrupted_value": corrupted_value,
        "corruption_type": corruption_type,
    }


def _prediction(case_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "case_id": case_id,
        "status": "completed",
        "raw_output": json.dumps(payload, ensure_ascii=False),
    }


INPUTS = [
    _input("clean", raw_text="2 Zimmer\n12043 Berlin"),
    _input("rooms", raw_text="3 Zimmer\n12043 Berlin", rooms=2.0),
    _input(
        "postal",
        raw_text="2 Zimmer\n13585 Berlin",
        postal_code="12043",
    ),
]
TRUTH = [
    _truth("clean"),
    _truth(
        "rooms",
        corrupted_field="rooms",
        expected_value=3.0,
        corrupted_value=2.0,
        corruption_type="rooms_neighbor_value",
    ),
    _truth(
        "postal",
        corrupted_field="postal_code",
        expected_value="13585",
        corrupted_value="12043",
        corruption_type="postal_code_substitution",
    ),
]


class AIQAReviewScorerTests(unittest.TestCase):
    def test_baseline_and_candidate_share_the_same_core_metrics(self) -> None:
        baseline = [
            _prediction(
                "clean",
                {"has_error": False, "error_field": None},
            ),
            _prediction(
                "rooms",
                {"has_error": True, "error_field": "rooms"},
            ),
            _prediction(
                "postal",
                {
                    "has_error": True,
                    "error_field": "address_postal_code",
                },
            ),
        ]
        candidate = [
            _prediction(
                "clean",
                {
                    "review_required": False,
                    "review_reason": None,
                    "error_field": None,
                    "source_value": None,
                    "snapshot_value": None,
                    "evidence_quote": None,
                },
            ),
            _prediction(
                "rooms",
                {
                    "review_required": True,
                    "review_reason": "direct_mismatch",
                    "error_field": "rooms",
                    "source_value": "3",
                    "snapshot_value": "2",
                    "evidence_quote": "3 Zimmer",
                },
            ),
            _prediction(
                "postal",
                {
                    "review_required": True,
                    "review_reason": "direct_mismatch",
                    "error_field": "address_postal_code",
                    "source_value": "13585",
                    "snapshot_value": "12043",
                    "evidence_quote": "13585 Berlin",
                },
            ),
        ]

        baseline_report = score_review_predictions(
            profile="baseline",
            input_rows=INPUTS,
            truth_rows=TRUTH,
            prediction_rows=baseline,
        )
        candidate_report = score_review_predictions(
            profile="candidate",
            input_rows=INPUTS,
            truth_rows=TRUTH,
            prediction_rows=candidate,
        )

        for metric in (
            "successful_check_rate",
            "parser_error_detection_rate",
            "false_alert_rate",
            "correct_field_detection_rate",
            "case_accuracy",
        ):
            self.assertEqual(
                baseline_report["metrics"][metric],
                candidate_report["metrics"][metric],
            )
        self.assertEqual(
            candidate_report["review_reasons"],
            {"direct_mismatch": 2},
        )

    def test_unclear_source_is_an_admin_alert(self) -> None:
        predictions = [
            _prediction(
                "clean",
                {
                    "review_required": True,
                    "review_reason": "unclear_source",
                    "error_field": "rooms",
                    "source_value": "2",
                    "snapshot_value": "2",
                    "evidence_quote": "2 Zimmer",
                },
            ),
            _prediction(
                "rooms",
                {
                    "review_required": True,
                    "review_reason": "unclear_source",
                    "error_field": "rooms",
                    "source_value": None,
                    "snapshot_value": "2",
                    "evidence_quote": "3 Zimmer",
                },
            ),
            _prediction(
                "postal",
                {
                    "review_required": True,
                    "review_reason": "direct_mismatch",
                    "error_field": "address_postal_code",
                    "source_value": "13585",
                    "snapshot_value": "12043",
                    "evidence_quote": "13585 Berlin",
                },
            ),
        ]

        report = score_review_predictions(
            profile="candidate",
            input_rows=INPUTS,
            truth_rows=TRUTH,
            prediction_rows=predictions,
        )

        self.assertEqual(
            report["metrics"]["parser_error_detection_rate"]["numerator"],
            2,
        )
        self.assertEqual(
            report["metrics"]["false_alert_rate"]["numerator"],
            1,
        )
        self.assertEqual(
            report["review_reasons"],
            {"direct_mismatch": 1, "unclear_source": 2},
        )

    def test_invalid_evidence_reduces_coverage_and_counts_as_a_miss(self) -> None:
        predictions = [
            _prediction(
                "clean",
                {
                    "review_required": False,
                    "review_reason": None,
                    "error_field": None,
                    "source_value": None,
                    "snapshot_value": None,
                    "evidence_quote": None,
                },
            ),
            _prediction(
                "rooms",
                {
                    "review_required": True,
                    "review_reason": "direct_mismatch",
                    "error_field": "rooms",
                    "source_value": "3",
                    "snapshot_value": "2",
                    "evidence_quote": "invented quote",
                },
            ),
            _prediction(
                "postal",
                {
                    "review_required": True,
                    "review_reason": "direct_mismatch",
                    "error_field": "address_postal_code",
                    "source_value": "13585",
                    "snapshot_value": "12043",
                    "evidence_quote": "13585 Berlin",
                },
            ),
        ]

        report = score_review_predictions(
            profile="candidate",
            input_rows=INPUTS,
            truth_rows=TRUTH,
            prediction_rows=predictions,
        )

        self.assertEqual(
            report["metrics"]["successful_check_rate"]["numerator"],
            2,
        )
        self.assertEqual(
            report["metrics"]["parser_error_detection_rate"]["numerator"],
            1,
        )
        self.assertEqual(len(report["diagnostics"]["false_negatives"]), 1)
        self.assertIn(
            "evidence_quote is not present",
            next(iter(report["failure_types"])),
        )

    def test_wrong_field_is_detected_but_not_correctly_localized(self) -> None:
        predictions = [
            _prediction(
                "clean",
                {"has_error": False, "error_field": None},
            ),
            _prediction(
                "rooms",
                {"has_error": True, "error_field": "floor"},
            ),
            _prediction(
                "postal",
                {
                    "has_error": True,
                    "error_field": "address_postal_code",
                },
            ),
        ]

        report = score_review_predictions(
            profile="baseline",
            input_rows=INPUTS,
            truth_rows=TRUTH,
            prediction_rows=predictions,
        )

        self.assertEqual(
            report["metrics"]["parser_error_detection_rate"]["numerator"],
            2,
        )
        self.assertEqual(
            report["metrics"]["correct_field_detection_rate"]["numerator"],
            1,
        )
        self.assertEqual(len(report["diagnostics"]["wrong_fields"]), 1)

    def test_incomplete_predictions_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "incomplete"):
            score_review_predictions(
                profile="baseline",
                input_rows=INPUTS,
                truth_rows=TRUTH,
                prediction_rows=[
                    _prediction(
                        "clean",
                        {"has_error": False, "error_field": None},
                    )
                ],
            )


if __name__ == "__main__":
    unittest.main()
