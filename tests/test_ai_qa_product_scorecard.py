from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from eval.ai_qa_product_scorecard import (
    FIELD_ORDER,
    MATCHING_CRITICAL_FIELDS,
    ProductScorecardError,
    build_product_scorecard,
    build_product_scorecard_from_files,
    write_product_scorecard,
)
from eval.ai_qa_scorer import score_predictions


def _truth(
    *,
    clean: int,
    field_counts: dict[str, int],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(clean):
        rows.append(
            {
                "case_id": f"clean-{index:03d}",
                "case_type": "clean",
                "corrupted_field": None,
                "expected_value": None,
                "corrupted_value": None,
                "corruption_type": None,
            }
        )
    truth_field = {
        "wbs": "display_wbs",
        "district": "district",
        "rent_kalt": "rent_kalt",
        "rooms": "rooms",
        "address_postal_code": "address",
        "floor": "floor",
        "rent_warm": "rent_warm",
    }
    for field, count in field_counts.items():
        for index in range(count):
            rows.append(
                {
                    "case_id": f"error-{field}-{index:03d}",
                    "case_type": "corrupted",
                    "corrupted_field": truth_field[field],
                    "expected_value": f"expected-{field}-{index}",
                    "corrupted_value": f"wrong-{field}-{index}",
                    "corruption_type": "test_corruption",
                }
            )
    return rows


def _prediction(
    case_id: str,
    *,
    has_error: bool,
    error_field: str | None,
    valid: bool = True,
) -> dict[str, object]:
    if not valid:
        return {
            "case_id": case_id,
            "status": "completed",
            "raw_output": "{invalid",
        }
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
    }


def _run_manifest(
    *,
    split: str,
    case_count: int,
    reasoning_effort: str = "medium",
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "runner_version": "1.5",
        "status": "completed",
        "experiment": "synthetic offline AI QA evaluation",
        "split": split,
        "case_count": case_count,
        "configuration": {
            "model": "gpt-5.6-terra",
            "reasoning_effort": reasoning_effort,
            "prompt_version": "terra-v1",
            "max_output_tokens": 256,
            "retries": 0,
            "strict_structured_outputs": True,
        },
        "input": {"sha256": "validation-input-hash"},
        "budget": {"hard_limit_usd": 5.0},
    }


def _freeze(
    *,
    split: str = "terra_validation",
    reasoning_effort: str = "medium",
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "status": "validation_authorized_once",
        "locked_holdout_authorized": False,
        "configuration": {
            "model": "gpt-5.6-terra",
            "reasoning_effort": reasoning_effort,
            "prompt_version": "terra-v1",
            "max_output_tokens": 256,
            "retries": 0,
            "runner_version": "1.5",
            "strict_structured_outputs": True,
        },
        "validation": {
            "split": split,
            "case_count": 280,
            "model_inputs_sha256": "validation-input-hash",
            "hard_budget_limit_usd": 5.0,
        },
    }


def _threshold_report(
    *,
    detected: int = 133,
    correct_field: int = 126,
    false_alerts: int = 4,
    covered: int = 279,
    split: str = "terra_validation",
) -> dict[str, object]:
    field_counts = {
        "wbs": 56,
        "district": 10,
        "rent_kalt": 21,
        "rooms": 21,
        "address_postal_code": 14,
        "floor": 10,
        "rent_warm": 8,
    }
    truth = _truth(clean=140, field_counts=field_counts)
    predictions: list[dict[str, object]] = []
    corrupted_seen = 0
    correct_seen = 0
    covered_seen = 0
    for row in truth:
        case_id = str(row["case_id"])
        if row["case_type"] == "clean":
            index = int(case_id.rsplit("-", 1)[1])
            prediction = _prediction(
                case_id,
                has_error=index < false_alerts,
                error_field="wbs" if index < false_alerts else None,
            )
        else:
            expected_field = case_id.removeprefix("error-").rsplit("-", 1)[0]
            is_detected = corrupted_seen < detected
            is_correct = is_detected and correct_seen < correct_field
            wrong_field = "wbs" if expected_field != "wbs" else "floor"
            prediction = _prediction(
                case_id,
                has_error=is_detected,
                error_field=(
                    expected_field
                    if is_correct
                    else (wrong_field if is_detected else None)
                ),
            )
            corrupted_seen += 1
            if is_correct:
                correct_seen += 1
        if covered_seen >= covered:
            prediction = _prediction(
                case_id,
                has_error=False,
                error_field=None,
                valid=False,
            )
        else:
            covered_seen += 1
        predictions.append(prediction)
    return score_predictions(
        truth,
        predictions,
        split=split,
        run_label="threshold-test",
    )


class ProductScorecardMetricTests(unittest.TestCase):
    def test_simple_metric_thresholds_use_absolute_validation_counts(self) -> None:
        report = _threshold_report()
        scorecard = build_product_scorecard(
            report,
            run_manifest=_run_manifest(
                split="terra_validation",
                case_count=280,
            ),
            freeze=_freeze(),
        )

        metrics = scorecard["metrics"]
        self.assertEqual(
            metrics["parser_error_detection_rate"]["result"]["numerator"],
            133,
        )
        self.assertEqual(
            metrics["parser_error_detection_rate"]["gate"]["status"],
            "pass",
        )
        self.assertEqual(
            metrics["false_alert_rate"]["result"]["numerator"],
            4,
        )
        self.assertEqual(
            metrics["false_alert_rate"]["gate"]["status"],
            "pass",
        )
        self.assertEqual(
            metrics["correct_field_detection_rate"]["result"]["numerator"],
            126,
        )
        self.assertEqual(
            metrics["correct_field_detection_rate"]["result"]["denominator"],
            140,
        )
        self.assertEqual(
            metrics["correct_field_detection_rate"]["gate"]["status"],
            "pass",
        )
        self.assertEqual(
            metrics["successful_check_rate"]["result"]["numerator"],
            279,
        )
        self.assertEqual(
            metrics["successful_check_rate"]["gate"]["status"],
            "pass",
        )

    def test_one_case_beyond_each_threshold_fails(self) -> None:
        scenarios = (
            ("detected", {"detected": 132}, "parser_error_detection_rate"),
            ("false_alerts", {"false_alerts": 5}, "false_alert_rate"),
            ("correct_field", {"correct_field": 125}, "correct_field_detection_rate"),
            ("covered", {"covered": 278}, "successful_check_rate"),
        )
        for label, overrides, metric_name in scenarios:
            with self.subTest(label=label):
                report = _threshold_report(**overrides)
                scorecard = build_product_scorecard(
                    report,
                    run_manifest=_run_manifest(
                        split="terra_validation",
                        case_count=280,
                    ),
                    freeze=_freeze(),
                )
                self.assertEqual(
                    scorecard["metrics"][metric_name]["gate"]["status"],
                    "fail",
                )

    def test_correct_field_rate_is_not_conditional_on_detected_cases(self) -> None:
        report = _threshold_report(detected=133, correct_field=126)
        scorecard = build_product_scorecard(
            report,
            run_manifest=_run_manifest(
                split="terra_validation",
                case_count=280,
            ),
            freeze=_freeze(),
        )

        self.assertAlmostEqual(
            report["metrics"]["field_localization_accuracy"]["value"],
            126 / 133,
        )
        self.assertAlmostEqual(
            scorecard["metrics"]["correct_field_detection_rate"]["result"]["value"],
            126 / 140,
        )

    def test_all_fields_are_reported_and_district_is_matching_critical(self) -> None:
        report = _threshold_report()
        scorecard = build_product_scorecard(
            report,
            run_manifest=_run_manifest(
                split="terra_validation",
                case_count=280,
            ),
            freeze=_freeze(),
        )

        self.assertEqual(tuple(scorecard["fields"]), FIELD_ORDER)
        self.assertEqual(
            tuple(
                field
                for field, result in scorecard["fields"].items()
                if result["matching_critical"]
            ),
            MATCHING_CRITICAL_FIELDS,
        )
        self.assertIsNotNone(scorecard["fields"]["district"]["guardrail"])
        self.assertIsNone(
            scorecard["fields"]["address_postal_code"]["guardrail"]
        )


class ProductScorecardBoundaryTests(unittest.TestCase):
    def test_calibration_is_explicitly_not_public(self) -> None:
        report = _threshold_report(split="terra_calibration")
        scorecard = build_product_scorecard(
            report,
            run_manifest=_run_manifest(
                split="terra_calibration",
                case_count=280,
            ),
        )

        self.assertEqual(
            scorecard["evidence_label"],
            "Synthetic calibration preview",
        )
        self.assertEqual(
            scorecard["publication_state"],
            "not_public_calibration_preview",
        )
        self.assertFalse(
            scorecard["decision"]["positive_landing_claim_allowed"]
        )

    def test_validation_requires_the_exact_freeze(self) -> None:
        report = _threshold_report()
        manifest = _run_manifest(split="terra_validation", case_count=280)
        with self.assertRaisesRegex(
            ProductScorecardError,
            "requires the configuration freeze",
        ):
            build_product_scorecard(report, run_manifest=manifest)

        changed = _freeze()
        changed["configuration"]["reasoning_effort"] = "low"
        with self.assertRaisesRegex(
            ProductScorecardError,
            "differs from freeze",
        ):
            build_product_scorecard(
                report,
                run_manifest=manifest,
                freeze=changed,
            )

    def test_validation_reads_runner_version_from_manifest_top_level(self) -> None:
        report = _threshold_report()
        manifest = _run_manifest(split="terra_validation", case_count=280)
        freeze = _freeze()

        scorecard = build_product_scorecard(
            report,
            run_manifest=manifest,
            freeze=freeze,
        )
        self.assertEqual(scorecard["source"]["split"], "terra_validation")

        changed_manifest = copy.deepcopy(manifest)
        changed_manifest["runner_version"] = "1.4"
        with self.assertRaisesRegex(
            ProductScorecardError,
            "runner_version",
        ):
            build_product_scorecard(
                report,
                run_manifest=changed_manifest,
                freeze=freeze,
            )

    def test_high_reasoning_validation_uses_its_exact_freeze(self) -> None:
        report = _threshold_report(split="terra_high_validation")
        manifest = _run_manifest(
            split="terra_high_validation",
            case_count=280,
            reasoning_effort="high",
        )
        freeze = _freeze(
            split="terra_high_validation",
            reasoning_effort="high",
        )
        freeze["boundaries"] = {
            "locked_holdout_authorized": False,
            "validation_authorized_once": True,
        }
        del freeze["locked_holdout_authorized"]

        scorecard = build_product_scorecard(
            report,
            run_manifest=manifest,
            freeze=freeze,
        )

        self.assertEqual(
            scorecard["evidence_label"],
            "Synthetic frozen validation",
        )
        self.assertEqual(scorecard["configuration"]["reasoning_effort"], "high")

    def test_output_is_aggregate_only_and_byte_reproducible(self) -> None:
        report = _threshold_report(split="terra_calibration")
        scorecard = build_product_scorecard(
            report,
            run_manifest=_run_manifest(
                split="terra_calibration",
                case_count=280,
            ),
        )
        serialized = json.dumps(scorecard, sort_keys=True)
        for prohibited in (
            "case_id",
            "raw_text",
            "parser_snapshot",
            "expected_value",
            "corrupted_value",
        ):
            self.assertNotIn(prohibited, serialized)

        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_paths = write_product_scorecard(scorecard, Path(first))
            second_paths = write_product_scorecard(scorecard, Path(second))
            self.assertEqual(
                {
                    key: path.read_bytes()
                    for key, path in first_paths.items()
                },
                {
                    key: path.read_bytes()
                    for key, path in second_paths.items()
                },
            )

    def test_writer_refuses_to_overwrite_existing_artifacts(self) -> None:
        report = _threshold_report(split="terra_calibration")
        scorecard = build_product_scorecard(
            report,
            run_manifest=_run_manifest(
                split="terra_calibration",
                case_count=280,
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            write_product_scorecard(scorecard, output_dir)
            with self.assertRaisesRegex(ProductScorecardError, "overwrite"):
                write_product_scorecard(scorecard, output_dir)

    def test_file_builder_records_source_hashes_without_credentials(self) -> None:
        report = _threshold_report(split="terra_calibration")
        manifest = _run_manifest(
            split="terra_calibration",
            case_count=280,
        )
        manifest["credential"] = {
            "source": ".env.eval.local",
            "value_persisted": False,
            "variable": "OPENAI_API_KEY",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "report.json"
            manifest_path = root / "run_manifest.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            scorecard = build_product_scorecard_from_files(
                report_path=report_path,
                run_manifest_path=manifest_path,
            )

        self.assertIsNotNone(scorecard["source"]["report_sha256"])
        self.assertIsNotNone(scorecard["source"]["run_manifest_sha256"])
        serialized = json.dumps(scorecard)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn(".env.eval.local", serialized)

    def test_inconsistent_report_counts_are_rejected(self) -> None:
        report = _threshold_report(split="terra_calibration")
        changed = copy.deepcopy(report)
        changed["counts"]["clean_cases"] = 139
        with self.assertRaisesRegex(ProductScorecardError, "do not sum"):
            build_product_scorecard(
                changed,
                run_manifest=_run_manifest(
                    split="terra_calibration",
                    case_count=280,
                ),
            )


if __name__ == "__main__":
    unittest.main()
