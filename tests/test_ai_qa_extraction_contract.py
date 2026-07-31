from __future__ import annotations

import json
import unittest
from pathlib import Path

from eval.ai_qa_extraction_compare import (
    SNAPSHOT_KEYS,
    compare_extraction_to_snapshot,
)
from eval.ai_qa_extraction_contract import (
    EXTRACTION_FIELDS,
    MODEL_OUTPUT_JSON_SCHEMA,
    ExtractionResult,
    ExtractionOutputError,
    parse_extraction_output,
    render_case_input,
)
from eval.ai_qa_scorer import TRUTH_FIELD_TO_ERROR_FIELD


RAW_TEXT = """\
Anschrift: Berliner Allee 169
PLZ / Ort: 13088 Berlin
Bezirk: Pankow
Zimmer: 2
Etage: 3
Grundmiete: 600,50 EUR
Warmmiete: 800,75 EUR
Vermietung mit WBS 100-140 möglich."""

QUOTES = {
    "wbs": "Vermietung mit WBS 100-140 möglich.",
    "rent_kalt": "Grundmiete: 600,50 EUR",
    "rooms": "Zimmer: 2",
    "address": "Anschrift: Berliner Allee 169",
    "postal_code": "PLZ / Ort: 13088 Berlin",
    "district": "Bezirk: Pankow",
    "floor": "Etage: 3",
    "rent_warm": "Warmmiete: 800,75 EUR",
}

SNAPSHOT = {
    "display_wbs": "100, 140",
    "rent_kalt": "600,50 EUR",
    "rooms": 2.0,
    "address": "Berliner Allee 169",
    "postal_code": "13088",
    "district": "Pankow",
    "floor": "3",
    "rent_warm": "800,75 EUR",
}


def _payload(
    *,
    quotes: dict[str, str | None] | None = None,
) -> dict[str, object]:
    quotes = quotes or {}
    return {
        field: quotes.get(field, QUOTES[field])
        for field in EXTRACTION_FIELDS
    }


def _parse(payload: dict[str, object]):
    return parse_extraction_output(
        json.dumps(payload, ensure_ascii=False),
        raw_text=RAW_TEXT,
    )


def _oracle_evidence(
    field: str,
    source_snapshot: dict[str, object],
) -> str:
    value = source_snapshot[SNAPSHOT_KEYS[field]]
    if field == "wbs":
        if value == "No WBS required":
            quote = "Kein WBS erforderlich"
        elif value == "WBS required, type unknown":
            quote = "WBS erforderlich"
        else:
            quote = f"WBS {value}"
    elif field == "rent_kalt":
        quote = f"Kaltmiete: {value}"
    elif field == "rooms":
        quote = f"Zimmer: {value}"
    elif field == "address":
        quote = f"Anschrift: {value}"
    elif field == "postal_code":
        quote = f"PLZ: {value}"
    elif field == "district":
        quote = f"Bezirk: {value}"
    elif field == "floor":
        quote = f"Etage: {value}"
    elif field == "rent_warm":
        quote = f"Warmmiete: {value}"
    else:
        raise AssertionError(f"unsupported field: {field}")
    return quote


class AIQAExtractionContractTests(unittest.TestCase):
    def test_schema_is_strict_for_all_eight_source_fields(self) -> None:
        self.assertFalse(MODEL_OUTPUT_JSON_SCHEMA["additionalProperties"])
        self.assertEqual(
            set(MODEL_OUTPUT_JSON_SCHEMA["required"]),
            set(EXTRACTION_FIELDS),
        )
        for field in EXTRACTION_FIELDS:
            field_schema = MODEL_OUTPUT_JSON_SCHEMA["properties"][field]
            self.assertEqual(
                field_schema,
                {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "null"},
                    ]
                },
            )

    def test_model_input_contains_raw_text_but_not_parser_snapshot(self) -> None:
        rendered = render_case_input(
            {
                "case_id": "hidden-id",
                "raw_text": RAW_TEXT,
                "parser_snapshot": SNAPSHOT,
            }
        )

        self.assertIn("raw_listing_text", rendered)
        self.assertNotIn("parser_snapshot", rendered)
        self.assertNotIn("hidden-id", rendered)
        self.assertNotIn("600,50 EUR", rendered.split("raw_listing_text")[0])

    def test_exact_evidence_for_all_fields_matches_clean_snapshot(self) -> None:
        review = compare_extraction_to_snapshot(
            extraction=_parse(_payload()),
            parser_snapshot=SNAPSHOT,
        )

        self.assertFalse(review.review_required)
        self.assertEqual(review.issues, ())

    def test_each_snapshot_difference_is_found_by_normal_code(self) -> None:
        mutations = (
            ("display_wbs", "100", "wbs"),
            ("rent_kalt", "601,50 EUR", "rent_kalt"),
            ("rooms", 3.0, "rooms"),
            (
                "address",
                "Berliner Allee 170",
                "address_postal_code",
            ),
            ("postal_code", "10115", "address_postal_code"),
            ("district", "Mitte", "district"),
            ("floor", "4", "floor"),
            ("rent_warm", "801,75 EUR", "rent_warm"),
        )
        for snapshot_key, wrong_value, expected_group in mutations:
            with self.subTest(snapshot_key=snapshot_key):
                snapshot = dict(SNAPSHOT)
                snapshot[snapshot_key] = wrong_value
                review = compare_extraction_to_snapshot(
                    extraction=_parse(_payload()),
                    parser_snapshot=snapshot,
                )

                self.assertTrue(review.review_required)
                self.assertEqual(len(review.issues), 1)
                self.assertEqual(
                    review.issues[0].error_field,
                    expected_group,
                )
                self.assertEqual(
                    review.issues[0].review_reason,
                    "direct_mismatch",
                )

    def test_null_quote_routes_parser_value_to_admin(self) -> None:
        extraction = _parse(_payload(quotes={"district": None}))
        review = compare_extraction_to_snapshot(
            extraction=extraction,
            parser_snapshot=SNAPSHOT,
        )

        self.assertTrue(review.review_required)
        self.assertEqual(review.issues[0].error_field, "district")
        self.assertEqual(
            review.issues[0].review_reason,
            "unclear_source",
        )

    def test_quote_that_cannot_be_normalized_routes_to_admin(self) -> None:
        raw_text = RAW_TEXT.replace("Etage: 3", "Etage: unbekannt")
        payload = _payload(quotes={"floor": "Etage: unbekannt"})
        extraction = parse_extraction_output(
            json.dumps(payload, ensure_ascii=False),
            raw_text=raw_text,
        )
        review = compare_extraction_to_snapshot(
            extraction=extraction,
            parser_snapshot=SNAPSHOT,
        )

        floor_issue = next(
            issue
            for issue in review.issues
            if issue.error_field == "floor"
        )
        self.assertEqual(floor_issue.review_reason, "unclear_source")

    def test_real_model_quote_variants_match_clean_snapshot(self) -> None:
        raw_text = """\
Anschrift     Berliner Allee 169
PLZ / Ort     13088 Berlin
Bezirk Pankow
Zimmer        2
Stockwerk     Hochparterre
Grundmiete    600,50 EUR
Warmmiete     800,75 EUR
Vermietung mit WBS 100-140 möglich."""
        payload = {
            "wbs": "Vermietung mit WBS 100-140 möglich.",
            "rent_kalt": "Grundmiete    600,50 EUR",
            "rooms": "Zimmer        2",
            "address": "Anschrift     Berliner Allee 169",
            "postal_code": "13088",
            "district": "Bezirk Pankow",
            "floor": "Stockwerk     Hochparterre",
            "rent_warm": "Warmmiete     800,75 EUR",
        }
        snapshot = {
            **SNAPSHOT,
            "floor": "Hochparterre",
        }

        extraction = parse_extraction_output(
            json.dumps(payload, ensure_ascii=False),
            raw_text=raw_text,
        )
        review = compare_extraction_to_snapshot(
            extraction=extraction,
            parser_snapshot=snapshot,
        )

        self.assertFalse(review.review_required)

    def test_bare_multiword_address_matches_clean_snapshot(self) -> None:
        raw_text = RAW_TEXT.replace(
            "Anschrift: Berliner Allee 169",
            "Adresse: Allee der Kosmonauten 208",
        )
        payload = _payload(
            quotes={"address": "Allee der Kosmonauten 208"}
        )
        snapshot = {
            **SNAPSHOT,
            "address": "Allee der Kosmonauten 208",
        }

        extraction = parse_extraction_output(
            json.dumps(payload, ensure_ascii=False),
            raw_text=raw_text,
        )
        review = compare_extraction_to_snapshot(
            extraction=extraction,
            parser_snapshot=snapshot,
        )

        self.assertFalse(review.review_required)

    def test_null_quote_passes_when_parser_value_is_also_null(self) -> None:
        extraction = _parse(_payload(quotes={"floor": None}))
        snapshot = dict(SNAPSHOT)
        snapshot["floor"] = None

        review = compare_extraction_to_snapshot(
            extraction=extraction,
            parser_snapshot=snapshot,
        )

        self.assertFalse(review.review_required)

    def test_non_string_quote_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ExtractionOutputError,
            "must be a non-empty quote or null",
        ):
            _parse(_payload(quotes={"floor": 3}))

    def test_invented_quote_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ExtractionOutputError,
            "not present in raw text",
        ):
            _parse(_payload(quotes={"rooms": "Zimmer: 5"}))

    def test_comparator_can_resolve_all_120_development_cases(self) -> None:
        dataset_dir = (
            Path(__file__).resolve().parents[1]
            / "eval"
            / "datasets"
            / "review_v1_development"
        )
        inputs = [
            json.loads(line)
            for line in (dataset_dir / "model_inputs.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        truth = {
            row["case_id"]: row
            for row in (
                json.loads(line)
                for line in (dataset_dir / "truth.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            )
        }

        for case in inputs:
            with self.subTest(case_id=case["case_id"]):
                truth_row = truth[case["case_id"]]
                source_snapshot = dict(case["parser_snapshot"])
                if truth_row["case_type"] == "corrupted":
                    corrupted_field = truth_row["corrupted_field"]
                    snapshot_key = (
                        corrupted_field
                        if corrupted_field in source_snapshot
                        else SNAPSHOT_KEYS[corrupted_field]
                    )
                    source_snapshot[snapshot_key] = truth_row[
                        "expected_value"
                    ]

                extraction = ExtractionResult(
                    fields={
                        field: _oracle_evidence(
                            field,
                            source_snapshot,
                        )
                        for field in EXTRACTION_FIELDS
                    }
                )
                review = compare_extraction_to_snapshot(
                    extraction=extraction,
                    parser_snapshot=case["parser_snapshot"],
                )
                if truth_row["case_type"] == "clean":
                    self.assertFalse(review.review_required)
                    continue

                expected_group = TRUTH_FIELD_TO_ERROR_FIELD[
                    truth_row["corrupted_field"]
                ]
                self.assertTrue(review.review_required)
                self.assertEqual(
                    [issue.error_field for issue in review.issues],
                    [expected_group],
                )
                self.assertEqual(
                    review.issues[0].review_reason,
                    "direct_mismatch",
                )


if __name__ == "__main__":
    unittest.main()
