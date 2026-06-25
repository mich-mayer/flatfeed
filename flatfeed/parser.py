from __future__ import annotations

import re
from dataclasses import dataclass

from flatfeed.ingestion.base import SourceListing
from flatfeed.listing_metadata import extract_listing_metadata
from flatfeed.matching import display_wbs_options_for_listing_text
from flatfeed.schemas import ListingConstraints
from flatfeed.wbs_rules import WBSRequirement, extract_wbs_requirement


@dataclass(frozen=True)
class ParsedListing:
    source_listing: SourceListing
    wbs_requirement: WBSRequirement
    display_wbs: str
    hidden_constraints: dict[str, object]


_NEGATION_BEFORE_RE = re.compile(
    r"(?:kein(?:e|en|er|es|em)?|nicht|ohne|no|not)\s+(?:\S+\s+){0,3}$",
    flags=re.IGNORECASE,
)
_NEGATION_AFTER_RE = re.compile(
    r"^\s+(?:ist\s+)?(?:nicht|not|kein(?:e|en|er|es|em)?)\s+"
    r"(?:erforderlich|notwendig|required|needed)",
    flags=re.IGNORECASE,
)


def _is_negated_marker(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 60) : start]
    suffix = text[end : end + 60]
    return bool(_NEGATION_BEFORE_RE.search(prefix) or _NEGATION_AFTER_RE.search(suffix))


def _contains_positive_marker(text: str, *markers: str) -> bool:
    lowered = text.lower()
    for marker in markers:
        marker_lower = marker.lower()
        for match in re.finditer(re.escape(marker_lower), lowered):
            if not _is_negated_marker(lowered, match.start(), match.end()):
                return True
    return False


def extract_listing_constraints(*, title: str | None, raw_text: str) -> ListingConstraints:
    """Deterministically extract hidden landlord constraints from listing text.

    No LLM is involved: WBS comes from ``wbs_rules`` and the remaining flags from
    negation-aware keyword matching. AI QA (``flatfeed/ai_qa.py``) is the only
    AI surface in this project and it merely audits this output, never replaces it.
    """
    text = f"{title or ''}\n{raw_text}"
    return ListingConstraints(
        required_wbs=extract_wbs_requirement(text).required_wbs,
        seniors_only=_contains_positive_marker(
            text,
            "ab 60 jahre",
            "ab 60",
            "60+",
            "senior",
            "senioren",
            "senior*innen",
        ),
        exchange_only_tauschwohnung=_contains_positive_marker(
            text,
            "tauschwohnung",
            "wohnungstausch",
            "nur im tausch",
            "im tausch",
        ),
        family_only=_contains_positive_marker(
            text,
            "nur für familien",
            "familienwohnung",
            "familie mit kind",
            "familien mit kind",
            "mehrpersonenhaushalt",
        ),
    )


def parse_listing_from_text(
    *,
    url: str,
    title: str | None,
    raw_text: str,
    image_url: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> ParsedListing:
    text = f"{title or ''}\n{raw_text or ''}".strip()
    metadata = extract_listing_metadata(title=title, raw_text=raw_text)
    requirement = extract_wbs_requirement(text)
    constraints = extract_listing_constraints(title=title, raw_text=raw_text).model_copy(
        update={"required_wbs": requirement.required_wbs}
    )
    source_listing = SourceListing(
        url=url,
        title=title,
        image_url=image_url,
        address=metadata.address,
        postal_code=metadata.postal_code,
        district=metadata.district,
        floor=metadata.floor,
        rooms=metadata.rooms,
        rent_kalt=metadata.rent_kalt,
        rent_warm=metadata.rent_warm,
        latitude=latitude,
        longitude=longitude,
        raw_text=raw_text,
    )
    return ParsedListing(
        source_listing=source_listing,
        wbs_requirement=requirement,
        display_wbs=display_wbs_options_for_listing_text(
            parsed_required_wbs=constraints.required_wbs,
            listing_title=title,
            listing_text=raw_text,
        ),
        hidden_constraints=constraints.model_dump(mode="json"),
    )
