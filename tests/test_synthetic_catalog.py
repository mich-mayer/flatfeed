import unittest
from pathlib import Path

from synthetic.case_catalog import CASE_TEMPLATES
from synthetic.listing_photos import LISTING_PHOTO_ASSETS, listing_photo_assets_exist
from synthetic.generator import generate_synthetic_listings
from flatfeed.integrations.transit_walk import compute_transit_walk_info
from flatfeed.parser import parse_listing_from_text


class SyntheticCatalogTests(unittest.TestCase):
    def test_listing_urls_do_not_include_case_tags(self) -> None:
        listings = generate_synthetic_listings(count=3)

        for listing in listings:
            for tag in listing.case_tags:
                self.assertNotIn(tag, listing.url)

    def test_synthetic_listings_have_stable_local_photo_assets(self) -> None:
        listings = generate_synthetic_listings(count=len(LISTING_PHOTO_ASSETS) + 1)

        expected = list(LISTING_PHOTO_ASSETS)
        expected[0] = CASE_TEMPLATES[0].photo_asset
        self.assertEqual(
            [listing.image_url for listing in listings[: len(LISTING_PHOTO_ASSETS)]],
            expected,
        )
        self.assertEqual(listings[-1].image_url, LISTING_PHOTO_ASSETS[0])
        self.assertTrue(listing_photo_assets_exist(Path(__file__).resolve().parents[1]))

    def test_showcase_listing_photo_matches_its_real_location(self) -> None:
        listing = generate_synthetic_listings(count=1)[0]

        self.assertIn("Suermondtstr. 56-64", listing.raw_text)
        self.assertEqual(listing.truth_postal_code, "13053")
        self.assertEqual(listing.truth_bezirk, "Lichtenberg")
        self.assertEqual(
            listing.image_url,
            "assets/listing_photos/berlin_hohenschoenhausen_suermondtstr_wohnblock.jpg",
        )

    def test_all_case_templates_drive_address_level_coordinates(self) -> None:
        for template in CASE_TEMPLATES:
            with self.subTest(template=template.tag):
                self.assertIsNotNone(template.truth_lat)
                self.assertIsNotNone(template.truth_lon)
                self.assertGreaterEqual(template.truth_lat, 52.3)
                self.assertLessEqual(template.truth_lat, 52.7)
                self.assertGreaterEqual(template.truth_lon, 13.0)
                self.assertLessEqual(template.truth_lon, 13.8)

        listings = generate_synthetic_listings(count=len(CASE_TEMPLATES) * 2)
        expected_coordinates = [
            (template.truth_lat, template.truth_lon)
            for template in CASE_TEMPLATES
        ] * 2

        self.assertEqual(
            [(listing.truth_lat, listing.truth_lon) for listing in listings],
            expected_coordinates,
        )

    def test_parser_reads_basic_wbs_and_metadata_from_synthetic_listing(self) -> None:
        listing = generate_synthetic_listings(count=1)[0]

        parsed = parse_listing_from_text(
            url=listing.url,
            title=listing.title,
            raw_text=listing.raw_text,
            image_url=listing.image_url,
            latitude=listing.truth_lat,
            longitude=listing.truth_lon,
        )
        source = parsed.source_listing

        self.assertEqual(parsed.display_wbs, listing.truth_wbs_display)
        self.assertEqual(parsed.wbs_requirement.allowed_percentages, listing.truth_wbs_allowed)
        self.assertEqual(source.district, listing.truth_bezirk)
        self.assertEqual(source.postal_code, listing.truth_postal_code)
        self.assertEqual(source.rooms, listing.truth_rooms)
        self.assertEqual(source.image_url, listing.image_url)

    def test_greifswalder_family_listing_uses_address_level_coordinates(self) -> None:
        listing = next(
            listing
            for listing in generate_synthetic_listings()
            if "Greifswalder Str. 210" in listing.raw_text
        )

        walk_info = compute_transit_walk_info(
            latitude=listing.truth_lat,
            longitude=listing.truth_lon,
        )

        self.assertEqual(walk_info.s_bahn_station, "Greifswalder Str.")
        self.assertEqual(walk_info.u_bahn_station, "Senefelderplatz")
        self.assertGreaterEqual(walk_info.s_bahn_minutes or 0, 15)


if __name__ == "__main__":
    unittest.main()
