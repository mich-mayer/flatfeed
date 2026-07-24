from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Callable, Sequence, TypeVar

from flatfeed.wbs_rules import (
    display_wbs_requirement,
    extract_wbs_requirement,
)


CLEAN_AI_QA_SEED = 20260720


@dataclass(frozen=True)
class ParserSnapshot:
    """Correct parser values paired with one clean synthetic listing."""

    required_wbs: str | None
    display_wbs: str
    rooms: float
    floor: str
    address: str
    postal_code: str
    district: str
    rent_kalt: str
    rent_warm: str

    def as_dict(self) -> dict[str, object]:
        """Return the JSON-compatible shape expected by the offline evaluator."""

        return {
            "required_wbs": self.required_wbs,
            "display_wbs": self.display_wbs,
            "rooms": self.rooms,
            "floor": self.floor,
            "address": self.address,
            "postal_code": self.postal_code,
            "district": self.district,
            "rent_kalt": self.rent_kalt,
            "rent_warm": self.rent_warm,
        }


@dataclass(frozen=True)
class CleanAIQACase:
    """A clean listing and its correct parser snapshot.

    This is an in-memory generator result, not a finalized eval-dataset row.
    """

    case_id: str
    title: str
    raw_text: str
    parser_snapshot: ParserSnapshot
    format_variant: str


@dataclass(frozen=True)
class _LocationTemplate:
    district: str
    locality: str
    postal_code: str
    street: str


@dataclass(frozen=True)
class _ListingFacts:
    address: str
    postal_code: str
    locality: str
    district: str
    rooms: float
    floor: str
    rent_kalt_cents: int
    rent_warm_cents: int
    wbs_text: str


_LOCATION_TEMPLATES: tuple[_LocationTemplate, ...] = (
    _LocationTemplate("Mitte", "Moabit", "10557", "Lehrter Straße"),
    _LocationTemplate("Mitte", "Wedding", "13353", "Müllerstraße"),
    _LocationTemplate(
        "Friedrichshain-Kreuzberg",
        "Friedrichshain",
        "10245",
        "Revaler Straße",
    ),
    _LocationTemplate(
        "Friedrichshain-Kreuzberg",
        "Kreuzberg",
        "10961",
        "Gneisenaustraße",
    ),
    _LocationTemplate("Pankow", "Pankow", "13187", "Florastraße"),
    _LocationTemplate("Pankow", "Weißensee", "13088", "Berliner Allee"),
    _LocationTemplate(
        "Charlottenburg-Wilmersdorf",
        "Charlottenburg",
        "10585",
        "Kaiser-Friedrich-Straße",
    ),
    _LocationTemplate(
        "Charlottenburg-Wilmersdorf",
        "Wilmersdorf",
        "14197",
        "Mecklenburgische Straße",
    ),
    _LocationTemplate("Spandau", "Spandau", "13585", "Neuendorfer Straße"),
    _LocationTemplate("Spandau", "Staaken", "13593", "Obstallee"),
    _LocationTemplate(
        "Steglitz-Zehlendorf",
        "Steglitz",
        "12163",
        "Schloßstraße",
    ),
    _LocationTemplate(
        "Steglitz-Zehlendorf",
        "Lichterfelde",
        "12207",
        "Osdorfer Straße",
    ),
    _LocationTemplate(
        "Tempelhof-Schöneberg",
        "Tempelhof",
        "12099",
        "Tempelhofer Damm",
    ),
    _LocationTemplate(
        "Tempelhof-Schöneberg",
        "Schöneberg",
        "10827",
        "Hauptstraße",
    ),
    _LocationTemplate("Neukölln", "Neukölln", "12043", "Donaustraße"),
    _LocationTemplate("Neukölln", "Gropiusstadt", "12353", "Lipschitzallee"),
    _LocationTemplate(
        "Treptow-Köpenick",
        "Adlershof",
        "12489",
        "Dörpfeldstraße",
    ),
    _LocationTemplate(
        "Treptow-Köpenick",
        "Oberschöneweide",
        "12459",
        "Edisonstraße",
    ),
    _LocationTemplate(
        "Marzahn-Hellersdorf",
        "Marzahn",
        "12681",
        "Allee der Kosmonauten",
    ),
    _LocationTemplate(
        "Marzahn-Hellersdorf",
        "Hellersdorf",
        "12627",
        "Hellersdorfer Straße",
    ),
    _LocationTemplate("Lichtenberg", "Lichtenberg", "10365", "Frankfurter Allee"),
    _LocationTemplate("Lichtenberg", "Karlshorst", "10319", "Sewanstraße"),
    _LocationTemplate(
        "Reinickendorf",
        "Wittenau",
        "13437",
        "Oranienburger Straße",
    ),
    _LocationTemplate(
        "Reinickendorf",
        "Märkisches Viertel",
        "13435",
        "Senftenberger Ring",
    ),
)

_DISTRICTS = tuple(dict.fromkeys(item.district for item in _LOCATION_TEMPLATES))
_ROOM_VALUES = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0)
_FLOOR_VALUES = ("EG", "Hochparterre", "1", "2", "3", "4", "5", "6", "7", "DG")
WBS_TEXTS = (
    "Für die Anmietung ist kein WBS erforderlich.",
    "Die Wohnung ist freifinanziert; ein WBS wird nicht benötigt.",
    "Ein gültiger Wohnberechtigungsschein ist erforderlich.",
    "Voraussetzung für die Bewerbung ist ein WBS 100.",
    "Bewerbung mit WBS 100-140 möglich.",
    "Benötigt wird ein Wohnberechtigungsschein 141-220 %.",
    "Zulässig sind WBS 140-220.",
    "Voraussetzung: WBS ab 160.",
    "Eine Bewerbung ist bis WBS 180 möglich.",
)

FORMAT_VARIANTS = (
    "portal_lines",
    "compact_block",
    "prose_first",
    "costs_first",
    "sectioned",
    "label_table",
)

_T = TypeVar("_T")


def _balanced_values(
    values: Sequence[_T],
    *,
    count: int,
    rng: random.Random,
) -> list[_T]:
    result: list[_T] = []
    while len(result) < count:
        block = list(values)
        rng.shuffle(block)
        result.extend(block)
    return result[:count]


def _locations_by_district() -> dict[str, tuple[_LocationTemplate, ...]]:
    return {
        district: tuple(
            location
            for location in _LOCATION_TEMPLATES
            if location.district == district
        )
        for district in _DISTRICTS
    }


def _format_money(cents: int, *, currency: str = "€") -> str:
    euros, remainder = divmod(cents, 100)
    grouped_euros = f"{euros:,}".replace(",", ".")
    return f"{grouped_euros},{remainder:02d} {currency}"


def _snapshot_money(cents: int) -> str:
    return _format_money(cents, currency="EUR")


def _format_rooms(rooms: float) -> str:
    if rooms.is_integer():
        return str(int(rooms))
    return str(rooms).replace(".", ",")


def _floor_text(floor: str) -> str:
    return {
        "EG": "Erdgeschoss",
        "Hochparterre": "Hochparterre",
        "DG": "Dachgeschoss",
    }.get(floor, floor)


def _render_portal_lines(facts: _ListingFacts) -> str:
    return (
        "Wohnungsangebot\n"
        "Adresse\n"
        f"{facts.address}\n"
        f"{facts.postal_code} Berlin, {facts.locality}\n"
        f"Bezirk: {facts.district}\n"
        "Zimmer\n"
        f"{_format_rooms(facts.rooms)}\n"
        "Etage\n"
        f"{_floor_text(facts.floor)}\n"
        f"Nettokaltmiete: {_format_money(facts.rent_kalt_cents)}\n"
        f"Warmmiete: {_format_money(facts.rent_warm_cents)}\n"
        f"{facts.wbs_text}"
    )


def _render_compact_block(facts: _ListingFacts) -> str:
    return (
        f"{facts.address} | {facts.postal_code} Berlin, {facts.locality}\n"
        f"Bezirk: {facts.district} | Zimmer: {_format_rooms(facts.rooms)}\n"
        f"Etage: {_floor_text(facts.floor)} | "
        f"Kaltmiete: {_format_money(facts.rent_kalt_cents, currency='Euro')} | "
        f"Gesamtmiete: {_format_money(facts.rent_warm_cents, currency='Euro')}\n"
        f"Zugang: {facts.wbs_text}"
    )


def _render_prose_first(facts: _ListingFacts) -> str:
    return (
        f"In {facts.locality} im Bezirk {facts.district} wird eine helle "
        f"{_format_rooms(facts.rooms)}-Zimmer-Wohnung angeboten. "
        f"Sie liegt in der Etage {_floor_text(facts.floor)}.\n"
        f"Die Adresse lautet {facts.address}, "
        f"{facts.postal_code} Berlin, {facts.locality}.\n"
        f"Die monatliche Grundmiete beträgt "
        f"{_format_money(facts.rent_kalt_cents)}; die Bruttowarmmiete liegt bei "
        f"{_format_money(facts.rent_warm_cents)}.\n"
        f"{facts.wbs_text}"
    )


def _render_costs_first(facts: _ListingFacts) -> str:
    return (
        "Mietkonditionen\n"
        f"Gesamtmiete: {_format_money(facts.rent_warm_cents)}\n"
        f"Netto-Kaltmiete: {_format_money(facts.rent_kalt_cents)}\n\n"
        "Wohnungsdaten\n"
        f"Zimmeranzahl: {_format_rooms(facts.rooms)}\n"
        f"Geschoss: {_floor_text(facts.floor)}\n\n"
        "Lage\n"
        f"Adresse: {facts.address}\n"
        f"{facts.postal_code} Berlin, {facts.locality}\n"
        f"Bezirk: {facts.district}\n"
        f"{facts.wbs_text}"
    )


def _render_sectioned(facts: _ListingFacts) -> str:
    return (
        "LAGE UND ANSCHRIFT\n"
        f"{facts.postal_code} Berlin, {facts.locality}\n"
        f"{facts.address}\n"
        f"Verwaltungsbezirk: {facts.district}\n\n"
        "OBJEKTDATEN\n"
        f"{_format_rooms(facts.rooms)} Zimmer\n"
        f"Etage: {_floor_text(facts.floor)}\n\n"
        "MIETE\n"
        f"{_format_money(facts.rent_kalt_cents)} Kaltmiete\n"
        f"{_format_money(facts.rent_warm_cents)} Warmmiete\n\n"
        f"HINWEIS\n{facts.wbs_text}"
    )


def _render_label_table(facts: _ListingFacts) -> str:
    return (
        f"Wohnlage      {facts.locality}, Bezirk {facts.district}\n"
        f"Anschrift     {facts.address}\n"
        f"PLZ / Ort     {facts.postal_code} Berlin\n"
        f"Warmmiete     {_format_money(facts.rent_warm_cents)}\n"
        f"Zimmer        {_format_rooms(facts.rooms)}\n"
        f"Stockwerk     {_floor_text(facts.floor)}\n"
        f"Grundmiete    {_format_money(facts.rent_kalt_cents)}\n"
        f"Vermietung    {facts.wbs_text}"
    )


_RENDERERS: dict[str, Callable[[_ListingFacts], str]] = {
    "portal_lines": _render_portal_lines,
    "compact_block": _render_compact_block,
    "prose_first": _render_prose_first,
    "costs_first": _render_costs_first,
    "sectioned": _render_sectioned,
    "label_table": _render_label_table,
}


def _make_address(
    location: _LocationTemplate,
    *,
    index: int,
    rng: random.Random,
) -> str:
    house_number = 1 + ((index * 37 + rng.randrange(0, 97)) % 220)
    suffix = rng.choice(("", "", "", "a", "b"))
    return f"{location.street} {house_number}{suffix}"


def _make_rents(
    *,
    rooms: float,
    district: str,
    rng: random.Random,
) -> tuple[int, int]:
    premium_districts = {
        "Mitte",
        "Friedrichshain-Kreuzberg",
        "Charlottenburg-Wilmersdorf",
        "Steglitz-Zehlendorf",
    }
    district_premium = 10_000 if district in premium_districts else 0
    kalt_cents = (
        30_000
        + int(rooms * 12_500)
        + district_premium
        + rng.randrange(0, 20_001)
    )
    warm_cents = kalt_cents + 8_000 + int(rooms * 3_500) + rng.randrange(0, 8_001)
    return kalt_cents, warm_cents


def _make_snapshot(facts: _ListingFacts) -> ParserSnapshot:
    wbs_requirement = extract_wbs_requirement(facts.wbs_text)
    return ParserSnapshot(
        required_wbs=wbs_requirement.required_wbs,
        display_wbs=display_wbs_requirement(wbs_requirement),
        rooms=facts.rooms,
        floor=facts.floor,
        address=facts.address,
        postal_code=facts.postal_code,
        district=facts.district,
        rent_kalt=_snapshot_money(facts.rent_kalt_cents),
        rent_warm=_snapshot_money(facts.rent_warm_cents),
    )


def _case_id(*, index: int, raw_text: str, snapshot: ParserSnapshot) -> str:
    payload = f"{raw_text}\n{snapshot.as_dict()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
    return f"clean-{index + 1:04d}-{digest}"


def generate_clean_ai_qa_cases(
    *,
    count: int,
    seed: int = CLEAN_AI_QA_SEED,
) -> list[CleanAIQACase]:
    """Generate clean German listings without persisting a final dataset.

    A local ``random.Random`` instance makes the output deterministic for the
    same seed and count without changing Python's global random state.
    """

    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError("count must be an integer")
    if count < 0:
        raise ValueError("count must be non-negative")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")

    rng = random.Random(seed)
    districts = _balanced_values(_DISTRICTS, count=count, rng=rng)
    room_values = _balanced_values(_ROOM_VALUES, count=count, rng=rng)
    floor_values = _balanced_values(_FLOOR_VALUES, count=count, rng=rng)
    wbs_texts = _balanced_values(WBS_TEXTS, count=count, rng=rng)
    format_variants = _balanced_values(FORMAT_VARIANTS, count=count, rng=rng)
    district_occurrences = {district: 0 for district in _DISTRICTS}
    locations = _locations_by_district()

    cases: list[CleanAIQACase] = []
    for index in range(count):
        district = districts[index]
        district_locations = locations[district]
        location_index = district_occurrences[district] % len(district_locations)
        location = district_locations[location_index]
        district_occurrences[district] += 1

        rooms = room_values[index]
        floor = floor_values[index]
        address = _make_address(location, index=index, rng=rng)
        rent_kalt_cents, rent_warm_cents = _make_rents(
            rooms=rooms,
            district=district,
            rng=rng,
        )
        title = (
            f"Helle {_format_rooms(rooms)}-Zimmer-Wohnung "
            f"in Berlin-{location.locality}"
        )
        facts = _ListingFacts(
            address=address,
            postal_code=location.postal_code,
            locality=location.locality,
            district=district,
            rooms=rooms,
            floor=floor,
            rent_kalt_cents=rent_kalt_cents,
            rent_warm_cents=rent_warm_cents,
            wbs_text=wbs_texts[index],
        )
        format_variant = format_variants[index]
        raw_text = _RENDERERS[format_variant](facts)
        snapshot = _make_snapshot(facts)
        cases.append(
            CleanAIQACase(
                case_id=_case_id(
                    index=index,
                    raw_text=raw_text,
                    snapshot=snapshot,
                ),
                title=title,
                raw_text=raw_text,
                parser_snapshot=snapshot,
                format_variant=format_variant,
            )
        )
    return cases
