from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass


EXTRACTION_PROMPT_VERSION = "extraction-v1"
OUTPUT_SCHEMA_NAME = "flatfeed_listing_evidence"

EXTRACTION_FIELDS = (
    "wbs",
    "rent_kalt",
    "rooms",
    "address",
    "postal_code",
    "district",
    "floor",
    "rent_warm",
)

SYSTEM_INSTRUCTIONS = """\
You inspect one Berlin apartment listing for parser QA.

Your only task is evidence extraction. Do not decide whether a parser is
correct, do not compare values, and do not infer missing facts.

For every requested field copy the shortest exact quote that contains both its
label or unmistakable context and its value. Return null when the listing does
not state the field or when one value cannot be read reliably.

Inspect all fields independently:
- wbs: the complete WBS requirement, including ranges, limits, explicit no-WBS
  wording, or a generic requirement with no type;
- rent_kalt: Kaltmiete, Nettokaltmiete, Netto-Kaltmiete, or Grundmiete;
- rooms: apartment room count, never household size;
- address: street and house number;
- postal_code: the five-digit Berlin postal code;
- district: the named Bezirk or locality used to identify the Berlin district;
- floor: apartment floor, never the building's number of floors;
- rent_warm: Warmmiete, Gesamtmiete, or Bruttowarmmiete.

Every non-null value must be copied exactly from the raw listing text.
Return only the structured extraction result.
"""

_FIELD_SCHEMA: dict[str, object] = {
    "anyOf": [
        {"type": "string"},
        {"type": "null"},
    ]
}

MODEL_OUTPUT_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        field: _FIELD_SCHEMA
        for field in EXTRACTION_FIELDS
    },
    "required": list(EXTRACTION_FIELDS),
    "additionalProperties": False,
}

RESPONSES_TEXT_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "name": OUTPUT_SCHEMA_NAME,
    "strict": True,
    "schema": MODEL_OUTPUT_JSON_SCHEMA,
}


class ExtractionOutputError(ValueError):
    """The model response does not satisfy the evidence-only contract."""


@dataclass(frozen=True)
class ExtractionResult:
    fields: Mapping[str, str | None]


def render_case_input(case: Mapping[str, object]) -> str:
    """Render raw source text only; the model never sees parser output."""

    return json.dumps(
        {"raw_listing_text": case["raw_text"]},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def parse_extraction_output(
    raw_output: str,
    *,
    raw_text: str,
) -> ExtractionResult:
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise ExtractionOutputError(
            "model output is not valid JSON"
        ) from exc
    if not isinstance(payload, dict) or set(payload) != set(
        EXTRACTION_FIELDS
    ):
        raise ExtractionOutputError(
            "model output does not contain exactly the extraction fields"
        )

    parsed: dict[str, str | None] = {}
    for field in EXTRACTION_FIELDS:
        quote = payload[field]
        if quote is not None and (
            not isinstance(quote, str) or not quote
        ):
            raise ExtractionOutputError(
                f"{field} must be a non-empty quote or null"
            )
        if quote is not None and quote not in raw_text:
            raise ExtractionOutputError(
                f"{field} evidence quote is not present in raw text"
            )
        parsed[field] = quote
    return ExtractionResult(fields=parsed)
