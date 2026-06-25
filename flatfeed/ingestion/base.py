from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, List, Optional, Protocol, Tuple, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from flatfeed.db.models import Listing
from flatfeed.listing_status import PARSED_STATUS, REMOVED_STATUS, UNPARSED_STATUS


T = TypeVar("T")
R = TypeVar("R")


@dataclass(frozen=True)
class SourceListing:
    url: str
    title: Optional[str]
    image_url: Optional[str]
    address: Optional[str]
    postal_code: Optional[str]
    district: Optional[str]
    floor: Optional[str]
    rooms: Optional[float]
    rent_kalt: Optional[int]
    rent_warm: Optional[int]
    latitude: Optional[float]
    longitude: Optional[float]
    raw_text: str
    parsed_constraints: Optional[dict] = None


@dataclass(frozen=True)
class SourceIngestionResult:
    saved_count: int
    created_count: int
    updated_count: int
    removed_count: int
    live_urls: Tuple[str, ...]
    collection_errors: Tuple[str, ...] = ()

    @property
    def is_partial(self) -> bool:
        return bool(self.collection_errors)


class SourceAdapter(Protocol):
    source_company: str
    base_url: str
    removed_status: str

    def collect(self, *, limit: Optional[int] = None) -> list[SourceListing]: ...

    def sync(
        self,
        *,
        limit: Optional[int] = None,
        mark_removed: Optional[bool] = None,
    ) -> SourceIngestionResult: ...

    def check_active(self, url: str) -> Optional[bool]: ...


def bounded_map(
    function: Callable[[T], R],
    items: Iterable[T],
    *,
    max_workers: int,
) -> List[R]:
    item_list = list(items)
    worker_count = min(max(1, max_workers), len(item_list))
    if worker_count <= 1:
        return [function(item) for item in item_list]

    with ThreadPoolExecutor(
        max_workers=worker_count,
        thread_name_prefix="source-detail",
    ) as executor:
        return list(executor.map(function, item_list))


def merge_source_listing(
    primary: SourceListing,
    fallback: SourceListing,
) -> SourceListing:
    def choose(primary_value, fallback_value):
        return primary_value if primary_value is not None else fallback_value

    return SourceListing(
        url=primary.url,
        title=choose(primary.title, fallback.title),
        image_url=choose(primary.image_url, fallback.image_url),
        address=choose(primary.address, fallback.address),
        postal_code=choose(primary.postal_code, fallback.postal_code),
        district=choose(primary.district, fallback.district),
        floor=choose(primary.floor, fallback.floor),
        rooms=choose(primary.rooms, fallback.rooms),
        rent_kalt=choose(primary.rent_kalt, fallback.rent_kalt),
        rent_warm=choose(primary.rent_warm, fallback.rent_warm),
        latitude=choose(primary.latitude, fallback.latitude),
        longitude=choose(primary.longitude, fallback.longitude),
        raw_text=primary.raw_text or fallback.raw_text,
    )


def save_source_listings(
    session: Session,
    *,
    source_company: str,
    listings: Iterable[SourceListing],
    removed_status: str = REMOVED_STATUS,
) -> Tuple[int, int]:
    created_count = 0
    updated_count = 0
    seen_at = datetime.utcnow()

    for item in listings:
        existing = session.scalar(select(Listing).where(Listing.url == item.url))
        if existing is None:
            session.add(
                Listing(
                    source_company=source_company,
                    url=item.url,
                    title=item.title,
                    image_url=item.image_url,
                    address=item.address,
                    postal_code=item.postal_code,
                    district=item.district,
                    floor=item.floor,
                    rooms=item.rooms,
                    rent_kalt=item.rent_kalt,
                    rent_warm=item.rent_warm,
                    latitude=item.latitude,
                    longitude=item.longitude,
                    raw_text=item.raw_text,
                    parsed_constraints=item.parsed_constraints,
                    source_active=True,
                    status=(
                        PARSED_STATUS
                        if item.parsed_constraints is not None
                        else UNPARSED_STATUS
                    ),
                    last_seen_at=seen_at,
                    last_checked_at=seen_at,
                )
            )
            created_count += 1
            continue

        raw_text_changed = existing.raw_text != item.raw_text
        location_changed = (
            existing.address != item.address
            or existing.postal_code != item.postal_code
        )
        coordinates_changed = (
            item.latitude is not None
            and item.longitude is not None
            and (
                existing.latitude != item.latitude
                or existing.longitude != item.longitude
            )
        )
        existing.title = item.title
        existing.image_url = item.image_url
        existing.address = item.address
        existing.postal_code = item.postal_code
        existing.district = item.district
        existing.floor = item.floor
        existing.rooms = item.rooms
        existing.rent_kalt = item.rent_kalt
        existing.rent_warm = item.rent_warm
        if item.latitude is not None and item.longitude is not None:
            existing.latitude = item.latitude
            existing.longitude = item.longitude
        elif location_changed:
            existing.latitude = None
            existing.longitude = None
        if location_changed or coordinates_changed:
            existing.transport_walk = None
        existing.raw_text = item.raw_text
        existing.source_company = source_company
        existing.source_active = True
        existing.last_seen_at = seen_at
        existing.last_checked_at = seen_at
        if item.parsed_constraints is not None:
            # Deterministic inline parse: refresh constraints and mark parsed.
            existing.parsed_constraints = item.parsed_constraints
            existing.status = PARSED_STATUS
        elif existing.status == removed_status or raw_text_changed:
            existing.status = UNPARSED_STATUS
        updated_count += 1

    return created_count, updated_count


def mark_missing_source_listings_removed(
    session: Session,
    *,
    source_company: str,
    live_urls: Iterable[str],
    removed_status: str = REMOVED_STATUS,
) -> int:
    live_url_set = set(live_urls)
    if not live_url_set:
        return 0

    statement = (
        select(Listing)
        .where(Listing.source_company == source_company)
        .where(~Listing.url.in_(live_url_set))
        .where(Listing.status != removed_status)
    )
    removed_count = 0
    checked_at = datetime.utcnow()
    for listing in session.scalars(statement):
        listing.source_active = False
        listing.status = removed_status
        listing.last_checked_at = checked_at
        removed_count += 1

    return removed_count


def should_mark_missing_removed(
    *,
    limit: Optional[int],
    mark_removed: Optional[bool],
    collection_errors: Iterable[str],
) -> bool:
    requested = (limit is None) if mark_removed is None else mark_removed
    return requested and not tuple(collection_errors)
