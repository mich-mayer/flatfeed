from __future__ import annotations

import json
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from eval.ai_qa_extraction_execution import (
    FREEZE_PATH,
    MODEL,
    _request_case,
    build_configuration_freeze,
    calculate_cost_usd,
    execute_frozen_run,
    load_eval_api_key,
    rebuild_saved_decisions,
    score_predictions,
    verify_configuration_freeze,
)


RAW_TEXT = """\
Anschrift: Teststraße 10
PLZ: 12043
Bezirk: Neukölln
Zimmer: 2
Etage: 2
Kaltmiete: 600,00 EUR
Warmmiete: 800,00 EUR
WBS 100-140"""

EXTRACTION = {
    "wbs": "WBS 100-140",
    "rent_kalt": "Kaltmiete: 600,00 EUR",
    "rooms": "Zimmer: 2",
    "address": "Anschrift: Teststraße 10",
    "postal_code": "PLZ: 12043",
    "district": "Bezirk: Neukölln",
    "floor": "Etage: 2",
    "rent_warm": "Warmmiete: 800,00 EUR",
}

SNAPSHOT = {
    "display_wbs": "100, 140",
    "rooms": 2.0,
    "floor": "2",
    "address": "Teststraße 10",
    "postal_code": "12043",
    "district": "Neukölln",
    "rent_kalt": "600,00 EUR",
    "rent_warm": "800,00 EUR",
}


class _FakeResponses:
    def __init__(self, response: object) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.requests.append(kwargs)
        return self.response


class _FakeClient:
    def __init__(self, response: object) -> None:
        self.responses = _FakeResponses(response)
        self.models = SimpleNamespace(
            retrieve=lambda model: SimpleNamespace(id=model)
        )


def _input(
    case_id: str,
    *,
    raw_text: str = RAW_TEXT,
    **snapshot: object,
) -> dict[str, object]:
    parser_snapshot = dict(SNAPSHOT)
    parser_snapshot.update(snapshot)
    return {
        "case_id": case_id,
        "raw_text": raw_text,
        "parser_snapshot": parser_snapshot,
    }


def _truth(
    case_id: str,
    *,
    corrupted_field: str | None = None,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "case_type": "corrupted" if corrupted_field else "clean",
        "corrupted_field": corrupted_field,
        "expected_value": None,
        "corrupted_value": None,
        "corruption_type": None,
    }


def _completed(
    case_id: str,
    *issue_fields: str,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "status": "completed",
        "decision": {
            "review_required": bool(issue_fields),
            "issues": [
                {
                    "error_field": field,
                    "review_reason": "direct_mismatch",
                }
                for field in issue_fields
            ],
        },
    }


class AIQAExtractionExecutionTests(unittest.TestCase):
    def test_committed_freeze_matches_current_code_and_data(self) -> None:
        freeze = verify_configuration_freeze(FREEZE_PATH)

        self.assertEqual(freeze, build_configuration_freeze())
        self.assertEqual(freeze["authorization"]["case_requests"], 120)
        self.assertFalse(
            freeze["pricing"]["must_refresh_before_execute"]
        )
        self.assertTrue(
            freeze["pricing"]["verified_against_official_docs"]
        )

    def test_key_is_loaded_only_from_repo_local_eval_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env.eval.local"
            env_path.write_text(
                "OPENAI_API_KEY=local-eval-key\n",
                encoding="utf-8",
            )
            with (
                patch(
                    "eval.ai_qa_extraction_execution.EVAL_ENV_PATH",
                    env_path,
                ),
                patch.dict(
                    os.environ,
                    {"OPENAI_API_KEY": "environment-key"},
                ),
            ):
                self.assertEqual(load_eval_api_key(), "local-eval-key")

    def test_cost_tracks_regular_cached_and_cache_write_tokens(self) -> None:
        usage = {
            "input_tokens": 100,
            "cached_input_tokens": 20,
            "cache_write_tokens": 30,
            "output_tokens": 10,
            "reasoning_tokens": 4,
        }
        expected = (
            Decimal(50) * Decimal("2.50")
            + Decimal(20) * Decimal("0.25")
            + Decimal(30) * Decimal("3.125")
            + Decimal(10) * Decimal("15.00")
        ) / Decimal(1_000_000)

        self.assertEqual(calculate_cost_usd(usage), expected)

    def test_request_uses_frozen_parameters_and_compares_locally(self) -> None:
        response = SimpleNamespace(
            status="completed",
            model=MODEL,
            output=[],
            output_text=json.dumps(EXTRACTION, ensure_ascii=False),
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=10,
                input_tokens_details=SimpleNamespace(
                    cached_tokens=20,
                    cache_write_tokens=30,
                ),
                output_tokens_details=SimpleNamespace(
                    reasoning_tokens=4
                ),
            ),
        )
        client = _FakeClient(response)
        case = _input("case-1")

        prediction = _request_case(
            client=client,
            case=case,
            monotonic_fn=iter((0.0, 0.1)).__next__,
        )

        self.assertEqual(prediction["status"], "completed")
        self.assertFalse(prediction["decision"]["review_required"])
        request = client.responses.requests[0]
        self.assertEqual(request["model"], MODEL)
        self.assertEqual(request["reasoning"], {"effort": "high"})
        self.assertEqual(request["max_output_tokens"], 768)
        self.assertFalse(request["store"])
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertNotIn("case-1", request["input"])
        self.assertNotIn("parser_snapshot", request["input"])

    def test_invented_quote_is_an_unsuccessful_check(self) -> None:
        invalid = dict(EXTRACTION)
        invalid["rooms"] = "Zimmer: 5"
        response = SimpleNamespace(
            status="completed",
            model=MODEL,
            output=[],
            output_text=json.dumps(invalid, ensure_ascii=False),
            usage=None,
        )

        prediction = _request_case(
            client=_FakeClient(response),
            case=_input("case-1"),
            monotonic_fn=iter((0.0, 0.1)).__next__,
        )

        self.assertEqual(prediction["status"], "invalid_output")
        self.assertIn(
            "not present in raw text",
            prediction["failure"]["type"],
        )

    def test_scorer_counts_detection_false_alerts_and_extra_fields(self) -> None:
        inputs = [
            _input("clean"),
            _input("rooms"),
            _input("postal"),
        ]
        truth = [
            _truth("clean"),
            _truth("rooms", corrupted_field="rooms"),
            _truth("postal", corrupted_field="postal_code"),
        ]
        predictions = [
            _completed("clean"),
            _completed("rooms", "rooms"),
            _completed(
                "postal",
                "address_postal_code",
                "district",
            ),
        ]

        report = score_predictions(
            input_rows=inputs,
            truth_rows=truth,
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
        self.assertEqual(
            report["metrics"]["false_alert_rate"]["numerator"],
            0,
        )
        self.assertEqual(len(report["diagnostics"]["wrong_fields"]), 1)

    def test_saved_output_can_be_rescored_without_an_api_call(self) -> None:
        response_row = {
            "case_id": "clean",
            "status": "completed",
            "raw_output": json.dumps(
                {
                    **EXTRACTION,
                    "address": "Anschrift     Teststraße 10",
                    "postal_code": "12043",
                },
                ensure_ascii=False,
            ),
            "decision": {
                "review_required": True,
                "issues": [
                    {
                        "error_field": "address_postal_code",
                        "review_reason": "direct_mismatch",
                    }
                ],
            },
        }
        input_row = _input(
            "clean",
            raw_text=RAW_TEXT.replace(
                "Anschrift: Teststraße 10",
                "Anschrift     Teststraße 10",
            ),
        )

        rebuilt = rebuild_saved_decisions(
            input_rows=[input_row],
            prediction_rows=[response_row],
        )

        self.assertFalse(
            rebuilt[0]["decision"]["review_required"]
        )
        self.assertEqual(rebuilt[0]["decision"]["issues"], [])

    def test_existing_artifact_blocks_before_credential_read(self) -> None:
        freeze = build_configuration_freeze()
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "existing"
            output_dir.mkdir()
            with (
                patch(
                    "eval.ai_qa_extraction_execution.OUTPUT_DIR",
                    output_dir,
                ),
                patch(
                    "eval.ai_qa_extraction_execution.verify_configuration_freeze",
                    return_value=freeze,
                ),
            ):
                with self.assertRaisesRegex(
                    FileExistsError,
                    "refusing overwrite",
                ):
                    execute_frozen_run(
                        api_key_loader=lambda: (_ for _ in ()).throw(
                            AssertionError("credential must not be read")
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
