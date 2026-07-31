from __future__ import annotations

import json
import unittest

from eval.ai_qa_review_contract import (
    MODEL_OUTPUT_JSON_SCHEMA,
    RESPONSES_TEXT_FORMAT,
    REVIEW_PROMPT_VERSION,
    SYSTEM_INSTRUCTIONS,
    ReviewOutputError,
    parse_review_output,
    render_case_input,
)
from eval.ai_qa_scorer import ERROR_FIELDS


RAW_TEXT = """\
Wohnungsdaten
3 Zimmer
Etage: 2

Lage
Adresse: Teststraße 10
12043 Berlin, Neukölln
Bezirk: Neukölln

Miete
600,00 € Kaltmiete
800,00 € Warmmiete

Bewerbung mit WBS 100-140 möglich.
"""

PARSER_SNAPSHOT = {
    "display_wbs": "100, 140",
    "rooms": 2.0,
    "floor": "2",
    "address": "Teststraße 10",
    "postal_code": "12043",
    "district": "Neukölln",
    "rent_kalt": "600,00 EUR",
    "rent_warm": "800,00 EUR",
}


def _output(**overrides: object) -> str:
    payload: dict[str, object] = {
        "review_required": True,
        "review_reason": "direct_mismatch",
        "error_field": "rooms",
        "source_value": "3",
        "snapshot_value": "2.0",
        "evidence_quote": "3 Zimmer",
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class AIQAReviewPromptTests(unittest.TestCase):
    def test_prompt_keeps_task_rules_and_uses_review_language(self) -> None:
        self.assertEqual(REVIEW_PROMPT_VERSION, "review-v1")
        self.assertIn("mandatory seven-field inspection", SYSTEM_INSTRUCTIONS)
        self.assertIn(
            "Compare explicit apartment room counts exactly",
            SYSTEM_INSTRUCTIONS,
        )
        self.assertIn("different explicit postal code", SYSTEM_INSTRUCTIONS)
        self.assertIn("review_required=true", SYSTEM_INSTRUCTIONS)
        self.assertIn("direct_mismatch", SYSTEM_INSTRUCTIONS)
        self.assertIn("unclear_source", SYSTEM_INSTRUCTIONS)
        self.assertIn("evidence_quote", SYSTEM_INSTRUCTIONS)
        self.assertNotIn("Set has_error", SYSTEM_INSTRUCTIONS)
        self.assertNotIn(
            "do not flag genuinely ambiguous wording",
            SYSTEM_INSTRUCTIONS,
        )

    def test_schema_is_strict_and_covers_every_error_field(self) -> None:
        self.assertEqual(RESPONSES_TEXT_FORMAT["type"], "json_schema")
        self.assertTrue(RESPONSES_TEXT_FORMAT["strict"])
        self.assertFalse(MODEL_OUTPUT_JSON_SCHEMA["additionalProperties"])
        self.assertEqual(
            set(MODEL_OUTPUT_JSON_SCHEMA["required"]),
            {
                "review_required",
                "review_reason",
                "error_field",
                "source_value",
                "snapshot_value",
                "evidence_quote",
            },
        )
        field_schema = MODEL_OUTPUT_JSON_SCHEMA["properties"]["error_field"]
        self.assertEqual(
            tuple(field_schema["anyOf"][0]["enum"]),
            ERROR_FIELDS,
        )

    def test_rendered_input_excludes_case_id_and_truth(self) -> None:
        rendered = render_case_input(
            {
                "case_id": "hidden-case",
                "case_type": "corrupted",
                "corrupted_field": "rooms",
                "expected_value": 3,
                "raw_text": RAW_TEXT,
                "parser_snapshot": PARSER_SNAPSHOT,
            }
        )
        parsed = json.loads(rendered)

        self.assertEqual(
            set(parsed),
            {"raw_listing_text", "parser_snapshot"},
        )
        for forbidden in (
            "hidden-case",
            "case_type",
            "corrupted_field",
            "expected_value",
        ):
            self.assertNotIn(forbidden, rendered)


class AIQAReviewOutputTests(unittest.TestCase):
    def test_direct_mismatch_routes_to_admin_with_exact_evidence(self) -> None:
        decision = parse_review_output(
            _output(),
            raw_text=RAW_TEXT,
            parser_snapshot=PARSER_SNAPSHOT,
        )

        self.assertTrue(decision.review_required)
        self.assertEqual(decision.review_reason, "direct_mismatch")
        self.assertEqual(decision.error_field, "rooms")
        self.assertEqual(decision.source_value, "3")
        self.assertEqual(decision.snapshot_value, "2.0")
        self.assertEqual(decision.evidence_quote, "3 Zimmer")

    def test_unclear_source_also_routes_to_admin(self) -> None:
        decision = parse_review_output(
            _output(
                review_reason="unclear_source",
                source_value=None,
                evidence_quote="3 Zimmer",
            ),
            raw_text=RAW_TEXT,
            parser_snapshot=PARSER_SNAPSHOT,
        )

        self.assertTrue(decision.review_required)
        self.assertEqual(decision.review_reason, "unclear_source")
        self.assertIsNone(decision.source_value)

    def test_consistent_listing_does_not_route_to_admin(self) -> None:
        decision = parse_review_output(
            _output(
                review_required=False,
                review_reason=None,
                error_field=None,
                source_value=None,
                snapshot_value=None,
                evidence_quote=None,
            ),
            raw_text=RAW_TEXT,
            parser_snapshot=PARSER_SNAPSHOT,
        )

        self.assertFalse(decision.review_required)
        self.assertIsNone(decision.review_reason)
        self.assertIsNone(decision.error_field)

    def test_numeric_snapshot_value_accepts_equivalent_string(self) -> None:
        decision = parse_review_output(
            _output(snapshot_value="2"),
            raw_text=RAW_TEXT,
            parser_snapshot=PARSER_SNAPSHOT,
        )

        self.assertEqual(decision.snapshot_value, "2")

    def test_postal_review_must_copy_the_actual_snapshot_value(self) -> None:
        postal_raw_text = RAW_TEXT.replace(
            "12043 Berlin, Neukölln",
            "13585 Berlin, Neukölln",
        )
        decision = parse_review_output(
            _output(
                error_field="address_postal_code",
                source_value="13585",
                snapshot_value="12043",
                evidence_quote="13585 Berlin, Neukölln",
            ),
            raw_text=postal_raw_text,
            parser_snapshot=PARSER_SNAPSHOT,
        )

        self.assertTrue(decision.review_required)
        self.assertEqual(decision.error_field, "address_postal_code")

    def test_no_review_rejects_non_null_details(self) -> None:
        with self.assertRaisesRegex(
            ReviewOutputError,
            "no-review response",
        ):
            parse_review_output(
                _output(
                    review_required=False,
                    review_reason=None,
                    error_field=None,
                    source_value=None,
                    snapshot_value=None,
                ),
                raw_text=RAW_TEXT,
                parser_snapshot=PARSER_SNAPSHOT,
            )

    def test_review_rejects_quote_not_found_in_source(self) -> None:
        with self.assertRaisesRegex(
            ReviewOutputError,
            "not present in the raw listing",
        ):
            parse_review_output(
                _output(evidence_quote="4 Zimmer"),
                raw_text=RAW_TEXT,
                parser_snapshot=PARSER_SNAPSHOT,
            )

    def test_review_rejects_snapshot_value_not_in_snapshot(self) -> None:
        with self.assertRaisesRegex(
            ReviewOutputError,
            "does not match",
        ):
            parse_review_output(
                _output(snapshot_value="4"),
                raw_text=RAW_TEXT,
                parser_snapshot=PARSER_SNAPSHOT,
            )

    def test_direct_mismatch_requires_source_value(self) -> None:
        with self.assertRaisesRegex(
            ReviewOutputError,
            "requires source_value",
        ):
            parse_review_output(
                _output(source_value=None),
                raw_text=RAW_TEXT,
                parser_snapshot=PARSER_SNAPSHOT,
            )

    def test_source_value_must_be_present_in_evidence_quote(self) -> None:
        with self.assertRaisesRegex(
            ReviewOutputError,
            "not present in evidence_quote",
        ):
            parse_review_output(
                _output(source_value="4"),
                raw_text=RAW_TEXT,
                parser_snapshot=PARSER_SNAPSHOT,
            )

    def test_review_rejects_unsupported_field(self) -> None:
        with self.assertRaisesRegex(ReviewOutputError, "error_field"):
            parse_review_output(
                _output(error_field="source_company"),
                raw_text=RAW_TEXT,
                parser_snapshot=PARSER_SNAPSHOT,
            )

    def test_output_rejects_extra_key_and_invalid_json(self) -> None:
        with self.assertRaisesRegex(ReviewOutputError, "review schema"):
            parse_review_output(
                _output(debug="not allowed"),
                raw_text=RAW_TEXT,
                parser_snapshot=PARSER_SNAPSHOT,
            )
        with self.assertRaisesRegex(ReviewOutputError, "valid JSON"):
            parse_review_output(
                "{invalid",
                raw_text=RAW_TEXT,
                parser_snapshot=PARSER_SNAPSHOT,
            )


if __name__ == "__main__":
    unittest.main()
