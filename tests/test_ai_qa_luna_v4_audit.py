from __future__ import annotations

import json
import unittest

from eval.ai_qa_luna_v4_audit import build_failure_audit, render_markdown
from eval.ai_qa_luna_v4_cycle import WBS_SEMANTIC_DRIFT_PHRASES


def _input(case_id: str, phrase: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "raw_text": f"Wohnung\n{phrase}",
        "parser_snapshot": {},
    }


def _prediction(
    case_id: str,
    *,
    has_error: bool,
    error_field: str | None,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "status": "completed",
        "raw_output": json.dumps(
            {"has_error": has_error, "error_field": error_field}
        ),
    }


class LunaV4FailureAuditTests(unittest.TestCase):
    def test_aggregates_wbs_salience_without_case_level_output(self) -> None:
        phrase = WBS_SEMANTIC_DRIFT_PHRASES["160, 180, 220"][0]
        inputs = [_input("clean", phrase), _input("rooms", phrase)]
        truth = [
            {
                "case_id": "clean",
                "case_type": "clean",
                "corrupted_field": None,
            },
            {
                "case_id": "rooms",
                "case_type": "corrupted",
                "corrupted_field": "rooms",
            },
        ]
        predictions = [
            _prediction("clean", has_error=True, error_field="wbs"),
            _prediction("rooms", has_error=True, error_field="wbs"),
        ]

        audit = build_failure_audit(
            input_rows=inputs,
            truth_rows=truth,
            prediction_rows=predictions,
        )

        self.assertEqual(audit["totals"]["false_alerts"], 1)
        self.assertEqual(audit["totals"]["wrongly_localized_to_wbs"], 1)
        self.assertNotIn("case_id", json.dumps(audit))
        self.assertIn("WBS salience", render_markdown(audit))


if __name__ == "__main__":
    unittest.main()
