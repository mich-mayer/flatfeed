from __future__ import annotations

import html
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from flatfeed.db.models import Listing, SentListingNotification, User
from flatfeed.listing_status import PARSED_STATUS
from flatfeed.listing_metadata import normalize_berlin_district
from flatfeed.schemas import ListingConstraints, UserPreferences
from flatfeed.wbs_rules import (
    ANY_WBS_VALUE,
    GENERIC_WBS_REQUIREMENT,
    NO_WBS_VALUE,
    SUPPORTED_WBS_PERCENTAGES,
    WBSRequirement,
    display_wbs_requirement,
    display_wbs_value,
    extract_wbs_requirement,
)


PARSED_LISTING_STATUS = PARSED_STATUS
KALT_RENT_LABELS = ("kaltmiete", "nettokaltmiete", "netto-kaltmiete", "grundmiete")
WARM_RENT_LABELS = (
    "warmmiete",
    "gesamtmiete",
    "bruttowarmmiete",
    "miete inkl. nk",
)

@dataclass(frozen=True)
class MatchDecision:
    is_match: bool
    reasons: Tuple[str, ...]


@dataclass(frozen=True)
class ListingMatch:
    user_id: int
    listing_id: int
    source_company: str
    title: Optional[str]
    url: str
    image_url: Optional[str]
    district: Optional[str]
    address: Optional[str]
    postal_code: Optional[str]
    floor: Optional[str]
    rooms: Optional[float]
    required_wbs: Optional[str]
    rent_kalt: Optional[int]
    rent_warm: Optional[int]
    s_bahn_minutes: Optional[int]
    u_bahn_minutes: Optional[int]
    reasons: Tuple[str, ...]
    s_bahn_station: Optional[str] = None
    u_bahn_station: Optional[str] = None
    display_wbs: Optional[str] = None
    display_rent_kalt: Optional[str] = None
    display_rent_warm: Optional[str] = None


def _extract_wbs_percent(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    matches = re.findall(r"\b(\d{2,3})\b", value)
    if not matches:
        return None
    return max(int(match) for match in matches)


def _format_price_value(value: str) -> str:
    value = value.strip()
    if "," in value:
        normalized = value.replace(".", "").replace(",", ".")
    elif re.search(r"\.\d{1,2}$", value):
        normalized = value
    else:
        normalized = value.replace(".", "")
    amount = Decimal(normalized)
    if amount == amount.to_integral_value():
        return f"{int(amount)} EUR"
    return f"{amount:.2f}".replace(".", ",") + " EUR"


def extract_rent_display(raw_text: str, labels: Tuple[str, ...]) -> Optional[str]:
    label_group = "|".join(re.escape(label) for label in labels)
    amount_pattern = r"(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d{2,5}(?:[,.]\d{1,2})?)"
    patterns = (
        rf"{amount_pattern}\s*(?:€|eur)[^\n]{{0,60}}(?:{label_group})",
        rf"(?:{label_group})[^\d]{{0,60}}{amount_pattern}\s*(?:€|eur)?",
    )
    for pattern in patterns:
        match = re.search(pattern, raw_text, flags=re.IGNORECASE)
        if match:
            return _format_price_value(match.group(1))
    return None


def _fallback_rent_display(value: Optional[int]) -> str:
    return f"{value} EUR" if value is not None else "not specified"


def _display_rooms(value: Optional[float]) -> str:
    if value is None:
        return "not specified"
    if float(value).is_integer():
        return str(int(value))
    return str(value).replace(".", ",")


def _display_floor(value: Optional[str]) -> str:
    if value is None:
        return "not specified"
    cleaned = str(value).strip()
    return cleaned or "not specified"


def display_wbs_options_for_listing(required_wbs: Optional[str]) -> str:
    if not required_wbs:
        return "No WBS required"
    requirement = extract_wbs_requirement(required_wbs)
    if requirement.rule_type != "not_mentioned":
        return display_wbs_requirement(requirement)

    required_percent = _extract_wbs_percent(required_wbs)
    if required_percent is None:
        return display_wbs_value(required_wbs)

    values = tuple(
        percent for percent in SUPPORTED_WBS_PERCENTAGES
        if percent <= required_percent
    )
    if not values:
        return display_wbs_value(required_wbs)
    return ", ".join(str(value) for value in values)


def effective_wbs_requirement(
    *,
    parsed_required_wbs: Optional[str],
    listing_title: Optional[str],
    listing_text: str,
) -> WBSRequirement:
    full_text = f"{listing_title or ''}\n{listing_text or ''}".strip()
    if full_text:
        return extract_wbs_requirement(full_text)
    if parsed_required_wbs:
        return extract_wbs_requirement(parsed_required_wbs)
    return extract_wbs_requirement("")


def display_wbs_options_for_listing_text(
    *,
    parsed_required_wbs: Optional[str],
    listing_title: Optional[str],
    listing_text: str,
) -> str:
    return display_wbs_requirement(
        effective_wbs_requirement(
            parsed_required_wbs=parsed_required_wbs,
            listing_title=listing_title,
            listing_text=listing_text,
        )
    )


def effective_required_wbs(
    *,
    parsed_required_wbs: Optional[str],
    listing_title: Optional[str],
    listing_text: str,
) -> Optional[str]:
    return effective_wbs_requirement(
        parsed_required_wbs=parsed_required_wbs,
        listing_title=listing_title,
        listing_text=listing_text,
    ).required_wbs


def _wbs_matches(requirement: WBSRequirement, user_wbs: Optional[str]) -> bool:
    if user_wbs == ANY_WBS_VALUE:
        return requirement.requires_wbs
    if not requirement.requires_wbs:
        return True
    if user_wbs == NO_WBS_VALUE:
        return False
    if not user_wbs:
        return False

    user_percent = _extract_wbs_percent(user_wbs)
    if not requirement.allowed_percentages and requirement.required_wbs == GENERIC_WBS_REQUIREMENT:
        return True
    if user_percent is None:
        return False

    if requirement.allowed_percentages:
        return user_percent in requirement.allowed_percentages

    required_percent = _extract_wbs_percent(requirement.required_wbs)
    if required_percent is None:
        return True

    return user_percent <= required_percent


def _location_matches(
    *,
    preferred_locations: Optional[Iterable[str]],
    listing_district: Optional[str],
    listing_title: Optional[str],
    listing_text: str,
) -> bool:
    locations = [location.strip().lower() for location in preferred_locations or () if location]
    if not locations:
        return True

    if listing_district:
        normalized_district = normalize_berlin_district(listing_district) or listing_district
        return normalized_district.strip().lower() in locations

    haystack = f"{listing_title or ''}\n{listing_text}".lower()
    return any(location in haystack for location in locations)


def _money_to_cents(value: str) -> Optional[int]:
    try:
        amount = Decimal(value.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None
    return int(amount * 100)


def _extract_listing_rent_cents(raw_text: str) -> Optional[int]:
    patterns = (
        r"(?:kaltmiete|nettokaltmiete|netto-kaltmiete|grundmiete)[^\d]{0,40}(\d{2,5}(?:[,.]\d{1,2})?)\s*(?:€|eur|euro)?",
        r"(\d{2,5}(?:[,.]\d{1,2})?)\s*(?:€|eur|euro)[^\n]{0,40}(?:kalt|kaltmiete|nettokaltmiete|grundmiete)",
    )
    for pattern in patterns:
        match = re.search(pattern, raw_text, flags=re.IGNORECASE)
        if match:
            cents = _money_to_cents(match.group(1))
            if cents is not None:
                return cents
    return None


def _rent_matches(
    *,
    max_rent: Optional[int],
    listing_rent: Optional[int],
    raw_text: str,
) -> bool:
    if max_rent is None:
        return True
    listing_rent_cents = _extract_listing_rent_cents(raw_text)
    if listing_rent_cents is None and listing_rent is not None:
        listing_rent_cents = listing_rent * 100
    if listing_rent_cents is None:
        return False
    return listing_rent_cents <= max_rent * 100


def _room_matches(*, preferred_rooms: Optional[float], listing_rooms: Optional[float]) -> bool:
    if preferred_rooms is None:
        return True
    if listing_rooms is None:
        return False
    if preferred_rooms >= 5:
        return listing_rooms >= 5
    return abs(listing_rooms - preferred_rooms) < 0.01


def is_listing_match(
    *,
    preferences: UserPreferences,
    constraints: ListingConstraints,
    listing: Listing,
    user_raw_input: Optional[str] = None,
) -> MatchDecision:
    reasons: List[str] = []
    wbs_requirement = effective_wbs_requirement(
        parsed_required_wbs=constraints.required_wbs,
        listing_title=listing.title,
        listing_text=listing.raw_text,
    )

    del user_raw_input

    if not _wbs_matches(wbs_requirement, preferences.wbs_type):
        return MatchDecision(False, ("listing WBS does not match the filter",))
    if not _location_matches(
        preferred_locations=preferences.location,
        listing_district=listing.district,
        listing_title=listing.title,
        listing_text=listing.raw_text,
    ):
        return MatchDecision(False, ("listing district does not match the filter",))
    if not _rent_matches(
        max_rent=preferences.max_rent,
        listing_rent=listing.rent_kalt,
        raw_text=listing.raw_text,
    ):
        return MatchDecision(False, ("rent is above the filter maximum",))
    if not _room_matches(preferred_rooms=preferences.rooms, listing_rooms=listing.rooms):
        return MatchDecision(False, ("room count is below the filter",))

    if wbs_requirement.requires_wbs:
        reasons.append(f"WBS matches: {display_wbs_requirement(wbs_requirement)}")
    if preferences.location:
        reasons.append("district matches the filter")
    if preferences.max_rent is not None:
        reasons.append("within rent limit")
    if preferences.rooms is not None:
        reasons.append("room count matches")

    return MatchDecision(True, tuple(reasons or ("basic filters match",)))


def find_matches_for_user(
    *,
    session: Session,
    user: User,
    exclude_sent: bool = True,
    limit: Optional[int] = None,
    only_new_since_filter_update: bool = False,
    allowed_listing_urls: Optional[Iterable[str]] = None,
    order_by_allowed_listing_urls: bool = False,
    source_companies: Optional[Iterable[str]] = None,
    require_parsed_status: bool = True,
    active_only: bool = True,
) -> List[ListingMatch]:
    if not user.parsed_preferences:
        return []

    preferences = UserPreferences.model_validate(user.parsed_preferences)
    allowed_url_tuple = tuple(allowed_listing_urls or ())
    source_company_tuple = tuple(source_companies or ())
    statement = select(Listing).order_by(Listing.first_seen_at.desc(), Listing.listing_id.desc())
    if active_only:
        statement = (
            statement
            .where(Listing.source_active.is_(True))
            .where(Listing.status != "removed_from_source")
        )
    if require_parsed_status:
        statement = statement.where(Listing.status == PARSED_LISTING_STATUS)
    if allowed_url_tuple:
        statement = statement.where(Listing.url.in_(allowed_url_tuple))
    if source_company_tuple:
        statement = statement.where(Listing.source_company.in_(source_company_tuple))
    if only_new_since_filter_update and user.filter_updated_at is not None:
        statement = statement.where(Listing.first_seen_at >= user.filter_updated_at)
    listings = list(session.scalars(statement))
    if order_by_allowed_listing_urls and allowed_url_tuple:
        listing_url_rank = {url: index for index, url in enumerate(allowed_url_tuple)}
        listings.sort(
            key=lambda listing: (
                listing_url_rank.get(listing.url, len(listing_url_rank)),
                -(listing.first_seen_at.timestamp() if listing.first_seen_at else 0),
                -listing.listing_id,
            )
        )

    sent_listing_ids = set()
    if exclude_sent:
        sent_listing_ids = set(
            session.scalars(
                select(SentListingNotification.listing_id).where(
                    SentListingNotification.user_id == user.user_id
                )
            )
        )

    matches: List[ListingMatch] = []
    for listing in listings:
        if listing.listing_id in sent_listing_ids:
            continue

        constraints = (
            ListingConstraints.model_validate(listing.parsed_constraints)
            if listing.parsed_constraints
            else ListingConstraints()
        )
        wbs_requirement = effective_wbs_requirement(
            parsed_required_wbs=constraints.required_wbs,
            listing_title=listing.title,
            listing_text=listing.raw_text,
        )
        required_wbs = wbs_requirement.required_wbs
        decision = is_listing_match(
            preferences=preferences,
            constraints=constraints,
            listing=listing,
            user_raw_input=user.raw_input,
        )
        if not decision.is_match:
            continue

        matches.append(
            ListingMatch(
                user_id=user.user_id,
                listing_id=listing.listing_id,
                source_company=listing.source_company,
                title=listing.title,
                url=listing.url,
                image_url=listing.image_url,
                district=listing.district,
                address=listing.address,
                postal_code=listing.postal_code,
                floor=listing.floor,
                rooms=listing.rooms,
                required_wbs=required_wbs,
                rent_kalt=listing.rent_kalt,
                rent_warm=listing.rent_warm,
                s_bahn_minutes=(listing.transport_walk or {}).get("s_bahn_minutes"),
                u_bahn_minutes=(listing.transport_walk or {}).get("u_bahn_minutes"),
                s_bahn_station=(listing.transport_walk or {}).get("s_bahn_station"),
                u_bahn_station=(listing.transport_walk or {}).get("u_bahn_station"),
                reasons=decision.reasons,
                display_wbs=display_wbs_requirement(wbs_requirement),
                display_rent_kalt=extract_rent_display(
                    listing.raw_text,
                    KALT_RENT_LABELS,
                ),
                display_rent_warm=extract_rent_display(
                    listing.raw_text,
                    WARM_RENT_LABELS,
                ),
            )
        )
        if limit is not None and len(matches) >= limit:
            break

    return matches


def find_pending_matches(
    *,
    session: Session,
    limit_per_user: int,
    source_companies: Optional[Iterable[str]] = None,
) -> List[ListingMatch]:
    users = list(
        session.scalars(
            select(User)
            .where(User.parsed_preferences.is_not(None))
            .order_by(User.updated_at.desc(), User.user_id.asc())
        )
    )

    matches: List[ListingMatch] = []
    for user in users:
        matches.extend(
            find_matches_for_user(
                session=session,
                user=user,
                exclude_sent=True,
                limit=limit_per_user,
                only_new_since_filter_update=True,
                source_companies=source_companies,
            )
        )
    return matches


def mark_match_sent(*, session: Session, match: ListingMatch) -> None:
    already_sent = session.scalar(
        select(SentListingNotification).where(
            SentListingNotification.user_id == match.user_id,
            SentListingNotification.listing_id == match.listing_id,
        )
    )
    if already_sent is not None:
        return

    session.add(
        SentListingNotification(
            user_id=match.user_id,
            listing_id=match.listing_id,
        )
    )


def format_match_message(match: ListingMatch) -> str:
    district = html.escape(match.district or "not specified")
    if match.address and match.postal_code:
        address_value = f"{match.address}, {match.postal_code} Berlin"
    else:
        address_value = match.address or "not specified"
    address = html.escape(address_value)
    floor = html.escape(_display_floor(match.floor))
    rooms = html.escape(_display_rooms(match.rooms))
    s_bahn = _format_transit_walk(match.s_bahn_minutes, match.s_bahn_station)
    u_bahn = _format_transit_walk(match.u_bahn_minutes, match.u_bahn_station)
    source_company = html.escape(match.source_company or "not specified")
    wbs = html.escape(match.display_wbs or display_wbs_value(match.required_wbs))
    rent_kalt = html.escape(match.display_rent_kalt or _fallback_rent_display(match.rent_kalt))
    rent_warm = html.escape(match.display_rent_warm or _fallback_rent_display(match.rent_warm))
    url = html.escape(match.url)
    return (
        f"<b>District:</b> {district}\n"
        f"<b>Address:</b> {address}\n"
        f"<b>Floor:</b> {floor}\n"
        f"<b>Rooms:</b> {rooms}\n"
        f"<b>S-Bahn:</b> {s_bahn}\n"
        f"<b>U-Bahn:</b> {u_bahn}\n"
        f"<b>WBS:</b> {wbs}\n"
        f"<b>Source:</b> {source_company}\n\n"
        f"<b>Kalt:</b> {rent_kalt}\n"
        f"<b>Warm:</b> {rent_warm}\n\n"
        f"<a href=\"{url}\">Open listing</a>"
    )


def _format_transit_walk(minutes: Optional[int], station: Optional[str]) -> str:
    if minutes is None:
        return "not calculated"
    if station:
        return f"{minutes} min walk to {html.escape(station)}"
    return f"{minutes} min walk"
