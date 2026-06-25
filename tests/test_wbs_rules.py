import unittest

from flatfeed.db.models import Listing
from flatfeed.matching import is_listing_match
from flatfeed.schemas import ListingConstraints, UserPreferences
from flatfeed.wbs_rules import display_wbs_requirement, extract_wbs_requirement


class WBSRequirementTests(unittest.TestCase):
    def assert_display(self, text: str, expected: str) -> None:
        requirement = extract_wbs_requirement(text)
        self.assertEqual(display_wbs_requirement(requirement), expected)

    def test_parenthesized_wbs_range(self) -> None:
        self.assert_display("Ihr neues zu Hause mit WBS (100-140)", "100, 140")

    def test_exclusive_lower_range(self) -> None:
        self.assert_display("3-Zimmer-Wohnung mit WBS größer140-180", "160, 180")

    def test_full_wbs_term_range_above_140(self) -> None:
        self.assert_display(
            "Benötigt wird ein Wohnberechtigungsschein 141-220 %.",
            "160, 180, 220",
        )

    def test_decimal_income_range_excludes_140(self) -> None:
        self.assert_display("Einkommensgrenze 140,01 % - 220%", "160, 180, 220")

    def test_explicit_no_wbs(self) -> None:
        self.assert_display("3-Zimmer Wohnung - Neubau Zweitbezug - ohne WBS", "No WBS required")

    def test_generic_wbs_requirement(self) -> None:
        self.assert_display("WBS erforderlich", "WBS required, type unknown")

    def test_explicit_german_yes_requires_generic_wbs(self) -> None:
        self.assert_display("WBS: ja", "WBS required, type unknown")

    def test_listing_with_wbs_requires_generic_wbs(self) -> None:
        self.assert_display(
            "Familienwohnung mit WBS - Venusstr. 22",
            "WBS required, type unknown",
        )

    def test_application_with_wbs_not_possible_is_not_generic_requirement(self) -> None:
        self.assert_display("Bewerbung mit WBS nicht möglich", "No WBS required")

    def test_explicit_german_no_does_not_require_wbs(self) -> None:
        self.assert_display("WBS: nein", "No WBS required")


class WBSMatchingTests(unittest.TestCase):
    def make_listing(self, *, title: str, raw_text: str) -> Listing:
        return Listing(
            source_company="FlatFeed Synthetic",
            url="https://demo.flatfeed.local/listings/test",
            title=title,
            raw_text=raw_text,
            rent_kalt=1000,
            source_active=True,
            status="parsed",
        )

    def test_wbs_220_does_not_match_100_140_listing(self) -> None:
        preferences = UserPreferences(wbs_type="WBS 220", max_rent=2000)
        listing = self.make_listing(
            title="Ihr neues zu Hause mit WBS (100-140)",
            raw_text="WBS erforderlich!",
        )

        decision = is_listing_match(
            preferences=preferences,
            constraints=ListingConstraints(),
            listing=listing,
        )

        self.assertFalse(decision.is_match)

    def test_wbs_140_matches_100_140_listing(self) -> None:
        preferences = UserPreferences(wbs_type="WBS 140", max_rent=2000)
        listing = self.make_listing(
            title="Ihr neues zu Hause mit WBS (100-140)",
            raw_text="WBS erforderlich!",
        )

        decision = is_listing_match(
            preferences=preferences,
            constraints=ListingConstraints(),
            listing=listing,
        )

        self.assertTrue(decision.is_match)


if __name__ == "__main__":
    unittest.main()
