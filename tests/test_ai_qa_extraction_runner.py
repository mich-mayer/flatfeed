from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from eval.ai_qa_extraction_contract import render_case_input
from eval.ai_qa_extraction_runner import (
    DEFAULT_PLAN_PATH,
    ExtractionRunnerError,
    build_extraction_development_dry_run,
    main,
    verify_dry_run_plan,
)


class AIQAExtractionRunnerTests(unittest.TestCase):
    def test_dry_run_makes_no_network_or_credential_read(self) -> None:
        plan = build_extraction_development_dry_run()

        self.assertEqual(plan["mode"], "dry_run")
        self.assertEqual(plan["network_calls_made"], 0)
        self.assertFalse(plan["credential_read"])
        self.assertEqual(plan["dataset"]["case_count"], 120)
        self.assertEqual(plan["requests"]["case_requests"], 120)
        self.assertEqual(
            plan["requests"]["maximum_responses_api_requests"],
            120,
        )
        self.assertEqual(plan["requests"]["maximum_total_api_calls"], 121)

    def test_model_input_is_raw_text_only(self) -> None:
        case = {
            "case_id": "hidden-case",
            "raw_text": "Zimmer: 2",
            "parser_snapshot": {"rooms": 3},
        }

        rendered = json.loads(render_case_input(case))

        self.assertEqual(rendered, {"raw_listing_text": "Zimmer: 2"})
        self.assertNotIn("hidden-case", json.dumps(rendered))
        self.assertNotIn("parser_snapshot", rendered)

    def test_configuration_and_development_boundaries_are_explicit(self) -> None:
        plan = build_extraction_development_dry_run()

        self.assertEqual(plan["configuration"]["model"], "gpt-5.6-terra")
        self.assertEqual(plan["configuration"]["reasoning_effort"], "high")
        self.assertEqual(
            plan["configuration"]["prompt_version"],
            "extraction-v1",
        )
        self.assertEqual(
            plan["configuration"]["max_output_tokens"],
            768,
        )
        self.assertFalse(
            plan["configuration"]["model_receives_parser_snapshot"]
        )
        self.assertTrue(plan["dataset"]["reused_development_set"])
        self.assertTrue(plan["boundaries"]["development_only"])
        self.assertFalse(plan["boundaries"]["final_600_case_evidence"])
        self.assertFalse(plan["boundaries"]["consumed_holdout_reused"])

    def test_budget_is_conservative_and_execution_is_blocked(self) -> None:
        plan = build_extraction_development_dry_run()

        self.assertGreater(
            Decimal(plan["preflight"]["hard_budget_limit_usd"]),
            Decimal("0"),
        )
        self.assertEqual(
            plan["pricing"]["cache_write_per_1m_usd"],
            "3.125",
        )
        self.assertTrue(plan["pricing"]["must_refresh_before_execute"])
        self.assertEqual(plan["execution_guard"]["status"], "blocked")

    def test_committed_plan_matches_current_code_and_dataset(self) -> None:
        plan = verify_dry_run_plan(DEFAULT_PLAN_PATH)

        self.assertEqual(plan["dataset"]["case_count"], 120)
        self.assertEqual(
            plan["development_targets"]["rooms_correct_field"],
            "at least 19/20",
        )

    def test_changed_plan_is_rejected(self) -> None:
        plan = build_extraction_development_dry_run()
        plan["configuration"]["reasoning_effort"] = "low"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changed.json"
            path.write_text(
                json.dumps(plan, ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "does not match current inputs",
            ):
                verify_dry_run_plan(path)

    def test_execute_flag_is_blocked_before_any_api_work(self) -> None:
        with (
            patch(
                "sys.argv",
                ["ai_qa_extraction_runner", "--execute"],
            ),
            self.assertRaisesRegex(
                ExtractionRunnerError,
                "API execution is disabled",
            ),
        ):
            main()


if __name__ == "__main__":
    unittest.main()
