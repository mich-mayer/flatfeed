import unittest

from flatfeed.listing_metadata import (
    address_diagnostics,
    extract_address,
    extract_berlin_coordinates,
    extract_district,
    extract_floor,
    extract_rent,
    extract_rooms,
    extract_postal_code,
    normalize_berlin_district,
)


class ListingMetadataTests(unittest.TestCase):
    def test_extract_floor_before_etagenzahl(self) -> None:
        self.assertEqual(
            extract_floor("Etage:\n3\nEtagenzahl:\n6\nZimmer:\n2"),
            "3",
        )

    def test_does_not_use_etagenzahl_as_floor(self) -> None:
        self.assertIsNone(extract_floor("Etage:\nEtagenzahl:\n6\nZimmer:\n2"))

    def test_extracts_og_floor(self) -> None:
        self.assertEqual(extract_floor("Wohnung im 3. OG"), "3")

    def test_personen_haushalt_is_not_room_count(self) -> None:
        self.assertIsNone(
            extract_rooms("Für die Anmietung ist ein WBS ab 160 für 3 Personenhaushalt erforderlich")
        )

    def test_extract_rooms_from_labelled_multiline_block(self) -> None:
        self.assertEqual(extract_rooms("Etage\n5\nZimmer\n2\nKaltmiete: 681,90 €"), 2.0)

    def test_extract_rent_accepts_dot_decimal(self) -> None:
        self.assertEqual(extract_rent("Warmmiete: 652.85 €", ("warmmiete",)), 652)

    def test_extract_rent_accepts_german_thousands_and_decimal(self) -> None:
        self.assertEqual(extract_rent("Kaution: 1.365,12 €", ("kaution",)), 1365)

    def test_extract_address_from_explicit_address_block(self) -> None:
        self.assertEqual(
            extract_address(
                "Adresse:\n"
                "Straße am Flugplatz 65 A,\n"
                "12487 Berlin, Johannisthal\n"
                "Objektdetails"
            ),
            "Straße am Flugplatz 65 A",
        )

    def test_address_diagnostics_marks_explicit_address_block_ok(self) -> None:
        diagnostics = address_diagnostics(
            "Adresse:\n"
            "Straße am Flugplatz 65 A,\n"
            "12487 Berlin, Johannisthal\n"
        )

        self.assertEqual(diagnostics.address, "Straße am Flugplatz 65 A")
        self.assertEqual(diagnostics.source, "explicit_address_block")
        self.assertEqual(diagnostics.sanity_status, "ok")

    def test_address_diagnostics_marks_fallback_address_warning(self) -> None:
        diagnostics = address_diagnostics(
            "Objektbeschreibung\n"
            "Die Wohnung befindet sich in der Beispielstraße 12.\n"
            "12487 Berlin\n"
        )

        self.assertEqual(diagnostics.address, "Beispielstraße 12")
        self.assertEqual(diagnostics.source, "fallback_regex")
        self.assertEqual(diagnostics.sanity_status, "warning")

    def test_extracts_berlin_postal_code_near_address(self) -> None:
        self.assertEqual(
            extract_postal_code("Adresse: Daumstr. 62, 13599 Berlin"),
            "13599",
        )

    def test_does_not_treat_listing_number_as_berlin_postal_code(self) -> None:
        self.assertIsNone(extract_postal_code("Objekt-Nr. 1771-14536-9997"))

    def test_extracts_html_map_coordinates(self) -> None:
        self.assertEqual(
            extract_berlin_coordinates(
                '<div class="map" data-lat="52.4253353" data-long="13.5877607">'
            ),
            (52.4253353, 13.5877607),
        )

    def test_rejects_coordinates_outside_berlin(self) -> None:
        self.assertEqual(
            extract_berlin_coordinates(
                '<div data-lat="48.137154" data-long="11.576124">'
            ),
            (None, None),
        )

    def test_hohenschoenhausen_maps_to_lichtenberg_bezirk(self) -> None:
        self.assertEqual(normalize_berlin_district("Alt-Hohenschönhausen"), "Lichtenberg")
        self.assertEqual(normalize_berlin_district("Neu-Hohenschönhausen"), "Lichtenberg")
        self.assertEqual(normalize_berlin_district("Hohenschönhausen"), "Lichtenberg")
        self.assertEqual(normalize_berlin_district("Hohenschoenhausen"), "Lichtenberg")

    def test_extract_district_uses_bezirk_for_hohenschoenhausen_address(self) -> None:
        self.assertEqual(
            extract_district("Adresse: 13055 Berlin, Hohenschönhausen"),
            "Lichtenberg",
        )

    def test_joachim_ringelnatz_siedlung_maps_to_marzahn_hellersdorf(self) -> None:
        self.assertEqual(
            normalize_berlin_district("Joachim-Ringelnatz-Siedlung"),
            "Marzahn-Hellersdorf",
        )

    def test_named_neighborhoods_map_to_bezirke(self) -> None:
        self.assertEqual(normalize_berlin_district("Adlershof West"), "Treptow-Köpenick")
        self.assertEqual(normalize_berlin_district("Buckower Felder"), "Neukölln")
        self.assertEqual(
            normalize_berlin_district("Kaulsdorf-Nord II"),
            "Marzahn-Hellersdorf",
        )


if __name__ == "__main__":
    unittest.main()
