from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from eval.ai_qa_runner import (
    EVAL_ROOT,
    LOCKED_HOLDOUT_HARD_BUDGET_USD,
    LOCKED_HOLDOUT_RUN_DIR,
    OfflineRunnerError,
    RunnerConfig,
    build_run_plan,
    dry_run_summary,
    execute_run_plan,
    write_locked_holdout_configuration_freeze,
)


class LockedHoldoutReleaseTests(unittest.TestCase):
    def _config(self) -> RunnerConfig:
        return RunnerConfig(
            model="gpt-5.6-terra",
            reasoning_effort="high",
            max_output_tokens=256,
            retries=0,
            prompt_version="terra-v1",
        )

    def test_freeze_releases_only_the_exact_full_holdout(self) -> None:
        with tempfile.TemporaryDirectory(
            dir=EVAL_ROOT,
            prefix="holdout-release-test-",
        ) as directory:
            root = Path(directory)
            freeze_path = root / "freeze.json"
            run_dir = root / "run"
            with patch(
                "eval.ai_qa_runner.LOCKED_HOLDOUT_RUN_DIR",
                run_dir,
            ):
                written = write_locked_holdout_configuration_freeze(
                    output_path=freeze_path,
                )
            freeze = json.loads(written.read_text(encoding="utf-8"))
            self.assertEqual(freeze["status"], "holdout_authorized_once")
            self.assertEqual(
                freeze["holdout"]["hard_budget_limit_usd"],
                10.4,
            )
            self.assertTrue(
                freeze["boundaries"]["locked_holdout_authorized"]
            )

            with patch(
                "eval.ai_qa_runner.LOCKED_HOLDOUT_FREEZE_PATH",
                freeze_path,
            ):
                plan = build_run_plan(
                    split="locked_holdout",
                    config=self._config(),
                )
                summary = dry_run_summary(
                    plan,
                    budget_limit_usd=LOCKED_HOLDOUT_HARD_BUDGET_USD,
                    output_dir=LOCKED_HOLDOUT_RUN_DIR,
                )
                self.assertEqual(plan.case_count, 600)
                self.assertLessEqual(
                    plan.worst_case_cost_usd,
                    LOCKED_HOLDOUT_HARD_BUDGET_USD,
                )
                self.assertTrue(summary["locked_holdout_enabled"])
                self.assertIsNone(summary["selected_case_ids"])
                self.assertTrue(summary["budget_sufficient"])

                with self.assertRaisesRegex(
                    OfflineRunnerError,
                    "must use all 600 cases",
                ):
                    build_run_plan(
                        split="locked_holdout",
                        limit=599,
                        config=self._config(),
                    )

    def test_execute_rejects_wrong_budget_before_reading_credential(self) -> None:
        with tempfile.TemporaryDirectory(
            dir=EVAL_ROOT,
            prefix="holdout-budget-test-",
        ) as directory:
            root = Path(directory)
            freeze_path = root / "freeze.json"
            run_dir = root / "run"
            with patch(
                "eval.ai_qa_runner.LOCKED_HOLDOUT_RUN_DIR",
                run_dir,
            ):
                write_locked_holdout_configuration_freeze(
                    output_path=freeze_path,
                )
                with patch(
                    "eval.ai_qa_runner.LOCKED_HOLDOUT_FREEZE_PATH",
                    freeze_path,
                ):
                    plan = build_run_plan(
                        split="locked_holdout",
                        config=self._config(),
                    )
                    with self.assertRaisesRegex(
                        OfflineRunnerError,
                        "hard budget",
                    ):
                        execute_run_plan(
                            plan,
                            output_dir=run_dir,
                            budget_limit_usd=Decimal("10.38"),
                            api_key_loader=lambda: self.fail(
                                "credential must not be read"
                            ),
                        )


if __name__ == "__main__":
    unittest.main()
