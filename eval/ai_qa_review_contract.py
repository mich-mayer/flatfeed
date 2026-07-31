from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from eval.ai_qa_prompt import TERRA_V1_SYSTEM_INSTRUCTIONS
from eval.ai_qa_scorer import ERROR_FIELDS


REVIEW_PROMPT_VERSION = "review-v1"
OUTPUT_SCHEMA_NAME = "flatfeed_parser_review"

ReviewReason = Literal["direct_mismatch", "unclear_source"]

REVIEW_REASONS: tuple[ReviewReason, ...] = (
    "direct_mismatch",
    "unclear_source",
)

_OLD_AMBIGUITY_INSTRUCTION = (
    "Do\nnot infer hidden facts and do not flag genuinely ambiguous wording."
)
_NEW_AMBIGUITY_INSTRUCTION = """\
Do not infer hidden facts. When wording for one field is genuinely ambiguous
and prevents a reliable comparison, request admin review with unclear_source
instead of inventing a value."""

_OLD_OUTPUT_INSTRUCTIONS = """\
Set has_error to false and error_field to null when the snapshot is materially
consistent with the listing. Set has_error to true and name exactly one field
when there is a material contradiction. Return only the structured result.
"""
_NEW_OUTPUT_INSTRUCTIONS = """\
Return review_required=false only when every checked field is materially
consistent with the listing. Set every other output field to null in that case.

Return review_required=true whenever the listing needs admin review:
- use review_reason=direct_mismatch for an explicit source value that
  contradicts the matching parser snapshot value;
- use review_reason=unclear_source only when the source wording for one field
  is genuinely ambiguous enough that a reliable comparison cannot be made.

For every review, name exactly one error_field and copy snapshot_value from the
matching parser_snapshot field as a string. For address_postal_code, copy the
challenged address or postal_code value. For a direct mismatch, source_value
must copy the explicit source value exactly as it appears inside evidence_quote.
For unclear_source, source_value may be null when no single value can be read;
when present, it must also be copied from evidence_quote.

Every review must include a short evidence_quote copied exactly from the raw
listing text. Do not paraphrase it. Return only the structured result.
"""

if _OLD_AMBIGUITY_INSTRUCTION not in TERRA_V1_SYSTEM_INSTRUCTIONS:
    raise RuntimeError("terra-v1 ambiguity instruction changed")
if _OLD_OUTPUT_INSTRUCTIONS not in TERRA_V1_SYSTEM_INSTRUCTIONS:
    raise RuntimeError("terra-v1 output instruction changed")

SYSTEM_INSTRUCTIONS = TERRA_V1_SYSTEM_INSTRUCTIONS.replace(
    _OLD_AMBIGUITY_INSTRUCTION,
    _NEW_AMBIGUITY_INSTRUCTION,
    1,
).replace(
    _OLD_OUTPUT_INSTRUCTIONS,
    _NEW_OUTPUT_INSTRUCTIONS,
    1,
)

_NULLABLE_STRING_SCHEMA: dict[str, object] = {
    "anyOf": [
        {"type": "string"},
        {"type": "null"},
    ]
}

MODEL_OUTPUT_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "review_required": {"type": "boolean"},
        "review_reason": {
            "anyOf": [
                {
                    "type": "string",
                    "enum": list(REVIEW_REASONS),
                },
                {"type": "null"},
            ]
        },
        "error_field": {
            "anyOf": [
                {
                    "type": "string",
                    "enum": list(ERROR_FIELDS),
                },
                {"type": "null"},
            ]
        },
        "source_value": _NULLABLE_STRING_SCHEMA,
        "snapshot_value": _NULLABLE_STRING_SCHEMA,
        "evidence_quote": _NULLABLE_STRING_SCHEMA,
    },
    "required": [
        "review_required",
        "review_reason",
        "error_field",
        "source_value",
        "snapshot_value",
        "evidence_quote",
    ],
    "additionalProperties": False,
}

RESPONSES_TEXT_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "name": OUTPUT_SCHEMA_NAME,
    "strict": True,
    "schema": MODEL_OUTPUT_JSON_SCHEMA,
}

_OUTPUT_KEYS = frozenset(MODEL_OUTPUT_JSON_SCHEMA["required"])
_FIELD_TO_SNAPSHOT_KEYS = {
    "wbs": ("display_wbs",),
    "rent_kalt": ("rent_kalt",),
    "rooms": ("rooms",),
    "address_postal_code": ("address", "postal_code"),
    "district": ("district",),
    "floor": ("floor",),
    "rent_warm": ("rent_warm",),
}


class ReviewOutputError(ValueError):
    """The model response does not satisfy the local review contract."""


@dataclass(frozen=True)
class ReviewDecision:
    review_required: bool
    review_reason: ReviewReason | None
    error_field: str | None
    source_value: str | None
    snapshot_value: str | None
    evidence_quote: str | None


def render_case_input(case: Mapping[str, object]) -> str:
    """Render model-visible input without case IDs or hidden answer data."""

    payload = {
        "raw_listing_text": case["raw_text"],
        "parser_snapshot": case["parser_snapshot"],
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _nonempty_string(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def _numeric_strings_match(candidate: str, snapshot_value: object) -> bool:
    if (
        isinstance(snapshot_value, bool)
        or not isinstance(snapshot_value, (int, float))
    ):
        return False
    if isinstance(snapshot_value, float) and not math.isfinite(snapshot_value):
        return False
    try:
        return Decimal(candidate) == Decimal(str(snapshot_value))
    except InvalidOperation:
        return False


def _matches_snapshot_value(
    candidate: str,
    snapshot_value: object,
) -> bool:
    if snapshot_value is None:
        return candidate == "null"
    if isinstance(snapshot_value, str):
        return candidate == snapshot_value
    if _numeric_strings_match(candidate, snapshot_value):
        return True
    return candidate == str(snapshot_value)


def _validate_snapshot_value(
    *,
    error_field: str,
    candidate: str,
    parser_snapshot: Mapping[str, object],
) -> None:
    snapshot_keys = _FIELD_TO_SNAPSHOT_KEYS[error_field]
    missing_keys = [key for key in snapshot_keys if key not in parser_snapshot]
    if missing_keys:
        raise ReviewOutputError(
            "parser snapshot is missing field data required for validation"
        )
    if not any(
        _matches_snapshot_value(candidate, parser_snapshot[key])
        for key in snapshot_keys
    ):
        raise ReviewOutputError(
            "snapshot_value does not match the challenged parser field"
        )


def parse_review_output(
    raw_output: str,
    *,
    raw_text: str,
    parser_snapshot: Mapping[str, object],
) -> ReviewDecision:
    """Parse and deterministically validate one structured model response."""

    if not isinstance(raw_output, str) or not raw_output:
        raise ReviewOutputError("model output must be a non-empty string")
    try:
        output = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise ReviewOutputError("model output is not valid JSON") from exc
    if not isinstance(output, dict) or set(output) != _OUTPUT_KEYS:
        raise ReviewOutputError("model output does not match the review schema")

    review_required = output["review_required"]
    if not isinstance(review_required, bool):
        raise ReviewOutputError("review_required must be a boolean")

    if review_required is False:
        detail_keys = _OUTPUT_KEYS - {"review_required"}
        if any(output[key] is not None for key in detail_keys):
            raise ReviewOutputError(
                "a no-review response must set every detail field to null"
            )
        return ReviewDecision(
            review_required=False,
            review_reason=None,
            error_field=None,
            source_value=None,
            snapshot_value=None,
            evidence_quote=None,
        )

    review_reason = output["review_reason"]
    error_field = output["error_field"]
    source_value = output["source_value"]
    snapshot_value = _nonempty_string(output["snapshot_value"])
    evidence_quote = _nonempty_string(output["evidence_quote"])

    if review_reason not in REVIEW_REASONS:
        raise ReviewOutputError("review_reason is invalid")
    if error_field not in ERROR_FIELDS:
        raise ReviewOutputError("error_field is invalid")
    if snapshot_value is None:
        raise ReviewOutputError("a review requires snapshot_value")
    if evidence_quote is None:
        raise ReviewOutputError("a review requires evidence_quote")
    if evidence_quote not in raw_text:
        raise ReviewOutputError("evidence_quote is not present in the raw listing")

    _validate_snapshot_value(
        error_field=error_field,
        candidate=snapshot_value,
        parser_snapshot=parser_snapshot,
    )

    parsed_source_value = _nonempty_string(source_value)
    if review_reason == "direct_mismatch":
        if parsed_source_value is None:
            raise ReviewOutputError("a direct mismatch requires source_value")
        if parsed_source_value.strip() == snapshot_value.strip():
            raise ReviewOutputError(
                "a direct mismatch cannot repeat the same source and snapshot value"
            )
    elif source_value is not None and parsed_source_value is None:
        raise ReviewOutputError(
            "unclear_source source_value must be null or a non-empty string"
        )
    if (
        parsed_source_value is not None
        and parsed_source_value not in evidence_quote
    ):
        raise ReviewOutputError(
            "source_value is not present in evidence_quote"
        )

    return ReviewDecision(
        review_required=True,
        review_reason=review_reason,
        error_field=error_field,
        source_value=parsed_source_value,
        snapshot_value=snapshot_value,
        evidence_quote=evidence_quote,
    )
