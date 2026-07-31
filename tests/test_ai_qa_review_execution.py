from __future__ import annotations

import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from eval.ai_qa_review_execution import (
    FREEZE_PATH,
    MODEL,
    _request_case,
    build_configuration_freeze,
    calculate_cost_usd,
    execute_frozen_pair,
    load_eval_api_key,
    verify_configuration_freeze,
)


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


class AIQAReviewExecutionTests(unittest.TestCase):
    def test_committed_freeze_matches_current_code_and_data(self) -> None:
        freeze = verify_configuration_freeze(FREEZE_PATH)

        self.assertEqual(freeze, build_configuration_freeze())
        self.assertEqual(
            freeze["status"],
            "paired_development_authorized_once",
        )
        self.assertEqual(
            freeze["authorization"]["total_case_requests"],
            240,
        )
        self.assertFalse(
            freeze["pricing"]["must_refresh_before_execute"],
        )
        self.assertTrue(
            freeze["pricing"]["verified_against_official_docs"],
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
                    "eval.ai_qa_review_execution.EVAL_ENV_PATH",
                    env_path,
                ),
                patch.dict(
                    os.environ,
                    {"OPENAI_API_KEY": "environment-key"},
                ),
            ):
                self.assertEqual(load_eval_api_key(), "local-eval-key")

    def test_cost_uses_cached_discount_without_double_counting(self) -> None:
        usage = {
            "input_tokens": 100,
            "cached_input_tokens": 20,
            "output_tokens": 10,
            "reasoning_tokens": 4,
        }
        expected = (
            Decimal(80) * Decimal("2.50")
            + Decimal(20) * Decimal("0.25")
            + Decimal(10) * Decimal("15.00")
        ) / Decimal(1_000_000)

        self.assertEqual(calculate_cost_usd(usage), expected)

    def test_request_uses_frozen_responses_parameters(self) -> None:
        response = SimpleNamespace(
            status="completed",
            model=MODEL,
            output=[],
            output_text='{"has_error":false,"error_field":null}',
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=10,
                input_tokens_details=SimpleNamespace(cached_tokens=20),
                output_tokens_details=SimpleNamespace(
                    reasoning_tokens=4
                ),
            ),
        )
        client = _FakeClient(response)
        case = {
            "case_id": "case-1",
            "raw_text": "2 Zimmer",
            "parser_snapshot": {
                "display_wbs": "100",
                "rooms": 2,
                "floor": "2",
                "address": "Teststraße 1",
                "postal_code": "12043",
                "district": "Neukölln",
                "rent_kalt": "600 EUR",
                "rent_warm": "800 EUR",
            },
        }

        prediction = _request_case(
            client=client,
            profile_name="baseline",
            case=case,
            monotonic_fn=iter((0.0, 0.1)).__next__,
        )

        self.assertEqual(prediction["status"], "completed")
        self.assertEqual(len(client.responses.requests), 1)
        request = client.responses.requests[0]
        self.assertEqual(request["model"], MODEL)
        self.assertEqual(request["reasoning"], {"effort": "high"})
        self.assertEqual(request["max_output_tokens"], 256)
        self.assertFalse(request["store"])
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertNotIn("case-1", request["input"])

    def test_existing_artifact_blocks_before_credential_read(self) -> None:
        freeze = build_configuration_freeze()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            candidate = root / "candidate"
            baseline.mkdir()
            (baseline / "predictions.jsonl").write_text(
                "existing\n",
                encoding="utf-8",
            )
            with (
                patch(
                    "eval.ai_qa_review_execution.PROFILE_OUTPUT_DIRS",
                    {
                        "baseline": baseline,
                        "candidate": candidate,
                    },
                ),
                patch(
                    "eval.ai_qa_review_execution.COMPARISON_PATH",
                    root / "comparison.json",
                ),
                patch(
                    "eval.ai_qa_review_execution.verify_configuration_freeze",
                    return_value=freeze,
                ),
            ):
                with self.assertRaisesRegex(
                    FileExistsError,
                    "refusing overwrite",
                ):
                    execute_frozen_pair(
                        api_key_loader=lambda: (_ for _ in ()).throw(
                            AssertionError("credential must not be read")
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
