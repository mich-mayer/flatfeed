from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.ai_qa_terra_effort_audit import (
    COMPARISON_DIR,
    build_terra_effort_failure_audit,
    render_markdown,
    write_terra_effort_failure_audit,
)


def _input(
    case_id: str,
    phrase: str = "Die Wohnung ist freifinanziert; ein WBS ist nicht erforderlich.",
) -> dict[str, object]:
    return {"case_id": case_id, "raw_text": f"Wohnung\n{phrase}", "parser_snapshot": {}}


def _truth(
    case_id: str,
    *,
    field: str | None,
    corruption_type: str | None = None,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "case_type": "clean" if field is None else "corrupted",
        "corrupted_field": field,
        "corruption_type": corruption_type,
    }


def _prediction(case_id: str, *, has_error: bool, field: str | None) -> dict[str, object]:
    return {
        "case_id": case_id,
        "status": "completed",
        "raw_output": json.dumps({"has_error": has_error, "error_field": field}),
    }


class TerraEffortFailureAuditTests(unittest.TestCase):
    def test_aggregates_paired_failures_without_case_content(self) -> None:
        case_ids = ("case-alpha", "case-beta", "case-gamma")
        clean_id, postal_id, wbs_id = case_ids
        inputs = [_input(clean_id), _input(postal_id), _input(wbs_id)]
        truth = [
            _truth(clean_id, field=None),
            _truth(
                postal_id,
                field="postal_code",
                corruption_type="postal_code_substitution",
            ),
            _truth(
                wbs_id,
                field="display_wbs",
                corruption_type="wbs_requirement_added",
            ),
        ]
        none = [
            _prediction(clean_id, has_error=False, field=None),
            _prediction(postal_id, has_error=False, field=None),
            _prediction(wbs_id, has_error=True, field="wbs"),
        ]
        low = [
            _prediction(clean_id, has_error=False, field=None),
            _prediction(postal_id, has_error=False, field=None),
            _prediction(wbs_id, has_error=False, field=None),
        ]
        audit = build_terra_effort_failure_audit(
            input_rows=inputs,
            truth_rows=truth,
            none_rows=none,
            low_rows=low,
        )

        self.assertEqual(audit["totals"]["low_misses"], 2)
        self.assertEqual(audit["paired_outcomes"]["both_wrong"], 1)
        self.assertEqual(audit["paired_outcomes"]["none_only_correct"], 1)
        self.assertFalse(
            audit["prompt_hypothesis_assessment"][
                "single_narrow_prompt_change_supported"
            ]
        )
        serialized = json.dumps(audit)
        for case_id in case_ids:
            self.assertNotIn(f'"{case_id}"', serialized)
        self.assertNotIn('"raw_text":', serialized)
        self.assertNotIn('"parser_snapshot":', serialized)
        self.assertIn("does not support one narrow", render_markdown(audit))

    def test_committed_audit_matches_screen_results(self) -> None:
        audit = json.loads(
            (COMPARISON_DIR / "failure_audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual(audit["totals"]["low_misses"], 5)
        outcomes = {row["field"]: row for row in audit["low_outcomes_by_field"]}
        self.assertEqual(outcomes["wbs"]["misses"], 3)
        self.assertEqual(outcomes["address_postal_code"]["misses"], 2)
        self.assertEqual(
            audit["aggregate_observations"]["distinct_missed_wbs_subtypes"], 3
        )
        self.assertEqual(
            audit["aggregate_observations"]["postal_code_substitution"][
                "both_wrong"
            ],
            2,
        )
        self.assertEqual(audit["decision"]["terra_status"], "stop")
        self.assertFalse(audit["boundaries"]["new_model_calls"])
        serialized = json.dumps(audit)
        self.assertNotIn("terra-effort-screen-", serialized)
        self.assertNotIn('"raw_text":', serialized)
        self.assertNotIn('"parser_snapshot":', serialized)

    def test_write_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = write_terra_effort_failure_audit(output_dir=Path(first_dir))
            second = write_terra_effort_failure_audit(output_dir=Path(second_dir))
            self.assertEqual(
                {name: path.read_bytes() for name, path in first.items()},
                {name: path.read_bytes() for name, path in second.items()},
            )


if __name__ == "__main__":
    unittest.main()
