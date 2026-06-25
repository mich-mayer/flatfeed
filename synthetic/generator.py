from __future__ import annotations

from dataclasses import dataclass
import random

from synthetic.case_catalog import CASE_TEMPLATES, CaseTemplate
from synthetic.listing_photos import listing_photo_for_index


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


DISTRICT_COORDINATES = {
    "Mitte": (52.5200, 13.4050),
    "Friedrichshain-Kreuzberg": (52.5008, 13.4447),
    "Pankow": (52.5692, 13.4023),
    "Charlottenburg-Wilmersdorf": (52.5079, 13.2637),
    "Spandau": (52.5358, 13.1978),
    "Steglitz-Zehlendorf": (52.4309, 13.1927),
    "Tempelhof-Schöneberg": (52.4575, 13.3851),
    "Neukölln": (52.4811, 13.4353),
    "Treptow-Köpenick": (52.4179, 13.6002),
    "Marzahn-Hellersdorf": (52.5228, 13.5877),
    "Lichtenberg": (52.5155, 13.4995),
    "Reinickendorf": (52.6048, 13.2951),
}


def _coordinates(template: CaseTemplate, rng: random.Random) -> tuple[float, float]:
    base_lat, base_lon = DISTRICT_COORDINATES[template.truth_bezirk]
    return (
        round(base_lat + rng.uniform(-0.015, 0.015), 6),
        round(base_lon + rng.uniform(-0.015, 0.015), 6),
    )


def _listing_from_template(
    template: CaseTemplate,
    *,
    index: int,
    rng: random.Random,
) -> SyntheticListing:
    latitude, longitude = _coordinates(template, rng)
    url = f"https://demo.flatfeed.local/listings/{index:04d}"
    return SyntheticListing(
        truth_wbs_display=template.truth_wbs_display,
        truth_wbs_allowed=template.truth_wbs_allowed,
        truth_rent_kalt_cents=template.truth_rent_kalt_cents,
        truth_rent_warm_cents=template.truth_rent_warm_cents,
        truth_rooms=template.truth_rooms,
        truth_floor=template.truth_floor,
        truth_bezirk=template.truth_bezirk,
        truth_postal_code=template.postal_code,
        truth_lat=latitude,
        truth_lon=longitude,
        truth_seniors_only=template.truth_seniors_only,
        truth_exchange_only=template.truth_exchange_only,
        truth_family_only=template.truth_family_only,
        title=template.title,
        raw_text=template.raw_text,
        url=url,
        image_url=listing_photo_for_index(index),
        case_tags=(template.tag,),
        difficulty=template.difficulty,
    )


def generate_synthetic_listings(
    *,
    seed: int = 20260623,
    count: int | None = None,
) -> list[SyntheticListing]:
    rng = random.Random(seed)
    templates = list(CASE_TEMPLATES)
    if count is None:
        count = len(templates)
    listings: list[SyntheticListing] = []
    for index in range(count):
        template = templates[index % len(templates)]
        listings.append(_listing_from_template(template, index=index + 1, rng=rng))
    return listings
