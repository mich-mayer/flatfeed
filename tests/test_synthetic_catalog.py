import unittest
from pathlib import Path

from synthetic.listing_photos import LISTING_PHOTO_ASSETS, listing_photo_assets_exist
from synthetic.generator import generate_synthetic_listings
from flatfeed.parser import parse_listing_from_text


class SyntheticCatalogTests(unittest.TestCase):
    def test_listing_urls_do_not_include_case_tags(self) -> None:
        listings = generate_synthetic_listings(count=3)

        for listing in listings:
            for tag in listing.case_tags:
                self.assertNotIn(tag, listing.url)

    def test_synthetic_listings_have_stable_local_photo_assets(self) -> None:
        listings = generate_synthetic_listings(count=len(LISTING_PHOTO_ASSETS) + 1)

        self.assertEqual(
            [listing.image_url for listing in listings[: len(LISTING_PHOTO_ASSETS)]],
            list(LISTING_PHOTO_ASSETS),
        )
        self.assertEqual(listings[-1].image_url, LISTING_PHOTO_ASSETS[0])
        self.assertTrue(listing_photo_assets_exist(Path(__file__).resolve().parents[1]))

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


if __name__ == "__main__":
    unittest.main()
