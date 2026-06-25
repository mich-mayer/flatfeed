import unittest
from typing import Optional

from flatfeed.db.models import Listing
from flatfeed.matching import KALT_RENT_LABELS, WARM_RENT_LABELS, extract_rent_display, is_listing_match
from flatfeed.schemas import ListingConstraints, UserPreferences


class RentMatchingTests(unittest.TestCase):
    def make_listing(self, raw_text: str, rent_kalt: Optional[int] = None) -> Listing:
        return Listing(
            source_company="FlatFeed Synthetic",
            url="https://demo.flatfeed.local/listings/test",
            title="Wohnung ohne WBS",
            raw_text=raw_text,
            rent_kalt=rent_kalt,
            source_active=True,
            status="parsed",
        )

    def test_decimal_kaltmiete_above_limit_does_not_match(self) -> None:
        decision = is_listing_match(
            preferences=UserPreferences(wbs_type="NO_WBS", max_rent=650),
            constraints=ListingConstraints(),
            listing=self.make_listing("Kaltmiete: 650,99 €", rent_kalt=650),
        )

        self.assertFalse(decision.is_match)

    def test_decimal_kaltmiete_equal_to_limit_matches(self) -> None:
        decision = is_listing_match(
            preferences=UserPreferences(wbs_type="NO_WBS", max_rent=650),
            constraints=ListingConstraints(),
            listing=self.make_listing("Kaltmiete: 650,00 €", rent_kalt=650),
        )

        self.assertTrue(decision.is_match)

    def test_falls_back_to_stored_integer_rent_when_text_has_no_kaltmiete(self) -> None:
        decision = is_listing_match(
            preferences=UserPreferences(wbs_type="NO_WBS", max_rent=650),
            constraints=ListingConstraints(),
            listing=self.make_listing("Warmmiete: 800,00 €", rent_kalt=651),
        )

        self.assertFalse(decision.is_match)

    def test_unknown_rent_does_not_match_when_user_has_maximum(self) -> None:
        decision = is_listing_match(
            preferences=UserPreferences(wbs_type="NO_WBS", max_rent=650),
            constraints=ListingConstraints(),
            listing=self.make_listing("Miete auf Anfrage"),
        )

        self.assertFalse(decision.is_match)

    def test_unknown_rooms_do_not_match_exact_room_filter(self) -> None:
        listing = self.make_listing("Kaltmiete: 500,00 Euro", rent_kalt=500)
        listing.rooms = None

        decision = is_listing_match(
            preferences=UserPreferences(wbs_type="NO_WBS", rooms=2),
            constraints=ListingConstraints(),
            listing=listing,
        )

        self.assertFalse(decision.is_match)

    def test_display_rent_accepts_dot_decimal(self) -> None:
        self.assertEqual(
            extract_rent_display("Warmmiete: 652.85 €", ("warmmiete",)),
            "652,85 EUR",
        )

    def test_display_rent_accepts_german_thousands_and_decimal(self) -> None:
        self.assertEqual(
            extract_rent_display("Kaution: 1.365,12 €", ("kaution",)),
            "1365,12 EUR",
        )

    def test_grundmiete_keeps_cents_for_display(self) -> None:
        self.assertEqual(
            extract_rent_display("Grundmiete\n512,14 Euro", KALT_RENT_LABELS),
            "512,14 EUR",
        )

    def test_miete_inkl_nk_keeps_cents_for_display(self) -> None:
        self.assertEqual(
            extract_rent_display("Miete inkl. NK:\n469,67 €", WARM_RENT_LABELS),
            "469,67 EUR",
        )

    def test_warmmiete_prefers_amount_before_label(self) -> None:
        raw_text = "\n".join(
            (
                "946,35",
                "Euro Warmmiete",
                "45,52",
                "m²",
            )
        )

        self.assertEqual(
            extract_rent_display(raw_text, WARM_RENT_LABELS),
            "946,35 EUR",
        )

    def test_grundmiete_cents_are_used_for_matching(self) -> None:
        decision = is_listing_match(
            preferences=UserPreferences(wbs_type="NO_WBS", max_rent=512),
            constraints=ListingConstraints(),
            listing=self.make_listing("Grundmiete: 512,14 Euro", rent_kalt=512),
        )

        self.assertFalse(decision.is_match)


if __name__ == "__main__":
    unittest.main()
