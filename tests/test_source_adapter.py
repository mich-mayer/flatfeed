import unittest
from threading import Lock
from time import sleep

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from flatfeed.db.models import Base, Listing
from flatfeed.ingestion import (
    SYNTHETIC_ADAPTER,
    SYNTHETIC_SOURCE_COMPANY,
    get_source_adapter,
    list_source_adapters,
)
from flatfeed.ingestion.base import (
    REMOVED_STATUS,
    UNPARSED_STATUS,
    SourceListing,
    bounded_map,
    mark_missing_source_listings_removed,
    merge_source_listing,
    save_source_listings,
)


class BoundedMapTests(unittest.TestCase):
    def test_preserves_order_and_respects_worker_limit(self) -> None:
        lock = Lock()
        active = 0
        maximum_active = 0

        def work(value: int) -> int:
            nonlocal active, maximum_active
            with lock:
                active += 1
                maximum_active = max(maximum_active, active)
            sleep(0.02)
            with lock:
                active -= 1
            return value * 10

        result = bounded_map(work, [1, 2, 3, 4], max_workers=2)

        self.assertEqual(result, [10, 20, 30, 40])
        self.assertEqual(maximum_active, 2)

    def test_empty_input_does_not_start_executor(self) -> None:
        self.assertEqual(bounded_map(lambda value: value, [], max_workers=4), [])


class SourceAdapterRegistryTests(unittest.TestCase):
    def test_enabled_source_adapters_are_registered(self) -> None:
        self.assertEqual(
            {adapter.source_company for adapter in list_source_adapters()},
            {SYNTHETIC_SOURCE_COMPANY},
        )
        self.assertIs(get_source_adapter(SYNTHETIC_SOURCE_COMPANY), SYNTHETIC_ADAPTER)


class SourcePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    @staticmethod
    def make_listing(url: str, *, raw_text: str = "initial") -> SourceListing:
        return SourceListing(
            url=url,
            title="Test listing",
            image_url=None,
            address="Teststr. 1",
            postal_code="10115",
            district="Mitte",
            floor="2",
            rooms=2.0,
            rent_kalt=50000,
            rent_warm=65000,
            latitude=None,
            longitude=None,
            raw_text=raw_text,
        )

    def test_save_reactivates_removed_listing_and_resets_parse_state(self) -> None:
        url = "https://example.test/listing/1"
        with Session(self.engine) as session:
            created, updated = save_source_listings(
                session,
                source_company="Example",
                listings=[self.make_listing(url)],
            )
            session.flush()
            listing = session.scalar(select(Listing).where(Listing.url == url))
            self.assertIsNotNone(listing)
            assert listing is not None
            listing.source_active = False
            listing.status = REMOVED_STATUS

            created_again, updated_again = save_source_listings(
                session,
                source_company="Example",
                listings=[self.make_listing(url, raw_text="updated")],
            )
            session.flush()

            self.assertEqual((created, updated), (1, 0))
            self.assertEqual((created_again, updated_again), (0, 1))
            self.assertTrue(listing.source_active)
            self.assertEqual(listing.status, UNPARSED_STATUS)

    def test_mark_missing_only_changes_requested_source(self) -> None:
        example_live = "https://example.test/listing/live"
        example_missing = "https://example.test/listing/missing"
        other_source = "https://other.test/listing/missing"

        with Session(self.engine) as session:
            save_source_listings(
                session,
                source_company="Example",
                listings=[
                    self.make_listing(example_live),
                    self.make_listing(example_missing),
                ],
            )
            save_source_listings(
                session,
                source_company="Other",
                listings=[self.make_listing(other_source)],
            )
            session.flush()

            removed_count = mark_missing_source_listings_removed(
                session,
                source_company="Example",
                live_urls=[example_live],
            )
            session.flush()

            listings = {
                listing.url: listing
                for listing in session.scalars(select(Listing)).all()
            }
            self.assertEqual(removed_count, 1)
            self.assertTrue(listings[example_live].source_active)
            self.assertFalse(listings[example_missing].source_active)
            self.assertEqual(listings[example_missing].status, REMOVED_STATUS)
            self.assertTrue(listings[other_source].source_active)
            self.assertEqual(listings[other_source].status, UNPARSED_STATUS)

    def test_merge_keeps_detail_values_and_fills_missing_index_values(self) -> None:
        fallback = self.make_listing("https://example.test/listing/1")
        primary = SourceListing(
            url=fallback.url,
            title="Detail title",
            image_url=None,
            address="Detailstr. 2",
            postal_code=None,
            district=None,
            floor="4",
            rooms=1.0,
            rent_kalt=45000,
            rent_warm=55000,
            latitude=None,
            longitude=None,
            raw_text="detail",
        )

        merged = merge_source_listing(primary, fallback)

        self.assertEqual(merged.title, "Detail title")
        self.assertEqual(merged.address, "Detailstr. 2")
        self.assertEqual(merged.postal_code, "10115")
        self.assertEqual(merged.district, "Mitte")
        self.assertEqual(merged.floor, "4")
        self.assertEqual(merged.raw_text, "detail")

    def test_save_preserves_enriched_coordinates_when_source_has_none(self) -> None:
        url = "https://example.test/listing/coordinates"
        with Session(self.engine) as session:
            save_source_listings(
                session,
                source_company="Example",
                listings=[self.make_listing(url)],
            )
            session.flush()
            listing = session.scalar(select(Listing).where(Listing.url == url))
            assert listing is not None
            listing.latitude = 52.52
            listing.longitude = 13.40
            listing.transport_walk = {"s_bahn_minutes": 5}

            save_source_listings(
                session,
                source_company="Example",
                listings=[self.make_listing(url, raw_text="updated")],
            )
            session.flush()

            self.assertEqual(listing.latitude, 52.52)
            self.assertEqual(listing.longitude, 13.40)
            self.assertEqual(listing.transport_walk, {"s_bahn_minutes": 5})


if __name__ == "__main__":
    unittest.main()
