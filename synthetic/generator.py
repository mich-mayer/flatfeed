from __future__ import annotations

from dataclasses import dataclass

from synthetic.case_catalog import CASE_TEMPLATES, CaseTemplate
from synthetic.listing_photos import listing_photo_for_index


# Single source of truth for synthetic listing URLs. Points at a static demo
# page on GitHub Pages (docs/demo-listing.html) so the card's "Open listing"
# link resolves to something real for an external portfolio viewer, rather
# than a domain that never existed publicly. flatfeed/ingestion/synthetic.py
# imports this same constant for its local (no-network) activity check, so
# both stay in sync by construction.
SYNTHETIC_BASE_URL = "https://mich-mayer.github.io/flatfeed/demo-listing.html"


@dataclass(frozen=True)
class SyntheticListing:
    truth_wbs_display: str
    truth_wbs_allowed: tuple[int, ...]
    truth_rent_kalt_cents: int | None
    truth_rent_warm_cents: int | None
    truth_rooms: float | None
    truth_floor: str | None
    truth_bezirk: str
    truth_postal_code: str
    truth_lat: float
    truth_lon: float
    truth_seniors_only: bool
    truth_exchange_only: bool
    truth_family_only: bool
    title: str
    raw_text: str
    url: str
    image_url: str
    case_tags: tuple[str, ...]
    difficulty: str


def _listing_from_template(
    template: CaseTemplate,
    *,
    index: int,
) -> SyntheticListing:
    url = f"{SYNTHETIC_BASE_URL}?id={index:04d}"
    return SyntheticListing(
        truth_wbs_display=template.truth_wbs_display,
        truth_wbs_allowed=template.truth_wbs_allowed,
        truth_rent_kalt_cents=template.truth_rent_kalt_cents,
        truth_rent_warm_cents=template.truth_rent_warm_cents,
        truth_rooms=template.truth_rooms,
        truth_floor=template.truth_floor,
        truth_bezirk=template.truth_bezirk,
        truth_postal_code=template.postal_code,
        truth_lat=template.truth_lat,
        truth_lon=template.truth_lon,
        truth_seniors_only=template.truth_seniors_only,
        truth_exchange_only=template.truth_exchange_only,
        truth_family_only=template.truth_family_only,
        title=template.title,
        raw_text=template.raw_text,
        url=url,
        image_url=template.photo_asset or listing_photo_for_index(index),
        case_tags=(template.tag,),
        difficulty=template.difficulty,
    )


def generate_synthetic_listings(
    *,
    seed: int = 20260623,
    count: int | None = None,
) -> list[SyntheticListing]:
    _ = seed
    templates = list(CASE_TEMPLATES)
    if count is None:
        count = len(templates)
    listings: list[SyntheticListing] = []
    for index in range(count):
        template = templates[index % len(templates)]
        listings.append(_listing_from_template(template, index=index + 1))
    return listings
