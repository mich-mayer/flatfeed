from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from eval.ai_qa_review_runner import (
    DEFAULT_PLAN_PATH,
    ReviewRunnerError,
    build_review_development_dry_run,
    main,
    verify_dry_run_plan,
    write_dry_run_plan,
)


class AIQAReviewRunnerTests(unittest.TestCase):
    def test_dry_run_is_paired_and_makes_no_network_call(self) -> None:
        plan = build_review_development_dry_run()
        paired = plan["paired_comparison"]

        self.assertEqual(plan["mode"], "dry_run")
        self.assertEqual(plan["network_calls_made"], 0)
        self.assertFalse(plan["credential_read"])
        self.assertEqual(plan["dataset"]["case_count"], 120)
        self.assertEqual(paired["responses_api_requests"], 240)
        self.assertEqual(paired["model_availability_checks"], 1)
        self.assertEqual(paired["maximum_total_api_calls"], 241)
        self.assertTrue(paired["same_cases"])
        self.assertTrue(paired["same_model"])
        self.assertTrue(paired["same_reasoning_effort"])

    def test_profiles_use_expected_prompts_schemas_and_limits(self) -> None:
        profiles = build_review_development_dry_run()[
            "paired_comparison"
        ]["profiles"]
        baseline = profiles["baseline"]
        candidate = profiles["candidate"]

        self.assertEqual(
            baseline["configuration"]["prompt_version"],
            "terra-v1",
        )
        self.assertEqual(
            candidate["configuration"]["prompt_version"],
            "review-v1",
        )
        self.assertEqual(
            baseline["configuration"]["max_output_tokens"],
            256,
        )
        self.assertEqual(
            candidate["configuration"]["max_output_tokens"],
            512,
        )
        self.assertNotEqual(
            baseline["hashes"]["prompt_sha256"],
            candidate["hashes"]["prompt_sha256"],
        )
        self.assertNotEqual(
            baseline["hashes"]["output_schema_sha256"],
            candidate["hashes"]["output_schema_sha256"],
        )
        self.assertEqual(
            baseline["hashes"]["rendered_inputs_sha256"],
            candidate["hashes"]["rendered_inputs_sha256"],
        )

    def test_budget_is_conservative_and_execution_requires_refresh(self) -> None:
        plan = build_review_development_dry_run()
        profiles = plan["paired_comparison"]["profiles"]
        combined = sum(
            Decimal(profile["preflight"]["hard_budget_limit_usd"])
            for profile in profiles.values()
        )

        self.assertEqual(
            combined,
            Decimal(plan["combined_hard_budget_limit_usd"]),
        )
        self.assertGreater(combined, Decimal("0"))
        self.assertTrue(plan["pricing"]["must_refresh_before_execute"])
        self.assertEqual(plan["execution_guard"]["status"], "blocked")

    def test_plan_write_is_reproducible_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            first = write_dry_run_plan(path)
            stored = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(first, stored)
            self.assertEqual(verify_dry_run_plan(path), stored)
            with self.assertRaises(FileExistsError):
                write_dry_run_plan(path)

    def test_committed_plan_matches_current_code_and_dataset(self) -> None:
        plan = verify_dry_run_plan(DEFAULT_PLAN_PATH)

        self.assertEqual(
            plan["dataset"]["focus_cases"],
            {
                "postal_code_substitution": 6,
                "rooms_neighbor_value": 20,
            },
        )
        self.assertFalse(plan["boundaries"]["old_holdout_reused"])
        self.assertFalse(plan["boundaries"]["product_runtime_modified"])

    def test_execute_flag_is_blocked_before_any_api_work(self) -> None:
        with (
            patch(
                "sys.argv",
                ["ai_qa_review_runner", "--execute"],
            ),
            self.assertRaisesRegex(
                ReviewRunnerError,
                "disabled until a separate configuration freeze",
            ),
        ):
            main()


if __name__ == "__main__":
    unittest.main()
