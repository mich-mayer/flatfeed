from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


BERLIN_DISTRICTS = (
    "Mitte",
    "Friedrichshain-Kreuzberg",
    "Pankow",
    "Charlottenburg-Wilmersdorf",
    "Spandau",
    "Steglitz-Zehlendorf",
    "Tempelhof-Schöneberg",
    "Neukölln",
    "Treptow-Köpenick",
    "Marzahn-Hellersdorf",
    "Lichtenberg",
    "Reinickendorf",
)

ORTSTEIL_TO_DISTRICT = {
    "adlershof": "Treptow-Köpenick",
    "adlershof ost": "Treptow-Köpenick",
    "adlershof west": "Treptow-Köpenick",
    "alt-hohenschönhausen": "Lichtenberg",
    "altglienicke": "Treptow-Köpenick",
    "alt-treptow": "Treptow-Köpenick",
    "baumschulenweg": "Treptow-Köpenick",
    "biesdorf": "Marzahn-Hellersdorf",
    "blankenburg": "Pankow",
    "blankenfelde": "Pankow",
    "bohnsdorf": "Treptow-Köpenick",
    "borsigwalde": "Reinickendorf",
    "britz": "Neukölln",
    "buckower felder": "Neukölln",
    "buch": "Pankow",
    "buckow": "Neukölln",
    "charlottenburg": "Charlottenburg-Wilmersdorf",
    "charlottenburg-nord": "Charlottenburg-Wilmersdorf",
    "dahlem": "Steglitz-Zehlendorf",
    "falkenberg": "Lichtenberg",
    "falkenhagener feld": "Spandau",
    "fennpfuhl": "Lichtenberg",
    "französisch buchholz": "Pankow",
    "friedenau": "Tempelhof-Schöneberg",
    "friedrichshain": "Friedrichshain-Kreuzberg",
    "friedrichsfelde": "Lichtenberg",
    "friedrichshagen": "Treptow-Köpenick",
    "frohnau": "Reinickendorf",
    "gatow": "Spandau",
    "gelbes viertel": "Marzahn-Hellersdorf",
    "gesundbrunnen": "Mitte",
    "gropiusstadt": "Neukölln",
    "grünau": "Treptow-Köpenick",
    "grunau": "Treptow-Köpenick",
    "grunewald": "Charlottenburg-Wilmersdorf",
    "hakenfelde": "Spandau",
    "halensee": "Charlottenburg-Wilmersdorf",
    "hansaviertel": "Mitte",
    "haselhorst": "Spandau",
    "heiligensee": "Reinickendorf",
    "heinersdorf": "Pankow",
    "hellersdorf": "Marzahn-Hellersdorf",
    "hermsdorf": "Reinickendorf",
    "hohenschönhausen": "Lichtenberg",
    "hohenschoenhausen": "Lichtenberg",
    "johannisthal": "Treptow-Köpenick",
    "joachim-ringelnatz-siedlung": "Marzahn-Hellersdorf",
    "karow": "Pankow",
    "karlshorst": "Lichtenberg",
    "kaulsdorf": "Marzahn-Hellersdorf",
    "kaulsdorf-nord ii": "Marzahn-Hellersdorf",
    "kladow": "Spandau",
    "konradshöhe": "Reinickendorf",
    "kosmosviertel betreuungsakt": "Treptow-Köpenick",
    "kosmosviertel betrauungsakt": "Treptow-Köpenick",
    "köpenick": "Treptow-Köpenick",
    "koepenick": "Treptow-Köpenick",
    "kreuzberg": "Friedrichshain-Kreuzberg",
    "lankwitz": "Steglitz-Zehlendorf",
    "lichtenrade": "Tempelhof-Schöneberg",
    "lichterfelde": "Steglitz-Zehlendorf",
    "lübars": "Reinickendorf",
    "malchow": "Lichtenberg",
    "mahlsdorf": "Marzahn-Hellersdorf",
    "mariendorf": "Tempelhof-Schöneberg",
    "marienfelde": "Tempelhof-Schöneberg",
    "marzahn": "Marzahn-Hellersdorf",
    "märkisches viertel": "Reinickendorf",
    "mitte": "Mitte",
    "moabit": "Mitte",
    "müggelheim": "Treptow-Köpenick",
    "neu-hohenschönhausen": "Lichtenberg",
    "neukölln": "Neukölln",
    "niederschöneweide": "Treptow-Köpenick",
    "niederschöneweide 1": "Treptow-Köpenick",
    "niederschönhausen": "Pankow",
    "nikolassee": "Steglitz-Zehlendorf",
    "oberschöneweide": "Treptow-Köpenick",
    "pankow": "Pankow",
    "plänterwald": "Treptow-Köpenick",
    "prenzlauer berg": "Pankow",
    "rahnsdorf": "Treptow-Köpenick",
    "reinickendorf": "Reinickendorf",
    "rosenthal": "Pankow",
    "rudow": "Neukölln",
    "rummelsburg": "Lichtenberg",
    "schöneberg": "Tempelhof-Schöneberg",
    "schoeneberg": "Tempelhof-Schöneberg",
    "schlachtensee": "Steglitz-Zehlendorf",
    "schmargendorf": "Charlottenburg-Wilmersdorf",
    "schmöckwitz": "Treptow-Köpenick",
    "siemensstadt": "Spandau",
    "spandau": "Spandau",
    "staaken": "Spandau",
    "stadtrandsiedlung malchow": "Pankow",
    "steglitz": "Steglitz-Zehlendorf",
    "tegel": "Reinickendorf",
    "tempelhof": "Tempelhof-Schöneberg",
    "tiergarten": "Mitte",
    "treptow": "Treptow-Köpenick",
    "waidmannslust": "Reinickendorf",
    "wannsee": "Steglitz-Zehlendorf",
    "wartenberg": "Lichtenberg",
    "wedding": "Mitte",
    "weißensee": "Pankow",
    "weissensee": "Pankow",
    "westend": "Charlottenburg-Wilmersdorf",
    "wilhelmstadt": "Spandau",
    "wilhelmsruh": "Pankow",
    "wilmersdorf": "Charlottenburg-Wilmersdorf",
    "wittenau": "Reinickendorf",
    "zehlendorf": "Steglitz-Zehlendorf",
}


def normalize_berlin_district(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = " ".join(value.replace(",", " ").split())
    if not cleaned:
        return None

    cleaned_lower = cleaned.lower()
    for district in BERLIN_DISTRICTS:
        if district.lower() == cleaned_lower:
            return district
    return ORTSTEIL_TO_DISTRICT.get(cleaned_lower)


@dataclass(frozen=True)
class ListingMetadata:
    address: Optional[str]
    postal_code: Optional[str]
    district: Optional[str]
    floor: Optional[str]
    rooms: Optional[float]
    rent_kalt: Optional[int]
    rent_warm: Optional[int]


@dataclass(frozen=True)
class AddressDiagnostics:
    address: Optional[str]
    source: str
    sanity_status: str
    sanity_details: str


def _normalize_money(value: str) -> int:
    value = value.strip()
    if "," in value:
        cleaned = value.replace(".", "").replace(",", ".")
    elif re.search(r"\.\d{1,2}$", value):
        cleaned = value
    else:
        cleaned = value.replace(".", "")
    return int(float(cleaned))


def extract_rooms(text: str) -> Optional[float]:
    patterns = (
        r"\b(?:anzahl\s+zimmer|zimmeranzahl|zimmer)\s*[:\n]\s*(\d+(?:[,.]\d+)?)\b",
        r"\b(?:anzahl\s+zimmer|zimmeranzahl|zimmer:)\D{0,10}(\d+(?:[,.]\d+)?)\b",
        r"\b(\d+(?:[,.]\d+)?)[ \t]*[- ]?[ \t]*(?:zimmer|zi\.|räume|rooms?)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def _normalize_floor(value: str) -> Optional[str]:
    cleaned = " ".join(value.strip().strip(":").split())
    cleaned = cleaned.strip(".,;")
    if not cleaned:
        return None

    normalized = cleaned.lower()
    floor_aliases = {
        "eg": "EG",
        "erdgeschoss": "EG",
        "hochparterre": "Hochparterre",
        "dg": "DG",
        "dachgeschoss": "DG",
        "ug": "UG",
        "untergeschoss": "UG",
        "souterrain": "Souterrain",
    }
    if normalized in floor_aliases:
        return floor_aliases[normalized]

    numeric_match = re.search(r"\b(-?\d{1,2})\b", cleaned)
    if numeric_match:
        return numeric_match.group(1)

    return None


def extract_floor(text: str) -> Optional[str]:
    lines = [line.strip() for line in text.splitlines()]
    floor_labels = {"etage", "geschoss", "stockwerk"}
    ignored_labels = {"etagenzahl"}
    metadata_labels = floor_labels | ignored_labels | {
        "zimmer",
        "fläche",
        "flaeche",
        "wohnfläche",
        "wohnflaeche",
        "wi-nr.",
        "mietkosten",
    }
    for index, line in enumerate(lines):
        label = line.strip().strip(":").lower()
        if label in ignored_labels or label not in floor_labels:
            continue
        for candidate in lines[index + 1 : index + 4]:
            candidate_label = candidate.strip().strip(":").lower()
            if not candidate:
                continue
            if candidate_label in metadata_labels or candidate.endswith(":"):
                break
            floor = _normalize_floor(candidate)
            if floor is not None:
                return floor

    patterns = (
        r"\b(?:etage|geschoss|stockwerk)\s*[:\-]?\s*(eg|erdgeschoss|dg|dachgeschoss|ug|untergeschoss|souterrain|-?\d{1,2})\b",
        r"\b(eg|erdgeschoss|dg|dachgeschoss|ug|untergeschoss|souterrain|-?\d{1,2})\.?\s*(?:etage|geschoss|stockwerk|og)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            floor = _normalize_floor(match.group(1))
            if floor is not None:
                return floor
    return None


def extract_rent(text: str, labels: tuple[str, ...]) -> Optional[int]:
    label_group = "|".join(re.escape(label) for label in labels)
    amount_pattern = r"(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d{2,5}(?:[,.]\d{1,2})?)"
    patterns = (
        rf"(?:{label_group})[^\d]{{0,60}}{amount_pattern}\s*(?:€|eur)?",
        rf"{amount_pattern}\s*(?:€|eur)[^\n]{{0,60}}(?:{label_group})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _normalize_money(match.group(1))
    return None


def extract_district(text: str) -> Optional[str]:
    address_location = extract_location_from_address(text)
    if address_location is not None:
        return address_location

    label_pattern = re.compile(
        r"(?:stadtteil|bezirk|ortsteil|lage)\s*[:\n]\s*([A-Za-zÄÖÜäöüß -]+)",
        flags=re.IGNORECASE,
    )
    for match in label_pattern.finditer(text):
        candidate = match.group(1).strip().splitlines()[0]
        normalized = normalize_berlin_district(candidate)
        if normalized is not None:
            return normalized
        candidate_lower = candidate.lower()
        for alias, district in ORTSTEIL_TO_DISTRICT.items():
            if re.search(rf"\b{re.escape(alias)}\b", candidate_lower):
                return district

    title_pattern = re.compile(
        r"\b(?:in|berlin[- ])\s*([A-Za-zÄÖÜäöüß-]+)\b",
        flags=re.IGNORECASE,
    )
    for match in title_pattern.finditer(text):
        candidate_lower = match.group(1).strip().lower()
        normalized = normalize_berlin_district(candidate_lower)
        if normalized is not None:
            return normalized

    for district in BERLIN_DISTRICTS:
        if re.search(rf"\b{re.escape(district)}\b", text, flags=re.IGNORECASE):
            return district
    lowered = text.lower()
    for alias, district in ORTSTEIL_TO_DISTRICT.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return district
    return None


def _clean_location_part(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = " ".join(value.replace("\n", " ").split()).strip(" ,")
    return cleaned or None


def extract_location_from_address(text: str) -> Optional[str]:
    address_pattern = re.compile(
        r"\b(?P<postal_code>\d{5})\s+"
        r"(?P<city>[A-Za-zÄÖÜäöüß -]+?)"
        r"(?:,\s*(?P<area>[A-Za-zÄÖÜäöüß -]+))?"
        r"(?=\n|$)",
        flags=re.IGNORECASE,
    )
    for match in address_pattern.finditer(text):
        city = _clean_location_part(match.group("city"))
        area = _clean_location_part(match.group("area"))
        if city is None:
            continue

        if city.lower() == "berlin":
            normalized_area = normalize_berlin_district(area)
            if normalized_area is not None:
                return normalized_area
            continue

        if area and area.lower() == "brandenburg":
            return city

        normalized_city = normalize_berlin_district(city)
        if normalized_city is not None:
            return normalized_city

    return None


def extract_postal_code(text: str) -> Optional[str]:
    berlin_postal_code = r"(?:1[0-3]\d{3}|14[01]\d{2})"
    patterns = (
        rf"\b({berlin_postal_code})\s+Berlin\b",
        rf"\b(?:PLZ|Postleitzahl)\s*:?\s*({berlin_postal_code})\b",
        rf"\bAdresse\s*:[^\n]{{0,160}}?\b({berlin_postal_code})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def extract_berlin_coordinates(html: str) -> tuple[Optional[float], Optional[float]]:
    number = r"(-?\d{1,3}(?:\.\d+)?)"
    pairs = (
        rf'data-lat=["\']{number}["\'][^>]{{0,300}}data-(?:long|lng|lon)=["\']{number}["\']',
        rf'data-(?:long|lng|lon)=["\']{number}["\'][^>]{{0,300}}data-lat=["\']{number}["\']',
        rf'["\']latitude["\']\s*:\s*["\']?{number}["\']?.{{0,200}}["\']longitude["\']\s*:\s*["\']?{number}',
        rf'["\']lat["\']\s*:\s*["\']?{number}["\']?.{{0,200}}["\'](?:lng|lon|long)["\']\s*:\s*["\']?{number}',
    )
    for index, pattern in enumerate(pairs):
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match is None:
            continue
        first = float(match.group(1))
        second = float(match.group(2))
        latitude, longitude = (second, first) if index == 1 else (first, second)
        if 52.3 <= latitude <= 52.7 and 13.0 <= longitude <= 13.8:
            return latitude, longitude
    return None, None


def _extract_address_from_explicit_block(text: str) -> Optional[str]:
    lines = [line.strip().strip(",") for line in text.splitlines()]
    metadata_labels = {
        "auf karte zeigen",
        "street view",
        "warmmiete",
        "wohnfläche",
        "wohnflaeche",
        "zimmer",
        "bezugsfrei",
        "merkmale",
        "objektdetails",
    }
    for index, line in enumerate(lines):
        if line.strip().strip(":").lower() != "adresse":
            continue
        for candidate in lines[index + 1 : index + 4]:
            if not candidate:
                continue
            candidate_label = candidate.strip().strip(":").lower()
            if candidate_label in metadata_labels:
                break
            if re.search(r"\b\d{5}\b", candidate):
                continue
            if re.search(r"\b\d+[a-zA-Z]?\b", candidate):
                return " ".join(candidate.split())
    return None


def _extract_address_fallback(text: str) -> Optional[str]:
    street_suffixes = (
        r"str\.",
        r"straße",
        r"strasse",
        r"weg",
        r"allee",
        r"damm",
        r"platz",
        r"ufer",
        r"ring",
        r"chaussee",
    )
    suffix_group = "|".join(street_suffixes)

    compact_pattern = rf"\b([A-ZÄÖÜ][\wÄÖÜäöüß.-]*(?:{suffix_group})\s*\d+[a-zA-Z]?)\b"
    compact_match = re.search(compact_pattern, text, flags=re.IGNORECASE)
    if compact_match:
        return " ".join(compact_match.group(1).split())

    multi_word_pattern = (
        rf"\b([A-ZÄÖÜ][\wÄÖÜäöüß.-]{{2,}}"
        rf"(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.-]{{2,}}){{0,2}}\s+"
        rf"(?:{suffix_group})\s*\d+[a-zA-Z]?)\b"
    )
    multi_word_match = re.search(multi_word_pattern, text, flags=re.IGNORECASE)
    if multi_word_match:
        return " ".join(multi_word_match.group(1).split())
    return None


def extract_address(text: str) -> Optional[str]:
    return _extract_address_from_explicit_block(text) or _extract_address_fallback(text)


def address_diagnostics(text: str, address: Optional[str] = None) -> AddressDiagnostics:
    explicit_address = _extract_address_from_explicit_block(text)
    fallback_address = _extract_address_fallback(text)
    resolved_address = address or explicit_address or fallback_address
    if resolved_address is None:
        return AddressDiagnostics(
            address=None,
            source="missing",
            sanity_status="warning",
            sanity_details="Address not found",
        )

    source = "explicit_address_block" if explicit_address == resolved_address else "fallback_regex"
    has_house_number = bool(re.search(r"\b\d+[a-zA-Z]?\b", resolved_address))
    has_postal_context = bool(re.search(r"\b\d{5}\s+[A-Za-zÄÖÜäöüß -]+", text))
    if source == "explicit_address_block" and has_house_number:
        return AddressDiagnostics(
            address=resolved_address,
            source=source,
            sanity_status="ok",
            sanity_details="Address was taken from the Adresse block and contains a house number",
        )
    if has_house_number and has_postal_context:
        return AddressDiagnostics(
            address=resolved_address,
            source=source,
            sanity_status="warning",
            sanity_details="Address was found by fallback regex; nearby postal code exists",
        )
    if has_house_number:
        return AddressDiagnostics(
            address=resolved_address,
            source=source,
            sanity_status="warning",
            sanity_details="Address was found by fallback regex; source is less reliable",
        )
    return AddressDiagnostics(
        address=resolved_address,
        source=source,
        sanity_status="warning",
        sanity_details="Address found, but house number is not confirmed",
    )


def extract_listing_metadata(*, title: Optional[str], raw_text: str) -> ListingMetadata:
    text = f"{raw_text}\n{title or ''}"
    return ListingMetadata(
        address=extract_address(text),
        postal_code=extract_postal_code(text),
        district=extract_district(text),
        floor=extract_floor(text),
        rooms=extract_rooms(text),
        rent_kalt=extract_rent(text, ("kaltmiete", "nettokaltmiete", "netto-kaltmiete")),
        rent_warm=extract_rent(text, ("warmmiete", "gesamtmiete", "bruttowarmmiete")),
    )
