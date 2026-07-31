from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import logging
import os
from pathlib import Path
import random
import re
from contextlib import suppress
from typing import Any, Callable, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from sqlalchemy import delete, select

from flatfeed.ai_qa import (
    AIQARunResult,
    AI_QA_FEEDBACK_PARSER_CORRECT,
    AI_QA_FEEDBACK_PARSER_ERROR,
    AI_QA_FEEDBACK_UNSURE,
    AI_QA_TRIGGER_NEW_LISTING,
    load_ai_qa_reviews_for_alert,
    run_ai_qa_for_unreviewed_active_listings,
    update_ai_qa_feedback,
)
from flatfeed.config import PROJECT_ROOT, get_settings
from flatfeed.db.models import AIQAReview, Listing, SentListingNotification, User
from flatfeed.db.session import SessionLocal, init_db
from flatfeed.ingestion import (
    ENABLED_SOURCE_COMPANIES,
    REMOVED_STATUS,
    get_source_adapter,
)
from flatfeed.integrations.transit_walk import enrich_missing_transport_walk
from flatfeed.matching import (
    ANY_WBS_VALUE,
    KALT_RENT_LABELS,
    ListingMatch,
    NO_WBS_VALUE,
    PARSED_LISTING_STATUS,
    WARM_RENT_LABELS,
    display_wbs_value,
    display_wbs_options_for_listing_text,
    effective_required_wbs,
    effective_wbs_requirement,
    extract_rent_display,
    find_matches_for_user,
    find_pending_matches,
    format_match_message,
    is_listing_match,
    mark_match_sent,
)
from flatfeed.monitoring import (
    INGESTION_STATUS_PARTIAL_SUCCESS,
    INGESTION_STATUS_SUCCESS,
    get_ingestion_alert_candidate,
    load_ingestion_health_summary,
    mark_ingestion_alert_sent,
    record_ingestion_failure,
    record_ingestion_success,
)
from flatfeed.schemas import ListingConstraints, UserPreferences


logger = logging.getLogger(__name__)
router = Router()

BTN_SETTINGS = "⚙ Filter"
BTN_MATCHES = "🔎 Show matches"

CASE_STUDY_URL = "https://mich-mayer.github.io/flatfeed/case-study.html"

CURRENT_LISTINGS_LIMIT = 3
ACTIVE_LISTING_CANDIDATE_LIMIT = 120
LIVE_CHECK_BATCH_SIZE = 8
TELEGRAM_PHOTO_CAPTION_LIMIT = 1024
PRIMARY_SOURCE_COMPANY = "FlatFeed Synthetic"
ACTIVE_SOURCE_COMPANIES = ENABLED_SOURCE_COMPANIES
SOURCE_TRIGGER_BACKGROUND = "background"
SOURCE_TRIGGER_FILTERED_MATCHES = "filtered_matches"


@dataclass(frozen=True)
class RefreshResult:
    listings_found: int
    created_count: int
    updated_count: int
    saved_count: int
    removed_count: int
    parsed_count: int
    transport_count: int
    is_partial: bool
    collection_error_count: int
    ai_qa_checked_count: int
    ai_qa_alert_review_ids: tuple[int, ...]

WBS_OPTIONS = (
    ("Any WBS", ANY_WBS_VALUE),
    ("WBS 100", "WBS 100"),
    ("WBS 140", "WBS 140"),
    ("WBS 160", "WBS 160"),
    ("WBS 180", "WBS 180"),
    ("WBS 220", "WBS 220"),
    ("No WBS required", NO_WBS_VALUE),
)

DISTRICT_OPTIONS = (
    ("Any district", "ANY"),
    ("Mitte", "Mitte"),
    ("Friedrichshain-Kreuzberg", "Friedrichshain-Kreuzberg"),
    ("Pankow", "Pankow"),
    ("Charlottenburg-Wilmersdorf", "Charlottenburg-Wilmersdorf"),
    ("Spandau", "Spandau"),
    ("Steglitz-Zehlendorf", "Steglitz-Zehlendorf"),
    ("Tempelhof-Schöneberg", "Tempelhof-Schöneberg"),
    ("Neukölln", "Neukölln"),
    ("Treptow-Köpenick", "Treptow-Köpenick"),
    ("Marzahn-Hellersdorf", "Marzahn-Hellersdorf"),
    ("Lichtenberg", "Lichtenberg"),
    ("Reinickendorf", "Reinickendorf"),
)

ROOM_OPTIONS = (
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
    ("4", "4"),
    ("5+", "5PLUS"),
    ("Any number", "ANY"),
)


RENT_PRESETS = (600, 800, 1000, 1200)

# Wizard navigation callbacks shared by every setup step.
NAV_BACK = "filter:nav:back"
NAV_CANCEL = "filter:nav:cancel"

SETUP_STEP_TOTAL = 4

WBS_HINT = (
    "<i>WBS (Wohnberechtigungsschein) is a Berlin eligibility certificate. The number "
    "is the income tier it covers — a higher number allows a higher household income. "
    "Pick the tier printed on your WBS, or choose “Any WBS”.</i>"
)
KALTMIETE_HINT = "<i>Kaltmiete is the base rent without utilities (Nebenkosten).</i>"

SETUP_EXPIRED_TEXT = (
    "Your setup session expired (the bot restarted), so I lost the earlier answers. "
    "Let's start again.\n\n"
)


def _step_prefix(step: int) -> str:
    return f"<b>Step {step}/{SETUP_STEP_TOTAL}</b>\n\n"


def _rooms_option_value(rooms: Optional[float]) -> Optional[str]:
    if rooms is None:
        return None
    if rooms >= 5:
        return "5PLUS"
    return str(int(rooms))


class FilterSetup(StatesGroup):
    choosing_wbs = State()
    choosing_location = State()
    choosing_rent = State()
    choosing_rooms = State()


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=BTN_MATCHES)],
        [KeyboardButton(text=BTN_SETTINGS)],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Choose an action",
    )


def _nav_row(*, include_back: bool) -> List[InlineKeyboardButton]:
    row: List[InlineKeyboardButton] = []
    if include_back:
        row.append(InlineKeyboardButton(text="⬅ Back", callback_data=NAV_BACK))
    row.append(InlineKeyboardButton(text="✖ Cancel", callback_data=NAV_CANCEL))
    return row


def _keyboard(
    prefix: str,
    options: tuple[tuple[str, str], ...],
    columns: int = 2,
    *,
    selected: Optional[str] = None,
    include_back: bool = False,
    solo_values: tuple[str, ...] = (),
) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    current_row: List[InlineKeyboardButton] = []

    def flush() -> None:
        nonlocal current_row
        if current_row:
            rows.append(current_row)
            current_row = []

    for label, value in options:
        text = f"✓ {label}" if selected is not None and value == selected else label
        button = InlineKeyboardButton(text=text, callback_data=f"filter:{prefix}:{value}")
        # Meta options ("Any", "No WBS required") get their own full-width row so
        # they never sit next to a concrete value and stay easy to scan.
        if value in solo_values:
            flush()
            rows.append([button])
            continue
        current_row.append(button)
        if len(current_row) == columns:
            flush()
    flush()
    rows.append(_nav_row(include_back=include_back))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _wbs_keyboard(*, selected: Optional[str] = None, include_back: bool = False) -> InlineKeyboardMarkup:
    return _keyboard(
        "wbs",
        WBS_OPTIONS,
        columns=2,
        selected=selected,
        include_back=include_back,
        solo_values=(ANY_WBS_VALUE, NO_WBS_VALUE),
    )


def _location_keyboard(*, selected: Optional[str] = None, include_back: bool = False) -> InlineKeyboardMarkup:
    return _keyboard(
        "location",
        DISTRICT_OPTIONS,
        columns=1,
        selected=selected,
        include_back=include_back,
    )


def _rooms_keyboard(*, selected: Optional[str] = None, include_back: bool = False) -> InlineKeyboardMarkup:
    return _keyboard(
        "rooms",
        ROOM_OPTIONS,
        columns=2,
        selected=selected,
        include_back=include_back,
        solo_values=("ANY",),
    )


def _rent_keyboard(*, include_back: bool = False) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"≤ {RENT_PRESETS[0]} EUR", callback_data=f"filter:rent:{RENT_PRESETS[0]}"),
                InlineKeyboardButton(text=f"≤ {RENT_PRESETS[1]} EUR", callback_data=f"filter:rent:{RENT_PRESETS[1]}"),
            ],
            [
                InlineKeyboardButton(text=f"≤ {RENT_PRESETS[2]} EUR", callback_data=f"filter:rent:{RENT_PRESETS[2]}"),
                InlineKeyboardButton(text=f"≤ {RENT_PRESETS[3]} EUR", callback_data=f"filter:rent:{RENT_PRESETS[3]}"),
            ],
            [InlineKeyboardButton(text="No limit", callback_data="filter:rent:NO_LIMIT")],
            _nav_row(include_back=include_back),
        ]
    )


def _is_admin_user(user_id: Optional[int]) -> bool:
    if user_id is None:
        return False
    return user_id in get_settings().admin_telegram_user_ids


def _settings_keyboard(*, has_filter: bool) -> InlineKeyboardMarkup:
    if not has_filter:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Set up filter", callback_data="settings:filter")],
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Show matches", callback_data="settings:matches")],
            [InlineKeyboardButton(text="Edit filter", callback_data="settings:edit_menu")],
            [InlineKeyboardButton(text="Reset filter", callback_data="settings:reset")],
            [InlineKeyboardButton(text="🗑 Delete my data", callback_data="settings:delete")],
        ]
    )


def _reset_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Yes, reset filter", callback_data="settings:reset_confirm")],
            [InlineKeyboardButton(text="No, keep it", callback_data="settings:back")],
        ]
    )


def _delete_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Yes, delete saved data", callback_data="settings:delete_confirm")],
            [InlineKeyboardButton(text="No, keep my data", callback_data="settings:back")],
        ]
    )


def _no_filter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Set up filter", callback_data="settings:filter")],
            [InlineKeyboardButton(text="Try the demo", callback_data="tour:1")],
        ]
    )


def _no_matches_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Edit filter", callback_data="settings:edit_menu")],
            [InlineKeyboardButton(text="Try the demo filter", callback_data="tour:1")],
        ]
    )


def _edit_filter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="WBS", callback_data="settings:edit:wbs"),
                InlineKeyboardButton(text="District", callback_data="settings:edit:location"),
            ],
            [
                InlineKeyboardButton(text="Rent", callback_data="settings:edit:rent"),
                InlineKeyboardButton(text="Rooms", callback_data="settings:edit:rooms"),
            ],
            [InlineKeyboardButton(text="Back to filter", callback_data="settings:back")],
        ]
    )


def _display(value: Optional[Any], fallback: str = "not specified") -> str:
    if value is None:
        return fallback
    if isinstance(value, list):
        return ", ".join(value) if value else fallback
    return str(value)


def _display_rooms(value: Optional[float]) -> str:
    if value is None:
        return "Any number"
    if value >= 5:
        return "5+"
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def _display_wbs(value: Optional[str]) -> str:
    return display_wbs_value(value)


def _settings_card(preferences: Optional[UserPreferences]) -> str:
    settings = get_settings()
    if preferences is None:
        return (
            "<b>Your filter</b>\n\n"
            "The filter is not set up yet.\n\n"
            "Tap the button below and I will guide you through WBS type, district, rent, and rooms."
        )

    rent = f"up to {preferences.max_rent} EUR" if preferences.max_rent is not None else "no limit"
    delivery_label = (
        "<b>Notifications:</b> ON"
        if settings.bot_background_enabled
        else "<b>Demo mode:</b> matches on demand"
    )
    return (
        "<b>Your filter</b>\n\n"
        f"<b>WBS:</b> {_display_wbs(preferences.wbs_type)}\n"
        f"<b>District:</b> {_display(preferences.location, fallback='any district')}\n"
        f"<b>Kaltmiete:</b> {rent}\n"
        f"<b>Rooms:</b> {_display_rooms(preferences.rooms)}\n\n"
        f"{delivery_label}"
    )


def _preferences_from_filter_data(data: Dict[str, Any]) -> UserPreferences:
    wbs_type = data.get("wbs_type")
    location = data.get("location")
    max_rent = data.get("max_rent")
    rooms = data.get("rooms")
    return UserPreferences(
        location=[location] if location else None,
        wbs_type=wbs_type,
        max_rent=max_rent,
        rooms=rooms,
    )


def _preferences_from_state_data(data: Dict[str, Any]) -> UserPreferences:
    existing = data.get("existing_preferences") or {}
    existing_location = existing.get("location")
    if isinstance(existing_location, list):
        existing_location_value = existing_location[0] if existing_location else None
    else:
        existing_location_value = existing_location

    location = data.get("location", existing_location_value)
    return UserPreferences(
        location=[location] if location else None,
        wbs_type=data.get("wbs_type", existing.get("wbs_type")),
        max_rent=data.get("max_rent", existing.get("max_rent")),
        rooms=data.get("rooms", existing.get("rooms")),
    )


def _filter_summary(preferences: UserPreferences) -> str:
    rent = f"up to {preferences.max_rent} EUR" if preferences.max_rent is not None else "no limit"
    if get_settings().bot_background_enabled:
        next_step = (
            "I will send new matching listings here automatically, each one only once. "
            "To check the catalog right now, tap Show matches."
        )
    else:
        next_step = "Tap Show matches to check the synthetic catalog now."
    return (
        "Filter saved.\n\n"
        f"<b>WBS:</b> {_display_wbs(preferences.wbs_type)}\n"
        f"<b>District:</b> {_display(preferences.location, fallback='any district')}\n"
        f"<b>Kaltmiete:</b> {rent}\n"
        f"<b>Rooms:</b> {_display_rooms(preferences.rooms)}\n\n"
        f"{next_step}"
    )


def _rent_prompt() -> str:
    return (
        "What is your maximum Kaltmiete?\n\n"
        f"{KALTMIETE_HINT}\n\n"
        "Tap a preset below, type any amount in EUR (for example 650), "
        "or tap the button below for no limit."
    )


def _parse_rent_input(text: str) -> Optional[int]:
    normalized = text.strip().lower()
    if normalized in {"0", "none", "no limit", "nolimit", "no limit", "-"}:
        return None

    match = re.search(r"\d{2,5}", normalized.replace(" ", ""))
    if match is None:
        raise ValueError("Rent input must contain an amount.")

    amount = int(match.group(0))
    if amount <= 0:
        return None
    return amount


def _fixed_filter_raw_input(preferences: UserPreferences) -> str:
    return (
        "fixed_filter; "
        f"wbs_type={preferences.wbs_type or 'none'}; "
        f"location={','.join(preferences.location or []) or 'any'}; "
        f"max_rent={preferences.max_rent or 'none'}; "
        f"rooms={preferences.rooms or 'none'}"
    )


def save_fixed_preferences(*, user_id: int, preferences: UserPreferences) -> None:
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            user = User(user_id=user_id)
            session.add(user)
        user.raw_input = _fixed_filter_raw_input(preferences)
        user.parsed_preferences = preferences.model_dump(mode="json")
        user.filter_updated_at = datetime.utcnow()
        session.commit()


def load_user_preferences(user_id: int) -> Optional[UserPreferences]:
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None or not user.parsed_preferences:
            return None
        return UserPreferences.model_validate(user.parsed_preferences)


def reset_user_filter(user_id: int) -> bool:
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            return False
        user.raw_input = None
        user.parsed_preferences = None
        user.filter_updated_at = None
        session.commit()
        return True


def delete_user_data(user_id: int) -> bool:
    with SessionLocal() as session:
        user = session.get(User, user_id)
        had_user = user is not None
        if user is not None:
            session.delete(user)
        notification_result = session.execute(
            delete(SentListingNotification).where(
                SentListingNotification.user_id == user_id
            )
        )
        session.commit()
        return had_user or bool(notification_result.rowcount)


async def _remember_filter_prompt(state: FSMContext, message: Message) -> None:
    await state.update_data(
        filter_prompt_chat_id=message.chat.id,
        filter_prompt_message_id=message.message_id,
    )


async def _send_filter_prompt(
    *,
    answer: Callable[..., Any],
    state: FSMContext,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup],
) -> None:
    sent = await answer(text, reply_markup=reply_markup)
    await _remember_filter_prompt(state, sent)


async def _edit_filter_prompt(
    callback: CallbackQuery,
    state: FSMContext,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup],
) -> None:
    if callback.message is None:
        return

    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
        await _remember_filter_prompt(state, callback.message)
        return
    except TelegramAPIError:
        logger.warning("Could not edit filter prompt; sending a new prompt.", exc_info=True)

    await _send_filter_prompt(
        answer=callback.message.answer,
        state=state,
        text=text,
        reply_markup=reply_markup,
    )


async def _delete_filter_prompt(bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    chat_id = data.get("filter_prompt_chat_id")
    message_id = data.get("filter_prompt_message_id")
    if chat_id is None or message_id is None:
        return

    with suppress(TelegramAPIError):
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    await state.update_data(filter_prompt_chat_id=None, filter_prompt_message_id=None)


def load_user_matches(*, user_id: int, limit: int = 10) -> List[ListingMatch]:
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None or not user.parsed_preferences:
            return []
        matches = find_matches_for_user(
            session=session,
            user=user,
            exclude_sent=False,
            limit=limit,
            source_companies=ACTIVE_SOURCE_COMPANIES,
        )
        return matches


def _update_listing_activity_from_live_check(
    *,
    active_listing_ids: Iterable[int] = (),
    inactive_listing_ids: Iterable[int] = (),
) -> None:
    active_ids = tuple(active_listing_ids)
    inactive_ids = tuple(inactive_listing_ids)
    if not active_ids and not inactive_ids:
        return

    checked_at = datetime.utcnow()
    with SessionLocal() as session:
        if active_ids:
            listings = session.scalars(
                select(Listing).where(Listing.listing_id.in_(active_ids))
            )
            for listing in listings:
                listing.source_active = True
                listing.last_checked_at = checked_at
        if inactive_ids:
            listings = session.scalars(
                select(Listing).where(Listing.listing_id.in_(inactive_ids))
            )
            for listing in listings:
                listing.source_active = False
                listing.status = REMOVED_STATUS
                listing.last_checked_at = checked_at
        session.commit()


def _listing_match_from_model(
    listing: Listing,
    *,
    user_id: int = 0,
    reasons: tuple[str, ...] = ("current source listing",),
) -> ListingMatch:
    constraints = _listing_constraints_for_display(listing)
    required_wbs = effective_required_wbs(
        parsed_required_wbs=constraints.required_wbs,
        listing_title=listing.title,
        listing_text=listing.raw_text,
    )
    return ListingMatch(
        user_id=user_id,
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
        reasons=reasons,
        display_wbs=display_wbs_options_for_listing_text(
            parsed_required_wbs=constraints.required_wbs,
            listing_title=listing.title,
            listing_text=listing.raw_text,
        ),
        display_rent_kalt=extract_rent_display(
            listing.raw_text,
            KALT_RENT_LABELS,
        ),
        display_rent_warm=extract_rent_display(
            listing.raw_text,
            WARM_RENT_LABELS,
        ),
    )


def load_active_filtered_match_candidates(
    *,
    user_id: int,
    candidate_limit: int = ACTIVE_LISTING_CANDIDATE_LIMIT,
) -> List[ListingMatch]:
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None or not user.parsed_preferences:
            return []
        return find_matches_for_user(
            session=session,
            user=user,
            exclude_sent=False,
            limit=candidate_limit,
            source_companies=ACTIVE_SOURCE_COMPANIES,
            require_parsed_status=False,
            active_only=True,
        )


async def _check_match_source_active(
    match: ListingMatch,
) -> Optional[bool]:
    try:
        adapter = get_source_adapter(match.source_company)
        return await asyncio.to_thread(adapter.check_active, match.url)
    except (KeyError, ValueError):
        logger.warning(
            "No live-check adapter for listing_id=%s source=%s url=%s",
            match.listing_id,
            match.source_company,
            match.url,
            exc_info=True,
        )
        return None


async def _verified_active_matches(
    matches: List[ListingMatch],
    *,
    target_limit: int,
) -> List[ListingMatch]:
    verified: List[ListingMatch] = []

    for start in range(0, len(matches), LIVE_CHECK_BATCH_SIZE):
        batch = matches[start : start + LIVE_CHECK_BATCH_SIZE]
        results = await asyncio.gather(
            *(_check_match_source_active(match) for match in batch)
        )
        active_ids: List[int] = []
        inactive_ids: List[int] = []

        for match, is_active in zip(batch, results):
            if is_active is True:
                verified.append(match)
                active_ids.append(match.listing_id)
            elif is_active is False:
                inactive_ids.append(match.listing_id)

        await asyncio.to_thread(
            _update_listing_activity_from_live_check,
            active_listing_ids=active_ids,
            inactive_listing_ids=inactive_ids,
        )
        if len(verified) >= target_limit:
            return verified[:target_limit]

    return verified


def _validate_source_sync_result(source_company: str, sync_result: Any) -> None:
    if not sync_result.live_urls:
        raise RuntimeError(
            f"{source_company} returned 0 active listing URLs. "
            "This may indicate blocking, markup/API changes, or a temporary source outage."
        )


def _sync_status(sync_result: Any) -> str:
    return (
        INGESTION_STATUS_PARTIAL_SUCCESS
        if getattr(sync_result, "is_partial", False)
        else INGESTION_STATUS_SUCCESS
    )


def _sync_error_message(sync_result: Any, *, limit: int = 5) -> Optional[str]:
    errors = tuple(getattr(sync_result, "collection_errors", ()) or ())
    if not errors:
        return None
    visible_errors = "\n".join(errors[:limit])
    if len(errors) > limit:
        visible_errors += f"\n... and {len(errors) - limit} more collection errors"
    return visible_errors


def _short_error_message(value: Optional[str], *, limit: int = 700) -> str:
    if not value:
        return "no details"
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def _format_monitoring_timestamp(value: Optional[datetime]) -> str:
    if value is None:
        return "no data"
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


async def maybe_send_source_alerts(bot: Bot) -> None:
    settings = get_settings()
    if not settings.admin_telegram_user_ids:
        logger.warning(
            "Ingestion alerts skipped: ADMIN_TELEGRAM_USER_IDS is not configured."
        )
        return

    for source_company in ACTIVE_SOURCE_COMPANIES:
        candidate = await asyncio.to_thread(
            get_ingestion_alert_candidate,
            failure_threshold=settings.source_failure_alert_threshold,
            cooldown_seconds=settings.source_alert_cooldown_seconds,
            source_company=source_company,
            trigger_type=SOURCE_TRIGGER_BACKGROUND,
        )
        if candidate is None:
            continue

        text = (
            f"<b>{escape(source_company)}: possible source issue</b>\n\n"
            f"Consecutive failures: <b>{candidate.consecutive_failures}</b>\n"
            f"Trigger: {escape(candidate.trigger_type)}\n"
            f"Error type: {escape(candidate.error_type or 'unknown')}\n"
            f"Latest attempt: {_format_monitoring_timestamp(candidate.finished_at)}\n"
            f"Latest successful sync: {_format_monitoring_timestamp(candidate.last_success_at)}\n\n"
            "The bot may temporarily miss current listings from this source. "
            "The cause may be a timeout, site change, rate limit, or blocking.\n\n"
            f"Details: <code>{escape(_short_error_message(candidate.error_message))}</code>"
        )

        sent = False
        for admin_user_id in settings.admin_telegram_user_ids:
            try:
                await bot.send_message(chat_id=admin_user_id, text=text)
                sent = True
            except TelegramAPIError:
                logger.exception(
                    "Failed to send source alert source=%s admin_user_id=%s",
                    source_company,
                    admin_user_id,
                )

        if sent:
            await asyncio.to_thread(mark_ingestion_alert_sent, candidate.run_id)


def _risk_label(risk_score: int) -> str:
    if risk_score >= 75:
        return "high"
    if risk_score >= 41:
        return "medium"
    return "low"


def _short_evidence(value: str, *, max_len: int = 120) -> str:
    cleaned = " ".join(str(value or "").split())
    if not cleaned:
        return "not explicitly found"
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def _find_evidence_fragment(text: str, patterns: Iterable[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _short_evidence(match.group(0))
    return "not explicitly found"


def _format_parser_snapshot_value(value: Any) -> str:
    if value in (None, ""):
        return "not specified"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _field_issue_status(review: AIQAReview, field_aliases: Iterable[str]) -> str:
    issues = (review.ai_result or {}).get("issues") or []
    if not isinstance(issues, list):
        return "correct"
    aliases = tuple(alias.lower() for alias in field_aliases)
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        field = str(issue.get("field") or "").lower()
        if any(alias in field for alias in aliases):
            severity = str(issue.get("severity") or "risk").lower()
            return f"risk: {severity}"
    return "correct"


def _issue_field_label(field: str) -> str:
    labels = {
        "display_wbs": "WBS",
        "required_wbs": "WBS",
        "wbs": "WBS",
        "rooms": "Rooms",
        "room_count": "Rooms",
        "floor": "Floor",
        "address": "Address",
        "postal_code": "Postal code",
        "district": "District",
        "rent_kalt": "Kaltmiete",
        "kalt": "Kaltmiete",
        "rent_warm": "Warmmiete",
        "warm": "Warmmiete",
    }
    normalized = field.strip().lower()
    return labels.get(normalized, field or "Field")


def _review_issues(review: AIQAReview) -> List[Dict[str, Any]]:
    issues = (review.ai_result or {}).get("issues") or []
    if not isinstance(issues, list):
        return []
    return [issue for issue in issues if isinstance(issue, dict)]


def _wbs_evidence(review: AIQAReview) -> str:
    listing_text = _qa_listing_text(review)
    evidence = _find_evidence_fragment(
        listing_text,
        (
            r"wbs[^\n.!?]{0,80}",
            r"\b\d{2,3}(?:[,.]\d{1,2})?\s*(?:%|prozent)?[^\n.!?]{0,60}wbs\b",
            r"einkommensgrenze[^\n.!?]{0,100}",
            r"\bfreifinanziert\b",
            r"\bohne\s+(?:\S+\s+){0,4}?wbs\b",
            r"\bkein(?:e|en|er|es|em)?\s+(?:\S+\s+){0,4}?wbs\b",
            r"bewerbung\s+mit\s+wbs\s+nicht\s+möglich",
            r"wbs[^\n.!?]{0,50}(?:nicht\s+erforderlich|entfällt|frei)",
        ),
    )
    return evidence if evidence != "not explicitly found" else "WBS was not found in the listing text"


def _qa_listing_text(review: AIQAReview) -> str:
    with SessionLocal() as session:
        listing = session.get(Listing, review.listing_id)
        if listing is None:
            return ""
        return f"{listing.title or ''}\n{listing.raw_text or ''}"


def _qa_source_evidence(review: AIQAReview, field: str) -> str:
    text = _qa_listing_text(review)
    snapshot = review.parser_snapshot or {}
    value = snapshot.get(field)
    if field == "display_wbs":
        return _wbs_evidence(review)
    if value not in (None, ""):
        value_evidence = _find_evidence_fragment(text, (re.escape(str(value)),))
        if value_evidence != "not explicitly found" and field != "floor":
            return value_evidence
    if field == "rooms":
        return _find_evidence_fragment(
            text,
            (
                r"\b\d+(?:[,.]\d+)?[ \t]*[- ]?[ \t]*(?:zimmer|zi\.|räume|rooms?)\b",
                r"\b(?:anzahl\s+zimmer|zimmeranzahl|zimmer:)\D{0,10}\d+(?:[,.]\d+)?\b",
            ),
        )
    if field == "floor":
        return _find_evidence_fragment(
            text,
            (
                r"\b(?:etage|geschoss|stockwerk)\s*[:\-]?\s*(?:eg|erdgeschoss|dg|dachgeschoss|ug|untergeschoss|souterrain|-?\d{1,2})\b",
                r"\b(?:eg|erdgeschoss|dg|dachgeschoss|ug|untergeschoss|souterrain|-?\d{1,2})\.?\s*(?:etage|geschoss|stockwerk|og)\b",
            ),
        )
    if field == "address":
        return _find_evidence_fragment(
            text,
            (r"\b[A-ZÄÖÜ][\wÄÖÜäöüß.-]{2,}(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.-]{2,}){0,2}\s+(?:str\.|straße|strasse|weg|allee|damm|platz|ufer|ring|chaussee)\s*\d+[a-zA-Z]?\b",),
        )
    if field == "district":
        return _find_evidence_fragment(
            text,
            (
                r"\b\d{5}\s+[A-Za-zÄÖÜäöüß -]+(?:,\s*[A-Za-zÄÖÜäöüß -]+)?",
                r"\b(?:stadtteil|bezirk|ortsteil|lage)\s*[:\n]\s*[A-Za-zÄÖÜäöüß -]+",
                r"\bberlin[- ][A-Za-zÄÖÜäöüß-]+\b",
            ),
        )
    if field == "rent_kalt":
        return _find_evidence_fragment(
            text,
            (
                r"(?:kaltmiete|nettokaltmiete|netto-kaltmiete)[^\d]{0,60}\d{2,5}(?:[,.]\d{1,2})?\s*(?:€|eur)?",
                r"\d{2,5}(?:[,.]\d{1,2})?\s*(?:€|eur)[^\n]{0,60}(?:kalt|kaltmiete|nettokaltmiete)",
            ),
        )
    if field == "rent_warm":
        return _find_evidence_fragment(
            text,
            (
                r"(?:warmmiete|gesamtmiete|bruttowarmmiete)[^\d]{0,60}\d{2,5}(?:[,.]\d{1,2})?\s*(?:€|eur)?",
                r"\d{2,5}(?:[,.]\d{1,2})?\s*(?:€|eur)[^\n]{0,60}(?:warm|warmmiete|gesamtmiete|bruttowarmmiete)",
            ),
        )
    return "not explicitly found"


def _issue_source_evidence(review: AIQAReview, issue: Dict[str, Any]) -> str:
    evidence = str(issue.get("evidence") or "").strip()
    if evidence:
        return _short_evidence(evidence)

    field = str(issue.get("field") or "").strip().lower()
    if "wbs" in field:
        interpretation = (review.ai_result or {}).get("wbs_source_interpretation") or {}
        if isinstance(interpretation, dict):
            wbs_evidence = str(interpretation.get("evidence") or "").strip()
            if wbs_evidence:
                return _short_evidence(wbs_evidence)
        return _wbs_evidence(review)

    canonical_field = {
        "wbs": "display_wbs",
        "kalt": "rent_kalt",
        "warm": "rent_warm",
    }.get(field, field)
    return _qa_source_evidence(review, canonical_field)


def _human_issue_reason(reason: str) -> str:
    cleaned = " ".join(str(reason or "").split())
    technical_reasons = {
        "Mock QA re-read the WBS phrase and found a mismatch.": "The text states a different WBS condition.",
        "Mock QA re-read the room count in the listing text and found a mismatch.": "The text states a different room count.",
        "Mock QA re-read the Kaltmiete label and found a mismatch.": "The text states a different Kaltmiete.",
        "Mock QA re-read the Warmmiete/Gesamtmiete label and found a mismatch.": "The text states a different Warmmiete/Gesamtmiete.",
    }
    return technical_reasons.get(cleaned, cleaned or "no explanation")


def _format_qa_field(review: AIQAReview, *, title: str, field: str, aliases: Iterable[str]) -> str:
    snapshot = review.parser_snapshot or {}
    parser_value = _format_parser_snapshot_value(snapshot.get(field))
    extra_lines = ""
    if field == "address":
        address_sanity = snapshot.get("address_sanity")
        sanity_status = "not specified"
        sanity_details = "not specified"
        if isinstance(address_sanity, dict):
            sanity_status = str(address_sanity.get("status") or "not specified")
            sanity_details = str(address_sanity.get("details") or "not specified")
        extra_lines = (
            f"\nAddress source: {escape(str(snapshot.get('address_source') or 'not specified'))}"
            f"\nSanity: {escape(sanity_status)} — {escape(sanity_details)}"
        )
    return (
        f"<b>{title}</b>\n"
        f"Parser: {escape(str(parser_value))}\n"
        f"Source: {escape(_qa_source_evidence(review, field))}\n"
        f"AI: {escape(_field_issue_status(review, aliases))}"
        f"{extra_lines}"
    )


def _qa_field_blocks(review: AIQAReview) -> str:
    fields = (
        ("WBS", "display_wbs", ("wbs", "required_wbs", "display_wbs")),
        ("Rooms", "rooms", ("rooms", "zimmer")),
        ("Floor", "floor", ("floor", "etage")),
        ("Address", "address", ("address",)),
        ("District", "district", ("district",)),
        ("Kalt", "rent_kalt", ("rent_kalt", "kalt")),
        ("Warm", "rent_warm", ("rent_warm", "warm")),
    )
    return "\n\n".join(
        _format_qa_field(review, title=title, field=field, aliases=aliases)
        for title, field, aliases in fields
    )


def _issue_lines(review: AIQAReview, *, limit: int = 3) -> List[str]:
    issues = _review_issues(review)
    if not issues:
        return ["AI did not identify a specific field. Manual review is needed."]

    lines: List[str] = []
    for issue in issues[:limit]:
        field = str(issue.get("field") or "unknown")
        field_label = escape(_issue_field_label(field))
        parser_value = escape(str(issue.get("parser_value") or "not specified"))
        ai_value = escape(str(issue.get("ai_value") or "not specified"))
        reason = escape(_human_issue_reason(str(issue.get("reason") or "")))
        evidence = escape(_issue_source_evidence(review, issue))
        lines.append(
            f"<b>{field_label}</b>\n"
            f"Parser: {parser_value}\n"
            f"In listing: {evidence}\n"
            f"AI says: {ai_value}\n"
            f"Why: {reason}"
        )
    return lines or ["AI did not identify a specific field. Manual review is needed."]


def _format_wbs_source_interpretation(review: AIQAReview) -> str:
    interpretation = (review.ai_result or {}).get("wbs_source_interpretation") or {}
    if not isinstance(interpretation, dict) or not interpretation:
        return "AI did not provide a separate WBS source interpretation."

    kind_labels = {
        "no_wbs_mentioned": "WBS not mentioned",
        "no_wbs_required": "No WBS required",
        "generic_wbs_required": "WBS required, type unknown",
        "specific_wbs_values": "Specific WBS values found",
        "ambiguous": "Ambiguous",
    }
    kind = str(interpretation.get("kind") or "ambiguous")
    label = kind_labels.get(kind, kind)
    evidence = str(interpretation.get("evidence") or "not specified")
    explanation = str(interpretation.get("explanation") or "not specified")
    specific_values = interpretation.get("specific_values_found")
    if isinstance(specific_values, list) and specific_values:
        values_label = ", ".join(escape(str(value)) for value in specific_values)
    else:
        values_label = "none"
    return (
        f"Source type: <b>{escape(label)}</b>\n"
        f"Specific WBS values: {values_label}\n"
        f"Source fragment: {escape(evidence)}\n"
        f"AI explanation: {escape(explanation)}"
    )


def _ai_qa_feedback_keyboard(review_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Parser error",
                    callback_data=f"aiqa:feedback:{review_id}:{AI_QA_FEEDBACK_PARSER_ERROR}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Parser correct",
                    callback_data=f"aiqa:feedback:{review_id}:{AI_QA_FEEDBACK_PARSER_CORRECT}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Borderline / unsure",
                    callback_data=f"aiqa:feedback:{review_id}:{AI_QA_FEEDBACK_UNSURE}",
                ),
            ],
        ]
    )


def _format_ai_qa_review(
    review: AIQAReview,
    *,
    alert: bool,
    include_cost: bool = True,
    include_confidence: bool = True,
) -> str:
    header = (
        "<b>AI QA alert: possible parser error</b>"
        if alert
        else "<b>AI QA report</b>"
    )
    risk_score = int(review.risk_score or 0)
    confidence_percent = round(float(review.confidence or 0.0) * 100)
    issues = "\n\n".join(_issue_lines(review))
    confidence_line = f"AI confidence: {confidence_percent}%\n" if include_confidence else ""
    cost_line = (
        f"Check cost: ${float(review.total_cost_usd or 0.0):.6f}\n" if include_cost else ""
    )
    return (
        f"{header}\n\n"
        f"Listing:\n{escape(review.listing_url)}\n\n"
        "<b>Possible mismatch</b>\n"
        f"{issues}\n\n"
        "<b>Summary</b>\n"
        f"Risk score: <b>{risk_score} of 100 ({_risk_label(risk_score)})</b>\n"
        f"{confidence_line}"
        f"{cost_line}\n"
        "Choose a decision with the buttons below."
    )


def _feedback_decision_label(feedback_status: str) -> str:
    labels = {
        AI_QA_FEEDBACK_PARSER_ERROR: "parser error",
        AI_QA_FEEDBACK_PARSER_CORRECT: "parser correct",
        AI_QA_FEEDBACK_UNSURE: "borderline / unsure",
    }
    return labels.get(feedback_status, feedback_status)


async def send_ai_qa_alerts(bot: Bot, review_ids: Iterable[int]) -> int:
    review_id_tuple = tuple(review_ids)
    if not review_id_tuple:
        return 0

    settings = get_settings()
    if not settings.admin_telegram_user_ids:
        logger.warning("AI QA alert skipped: ADMIN_TELEGRAM_USER_IDS is not configured.")
        return 0

    sent_count = 0
    sent_review_ids: List[int] = []
    with SessionLocal() as session:
        reviews = load_ai_qa_reviews_for_alert(session, review_id_tuple)

    for review in reviews:
        text = _format_ai_qa_review(review, alert=True)
        sent_for_review = False
        for admin_user_id in settings.admin_telegram_user_ids:
            try:
                await bot.send_message(
                    chat_id=admin_user_id,
                    text=text,
                    reply_markup=_ai_qa_feedback_keyboard(review.review_id),
                    disable_web_page_preview=False,
                )
                sent_for_review = True
            except TelegramAPIError:
                logger.exception(
                    "Failed to send AI QA alert to admin_user_id=%s review_id=%s",
                    admin_user_id,
                    review.review_id,
                )
        if sent_for_review:
            sent_count += 1
            sent_review_ids.append(review.review_id)

    if sent_review_ids:
        with SessionLocal() as session:
            for review in session.scalars(
                select(AIQAReview).where(AIQAReview.review_id.in_(tuple(sent_review_ids)))
            ):
                review.alert_sent = True
            session.commit()

    return sent_count


def _run_ai_qa_for_urls(
    *,
    listing_urls: Iterable[str],
    trigger_type: str,
    source_company: str = PRIMARY_SOURCE_COMPANY,
) -> AIQARunResult:
    with SessionLocal() as session:
        result = run_ai_qa_for_unreviewed_active_listings(
            session,
            source_company=source_company,
            removed_status=REMOVED_STATUS,
            trigger_type=trigger_type,
            listing_urls=listing_urls,
        )
        session.commit()
        return result


def refresh_listing_database(
    *,
    trigger_type: str = SOURCE_TRIGGER_BACKGROUND,
) -> RefreshResult:
    listings_found = 0
    created_count = 0
    updated_count = 0
    saved_count = 0
    removed_count = 0
    parsed_count = 0
    transport_count = 0
    collection_error_count = 0
    ai_qa_checked_count = 0
    ai_qa_alert_review_ids: List[int] = []
    is_partial = False

    for source_company in ACTIVE_SOURCE_COMPANIES:
        adapter = get_source_adapter(source_company)
        started_at = datetime.utcnow()
        try:
            sync_result = adapter.sync(limit=None, mark_removed=True)
            _validate_source_sync_result(source_company, sync_result)
            live_urls = tuple(sync_result.live_urls)
            # Listings are parsed deterministically at ingestion, so every saved
            # listing is already parsed; there is no separate LLM parsing pass.
            source_parsed_count = sync_result.saved_count
            source_transport_count = enrich_missing_transport_walk(
                limit=None,
                listing_urls=live_urls,
            )
            ai_qa_result = _run_ai_qa_for_urls(
                listing_urls=live_urls,
                trigger_type=AI_QA_TRIGGER_NEW_LISTING,
                source_company=source_company,
            )
            ai_qa_checked_count += ai_qa_result.checked_count
            ai_qa_alert_review_ids.extend(ai_qa_result.alert_review_ids)
        except Exception as exc:
            logger.exception("Source refresh failed source=%s", source_company)
            record_ingestion_failure(
                trigger_type=trigger_type,
                error=exc,
                started_at=started_at,
                source_company=source_company,
            )
            is_partial = True
            collection_error_count += 1
            continue

        record_ingestion_success(
            trigger_type=trigger_type,
            listings_found=len(live_urls),
            saved_count=sync_result.saved_count,
            removed_count=sync_result.removed_count,
            parsed_count=source_parsed_count,
            transport_count=source_transport_count,
            started_at=started_at,
            source_company=source_company,
            status=_sync_status(sync_result),
            error_type=(
                f"Partial{source_company.replace(' ', '')}Sync"
                if sync_result.is_partial
                else None
            ),
            error_message=_sync_error_message(sync_result),
        )
        listings_found += len(live_urls)
        created_count += sync_result.created_count
        updated_count += sync_result.updated_count
        saved_count += sync_result.saved_count
        removed_count += sync_result.removed_count
        parsed_count += source_parsed_count
        transport_count += source_transport_count
        collection_error_count += len(sync_result.collection_errors)
        is_partial = is_partial or sync_result.is_partial

    return RefreshResult(
        listings_found=listings_found,
        created_count=created_count,
        updated_count=updated_count,
        saved_count=saved_count,
        removed_count=removed_count,
        parsed_count=parsed_count,
        transport_count=transport_count,
        is_partial=is_partial,
        collection_error_count=collection_error_count,
        ai_qa_checked_count=ai_qa_checked_count,
        ai_qa_alert_review_ids=tuple(ai_qa_alert_review_ids),
    )


def _listing_constraints_for_display(listing: Listing) -> ListingConstraints:
    if not listing.parsed_constraints:
        return ListingConstraints()
    return ListingConstraints.model_validate(listing.parsed_constraints)


def _local_listing_photo_path(image_url: Optional[str]) -> Optional[Path]:
    if not image_url or re.match(r"^https?://", image_url):
        return None
    candidate = Path(image_url)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    if not candidate.is_file():
        logger.warning("Listing photo asset is missing: %s", candidate)
        return None
    return candidate


async def send_match_to_chat(
    bot: Bot,
    *,
    chat_id: int,
    match: ListingMatch,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    text_prefix: str = "",
) -> None:
    # text_prefix lets the tour frame the card inside the same message (one
    # tap = one message); the card contract itself (field order, labels,
    # grouping) stays byte-identical below the prefix.
    text = text_prefix + format_match_message(match)
    photo_path = _local_listing_photo_path(match.image_url)
    if photo_path is not None:
        try:
            if len(text) <= TELEGRAM_PHOTO_CAPTION_LIMIT:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=FSInputFile(photo_path),
                    caption=text,
                    reply_markup=reply_markup,
                )
            else:
                await bot.send_photo(chat_id=chat_id, photo=FSInputFile(photo_path))
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup,
                )
            return
        except TelegramAPIError:
            logger.warning("Could not send listing photo; falling back to text.", exc_info=True)

    await bot.send_message(
        chat_id=chat_id,
        text=text,
        disable_web_page_preview=True,
        reply_markup=reply_markup,
    )


async def send_active_filtered_matches(message: Message, bot: Bot, *, user_id: int) -> None:
    if await asyncio.to_thread(load_user_preferences, user_id) is None:
        await message.answer(
            "The filter is not set up yet.\n\n"
            "Tap the button below to set it up, or send /filter.",
            reply_markup=_no_filter_keyboard(),
        )
        return

    await message.answer("Checking synthetic listings against your filter.")
    await asyncio.to_thread(enrich_missing_transport_walk, limit=None)
    candidates = await asyncio.to_thread(
        load_active_filtered_match_candidates,
        user_id=user_id,
        candidate_limit=ACTIVE_LISTING_CANDIDATE_LIMIT,
    )
    matches = await _verified_active_matches(
        candidates,
        target_limit=CURRENT_LISTINGS_LIMIT,
    )

    logger.info(
        "Filtered listing request finished: user_id=%s candidates=%s displayed=%s",
        user_id,
        len(candidates),
        len(matches),
    )

    if not matches:
        await message.answer(
            "There are no active listings matching your filter right now.\n\n"
            "Try loosening the filter, or run the temporary demo filter.",
            reply_markup=_no_matches_keyboard(),
        )
        return

    await message.answer(
        f"Showing up to {CURRENT_LISTINGS_LIMIT} active listings that match your filter."
    )
    for match in matches:
        await send_match_to_chat(bot, chat_id=message.chat.id, match=match)


async def send_settings_card(message: Message, *, user_id: int) -> None:
    preferences = await asyncio.to_thread(load_user_preferences, user_id)
    await message.answer(
        _settings_card(preferences),
        reply_markup=_settings_keyboard(has_filter=preferences is not None),
    )


async def send_settings_card_from_callback(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    preferences = await asyncio.to_thread(load_user_preferences, callback.from_user.id)
    await callback.message.answer(
        _settings_card(preferences),
        reply_markup=_settings_keyboard(has_filter=preferences is not None),
    )


def _wbs_step_text(*, expired: bool = False) -> str:
    prefix = SETUP_EXPIRED_TEXT if expired else ""
    return prefix + _step_prefix(1) + "Which WBS should match?\n\n" + WBS_HINT


async def begin_filter_setup(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(FilterSetup.choosing_wbs)
    await _send_filter_prompt(
        answer=message.answer,
        state=state,
        text=(
            "Let's set up the filter step by step. Choose options with the buttons, "
            "and tap ✖ Cancel any time to stop.\n\n" + _wbs_step_text()
        ),
        reply_markup=_wbs_keyboard(),
    )


async def _clear_markup(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=None)


# ---------------------------------------------------------------------------
# Guided tour
#
# A 2-step, button-only walkthrough for a first-time visitor with no
# context: (1) a temporary four-field filter, then (2) a result from the real
# matching predicate over the synthetic catalog. The optional "How matching
# works" explainer is available from the result without interrupting the core
# path.
# Every dynamic value (listing, district, prices, WBS phrasing, match count)
# is read from the tour listing and the demo catalog at runtime.
#
# The demo filter stays ephemeral (never written to `users`) until the
# visitor explicitly taps "Use this demo filter" on the result. Step 2 runs the
# real matching predicate (is_listing_match) and the synthetic adapter's local
# activity check over the demo catalog.
# ---------------------------------------------------------------------------


def _select_tour_listing() -> Optional[Listing]:
    """Deterministically pick one listing for the tour: 2 rooms, a WBS
    requirement that includes 140, a WBS phrase in the raw text, and transit
    data, so every screen has something concrete to show."""
    with SessionLocal() as session:
        candidates = list(
            session.scalars(
                select(Listing)
                .where(Listing.source_company.in_(ACTIVE_SOURCE_COMPANIES))
                .where(Listing.source_active.is_(True))
                .where(Listing.status != REMOVED_STATUS)
                .order_by(Listing.first_seen_at.asc(), Listing.listing_id.asc())
            )
        )

    for listing in candidates:
        if listing.rooms != 2:
            continue
        if "wbs" not in (listing.raw_text or "").lower():
            continue
        transport_walk = listing.transport_walk or {}
        if (
            transport_walk.get("s_bahn_minutes") is None
            and transport_walk.get("u_bahn_minutes") is None
        ):
            continue
        requirement = effective_wbs_requirement(
            parsed_required_wbs=_listing_constraints_for_display(listing).required_wbs,
            listing_title=listing.title,
            listing_text=listing.raw_text,
        )
        if 140 in (requirement.allowed_percentages or ()):
            return listing
    return None


def _tour_wbs_percent(allowed_percentages: tuple[int, ...]) -> int:
    return 140 if 140 in allowed_percentages else allowed_percentages[0]


def _tour_max_rent(rent_kalt_eur: Optional[int]) -> int:
    if rent_kalt_eur is None:
        return RENT_PRESETS[0]
    for preset in RENT_PRESETS:
        if preset >= rent_kalt_eur:
            return preset
    return (int(rent_kalt_eur) // 100 + 1) * 100


def _tour_filter_summary(listing: Listing) -> tuple[UserPreferences, int]:
    requirement = effective_wbs_requirement(
        parsed_required_wbs=_listing_constraints_for_display(listing).required_wbs,
        listing_title=listing.title,
        listing_text=listing.raw_text,
    )
    wbs_percent = _tour_wbs_percent(requirement.allowed_percentages or (140,))
    preferences = UserPreferences(
        location=[listing.district] if listing.district else None,
        wbs_type=f"WBS {wbs_percent}",
        max_rent=_tour_max_rent(listing.rent_kalt),
        rooms=float(listing.rooms) if listing.rooms is not None else None,
    )
    return preferences, wbs_percent


def _tour_candidate_matches(preferences: UserPreferences) -> List[ListingMatch]:
    """Every active, parsed listing that satisfies the ephemeral tour filter,
    using the same is_listing_match predicate the main matching path uses."""
    with SessionLocal() as session:
        listings = list(
            session.scalars(
                select(Listing)
                .where(Listing.source_company.in_(ACTIVE_SOURCE_COMPANIES))
                .where(Listing.source_active.is_(True))
                .where(Listing.status == PARSED_LISTING_STATUS)
            )
        )
    matches: List[ListingMatch] = []
    for listing in listings:
        decision = is_listing_match(
            preferences=preferences,
            constraints=_listing_constraints_for_display(listing),
            listing=listing,
        )
        if decision.is_match:
            matches.append(_listing_match_from_model(listing, reasons=decision.reasons))
    return matches


def _tour_next_keyboard(label: str, callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=callback_data)]]
    )


def _tour_intro_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Try the demo", callback_data="tour:1")],
            [InlineKeyboardButton(text="Set up my filter", callback_data="settings:filter")],
        ]
    )


def _tour_start_keyboard() -> InlineKeyboardMarkup:
    return _tour_next_keyboard("Try the demo", "tour:1")


def _tour_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Use this demo filter", callback_data="tour:save_filter")],
            [InlineKeyboardButton(text="Set up my own filter", callback_data="settings:filter")],
            [InlineKeyboardButton(text="How matching works", callback_data="tour:3")],
            [InlineKeyboardButton(text="Read the case study", url=CASE_STUDY_URL)],
        ]
    )


def _tour_explainer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Use this demo filter", callback_data="tour:save_filter")],
            [InlineKeyboardButton(text="Set up my own filter", callback_data="settings:filter")],
            [InlineKeyboardButton(text="Read the case study", url=CASE_STUDY_URL)],
        ]
    )


async def _send_tour_screen_0(message: Message) -> None:
    # Two messages by platform constraint, not by choice: a Telegram message
    # carries exactly one keyboard, and the persistent reply keyboard must be
    # attached to some message or the user has no menu after the tour. Both
    # arrive together before the user starts reading, so nothing scrolls away
    # mid-step; every actual tour step is a single message.
    await message.answer(
        "This is <b>FlatFeed</b> — a Telegram product prototype for matching Berlin "
        "WBS listings against four saved criteria. The catalog is synthetic, and "
        "FlatFeed does not save your filter until you explicitly keep it.",
        reply_markup=main_menu_keyboard(),
    )
    await message.answer(
        "<b>See a working match?</b>\n\n"
        "FlatFeed tests a narrow product hypothesis: one saved filter can make "
        "scattered, inconsistent WBS listings easier to check.\n\n"
        "Two steps, no typing: inspect a temporary filter, then run it against "
        "the demo catalog.",
        reply_markup=_tour_intro_keyboard(),
    )


async def _send_tour_screen_1(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    # _select_tour_listing() requires transit data; a freshly ingested
    # catalog (e.g. right after scripts/ingest_synthetic.py) has none yet,
    # since enrichment normally happens lazily on the first matching request.
    # The tour is often that first interaction, so it must trigger
    # enrichment itself instead of assuming it already ran.
    await asyncio.to_thread(enrich_missing_transport_walk, limit=None)
    listing = await asyncio.to_thread(_select_tour_listing)
    if listing is None:
        await callback.message.answer(
            "The tour needs at least one active synthetic listing with a WBS 140 "
            "requirement, and none is available right now. Set up your own filter "
            "or try again later."
        )
        return

    preferences, wbs_percent = _tour_filter_summary(listing)
    rent_label = (
        f"{preferences.max_rent} EUR" if preferences.max_rent is not None else "no limit"
    )
    district_label = listing.district or "any district"
    rooms_label = _display_rooms(listing.rooms)
    await callback.message.answer(
        "<b>Demo 1/2 · Temporary filter</b>\n\n"
        f"Say you hold a WBS-{wbs_percent} certificate — Berlin's housing-eligibility "
        f"document — and need a {escape(rooms_label)}-room flat in "
        f"{escape(district_label)} under {rent_label} Kaltmiete (base rent before "
        "utilities).\n\n"
        f"<b>WBS:</b> {wbs_percent}\n"
        f"<b>District:</b> {escape(district_label)}\n"
        f"<b>Kaltmiete:</b> up to {rent_label}\n"
        f"<b>Rooms:</b> {escape(rooms_label)}\n\n"
        "This demo filter is temporary — it is not saved unless you choose to "
        "keep it after seeing the result.",
        reply_markup=_tour_next_keyboard("Find matches", "tour:2"),
    )


async def _send_tour_screen_2(callback: CallbackQuery, bot: Bot) -> None:
    if callback.message is None:
        return
    listing = await asyncio.to_thread(_select_tour_listing)
    if listing is None:
        return

    preferences, _ = _tour_filter_summary(listing)
    candidate_matches = await asyncio.to_thread(_tour_candidate_matches, preferences)
    verified_matches = await _verified_active_matches(
        candidate_matches,
        target_limit=len(candidate_matches) or 1,
    )
    tour_match = next(
        (match for match in verified_matches if match.listing_id == listing.listing_id),
        None,
    )
    match_count = len(verified_matches)
    if tour_match is None:
        await callback.message.answer(
            "The selected synthetic listing did not pass the adapter activity check, "
            "so the tour will not present it as a verified match. Please try again."
        )
        return

    reasons_label = (
        " · ".join(tour_match.reasons) if tour_match.reasons else "all four criteria match"
    )
    plural = "s" if match_count != 1 else ""
    step_text = (
        "<b>Demo 2/2 · Matching result</b>\n\n"
        "FlatFeed applied four fixed matching rules to its synthetic catalog. This "
        f"card is 1 of {match_count} matching listing{plural}. Why it matched: "
        f"{reasons_label}.\n\n"
        "The listing summary also adds estimated walking times to the nearest "
        "S-Bahn and U-Bahn stations.\n\n"
    )

    await send_match_to_chat(
        bot,
        chat_id=callback.message.chat.id,
        match=tour_match,
        reply_markup=_tour_result_keyboard(),
        text_prefix=step_text,
    )


async def _send_tour_screen_3(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    await callback.message.answer(
        "<b>How the matching path works</b>\n\n"
        "<b>Collect:</b> one synthetic adapter adds new demo listings to the catalog.\n"
        "<b>Normalize:</b> fixed parsing rules turn free-form text into the fields "
        "you saw on the card.\n"
        "<b>Enrich:</b> local station data estimates walking times to the nearest "
        "S-Bahn and U-Bahn stations.\n"
        "<b>Match:</b> fixed rules compare WBS type, district, Kaltmiete and rooms.\n"
        "<b>Deliver:</b> the demo shows matches on request; optional background mode "
        "sends newly found matches automatically.\n\n"
        "No AI sits in this matching path. If you save a filter, FlatFeed stores your "
        "Telegram ID, filter and notification history; /delete removes those records "
        "from FlatFeed's database.",
        reply_markup=_tour_explainer_keyboard(),
    )


@router.callback_query(F.data == "tour:1")
async def handle_tour_screen_1(callback: CallbackQuery) -> None:
    await callback.answer()
    await _send_tour_screen_1(callback)


@router.callback_query(F.data == "tour:2")
async def handle_tour_screen_2(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    await _send_tour_screen_2(callback, bot)


@router.callback_query(F.data == "tour:3")
async def handle_tour_screen_3(callback: CallbackQuery) -> None:
    await callback.answer()
    await _send_tour_screen_3(callback)


@router.callback_query(F.data == "tour:save_filter")
async def handle_tour_save_filter(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    listing = await asyncio.to_thread(_select_tour_listing)
    if listing is None:
        await callback.message.answer(
            "The tour listing is no longer available. Use ⚙ Filter to set up your "
            "own filter instead."
        )
        return
    preferences, _ = _tour_filter_summary(listing)
    await asyncio.to_thread(
        save_fixed_preferences,
        user_id=callback.from_user.id,
        preferences=preferences,
    )
    await _clear_markup(callback)
    await callback.message.answer(
        "Saved. Tap 🔎 Show matches any time to see this filter's matches, or "
        "/delete to remove it."
    )


def _help_text() -> str:
    return (
        "<b>How FlatFeed works</b>\n\n"
        "FlatFeed is a demo assistant for Berlin WBS apartments. It matches a small "
        "catalog of <i>synthetic</i> listings — no real housing-company data is scraped.\n\n"
        "<b>Glossary</b>\n"
        "• WBS (Wohnberechtigungsschein): Berlin eligibility certificate; the number is "
        "the income tier (higher number = higher allowed income).\n"
        "• Kaltmiete: base rent without utilities (Nebenkosten).\n\n"
        "<b>What you can do</b>\n"
        "• ⚙ Filter — set up or edit WBS type, district, rent, and rooms.\n"
        "• 🔎 Show matches — up to three listings that match your saved filter.\n"
        "• Try the demo — run a temporary filter without saving it.\n\n"
        "<b>Commands</b>\n"
        "/filter — set up or edit your filter\n"
        "/matches — show matching listings\n"
        "/delete — delete your saved data\n"
        "/help — show this help"
    )


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user is None:
        return
    await _send_tour_screen_0(message)


@router.message(Command("help"))
async def handle_help_command(message: Message) -> None:
    await message.answer(_help_text(), reply_markup=_tour_start_keyboard())


@router.message(Command("settings"))
async def handle_settings_command(message: Message) -> None:
    if message.from_user is None:
        return
    await send_settings_card(message, user_id=message.from_user.id)


@router.message(Command("filter"))
async def handle_filter_command(message: Message, state: FSMContext) -> None:
    await begin_filter_setup(message, state)


@router.message(Command("reset"))
async def handle_reset_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user is None:
        return
    removed = await asyncio.to_thread(reset_user_filter, message.from_user.id)
    if removed:
        await message.answer(
            "Filter reset. Send /filter to set it up again.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await message.answer(
            "The filter was not set up yet. Send /filter to set it up.",
            reply_markup=main_menu_keyboard(),
        )


@router.message(Command("delete"))
async def handle_delete_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user is None:
        return
    await message.answer(
        "Delete <b>all</b> your data? This removes your saved filter and your "
        "sent-notification history. This cannot be undone.",
        reply_markup=_delete_confirm_keyboard(),
    )


@router.message(Command("matches"))
async def handle_matches_command(message: Message, bot: Bot) -> None:
    if message.from_user is None:
        return
    await send_active_filtered_matches(message, bot, user_id=message.from_user.id)


@router.message(F.text == BTN_SETTINGS)
async def handle_settings_button(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await state.clear()
    await send_settings_card(message, user_id=message.from_user.id)


@router.message(F.text == BTN_MATCHES)
async def handle_matches_button(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user is None:
        return
    await state.clear()
    await send_active_filtered_matches(message, bot, user_id=message.from_user.id)


async def _finish_edit_if_needed(callback: CallbackQuery, state: FSMContext) -> bool:
    data = await state.get_data()
    if not data.get("edit_field"):
        return False

    preferences = _preferences_from_state_data(data)
    await asyncio.to_thread(
        save_fixed_preferences,
        user_id=callback.from_user.id,
        preferences=preferences,
    )
    await state.clear()
    if callback.message:
        with suppress(TelegramAPIError):
            await callback.message.edit_text("Filter updated.", reply_markup=None)
    await send_settings_card_from_callback(callback)
    return True


@router.callback_query(F.data == "settings:filter")
async def handle_settings_filter(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(FilterSetup.choosing_wbs)
    await _edit_filter_prompt(
        callback,
        state,
        _wbs_step_text(),
        _wbs_keyboard(),
    )


@router.callback_query(F.data == "settings:edit_menu")
async def handle_settings_edit_menu(callback: CallbackQuery) -> None:
    preferences = await asyncio.to_thread(load_user_preferences, callback.from_user.id)
    if preferences is None:
        await callback.answer("Set up the filter first.", show_alert=True)
        return
    await callback.answer()
    if callback.message is None:
        return
    await callback.message.edit_text(
        "Choose what to edit:",
        reply_markup=_edit_filter_keyboard(),
    )


@router.callback_query(F.data == "settings:back")
async def handle_settings_back(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None:
        return
    preferences = await asyncio.to_thread(load_user_preferences, callback.from_user.id)
    await callback.message.edit_text(
        _settings_card(preferences),
        reply_markup=_settings_keyboard(has_filter=preferences is not None),
    )


@router.callback_query(F.data.startswith("settings:edit:"))
async def handle_settings_edit(callback: CallbackQuery, state: FSMContext) -> None:
    field = (callback.data or "").split(":", maxsplit=2)[2]
    preferences = await asyncio.to_thread(load_user_preferences, callback.from_user.id)
    if preferences is None:
        await callback.answer("Set up the filter first.", show_alert=True)
        return

    await callback.answer()
    await state.clear()
    await state.update_data(
        edit_field=field,
        existing_preferences=preferences.model_dump(mode="json"),
    )
    if field == "wbs":
        await state.set_state(FilterSetup.choosing_wbs)
        await _edit_filter_prompt(
            callback,
            state,
            "Choose a new WBS:\n\n" + WBS_HINT,
            _wbs_keyboard(selected=preferences.wbs_type, include_back=True),
        )
    elif field == "location":
        await state.set_state(FilterSetup.choosing_location)
        current_location = preferences.location[0] if preferences.location else "ANY"
        await _edit_filter_prompt(
            callback,
            state,
            "Choose a new district:",
            _location_keyboard(selected=current_location, include_back=True),
        )
    elif field == "rent":
        await state.set_state(FilterSetup.choosing_rent)
        await _edit_filter_prompt(callback, state, _rent_prompt(), _rent_keyboard(include_back=True))
    elif field == "rooms":
        await state.set_state(FilterSetup.choosing_rooms)
        await _edit_filter_prompt(
            callback,
            state,
            "Choose a new room count:",
            _rooms_keyboard(selected=_rooms_option_value(preferences.rooms), include_back=True),
        )


@router.callback_query(F.data == "settings:matches")
async def handle_settings_matches(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    if callback.message is None:
        return
    await send_active_filtered_matches(callback.message, bot, user_id=callback.from_user.id)


@router.callback_query(F.data.startswith("aiqa:feedback:"))
async def handle_ai_qa_feedback(callback: CallbackQuery) -> None:
    if not _is_admin_user(callback.from_user.id):
        await callback.answer("This button is only available to admins.", show_alert=True)
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Invalid button.", show_alert=True)
        return
    try:
        review_id = int(parts[2])
    except ValueError:
        await callback.answer("Invalid review_id.", show_alert=True)
        return
    feedback_status = parts[3]

    with SessionLocal() as session:
        updated = update_ai_qa_feedback(
            session,
            review_id=review_id,
            feedback_status=feedback_status,
            admin_user_id=callback.from_user.id,
        )
        session.commit()

    if not updated:
        await callback.answer("AI QA review not found.", show_alert=True)
        return

    await callback.answer(
        f"Saved: {_feedback_decision_label(feedback_status)}."
    )
    if callback.message is not None:
        with suppress(TelegramAPIError):
            await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data == "settings:reset")
async def handle_settings_reset(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None:
        return
    with suppress(TelegramAPIError):
        await callback.message.edit_text(
            "Reset the filter? This clears WBS type, district, rent, and rooms.",
            reply_markup=_reset_confirm_keyboard(),
        )


@router.callback_query(F.data == "settings:reset_confirm")
async def handle_settings_reset_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await asyncio.to_thread(reset_user_filter, callback.from_user.id)
    await _clear_markup(callback)
    if callback.message:
        await callback.message.answer(
            "Filter reset.",
            reply_markup=main_menu_keyboard(),
        )
    await send_settings_card_from_callback(callback)


@router.callback_query(F.data == "settings:delete")
async def handle_settings_delete(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None:
        return
    with suppress(TelegramAPIError):
        await callback.message.edit_text(
            "Delete your saved FlatFeed data? This removes your filter and your "
            "sent-notification history from the FlatFeed database. This cannot be undone.",
            reply_markup=_delete_confirm_keyboard(),
        )


@router.callback_query(F.data == "settings:delete_confirm")
async def handle_settings_delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    deleted = await asyncio.to_thread(delete_user_data, callback.from_user.id)
    await _clear_markup(callback)
    if callback.message:
        await callback.message.answer(
            "I deleted your saved filter and sent-notification history."
            if deleted
            else "I had no saved data for your Telegram ID.",
            reply_markup=main_menu_keyboard(),
        )


@router.callback_query(F.data == NAV_CANCEL)
async def handle_nav_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    was_edit = bool(data.get("edit_field"))
    await state.clear()
    await callback.answer("Cancelled.")
    if callback.message is not None:
        with suppress(TelegramAPIError):
            await callback.message.edit_text(
                "Edit cancelled." if was_edit else "Setup cancelled.",
                reply_markup=None,
            )
    await send_settings_card_from_callback(callback)


@router.callback_query(F.data == NAV_BACK)
async def handle_nav_back(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    if data.get("edit_field"):
        # Back from a single-field edit returns to the edit menu.
        await state.clear()
        if callback.message is not None:
            with suppress(TelegramAPIError):
                await callback.message.edit_text(
                    "Choose what to edit:",
                    reply_markup=_edit_filter_keyboard(),
                )
        return

    current = await state.get_state()
    if current == FilterSetup.choosing_location.state:
        await state.set_state(FilterSetup.choosing_wbs)
        await _edit_filter_prompt(
            callback,
            state,
            _wbs_step_text(),
            _wbs_keyboard(selected=data.get("wbs_type")),
        )
    elif current == FilterSetup.choosing_rent.state:
        await state.set_state(FilterSetup.choosing_location)
        loc = data.get("location")
        selected_loc = loc if loc else ("ANY" if data.get("location_selected") else None)
        await _edit_filter_prompt(
            callback,
            state,
            _step_prefix(2) + "Which district should I search in?",
            _location_keyboard(selected=selected_loc, include_back=True),
        )
    elif current == FilterSetup.choosing_rooms.state:
        await state.set_state(FilterSetup.choosing_rent)
        await _edit_filter_prompt(
            callback,
            state,
            _step_prefix(3) + _rent_prompt(),
            _rent_keyboard(include_back=True),
        )
    else:
        await state.set_state(FilterSetup.choosing_wbs)
        await _edit_filter_prompt(callback, state, _wbs_step_text(), _wbs_keyboard())


@router.callback_query(F.data.startswith("filter:wbs:"))
async def handle_wbs_choice(callback: CallbackQuery, state: FSMContext) -> None:
    value = (callback.data or "").split(":", maxsplit=2)[2]
    if value in {ANY_WBS_VALUE, NO_WBS_VALUE}:
        wbs_type = value
    else:
        wbs_type = value.replace("_", " ")
    await state.update_data(wbs_type=wbs_type, wbs_selected=True)
    if await _finish_edit_if_needed(callback, state):
        await callback.answer()
        return
    await state.set_state(FilterSetup.choosing_location)
    await callback.answer()
    await _edit_filter_prompt(
        callback,
        state,
        _step_prefix(2) + "Which district should I search in?",
        _location_keyboard(include_back=True),
    )


@router.callback_query(F.data.startswith("filter:location:"))
async def handle_location_choice(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("edit_field") and not data.get("wbs_selected"):
        await state.clear()
        await state.set_state(FilterSetup.choosing_wbs)
        await callback.answer("Setup session expired.")
        await _edit_filter_prompt(callback, state, _wbs_step_text(expired=True), _wbs_keyboard())
        return

    value = (callback.data or "").split(":", maxsplit=2)[2]
    location = None if value == "ANY" else value
    await state.update_data(location=location, location_selected=True)
    if await _finish_edit_if_needed(callback, state):
        await callback.answer()
        return
    await state.set_state(FilterSetup.choosing_rent)
    await callback.answer()
    await _edit_filter_prompt(
        callback,
        state,
        _step_prefix(3) + _rent_prompt(),
        _rent_keyboard(include_back=True),
    )


async def _save_rent_choice(
    *,
    max_rent: Optional[int],
    state: FSMContext,
    user_id: int,
) -> bool:
    await state.update_data(max_rent=max_rent, rent_selected=True)

    data = await state.get_data()
    if data.get("edit_field"):
        preferences = _preferences_from_state_data(data)
        await asyncio.to_thread(
            save_fixed_preferences,
            user_id=user_id,
            preferences=preferences,
        )
        await state.clear()
        return True

    await state.set_state(FilterSetup.choosing_rooms)
    return False


@router.callback_query(F.data.startswith("filter:rent:"))
async def handle_rent_choice(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("edit_field") and not data.get("location_selected"):
        await state.clear()
        await state.set_state(FilterSetup.choosing_wbs)
        await callback.answer("Setup session expired.")
        await _edit_filter_prompt(callback, state, _wbs_step_text(expired=True), _wbs_keyboard())
        return

    raw = (callback.data or "").split(":", maxsplit=2)[2]
    max_rent: Optional[int] = None if raw == "NO_LIMIT" else int(raw)

    await callback.answer()
    if callback.message is None:
        return
    edited = await _save_rent_choice(
        max_rent=max_rent,
        state=state,
        user_id=callback.from_user.id,
    )
    if edited:
        with suppress(TelegramAPIError):
            await callback.message.edit_text("Filter updated.", reply_markup=None)
        await send_settings_card_from_callback(callback)
    else:
        await _edit_filter_prompt(
            callback,
            state,
            _step_prefix(4) + "How many rooms do you need?",
            _rooms_keyboard(include_back=True),
        )


@router.message(FilterSetup.choosing_rent, F.text)
async def handle_rent_text(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user is None or message.text is None:
        return

    try:
        max_rent = _parse_rent_input(message.text)
    except ValueError:
        await message.answer(
            "I did not understand the amount. Enter a number in EUR, for example 650. "
            "If there is no limit, tap the No limit button."
        )
        return

    data = await state.get_data()
    if not data.get("edit_field") and not data.get("location_selected"):
        await state.clear()
        await state.set_state(FilterSetup.choosing_wbs)
        await message.answer(
            _wbs_step_text(expired=True),
            reply_markup=_wbs_keyboard(),
        )
        return

    await _delete_filter_prompt(bot, state)
    edited = await _save_rent_choice(
        max_rent=max_rent,
        state=state,
        user_id=message.from_user.id,
    )
    if edited:
        await message.answer("Filter updated.")
        await send_settings_card(message, user_id=message.from_user.id)
    else:
        await _send_filter_prompt(
            answer=message.answer,
            state=state,
            text=_step_prefix(4) + "How many rooms do you need?",
            reply_markup=_rooms_keyboard(include_back=True),
        )


@router.callback_query(F.data.startswith("filter:rooms:"))
async def handle_rooms_choice(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None:
        return
    data = await state.get_data()
    if not data.get("edit_field") and not data.get("rent_selected"):
        await state.clear()
        await state.set_state(FilterSetup.choosing_wbs)
        await callback.answer("Setup session expired.")
        await _edit_filter_prompt(callback, state, _wbs_step_text(expired=True), _wbs_keyboard())
        return

    value = (callback.data or "").split(":", maxsplit=2)[2]
    if value == "ANY":
        rooms = None
    else:
        rooms = 5.0 if value == "5PLUS" else float(value)
    await state.update_data(rooms=rooms)
    data = await state.get_data()
    preferences = _preferences_from_filter_data(data)

    await asyncio.to_thread(
        save_fixed_preferences,
        user_id=callback.from_user.id,
        preferences=preferences,
    )
    await state.clear()
    await callback.answer()
    if callback.message:
        with suppress(TelegramAPIError):
            await callback.message.edit_text(_filter_summary(preferences), reply_markup=None)
            return
        await callback.message.answer(
            _filter_summary(preferences),
            reply_markup=main_menu_keyboard(),
        )


@router.message(F.text)
async def handle_plain_text(message: Message) -> None:
    await message.answer(
        "I only change your filter through the buttons, so free-text messages "
        "cannot overwrite it by accident.\n\n"
        "Use the buttons below: set up a filter, show matches, or browse the demo catalog."
    )


async def run_ingestion_and_extraction() -> tuple[int, ...]:
    result = await asyncio.to_thread(
        refresh_listing_database,
        trigger_type=SOURCE_TRIGGER_BACKGROUND,
    )
    logger.info(
        (
            "Pipeline finished: found=%s saved=%s removed=%s parsed=%s transport=%s "
            "partial=%s errors=%s ai_qa_checked=%s ai_qa_alerts=%s"
        ),
        result.listings_found,
        result.saved_count,
        result.removed_count,
        result.parsed_count,
        result.transport_count,
        result.is_partial,
        result.collection_error_count,
        result.ai_qa_checked_count,
        len(result.ai_qa_alert_review_ids),
    )
    return result.ai_qa_alert_review_ids


async def send_pending_notifications(bot: Bot) -> int:
    settings = get_settings()
    await asyncio.to_thread(enrich_missing_transport_walk, limit=None)
    with SessionLocal() as session:
        matches = find_pending_matches(
            session=session,
            limit_per_user=settings.bot_notification_limit_per_user,
            source_companies=ACTIVE_SOURCE_COMPANIES,
        )
    verified_matches = await _verified_active_matches(
        matches,
        target_limit=len(matches),
    )

    sent_count = 0
    for match in verified_matches:
        try:
            await send_match_to_chat(bot, chat_id=match.user_id, match=match)
        except TelegramAPIError:
            logger.exception(
                "Failed to send listing notification user_id=%s listing_id=%s",
                match.user_id,
                match.listing_id,
            )
            continue

        with SessionLocal() as session:
            mark_match_sent(session=session, match=match)
            session.commit()
        sent_count += 1

    return sent_count


async def run_hourly_pipeline(bot: Bot) -> None:
    settings = get_settings()
    min_interval = max(settings.bot_scan_min_seconds, 60)
    max_interval = max(settings.bot_scan_max_seconds, min_interval)

    while True:
        try:
            ai_qa_alert_review_ids = await run_ingestion_and_extraction()
            ai_qa_alert_count = await send_ai_qa_alerts(bot, ai_qa_alert_review_ids)
            if ai_qa_alert_count:
                logger.info("AI QA alert pass finished: sent=%s", ai_qa_alert_count)
            sent_count = await send_pending_notifications(bot)
            logger.info("Notification pass finished: sent=%s", sent_count)
        except Exception:
            logger.exception("Background listing pipeline failed.")
            await maybe_send_source_alerts(bot)

        interval = random.randint(min_interval, max_interval)
        logger.info("Next multi-source background check in %s seconds.", interval)
        await asyncio.sleep(interval)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = get_settings()
    if not settings.telegram_bot_token:
        env_file = os.getenv("ENV_FILE", ".env")
        raise RuntimeError(
            f"TELEGRAM_BOT_TOKEN is not configured. Add it to {env_file}."
        )

    init_db()

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Start / main menu"),
            BotCommand(command="filter", description="Set up or edit your filter"),
            BotCommand(command="matches", description="Show matching listings"),
            BotCommand(command="help", description="How FlatFeed works"),
            BotCommand(command="delete", description="Delete my data"),
        ]
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)

    background_task: Optional[asyncio.Task[Any]] = None
    if settings.bot_background_enabled:
        background_task = asyncio.create_task(run_hourly_pipeline(bot))
    else:
        logger.info("Background multi-source pipeline is disabled for this bot process.")
    try:
        await dispatcher.start_polling(bot)
    finally:
        if background_task is not None:
            background_task.cancel()
            with suppress(asyncio.CancelledError):
                await background_task
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
