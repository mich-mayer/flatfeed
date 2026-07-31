from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from eval.ai_qa_extraction_contract import ExtractionResult
from flatfeed.listing_metadata import (
    extract_address,
    extract_district,
    extract_floor,
    extract_postal_code,
    normalize_berlin_district,
)
from flatfeed.wbs_rules import (
    display_wbs_requirement,
    extract_wbs_requirement,
)


ReviewReason = Literal["direct_mismatch", "unclear_source"]

COMPARISON_GROUPS = (
    "wbs",
    "rent_kalt",
    "rooms",
    "address_postal_code",
    "district",
    "floor",
    "rent_warm",
)

_GROUP_FIELDS = {
    "wbs": ("wbs",),
    "rent_kalt": ("rent_kalt",),
    "rooms": ("rooms",),
    "address_postal_code": ("address", "postal_code"),
    "district": ("district",),
    "floor": ("floor",),
    "rent_warm": ("rent_warm",),
}

SNAPSHOT_KEYS = {
    "wbs": "display_wbs",
    "rent_kalt": "rent_kalt",
    "rooms": "rooms",
    "address": "address",
    "postal_code": "postal_code",
    "district": "district",
    "floor": "floor",
    "rent_warm": "rent_warm",
}

_RENT_LABELS = {
    "rent_kalt": (
        "kaltmiete",
        "nettokaltmiete",
        "netto-kaltmiete",
        "grundmiete",
    ),
    "rent_warm": (
        "warmmiete",
        "gesamtmiete",
        "bruttowarmmiete",
    ),
}


@dataclass(frozen=True)
class ReviewIssue:
    error_field: str
    source_field: str
    review_reason: ReviewReason
    evidence_quote: str | None
    source_value: object | None
    snapshot_value: object | None


@dataclass(frozen=True)
class DeterministicReview:
    review_required: bool
    issues: tuple[ReviewIssue, ...]


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split()).strip()
    return cleaned.casefold() or None


def _snapshot_money(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("eur", "").replace("€", "")
    text = text.strip()
    if not text:
        return None
    if "," in text:
        normalized = text.replace(".", "").replace(",", ".")
    else:
        normalized = text
    try:
        return int(Decimal(normalized) * 100)
    except (InvalidOperation, ValueError):
        return None


def _source_money(
    value: str,
    labels: tuple[str, ...],
) -> int | None:
    label_group = "|".join(re.escape(label) for label in labels)
    amount = (
        r"(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?"
        r"|\d{2,5}(?:[,.]\d{1,2})?)"
    )
    patterns = (
        rf"(?:{label_group})[^\d]{{0,60}}{amount}\s*(?:€|eur|euro)?",
        rf"{amount}\s*(?:€|eur|euro)[^\n]{{0,60}}(?:{label_group})",
    )
    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            return _snapshot_money(match.group(1))
    return None


def _source_rooms(value: str) -> float | None:
    patterns = (
        r"\b(?:anzahl\s+zimmer|zimmeranzahl|zimmer)\s*[:\-]?\s*"
        r"(\d+(?:[,.]\d+)?)\b",
        r"\b(\d+(?:[,.]\d+)?)\s*[- ]?\s*(?:zimmer|zi\.|räume|rooms?)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def _source_labeled_text(
    value: str,
    labels: tuple[str, ...],
) -> str | None:
    label_group = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:{label_group})(?:\s*[:\-]\s*|\s+)(.+)",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    return " ".join(match.group(1).split()).strip(" ,;") or None


def _source_address(value: str) -> str | None:
    labeled = _source_labeled_text(value, ("anschrift", "adresse"))
    if labeled is not None:
        labeled = re.sub(
            r"^(?:lautet|ist)\s+",
            "",
            labeled,
            flags=re.IGNORECASE,
        )
        return labeled
    extracted = extract_address(value)
    if extracted is not None:
        return extracted
    cleaned = " ".join(value.split()).strip(" ,;.")
    if (
        re.search(r"\b\d+[a-zA-Z]?\b", cleaned)
        and not re.search(r"\b\d{5}\b", cleaned)
    ):
        return cleaned
    return None


def _source_district(value: str) -> str | None:
    labeled = _source_labeled_text(
        value,
        ("bezirk", "stadtteil", "ortsteil"),
    )
    if labeled is not None:
        normalized = normalize_berlin_district(labeled)
        if normalized is not None:
            return normalized
    extracted = extract_district(value)
    if extracted is not None:
        return extracted
    return normalize_berlin_district(value)


def _source_floor(value: str) -> str | None:
    labeled = _source_labeled_text(
        value,
        ("etage", "geschoss", "stockwerk", "lage"),
    )
    if labeled is not None:
        return _normalize_floor(labeled)
    extracted = extract_floor(value)
    return _normalize_floor(extracted)


def _normalize_floor(value: object) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    aliases = {
        "eg": "eg",
        "erdgeschoss": "eg",
        "dg": "dg",
        "dachgeschoss": "dg",
        "ug": "ug",
        "untergeschoss": "ug",
        "hochparterre": "hochparterre",
        "souterrain": "souterrain",
        "kellergeschoss": "kellergeschoss",
    }
    if normalized in aliases:
        return aliases[normalized]
    numeric = re.fullmatch(
        r"(-?\d+)(?:\.?\s*(?:og|obergeschoss))?",
        normalized,
    )
    if numeric:
        return numeric.group(1)
    return None


def normalize_evidence_value(
    field: str,
    quote: str | None,
) -> object | None:
    if quote is None:
        return None
    if field == "wbs":
        return display_wbs_requirement(extract_wbs_requirement(quote))
    if field in _RENT_LABELS:
        return _source_money(quote, _RENT_LABELS[field])
    if field == "rooms":
        return _source_rooms(quote)
    if field == "address":
        return _source_address(quote)
    if field == "postal_code":
        extracted = extract_postal_code(quote)
        if extracted is not None:
            return extracted
        match = re.search(r"\b(?:1[0-3]\d{3}|14[01]\d{2})\b", quote)
        return match.group(0) if match else None
    if field == "district":
        return _source_district(quote)
    if field == "floor":
        return _source_floor(quote)
    raise ValueError(f"unknown extraction field: {field}")


def normalize_snapshot_value(
    field: str,
    parser_snapshot: Mapping[str, object],
) -> object | None:
    value = parser_snapshot[SNAPSHOT_KEYS[field]]
    if field in _RENT_LABELS:
        return _snapshot_money(value)
    if field == "rooms":
        return float(value) if value is not None else None
    if field == "floor":
        return _normalize_floor(value)
    if field in {"address", "postal_code", "district"}:
        return _normalize_text(value)
    return value


def normalized_values_match(
    field: str,
    source_value: object | None,
    snapshot_value: object | None,
) -> bool:
    if field in {"address", "postal_code", "district", "floor"}:
        return _normalize_text(source_value) == snapshot_value
    return source_value == snapshot_value


def compare_extraction_to_snapshot(
    *,
    extraction: ExtractionResult,
    parser_snapshot: Mapping[str, object],
) -> DeterministicReview:
    expected_snapshot_keys = set(SNAPSHOT_KEYS.values())
    if set(parser_snapshot) != expected_snapshot_keys:
        raise ValueError("parser snapshot does not match its frozen schema")

    issues: list[ReviewIssue] = []
    for group in COMPARISON_GROUPS:
        for field in _GROUP_FIELDS[group]:
            quote = extraction.fields[field]
            snapshot_value = normalize_snapshot_value(
                field,
                parser_snapshot,
            )
            source_value = normalize_evidence_value(field, quote)
            if quote is None and snapshot_value is not None:
                issues.append(
                    ReviewIssue(
                        error_field=group,
                        source_field=field,
                        review_reason="unclear_source",
                        evidence_quote=None,
                        source_value=None,
                        snapshot_value=snapshot_value,
                    )
                )
                break
            if quote is not None and source_value is None:
                issues.append(
                    ReviewIssue(
                        error_field=group,
                        source_field=field,
                        review_reason="unclear_source",
                        evidence_quote=quote,
                        source_value=None,
                        snapshot_value=snapshot_value,
                    )
                )
                break
            if not normalized_values_match(
                field,
                source_value,
                snapshot_value,
            ):
                issues.append(
                    ReviewIssue(
                        error_field=group,
                        source_field=field,
                        review_reason="direct_mismatch",
                        evidence_quote=quote,
                        source_value=source_value,
                        snapshot_value=snapshot_value,
                    )
                )
                break

    return DeterministicReview(
        review_required=bool(issues),
        issues=tuple(issues),
    )
