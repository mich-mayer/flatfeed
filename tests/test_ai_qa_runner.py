from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import openai

from eval.ai_qa_prompt import (
    EVAL_PROMPT_VERSION,
    MODEL_OUTPUT_JSON_SCHEMA,
    RESPONSES_TEXT_FORMAT,
    SYSTEM_INSTRUCTIONS,
    render_case_input,
)
from eval.ai_qa_runner import (
    CACHED_INPUT_PRICE_PER_1M,
    DEFAULT_MODEL,
    EVAL_ROOT,
    INPUT_PRICE_PER_1M,
    OUTPUT_PRICE_PER_1M,
    OfflineRunnerError,
    RunnerConfig,
    build_run_plan,
    calculate_cost_usd,
    dry_run_summary,
    execute_run_plan,
    load_eval_api_key,
    main,
    verify_model_availability,
)
from eval.ai_qa_scorer import ERROR_FIELDS, load_jsonl, score_predictions


class _FakeModels:
    def __init__(self, returned_model: str = DEFAULT_MODEL) -> None:
        self.returned_model = returned_model
        self.calls: list[str] = []

    def retrieve(self, model: str) -> object:
        self.calls.append(model)
        return SimpleNamespace(id=self.returned_model)


class _FakeResponses:
    def __init__(self, results: list[object]) -> None:
        self.results = list(results)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class _FakeClient:
    def __init__(
        self,
        results: list[object],
        *,
        returned_model: str = DEFAULT_MODEL,
    ) -> None:
        self.models = _FakeModels(returned_model)
        self.responses = _FakeResponses(results)


def _response(
    *,
    raw_output: str = '{"has_error":false,"error_field":null}',
    model: str = DEFAULT_MODEL,
    status: str = "completed",
    input_tokens: int = 100,
    cached_tokens: int = 20,
    output_tokens: int = 10,
    reasoning_tokens: int = 0,
    output: list[object] | None = None,
) -> object:
    return SimpleNamespace(
        status=status,
        model=model,
        output_text=raw_output,
        output=output or [],
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            input_tokens_details=SimpleNamespace(
                cached_tokens=cached_tokens,
            ),
            output_tokens=output_tokens,
            output_tokens_details=SimpleNamespace(
                reasoning_tokens=reasoning_tokens,
            ),
        ),
    )


def _monotonic(values: list[float]):
    iterator = iter(values)
    return lambda: next(iterator)


class AIQARunnerPlanTests(unittest.TestCase):
    def test_default_development_dry_run_has_no_network_or_key_read(self) -> None:
        plan = build_run_plan(limit=3)
        summary = dry_run_summary(
            plan,
            budget_limit_usd=plan.worst_case_cost_usd,
            output_dir=EVAL_ROOT / "runs" / "dry-run-test",
        )

        self.assertEqual(plan.split, "development")
        self.assertEqual(plan.case_count, 3)
        self.assertEqual(plan.config.model, DEFAULT_MODEL)
        self.assertEqual(plan.config.reasoning_effort, "none")
        self.assertEqual(summary["network_calls"], 0)
        self.assertFalse(summary["credential_read"])
        self.assertFalse(summary["locked_holdout_enabled"])
        self.assertGreater(summary["preflight_worst_case_cost_usd"], 0)
        self.assertTrue(summary["budget_sufficient"])
        self.assertEqual(len(summary["selected_case_ids"]), 3)
        self.assertEqual(
            summary["request_plan"]["maximum_responses_api_requests"],
            9,
        )
        self.assertEqual(
            summary["request_plan"]["maximum_total_api_calls"],
            10,
        )
        self.assertEqual(
            summary["answer_key_leakage_check"]["status"],
            "passed",
        )
        self.assertEqual(
            summary["prompt"]["system_instructions"],
            SYSTEM_INSTRUCTIONS,
        )
        self.assertEqual(
            summary["structured_output"]["text_format"],
            RESPONSES_TEXT_FORMAT,
        )
        self.assertFalse(
            summary["future_artifacts"]["created_by_dry_run"]
        )
        self.assertEqual(
            summary["future_artifacts"]["paths"]["predictions"],
            "eval/runs/dry-run-test/predictions.jsonl",
        )
        self.assertEqual(
            summary["future_artifacts"]["paths"]["json_report"],
            "eval/runs/dry-run-test/reports/report.json",
        )

    def test_cli_dry_run_does_not_load_key_or_construct_client(self) -> None:
        stdout = io.StringIO()
        argv = ["ai_qa_runner", "--dry-run", "--limit", "1"]
        with (
            patch("sys.argv", argv),
            patch("sys.stdout", stdout),
            patch(
                "eval.ai_qa_runner.load_eval_api_key",
                side_effect=AssertionError("credential must not be read"),
            ),
            patch(
                "eval.ai_qa_runner._new_openai_client",
                side_effect=AssertionError("client must not be created"),
            ),
        ):
            main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode"], "dry_run")
        self.assertEqual(payload["network_calls"], 0)

    def test_locked_holdout_is_disabled_before_freeze(self) -> None:
        with self.assertRaisesRegex(
            OfflineRunnerError,
            "disabled until the configuration-freeze step",
        ):
            build_run_plan(split="locked_holdout", limit=1)

    def test_limit_and_config_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "limit must be positive"):
            build_run_plan(limit=0)
        with self.assertRaisesRegex(ValueError, "limit exceeds"):
            build_run_plan(limit=101)
        with self.assertRaisesRegex(ValueError, "reasoning_effort"):
            build_run_plan(
                limit=1,
                config=RunnerConfig(reasoning_effort="xhigh"),
            )
        with self.assertRaisesRegex(ValueError, "retries"):
            build_run_plan(
                limit=1,
                config=RunnerConfig(retries=-1),
            )

    def test_prompt_contains_only_model_visible_case_data(self) -> None:
        plan = build_run_plan(limit=20)
        for case in plan.cases:
            rendered = render_case_input(case)
            parsed = json.loads(rendered)

            self.assertEqual(
                set(parsed),
                {"raw_listing_text", "parser_snapshot"},
            )
            self.assertNotIn(str(case["case_id"]), rendered)
            for forbidden in (
                "answer_key",
                "case_type",
                "corrupted_field",
                "expected_value",
                "corrupted_value",
                "corruption_type",
                "truth",
                "split",
            ):
                self.assertNotIn(f'"{forbidden}"', rendered)

    def test_strict_output_schema_matches_scorer_categories(self) -> None:
        self.assertEqual(RESPONSES_TEXT_FORMAT["type"], "json_schema")
        self.assertTrue(RESPONSES_TEXT_FORMAT["strict"])
        self.assertFalse(MODEL_OUTPUT_JSON_SCHEMA["additionalProperties"])
        self.assertEqual(
            set(MODEL_OUTPUT_JSON_SCHEMA["required"]),
            {"has_error", "error_field"},
        )
        field_schema = MODEL_OUTPUT_JSON_SCHEMA["properties"][
            "error_field"
        ]
        self.assertEqual(
            tuple(field_schema["anyOf"][0]["enum"]),
            ERROR_FIELDS,
        )
        self.assertIn("no WBS mention", SYSTEM_INSTRUCTIONS)
        self.assertEqual(EVAL_PROMPT_VERSION, "dev-v2")
        self.assertIn("Check all seven fields", SYSTEM_INSTRUCTIONS)
        self.assertIn("exact allowed-tier", SYSTEM_INSTRUCTIONS)
        self.assertIn("room count exactly", SYSTEM_INSTRUCTIONS)


class AIQARunnerCredentialAndBudgetTests(unittest.TestCase):
    def test_key_is_loaded_only_from_eval_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env.eval.local"
            env_path.write_text(
                "OPENAI_API_KEY=file-only-key\n",
                encoding="utf-8",
            )
            with (
                patch("eval.ai_qa_runner.EVAL_ENV_PATH", env_path),
                patch.dict(
                    os.environ,
                    {"OPENAI_API_KEY": "environment-key"},
                ),
            ):
                self.assertEqual(load_eval_api_key(), "file-only-key")

    def test_missing_file_key_does_not_fall_back_to_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env.eval.local"
            env_path.write_text("OPENAI_API_KEY=\n", encoding="utf-8")
            with (
                patch("eval.ai_qa_runner.EVAL_ENV_PATH", env_path),
                patch.dict(
                    os.environ,
                    {"OPENAI_API_KEY": "must-not-be-used"},
                ),
            ):
                with self.assertRaisesRegex(
                    OfflineRunnerError,
                    "missing from .env.eval.local",
                ):
                    load_eval_api_key()

    def test_cost_uses_cached_input_discount_without_double_counting(self) -> None:
        usage = {
            "input_tokens": 100,
            "cached_input_tokens": 20,
            "output_tokens": 10,
            "reasoning_tokens": 4,
        }
        expected = (
            Decimal(80) * INPUT_PRICE_PER_1M
            + Decimal(20) * CACHED_INPUT_PRICE_PER_1M
            + Decimal(10) * OUTPUT_PRICE_PER_1M
        ) / Decimal(1_000_000)

        self.assertEqual(calculate_cost_usd(usage), expected)

    def test_luna_cost_uses_luna_rates(self) -> None:
        usage = {
            "input_tokens": 100,
            "cached_input_tokens": 20,
            "output_tokens": 10,
            "reasoning_tokens": 0,
        }
        expected = (
            Decimal(80) * Decimal("1.00")
            + Decimal(20) * Decimal("0.10")
            + Decimal(10) * Decimal("6.00")
        ) / Decimal(1_000_000)

        self.assertEqual(
            calculate_cost_usd(usage, model="gpt-5.6-luna"),
            expected,
        )

    def test_unknown_model_is_rejected_without_verified_pricing(self) -> None:
        with self.assertRaisesRegex(ValueError, "no verified pricing"):
            build_run_plan(
                limit=1,
                config=RunnerConfig(model="unpriced-model"),
            )

    def test_hard_budget_blocks_before_key_or_client_access(self) -> None:
        plan = build_run_plan(limit=1)
        key_calls = 0
        client_calls = 0

        def key_loader() -> str:
            nonlocal key_calls
            key_calls += 1
            return "test-key"

        def client_factory(_key: str) -> _FakeClient:
            nonlocal client_calls
            client_calls += 1
            return _FakeClient([])

        with self.assertRaisesRegex(OfflineRunnerError, "hard budget"):
            execute_run_plan(
                plan,
                output_dir=EVAL_ROOT / "never-created-budget-test",
                budget_limit_usd=plan.worst_case_cost_usd / 2,
                api_key_loader=key_loader,
                client_factory=client_factory,
            )
        self.assertEqual(key_calls, 0)
        self.assertEqual(client_calls, 0)

    def test_output_path_outside_eval_is_rejected_before_key_read(self) -> None:
        plan = build_run_plan(limit=1)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "inside eval"):
                execute_run_plan(
                    plan,
                    output_dir=Path(directory),
                    budget_limit_usd=plan.worst_case_cost_usd,
                    api_key_loader=lambda: (_ for _ in ()).throw(
                        AssertionError("credential must not be read")
                    ),
                )


class AIQARunnerExecutionTests(unittest.TestCase):
    def test_model_availability_requires_exact_snapshot(self) -> None:
        exact_client = _FakeClient([])
        verify_model_availability(exact_client, DEFAULT_MODEL)
        self.assertEqual(exact_client.models.calls, [DEFAULT_MODEL])

        alias_client = _FakeClient(
            [],
            returned_model="gpt-5.4-mini",
        )
        with self.assertRaisesRegex(
            OfflineRunnerError,
            "different model ID",
        ):
            verify_model_availability(alias_client, DEFAULT_MODEL)
        self.assertEqual(alias_client.responses.calls, [])

    def test_mock_execution_writes_scorer_compatible_artifacts(self) -> None:
        config = RunnerConfig(retries=0)
        plan = build_run_plan(limit=2, config=config)
        client = _FakeClient([_response(), _response()])
        captured_keys: list[str] = []

        def client_factory(api_key: str) -> _FakeClient:
            captured_keys.append(api_key)
            return client

        with tempfile.TemporaryDirectory(
            dir=EVAL_ROOT,
            prefix="runner-test-",
        ) as directory:
            paths = execute_run_plan(
                plan,
                output_dir=Path(directory) / "run",
                budget_limit_usd=plan.worst_case_cost_usd,
                api_key_loader=lambda: "secret-test-key",
                client_factory=client_factory,
                sleep_fn=lambda _seconds: None,
                monotonic_fn=_monotonic([0.0, 0.1, 0.1, 0.3]),
            )
            predictions = load_jsonl(paths["predictions"])
            manifest_text = paths["run_manifest"].read_text(
                encoding="utf-8"
            )
            manifest = json.loads(manifest_text)

            self.assertEqual(captured_keys, ["secret-test-key"])
            self.assertEqual(client.models.calls, [DEFAULT_MODEL])
            self.assertEqual(len(client.responses.calls), 2)
            self.assertEqual(len(predictions), 2)
            self.assertNotIn("secret-test-key", manifest_text)
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(
                manifest["configuration"]["model"],
                DEFAULT_MODEL,
            )
            self.assertEqual(
                manifest["configuration"]["reasoning_effort"],
                "none",
            )
            self.assertTrue(
                manifest["configuration"]["strict_structured_outputs"]
            )
            self.assertEqual(manifest["result"]["completed_cases"], 2)
            self.assertEqual(manifest["result"]["technical_failures"], 0)

            for case, call, prediction in zip(
                plan.cases,
                client.responses.calls,
                predictions,
            ):
                self.assertEqual(call["model"], DEFAULT_MODEL)
                self.assertEqual(call["reasoning"], {"effort": "none"})
                self.assertEqual(
                    call["text"],
                    {"format": RESPONSES_TEXT_FORMAT},
                )
                self.assertFalse(call["store"])
                self.assertEqual(call["service_tier"], "default")
                self.assertNotIn(str(case["case_id"]), call["input"])
                self.assertEqual(prediction["case_id"], case["case_id"])
                self.assertEqual(prediction["status"], "completed")
                self.assertEqual(
                    set(prediction["usage"]),
                    {
                        "input_tokens",
                        "cached_input_tokens",
                        "output_tokens",
                        "reasoning_tokens",
                    },
                )

            truth_by_id = {
                row["case_id"]: row
                for row in load_jsonl(
                    plan.input_path.with_name("development_truth.jsonl")
                )
            }
            selected_truth = [
                truth_by_id[str(case["case_id"])]
                for case in plan.cases
            ]
            report = score_predictions(
                selected_truth,
                predictions,
                split="mock-runner",
            )
            self.assertEqual(report["counts"]["total_cases"], 2)

    def test_retryable_failure_retries_identical_request(self) -> None:
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(429, request=request)
        rate_limit = openai.RateLimitError(
            "rate limited",
            response=response,
            body=None,
        )
        config = RunnerConfig(retries=2)
        plan = build_run_plan(limit=1, config=config)
        client = _FakeClient([rate_limit, _response()])
        sleeps: list[float] = []

        with tempfile.TemporaryDirectory(
            dir=EVAL_ROOT,
            prefix="runner-retry-test-",
        ) as directory:
            paths = execute_run_plan(
                plan,
                output_dir=Path(directory) / "run",
                budget_limit_usd=plan.worst_case_cost_usd,
                api_key_loader=lambda: "test-key",
                client_factory=lambda _key: client,
                sleep_fn=sleeps.append,
                monotonic_fn=_monotonic([0.0, 0.2]),
            )
            prediction = load_jsonl(paths["predictions"])[0]

        self.assertEqual(len(client.responses.calls), 2)
        self.assertEqual(client.responses.calls[0], client.responses.calls[1])
        self.assertEqual(sleeps, [1.0])
        self.assertEqual(prediction["status"], "completed")
        self.assertEqual(prediction["retry_count"], 1)

    def test_non_retryable_failure_is_safely_categorized(self) -> None:
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(400, request=request)
        bad_request = openai.BadRequestError(
            "provider detail must not be persisted",
            response=response,
            body=None,
        )
        plan = build_run_plan(
            limit=1,
            config=RunnerConfig(retries=2),
        )
        client = _FakeClient([bad_request])

        with tempfile.TemporaryDirectory(
            dir=EVAL_ROOT,
            prefix="runner-failure-test-",
        ) as directory:
            paths = execute_run_plan(
                plan,
                output_dir=Path(directory) / "run",
                budget_limit_usd=plan.worst_case_cost_usd,
                api_key_loader=lambda: "test-key",
                client_factory=lambda _key: client,
                sleep_fn=lambda _seconds: None,
                monotonic_fn=_monotonic([0.0, 0.1]),
            )
            artifact = paths["predictions"].read_text(encoding="utf-8")
            prediction = json.loads(artifact)

        self.assertEqual(len(client.responses.calls), 1)
        self.assertEqual(prediction["status"], "technical_failure")
        self.assertEqual(prediction["failure"], {"type": "api_bad_request"})
        self.assertNotIn("provider detail", artifact)

    def test_refusal_and_incomplete_response_become_technical_failures(
        self,
    ) -> None:
        refusal_item = SimpleNamespace(
            content=[SimpleNamespace(type="refusal")]
        )
        responses = [
            _response(output=[refusal_item]),
            _response(status="incomplete"),
        ]
        plan = build_run_plan(
            limit=2,
            config=RunnerConfig(retries=0),
        )
        client = _FakeClient(responses)

        with tempfile.TemporaryDirectory(
            dir=EVAL_ROOT,
            prefix="runner-response-test-",
        ) as directory:
            paths = execute_run_plan(
                plan,
                output_dir=Path(directory) / "run",
                budget_limit_usd=plan.worst_case_cost_usd,
                api_key_loader=lambda: "test-key",
                client_factory=lambda _key: client,
                sleep_fn=lambda _seconds: None,
                monotonic_fn=_monotonic([0.0, 0.1, 0.1, 0.2]),
            )
            predictions = load_jsonl(paths["predictions"])

        self.assertEqual(
            [row["failure"]["type"] for row in predictions],
            ["response_refusal", "response_incomplete"],
        )

    def test_existing_artifacts_are_never_overwritten(self) -> None:
        plan = build_run_plan(limit=1)
        with tempfile.TemporaryDirectory(
            dir=EVAL_ROOT,
            prefix="runner-overwrite-test-",
        ) as directory:
            output_dir = Path(directory) / "run"
            output_dir.mkdir()
            (output_dir / "predictions.jsonl").write_text(
                "existing\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(FileExistsError, "refusing overwrite"):
                execute_run_plan(
                    plan,
                    output_dir=output_dir,
                    budget_limit_usd=plan.worst_case_cost_usd,
                    api_key_loader=lambda: (_ for _ in ()).throw(
                        AssertionError("credential must not be read")
                    ),
                )


if __name__ == "__main__":
    unittest.main()
