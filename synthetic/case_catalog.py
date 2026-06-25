from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaseTemplate:
    tag: str
    difficulty: str
    district: str
    postal_code: str
    title: str
    raw_text: str
    truth_wbs_display: str
    truth_wbs_allowed: tuple[int, ...]
    truth_rent_kalt_cents: int | None
    truth_rent_warm_cents: int | None
    truth_rooms: float | None
    truth_floor: str | None
    truth_bezirk: str
    truth_seniors_only: bool = False
    truth_exchange_only: bool = False
    truth_family_only: bool = False


CASE_TEMPLATES: tuple[CaseTemplate, ...] = (
    CaseTemplate(
        tag="wbs_range_standard",
        difficulty="easy",
        district="Lichtenberg",
        postal_code="10315",
        title="2-Zimmer-Wohnung mit WBS 100-140",
        raw_text=(
            "Adresse\nRosenfelder Str. 12\n10315 Berlin, Friedrichsfelde\n"
            "Etage\n2\nZimmer\n2\nKaltmiete: 512,40 Euro\nWarmmiete: 690,20 Euro\n"
            "Für die Bewerbung ist ein WBS 100-140 erforderlich."
        ),
        truth_wbs_display="100, 140",
        truth_wbs_allowed=(100, 140),
        truth_rent_kalt_cents=51240,
        truth_rent_warm_cents=69020,
        truth_rooms=2.0,
        truth_floor="2",
        truth_bezirk="Lichtenberg",
    ),
    CaseTemplate(
        tag="wbs_range_above_140",
        difficulty="hard",
        district="Pankow",
        postal_code="13187",
        title="Familienwohnung in Pankow",
        raw_text=(
            "Adresse\nFlorastr. 44\n13187 Berlin, Pankow\nEtage: 4\n"
            "Zimmeranzahl: 3\nNettokaltmiete 760,00 €\nGesamtmiete 930,50 €\n"
            "Benötigt wird ein Wohnberechtigungsschein 141-220 %."
        ),
        truth_wbs_display="160, 180, 220",
        truth_wbs_allowed=(160, 180, 220),
        truth_rent_kalt_cents=76000,
        truth_rent_warm_cents=93050,
        truth_rooms=3.0,
        truth_floor="4",
        truth_bezirk="Pankow",
        truth_family_only=True,
    ),
    CaseTemplate(
        tag="wbs_upper_bound",
        difficulty="medium",
        district="Mitte",
        postal_code="13353",
        title="Kompakte Wohnung in Wedding",
        raw_text=(
            "Lage: Wedding\n13353 Berlin\nAdresse: Ackerstr. 8\n"
            "1 Zimmer, 1. Etage\nKaltmiete 430,00 EUR\nWarmmiete 555,00 EUR\n"
            "Bewerbung bis WBS 140 möglich."
        ),
        truth_wbs_display="100, 140",
        truth_wbs_allowed=(100, 140),
        truth_rent_kalt_cents=43000,
        truth_rent_warm_cents=55500,
        truth_rooms=1.0,
        truth_floor="1",
        truth_bezirk="Mitte",
    ),
    CaseTemplate(
        tag="wbs_lower_bound",
        difficulty="medium",
        district="Treptow-Köpenick",
        postal_code="12489",
        title="Helle Wohnung Berlin-Adlershof",
        raw_text=(
            "Ortsteil: Adlershof\nAdresse\nDörpfeldstr. 21\n12489 Berlin\n"
            "3 Zimmer\nGeschoss: 3\nGrundmiete: 688,75 €\nWarmmiete: 842,10 €\n"
            "Voraussetzung: WBS ab 160."
        ),
        truth_wbs_display="160, 180, 220",
        truth_wbs_allowed=(160, 180, 220),
        truth_rent_kalt_cents=68875,
        truth_rent_warm_cents=84210,
        truth_rooms=3.0,
        truth_floor="3",
        truth_bezirk="Treptow-Köpenick",
    ),
    CaseTemplate(
        tag="wbs_income_range",
        difficulty="hard",
        district="Neukölln",
        postal_code="12055",
        title="Neubauwohnung mit Förderweg",
        raw_text=(
            "Adresse\nDonaustr. 92\n12055 Berlin, Neukölln\n"
            "Etage\n5\nZimmer\n2\nKaltmiete: 681,90 €\nBruttowarmmiete: 829,70 €\n"
            "Förderweg: Einkommensgrenze 140,01 % - 220 %."
        ),
        truth_wbs_display="160, 180, 220",
        truth_wbs_allowed=(160, 180, 220),
        truth_rent_kalt_cents=68190,
        truth_rent_warm_cents=82970,
        truth_rooms=2.0,
        truth_floor="5",
        truth_bezirk="Neukölln",
    ),
    CaseTemplate(
        tag="wbs_generic",
        difficulty="easy",
        district="Spandau",
        postal_code="13585",
        title="Wohnung nur mit WBS",
        raw_text=(
            "Adresse\nNeuendorfer Str. 64\n13585 Berlin, Spandau\n"
            "Etage: EG\n2 Zimmer\nKaltmiete: 520 €\nWarmmiete: 672 €\n"
            "Für diese Wohnung ist ein WBS erforderlich."
        ),
        truth_wbs_display="WBS required, type unknown",
        truth_wbs_allowed=(),
        truth_rent_kalt_cents=52000,
        truth_rent_warm_cents=67200,
        truth_rooms=2.0,
        truth_floor="EG",
        truth_bezirk="Spandau",
    ),
    CaseTemplate(
        tag="wbs_negated",
        difficulty="medium",
        district="Charlottenburg-Wilmersdorf",
        postal_code="10585",
        title="Freifinanzierte Wohnung ohne WBS",
        raw_text=(
            "Adresse\nKaiser-Friedrich-Str. 33\n10585 Berlin, Charlottenburg\n"
            "Zimmer: 2\nEtage: 2\nNettokaltmiete: 890,00 €\nWarmmiete: 1040,00 €\n"
            "Freifinanziert, WBS nicht erforderlich."
        ),
        truth_wbs_display="No WBS required",
        truth_wbs_allowed=(),
        truth_rent_kalt_cents=89000,
        truth_rent_warm_cents=104000,
        truth_rooms=2.0,
        truth_floor="2",
        truth_bezirk="Charlottenburg-Wilmersdorf",
    ),
    CaseTemplate(
        tag="wbs_not_mentioned",
        difficulty="easy",
        district="Tempelhof-Schöneberg",
        postal_code="12103",
        title="Ruhige Wohnung am Tempelhofer Feld",
        raw_text=(
            "Adresse\nManfred-von-Richthofen-Str. 18\n12103 Berlin, Tempelhof\n"
            "2 Zimmer\nEtage: 1\nKaltmiete: 745,00 €\nWarmmiete: 910,00 €"
        ),
        truth_wbs_display="No WBS required",
        truth_wbs_allowed=(),
        truth_rent_kalt_cents=74500,
        truth_rent_warm_cents=91000,
        truth_rooms=2.0,
        truth_floor="1",
        truth_bezirk="Tempelhof-Schöneberg",
    ),
    CaseTemplate(
        tag="wbs_list",
        difficulty="medium",
        district="Marzahn-Hellersdorf",
        postal_code="12679",
        title="Wohnung in Marzahn mit WBS 100, 140 oder 160",
        raw_text=(
            "Adresse\nAllee der Kosmonauten 145\n12679 Berlin, Marzahn\n"
            "Etage: 8\nZimmer: 3\nKaltmiete 612,34 €\nGesamtmiete 780,00 €\n"
            "Akzeptiert werden WBS 100, 140 oder 160."
        ),
        truth_wbs_display="100, 140, 160",
        truth_wbs_allowed=(100, 140, 160),
        truth_rent_kalt_cents=61234,
        truth_rent_warm_cents=78000,
        truth_rooms=3.0,
        truth_floor="8",
        truth_bezirk="Marzahn-Hellersdorf",
    ),
    CaseTemplate(
        tag="price_kalt_missing",
        difficulty="hard",
        district="Reinickendorf",
        postal_code="13437",
        title="Wohnung in Wittenau",
        raw_text=(
            "Adresse\nOranienburger Str. 202\n13437 Berlin, Wittenau\n"
            "Zimmer: 2\nEtage: 3\nWarmmiete: 720,00 €\n"
            "WBS 100 erforderlich."
        ),
        truth_wbs_display="100",
        truth_wbs_allowed=(100,),
        truth_rent_kalt_cents=None,
        truth_rent_warm_cents=72000,
        truth_rooms=2.0,
        truth_floor="3",
        truth_bezirk="Reinickendorf",
    ),
    CaseTemplate(
        tag="rooms_household_trap",
        difficulty="hard",
        district="Lichtenberg",
        postal_code="10367",
        title="Wohnung für 3-Personenhaushalt",
        raw_text=(
            "Adresse\nFrankfurter Allee 190\n10367 Berlin, Lichtenberg\n"
            "Geeignet für einen 3-Personenhaushalt.\nZimmeranzahl: 2\nEtage: 6\n"
            "Kaltmiete: 599,00 €\nWarmmiete: 760,00 €\nMit WBS."
        ),
        truth_wbs_display="WBS required, type unknown",
        truth_wbs_allowed=(),
        truth_rent_kalt_cents=59900,
        truth_rent_warm_cents=76000,
        truth_rooms=2.0,
        truth_floor="6",
        truth_bezirk="Lichtenberg",
    ),
    CaseTemplate(
        tag="floor_etagenzahl_trap",
        difficulty="hard",
        district="Friedrichshain-Kreuzberg",
        postal_code="10245",
        title="Dachnahe Wohnung in Friedrichshain",
        raw_text=(
            "Adresse\nBoxhagener Str. 77\n10245 Berlin, Friedrichshain\n"
            "Etagenzahl\n7\nEtage\n5\nZimmer\n2\nKaltmiete: 640,00 €\n"
            "Warmmiete: 815,00 €\nWBS 140-220."
        ),
        truth_wbs_display="140, 160, 180, 220",
        truth_wbs_allowed=(140, 160, 180, 220),
        truth_rent_kalt_cents=64000,
        truth_rent_warm_cents=81500,
        truth_rooms=2.0,
        truth_floor="5",
        truth_bezirk="Friedrichshain-Kreuzberg",
    ),
    CaseTemplate(
        tag="seniors_only",
        difficulty="medium",
        district="Steglitz-Zehlendorf",
        postal_code="12203",
        title="Seniorenwohnung in Lichterfelde",
        raw_text=(
            "Adresse\nDrakestr. 31\n12203 Berlin, Lichterfelde\n"
            "1 Zimmer\nEtage: EG\nKaltmiete: 480,00 €\nWarmmiete: 610,00 €\n"
            "Nur für Senioren ab 60 Jahre. WBS erforderlich."
        ),
        truth_wbs_display="WBS required, type unknown",
        truth_wbs_allowed=(),
        truth_rent_kalt_cents=48000,
        truth_rent_warm_cents=61000,
        truth_rooms=1.0,
        truth_floor="EG",
        truth_bezirk="Steglitz-Zehlendorf",
        truth_seniors_only=True,
    ),
    CaseTemplate(
        tag="exchange_only",
        difficulty="medium",
        district="Mitte",
        postal_code="10119",
        title="Tauschwohnung in Mitte",
        raw_text=(
            "Adresse\nTorstr. 118\n10119 Berlin, Mitte\n"
            "2 Zimmer\nEtage: 2\nKaltmiete: 705,00 €\nWarmmiete: 860,00 €\n"
            "Nur im Tausch. Bewerbung ohne WBS möglich."
        ),
        truth_wbs_display="No WBS required",
        truth_wbs_allowed=(),
        truth_rent_kalt_cents=70500,
        truth_rent_warm_cents=86000,
        truth_rooms=2.0,
        truth_floor="2",
        truth_bezirk="Mitte",
        truth_exchange_only=True,
    ),
    CaseTemplate(
        tag="rooms_5plus",
        difficulty="easy",
        district="Pankow",
        postal_code="10409",
        title="Große Familienwohnung",
        raw_text=(
            "Adresse\nGreifswalder Str. 210\n10409 Berlin, Prenzlauer Berg\n"
            "5 Zimmer\nEtage: 3\nKaltmiete: 1.365,12 €\nWarmmiete: 1.590,00 €\n"
            "WBS 180 erforderlich."
        ),
        truth_wbs_display="100, 140, 160, 180",
        truth_wbs_allowed=(100, 140, 160, 180),
        truth_rent_kalt_cents=136512,
        truth_rent_warm_cents=159000,
        truth_rooms=5.0,
        truth_floor="3",
        truth_bezirk="Pankow",
        truth_family_only=True,
    ),
)
