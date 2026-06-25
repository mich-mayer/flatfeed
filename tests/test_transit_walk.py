import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from flatfeed.db.models import Base, Listing
from flatfeed.integrations.transit_walk import (
    TransitStation,
    compute_transit_walk_info,
    enrich_missing_transport_walk,
)


class TransitWalkTests(unittest.TestCase):
    def test_computes_minutes_to_nearest_s_and_u_bahn(self) -> None:
        stations = [
            TransitStation("S Test", "s_bahn", 52.5205, 13.405),
            TransitStation("U Test", "u_bahn", 52.52, 13.406),
        ]

        with patch(
            "flatfeed.integrations.transit_walk.load_transit_stations",
            return_value=stations,
        ):
            info = compute_transit_walk_info(latitude=52.52, longitude=13.405)

        self.assertEqual(info.s_bahn_station, "S Test")
        self.assertEqual(info.u_bahn_station, "U Test")
        self.assertEqual(info.s_bahn_minutes, 1)
        self.assertEqual(info.u_bahn_minutes, 2)

    def test_enrichment_uses_existing_coordinates_and_persists_walk_info(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        test_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        with test_session() as session:
            session.add(
                Listing(
                    source_company="FlatFeed Synthetic",
                    url="https://example.test/listing/1",
                    address="Teststr. 1",
                    postal_code="10115",
                    latitude=52.52,
                    longitude=13.405,
                    raw_text="Test",
                    source_active=True,
                    status="parsed",
                )
            )
            session.commit()

        stations = [
            TransitStation("S Test", "s_bahn", 52.5205, 13.405),
            TransitStation("U Test", "u_bahn", 52.52, 13.406),
        ]

        with patch(
            "flatfeed.integrations.transit_walk.SessionLocal",
            test_session,
        ), patch(
            "flatfeed.integrations.transit_walk.load_transit_stations",
            return_value=stations,
        ):
            count = enrich_missing_transport_walk()

        with Session(engine) as session:
            listing = session.scalar(select(Listing))
            assert listing is not None
            self.assertEqual(count, 1)
            self.assertEqual(listing.latitude, 52.52)
            self.assertEqual(listing.longitude, 13.405)
            self.assertEqual(listing.transport_walk["s_bahn_station"], "S Test")
            self.assertEqual(listing.transport_walk["u_bahn_station"], "U Test")

        engine.dispose()
