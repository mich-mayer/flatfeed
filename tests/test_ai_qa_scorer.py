from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from eval.ai_qa_reports import REPORT_FILENAMES, write_report_bundle
from eval.ai_qa_scorer import (
    ERROR_FIELDS,
    load_jsonl,
    score_predictions,
    wilson_95_interval,
)


def _clean(case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "case_type": "clean",
        "corrupted_field": None,
        "expected_value": None,
        "corrupted_value": None,
        "corruption_type": None,
    }


def _corrupted(
    case_id: str,
    corrupted_field: str,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "case_type": "corrupted",
        "corrupted_field": corrupted_field,
        "expected_value": f"expected-{case_id}",
        "corrupted_value": f"corrupted-{case_id}",
        "corruption_type": "controlled_test_corruption",
    }


def _completed(
    case_id: str,
    *,
    has_error: bool,
    error_field: str | None,
    **telemetry: object,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "status": "completed",
        "raw_output": json.dumps(
            {
                "has_error": has_error,
                "error_field": error_field,
            },
            separators=(",", ":"),
        ),
        **telemetry,
    }


def _technical(
    case_id: str,
    failure_type: str = "timeout",
    **telemetry: object,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "status": "technical_failure",
        "failure": {"type": failure_type},
        **telemetry,
    }


def _base_truth() -> list[dict[str, object]]:
    return [
        _clean("clean-1"),
        _clean("clean-2"),
        _corrupted("error-wbs", "display_wbs"),
        _corrupted("error-rooms", "rooms"),
    ]


def _base_predictions() -> list[dict[str, object]]:
    return [
        _completed("clean-1", has_error=False, error_field=None),
        _completed("clean-2", has_error=False, error_field=None),
        _completed("error-wbs", has_error=True, error_field="wbs"),
        _completed("error-rooms", has_error=True, error_field="rooms"),
    ]


class AIQAScorerMockTests(unittest.TestCase):
    def test_perfect_result(self) -> None:
        truth = [
            _clean("clean-1"),
            _clean("clean-2"),
            _corrupted("error-wbs", "display_wbs"),
            _corrupted("error-rent-kalt", "rent_kalt"),
            _corrupted("error-rooms", "rooms"),
            _corrupted("error-address", "address"),
            _corrupted("error-district", "district"),
            _corrupted("error-floor", "floor"),
            _corrupted("error-rent-warm", "rent_warm"),
        ]
        predictions = [
            _completed("clean-1", has_error=False, error_field=None),
            _completed("clean-2", has_error=False, error_field=None),
            _completed("error-wbs", has_error=True, error_field="wbs"),
            _completed(
                "error-rent-kalt",
                has_error=True,
                error_field="rent_kalt",
            ),
            _completed("error-rooms", has_error=True, error_field="rooms"),
            _completed(
                "error-address",
                has_error=True,
                error_field="address_postal_code",
            ),
            _completed(
                "error-district",
                has_error=True,
                error_field="district",
            ),
            _completed("error-floor", has_error=True, error_field="floor"),
            _completed(
                "error-rent-warm",
                has_error=True,
                error_field="rent_warm",
            ),
        ]

        report = score_predictions(
            truth,
            predictions,
            split="mock-perfect",
        )

        metrics = report["metrics"]
        for metric_name in (
            "error_recall",
            "challenge_set_precision",
            "field_localization_accuracy",
            "structured_output_coverage",
        ):
            self.assertEqual(metrics[metric_name]["value"], 1.0)
        for metric_name in (
            "missed_error_rate",
            "false_alert_rate",
            "technical_failure_rate",
        ):
            self.assertEqual(metrics[metric_name]["value"], 0.0)
        for field in ERROR_FIELDS:
            self.assertEqual(
                report["per_field_recall"][field]["value"],
                1.0,
            )
        self.assertEqual(
            report["acceptance_gates"]["overall_status"],
            "pass",
        )
        self.assertEqual(report["diagnostics"]["false_positives"], [])
        self.assertEqual(report["diagnostics"]["false_negatives"], [])

    def test_missed_errors(self) -> None:
        predictions = _base_predictions()
        predictions[2] = _completed(
            "error-wbs",
            has_error=False,
            error_field=None,
        )

        report = score_predictions(
            _base_truth(),
            predictions,
            split="mock-miss",
        )

        self.assertEqual(report["metrics"]["error_recall"]["value"], 0.5)
        self.assertEqual(report["metrics"]["missed_error_rate"]["value"], 0.5)
        self.assertEqual(
            report["metrics"]["challenge_set_precision"]["value"],
            1.0,
        )
        self.assertEqual(report["per_field_recall"]["wbs"]["value"], 0.0)
        self.assertEqual(
            report["field_breakdown"]["wbs"]["missed_by_reason"],
            {"model_no_alert": 1},
        )
        self.assertEqual(
            report["diagnostics"]["false_negatives"],
            [
                {
                    "case_id": "error-wbs",
                    "expected_field": "wbs",
                    "reason": "model_no_alert",
                }
            ],
        )

    def test_false_alerts(self) -> None:
        predictions = _base_predictions()
        predictions[0] = _completed(
            "clean-1",
            has_error=True,
            error_field="district",
        )

        report = score_predictions(
            _base_truth(),
            predictions,
            split="mock-false-alert",
        )

        self.assertEqual(report["metrics"]["false_alert_rate"]["value"], 0.5)
        self.assertAlmostEqual(
            report["metrics"]["challenge_set_precision"]["value"],
            2 / 3,
        )
        self.assertEqual(
            report["diagnostics"]["false_positives"],
            [{"case_id": "clean-1", "predicted_field": "district"}],
        )

    def test_wrong_field_localization(self) -> None:
        predictions = _base_predictions()
        predictions[2] = _completed(
            "error-wbs",
            has_error=True,
            error_field="district",
        )

        report = score_predictions(
            _base_truth(),
            predictions,
            split="mock-wrong-field",
        )

        self.assertEqual(report["metrics"]["error_recall"]["value"], 1.0)
        self.assertEqual(
            report["metrics"]["challenge_set_precision"]["value"],
            1.0,
        )
        self.assertEqual(
            report["metrics"]["field_localization_accuracy"]["value"],
            0.5,
        )
        self.assertEqual(report["per_field_recall"]["wbs"]["value"], 0.0)
        self.assertEqual(report["diagnostics"]["false_negatives"], [])
        self.assertEqual(
            report["diagnostics"]["wrong_field_localizations"],
            [
                {
                    "case_id": "error-wbs",
                    "expected_field": "wbs",
                    "predicted_field": "district",
                }
            ],
        )

    def test_invalid_json(self) -> None:
        predictions = _base_predictions()
        predictions[2] = {
            "case_id": "error-wbs",
            "status": "completed",
            "raw_output": "{not-json",
        }

        report = score_predictions(
            _base_truth(),
            predictions,
            split="mock-invalid-json",
        )

        self.assertEqual(
            report["metrics"]["structured_output_coverage"]["value"],
            0.75,
        )
        self.assertEqual(
            report["metrics"]["technical_failure_rate"]["value"],
            0.0,
        )
        self.assertEqual(report["metrics"]["error_recall"]["value"], 0.5)
        self.assertEqual(report["counts"]["outcome_invalid_json"], 1)
        self.assertEqual(
            report["diagnostics"]["false_negatives"][0]["reason"],
            "invalid_json",
        )

    def test_technical_failures(self) -> None:
        predictions = _base_predictions()
        predictions[2] = _technical("error-wbs", "timeout")

        report = score_predictions(
            _base_truth(),
            predictions,
            split="mock-technical-failure",
        )

        self.assertEqual(
            report["metrics"]["structured_output_coverage"]["value"],
            0.75,
        )
        self.assertEqual(
            report["metrics"]["technical_failure_rate"]["value"],
            0.25,
        )
        self.assertEqual(report["metrics"]["error_recall"]["value"], 0.5)
        self.assertEqual(
            report["diagnostics"]["technical_failure_categories"],
            {"timeout": 1},
        )
        self.assertEqual(
            report["diagnostics"]["false_negatives"][0]["reason"],
            "technical_failure",
        )


class AIQAScorerContractTests(unittest.TestCase):
    def test_address_and_postal_code_share_one_logical_field(self) -> None:
        truth = [
            _corrupted("error-address", "address"),
            _corrupted("error-postal", "postal_code"),
        ]
        predictions = [
            _completed(
                "error-address",
                has_error=True,
                error_field="address_postal_code",
            ),
            _completed(
                "error-postal",
                has_error=True,
                error_field="address_postal_code",
            ),
        ]

        report = score_predictions(truth, predictions, split="mock-address")

        field = report["field_breakdown"]["address_postal_code"]
        self.assertEqual(field["total_corrupted"], 2)
        self.assertEqual(field["correctly_localized"], 2)
        self.assertEqual(field["localized_recall"]["value"], 1.0)

    def test_zero_denominators_are_not_reported_as_zero(self) -> None:
        report = score_predictions(
            [_clean("clean-1")],
            [_completed("clean-1", has_error=False, error_field=None)],
            split="mock-zero-denominator",
        )

        self.assertIsNone(report["metrics"]["error_recall"]["value"])
        self.assertIsNone(
            report["metrics"]["challenge_set_precision"]["value"]
        )
        self.assertIsNone(
            report["metrics"]["field_localization_accuracy"]["value"]
        )
        self.assertIsNone(report["per_field_recall"]["wbs"]["value"])
        self.assertEqual(
            report["metrics"]["error_recall"]["wilson_95_ci"],
            {"low": None, "high": None},
        )

    def test_wilson_95_interval_known_values(self) -> None:
        interval = wilson_95_interval(1, 1)
        self.assertAlmostEqual(interval["low"], 0.2065493143772374)
        self.assertEqual(interval["high"], 1.0)
        interval = wilson_95_interval(2, 3)
        self.assertAlmostEqual(interval["low"], 0.2076596008020477)
        self.assertAlmostEqual(interval["high"], 0.9385080552796037)
        self.assertEqual(
            wilson_95_interval(0, 0),
            {"low": None, "high": None},
        )

    def test_incomplete_duplicate_and_unknown_predictions_are_rejected(
        self,
    ) -> None:
        truth = [_clean("clean-1"), _clean("clean-2")]
        with self.assertRaisesRegex(ValueError, "incomplete"):
            score_predictions(
                truth,
                [_completed("clean-1", has_error=False, error_field=None)],
                split="mock-incomplete",
            )
        with self.assertRaisesRegex(ValueError, "duplicate prediction"):
            score_predictions(
                [_clean("clean-1")],
                [
                    _completed(
                        "clean-1",
                        has_error=False,
                        error_field=None,
                    ),
                    _completed(
                        "clean-1",
                        has_error=False,
                        error_field=None,
                    ),
                ],
                split="mock-duplicate",
            )
        with self.assertRaisesRegex(ValueError, "unknown case_id"):
            score_predictions(
                [_clean("clean-1")],
                [
                    _completed(
                        "unknown",
                        has_error=False,
                        error_field=None,
                    )
                ],
                split="mock-unknown",
            )

    def test_duplicate_truth_and_empty_truth_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate truth"):
            score_predictions(
                [_clean("clean-1"), _clean("clean-1")],
                _base_predictions(),
                split="mock-duplicate-truth",
            )
        with self.assertRaisesRegex(ValueError, "at least one"):
            score_predictions([], [], split="mock-empty")

    def test_invalid_model_schema_is_uncovered_not_technical(self) -> None:
        invalid_outputs = (
            "{}",
            '{"has_error":true,"error_field":null}',
            '{"has_error":false,"error_field":"wbs"}',
            '{"has_error":true,"error_field":"unsupported"}',
            '{"has_error":false,"error_field":null,"extra":1}',
        )
        for index, raw_output in enumerate(invalid_outputs):
            with self.subTest(index=index):
                report = score_predictions(
                    [_corrupted("error-wbs", "display_wbs")],
                    [
                        {
                            "case_id": "error-wbs",
                            "status": "completed",
                            "raw_output": raw_output,
                        }
                    ],
                    split="mock-invalid-schema",
                )
                self.assertEqual(
                    report["metrics"]["structured_output_coverage"]["value"],
                    0.0,
                )
                self.assertEqual(
                    report["metrics"]["technical_failure_rate"]["value"],
                    0.0,
                )
                self.assertEqual(
                    report["counts"]["outcome_invalid_schema"],
                    1,
                )

    def test_outer_jsonl_corruption_is_an_artifact_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.jsonl"
            path.write_text("{not-envelope-json\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "envelope JSON"):
                load_jsonl(path)

    def test_telemetry_requires_complete_safe_schemas(self) -> None:
        with self.assertRaisesRegex(ValueError, "usage schema"):
            score_predictions(
                [_clean("clean-1")],
                [
                    _completed(
                        "clean-1",
                        has_error=False,
                        error_field=None,
                        usage={"input_tokens": 10},
                    )
                ],
                split="mock-usage-schema",
            )
        with self.assertRaisesRegex(ValueError, "safe category"):
            score_predictions(
                [_clean("clean-1")],
                [
                    {
                        "case_id": "clean-1",
                        "status": "technical_failure",
                        "failure": {
                            "type": "timeout",
                            "message": "arbitrary text is not persisted",
                        },
                    }
                ],
                split="mock-failure-schema",
            )
        for value in (-1, math.inf, math.nan):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "cost_usd"):
                    score_predictions(
                        [_clean("clean-1")],
                        [
                            _completed(
                                "clean-1",
                                has_error=False,
                                error_field=None,
                                cost_usd=value,
                            )
                        ],
                        split="mock-invalid-cost",
                    )


class AIQAOperationalAndReportTests(unittest.TestCase):
    def test_usage_cost_retries_and_latency_are_aggregated(self) -> None:
        truth = _base_truth()
        predictions = _base_predictions()
        telemetry = (
            (100, 10, 5, 0, 0, 0.001, 100),
            (200, 20, 10, 2, 1, 0.002, 200),
            (300, 30, 15, 4, 0, 0.003, 300),
            (400, 40, 20, 6, 2, 0.004, 400),
        )
        for row, values in zip(predictions, telemetry):
            input_tokens, cached, output, reasoning, retries, cost, latency = (
                values
            )
            row.update(
                {
                    "usage": {
                        "input_tokens": input_tokens,
                        "cached_input_tokens": cached,
                        "output_tokens": output,
                        "reasoning_tokens": reasoning,
                    },
                    "retry_count": retries,
                    "cost_usd": cost,
                    "latency_ms": latency,
                    "latency_mode": "synchronous",
                }
            )

        report = score_predictions(
            truth,
            predictions,
            split="mock-operational",
        )
        operational = report["operational"]

        self.assertEqual(operational["case_result_records"], 4)
        self.assertEqual(operational["completed_cases"], 4)
        self.assertEqual(operational["request_count"], 7)
        self.assertEqual(operational["retry_count"], 3)
        self.assertEqual(
            operational["token_usage"],
            {
                "input_tokens": 1000,
                "cached_input_tokens": 100,
                "output_tokens": 50,
                "reasoning_tokens": 12,
                "total_tokens": 1050,
                "records_with_usage": 4,
                "total_case_records": 4,
                "is_partial": False,
            },
        )
        self.assertAlmostEqual(operational["cost"]["total_usd"], 0.01)
        self.assertAlmostEqual(
            operational["cost"]["cost_per_completed_case_usd"],
            0.0025,
        )
        latency = operational["latency_by_mode"]["synchronous"]
        self.assertEqual(latency["p50_ms"], 250.0)
        self.assertEqual(latency["p95_ms"], 385.0)

    def test_partial_operational_data_is_explicit(self) -> None:
        truth = [_clean("clean-1"), _clean("clean-2")]
        predictions = [
            _completed(
                "clean-1",
                has_error=False,
                error_field=None,
                usage={
                    "input_tokens": 10,
                    "cached_input_tokens": 1,
                    "output_tokens": 2,
                    "reasoning_tokens": 1,
                },
                cost_usd=0.001,
                latency_ms=100,
                latency_mode="synchronous",
            ),
            _completed("clean-2", has_error=False, error_field=None),
        ]

        report = score_predictions(
            truth,
            predictions,
            split="mock-partial-telemetry",
        )
        operational = report["operational"]

        self.assertTrue(operational["token_usage"]["is_partial"])
        self.assertTrue(operational["cost"]["is_partial"])
        self.assertIsNone(
            operational["cost"]["cost_per_completed_case_usd"]
        )
        self.assertTrue(
            operational["latency_by_mode"]["synchronous"]["is_partial"]
        )

    def test_report_bundle_contains_requested_artifacts_without_truth_values(
        self,
    ) -> None:
        predictions = _base_predictions()
        predictions[0] = _completed(
            "clean-1",
            has_error=True,
            error_field="district",
        )
        predictions[2] = _completed(
            "error-wbs",
            has_error=False,
            error_field=None,
        )
        report = score_predictions(
            _base_truth(),
            predictions,
            split="mock-report",
            run_label="unit-test",
        )

        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            paths = write_report_bundle(report, output_dir)

            self.assertEqual(set(paths), set(REPORT_FILENAMES))
            self.assertTrue(all(path.is_file() for path in paths.values()))
            machine_report = json.loads(
                paths["json_report"].read_text(encoding="utf-8")
            )
            self.assertEqual(machine_report["split"], "mock-report")
            markdown = paths["markdown_report"].read_text(encoding="utf-8")
            self.assertIn("Synthetic offline AI QA evaluation", markdown)
            self.assertIn("not production precision", markdown)
            self.assertIn("does not integrate OpenAI", markdown)
            false_positives = paths["false_positives"].read_text(
                encoding="utf-8"
            )
            false_negatives = paths["false_negatives"].read_text(
                encoding="utf-8"
            )
            self.assertIn('"case_id":"clean-1"', false_positives)
            self.assertIn('"case_id":"error-wbs"', false_negatives)
            serialized_bundle = (
                markdown
                + false_positives
                + false_negatives
                + paths["field_breakdown"].read_text(encoding="utf-8")
            )
            self.assertNotIn("expected-error-wbs", serialized_bundle)
            self.assertNotIn("corrupted-error-wbs", serialized_bundle)


if __name__ == "__main__":
    unittest.main()
