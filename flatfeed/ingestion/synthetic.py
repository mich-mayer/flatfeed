from __future__ import annotations

import argparse
from dataclasses import replace
from typing import Iterable, Optional

from flatfeed.config import get_settings
from flatfeed.db.session import SessionLocal, init_db
from flatfeed.ingestion.base import (
    REMOVED_STATUS,
    SourceIngestionResult,
    SourceListing,
    mark_missing_source_listings_removed,
    save_source_listings,
    should_mark_missing_removed,
)
from flatfeed.ingestion.registry import register_source_adapter
from flatfeed.parser import parse_listing_from_text
from synthetic.generator import SyntheticListing, generate_synthetic_listings


SYNTHETIC_SOURCE_COMPANY = "FlatFeed Synthetic"
SYNTHETIC_BASE_URL = "https://demo.flatfeed.local"


def synthetic_to_source_listing(listing: SyntheticListing) -> SourceListing:
    # Parsing is fully deterministic and happens inline at ingestion, so the
    # parsed constraints travel with the listing and let it be stored already
    # marked as parsed (no separate LLM pass is needed or run).
    parsed = parse_listing_from_text(
        url=listing.url,
        title=listing.title,
        raw_text=listing.raw_text,
        image_url=listing.image_url,
        latitude=listing.truth_lat,
        longitude=listing.truth_lon,
    )
    return replace(parsed.source_listing, parsed_constraints=parsed.hidden_constraints)


def collect_synthetic_listings(*, limit: Optional[int] = None) -> list[SourceListing]:
    settings = get_settings()
    count = limit if limit is not None else settings.synthetic_listing_count
    return [
        synthetic_to_source_listing(listing)
        for listing in generate_synthetic_listings(
            seed=settings.synthetic_seed,
            count=count,
        )
    ]


def save_synthetic_listings(
    session,
    listings: Iterable[SourceListing],
) -> tuple[int, int]:
    return save_source_listings(
        session,
        source_company=SYNTHETIC_SOURCE_COMPANY,
        listings=listings,
    )


def mark_missing_synthetic_listings_removed(
    session,
    *,
    live_urls: Iterable[str],
) -> int:
    return mark_missing_source_listings_removed(
        session,
        source_company=SYNTHETIC_SOURCE_COMPANY,
        live_urls=live_urls,
    )


def sync_synthetic_listings(
    *,
    limit: Optional[int] = None,
    mark_removed: Optional[bool] = None,
) -> SourceIngestionResult:
    listings = collect_synthetic_listings(limit=limit)
    live_urls = tuple(listing.url for listing in listings)
    removed_count = 0
    with SessionLocal() as session:
        created_count, updated_count = save_synthetic_listings(session, listings)
        if should_mark_missing_removed(
            limit=limit,
            mark_removed=mark_removed,
            collection_errors=(),
        ):
            removed_count = mark_missing_synthetic_listings_removed(
                session,
                live_urls=live_urls,
            )
        session.commit()
    return SourceIngestionResult(
        saved_count=created_count + updated_count,
        created_count=created_count,
        updated_count=updated_count,
        removed_count=removed_count,
        live_urls=live_urls,
    )


def check_synthetic_listing_active(url: str) -> Optional[bool]:
    return url.startswith(f"{SYNTHETIC_BASE_URL}/listings/")


class SyntheticSourceAdapter:
    source_company = SYNTHETIC_SOURCE_COMPANY
    base_url = SYNTHETIC_BASE_URL
    removed_status = REMOVED_STATUS

    def collect(self, *, limit: Optional[int] = None) -> list[SourceListing]:
        return collect_synthetic_listings(limit=limit)

    def sync(
        self,
        *,
        limit: Optional[int] = None,
        mark_removed: Optional[bool] = None,
    ) -> SourceIngestionResult:
        return sync_synthetic_listings(limit=limit, mark_removed=mark_removed)

    def check_active(self, url: str) -> Optional[bool]:
        return check_synthetic_listing_active(url)


SYNTHETIC_ADAPTER = SyntheticSourceAdapter()
register_source_adapter(SYNTHETIC_ADAPTER)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load synthetic FlatFeed listings.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum listings to load.")
    args = parser.parse_args()
    init_db()
    result = sync_synthetic_listings(limit=args.limit)
    print(f"Saved or updated {result.saved_count} synthetic listings.")


if __name__ == "__main__":
    main()
