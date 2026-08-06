import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from flatfeed.db.models import Base, Listing, User
from synthetic.generator import SYNTHETIC_BASE_URL

import main as M


TEST_SOURCE_COMPANY = "FlatFeed Synthetic"


def _make_listing(
    *,
    suffix: str,
    rooms: float,
    district: str,
    raw_text: str,
    rent_kalt: int,
    first_seen_at: datetime,
    transport_walk=None,
) -> Listing:
    return Listing(
        source_company=TEST_SOURCE_COMPANY,
        url=f"{SYNTHETIC_BASE_URL}?id={suffix}",
        title=f"Listing {suffix}",
        raw_text=raw_text,
        district=district,
        rooms=rooms,
        rent_kalt=rent_kalt,
        rent_warm=rent_kalt + 150,
        source_active=True,
        status="parsed",
        first_seen_at=first_seen_at,
        transport_walk=(
            transport_walk
            if transport_walk is not None
            else {"s_bahn_minutes": 8, "s_bahn_station": "Test Bhf"}
        ),
    )


class _FakeChat:
    id = 42


class _FakeMessage:
    def __init__(self) -> None:
        self.chat = _FakeChat()
        self.answered: list[tuple[str, object]] = []

    async def answer(self, text, reply_markup=None, **_kwargs):
        self.answered.append((text, reply_markup))
        return self

    async def edit_reply_markup(self, reply_markup=None):
        return self


class _FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []

    async def send_message(self, *, chat_id, text, reply_markup=None, **_kwargs):
        self.sent_messages.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        )

    async def send_photo(self, *, chat_id, photo, caption=None, reply_markup=None, **_kwargs):
        self.sent_messages.append(
            {"chat_id": chat_id, "text": caption, "reply_markup": reply_markup}
        )


class _FakeCallback:
    def __init__(self, data: str = "") -> None:
        self.data = data
        self.message = _FakeMessage()
        self.from_user = SimpleNamespace(id=999)
        self.answered: list[tuple[str | None, bool | None]] = []

    async def answer(self, text=None, show_alert=None):
        self.answered.append((text, show_alert))


class _FakeState:
    async def clear(self) -> None:
        return None


def _in_memory_engine():
    """A StaticPool engine so asyncio.to_thread(...) calls (which run on a
    different thread) see the same in-memory database as the test."""
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


class TourListingSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.test_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        self.addCleanup(engine.dispose)

    def test_selects_first_listing_matching_all_tour_criteria(self) -> None:
        base_time = datetime(2026, 1, 1)
        with self.test_session() as session:
            # Wrong room count: rejected.
            session.add(
                _make_listing(
                    suffix="wrong-rooms",
                    rooms=3,
                    district="Mitte",
                    raw_text="WBS 100-140 erforderlich.",
                    rent_kalt=600,
                    first_seen_at=base_time,
                )
            )
            # No WBS phrase in raw text: rejected.
            session.add(
                _make_listing(
                    suffix="no-wbs-phrase",
                    rooms=2,
                    district="Mitte",
                    raw_text="Kaltmiete: 600,00 Euro. No eligibility text here.",
                    rent_kalt=600,
                    first_seen_at=base_time + timedelta(minutes=1),
                )
            )
            # No transit data: rejected.
            session.add(
                _make_listing(
                    suffix="no-transit",
                    rooms=2,
                    district="Mitte",
                    raw_text="WBS 100-140 erforderlich.",
                    rent_kalt=600,
                    first_seen_at=base_time + timedelta(minutes=2),
                    transport_walk={},
                )
            )
            # WBS range excludes 140: rejected.
            session.add(
                _make_listing(
                    suffix="no-140",
                    rooms=2,
                    district="Mitte",
                    raw_text="WBS 160-220 erforderlich.",
                    rent_kalt=600,
                    first_seen_at=base_time + timedelta(minutes=3),
                )
            )
            # Matches every criterion: expected pick (earliest first_seen_at).
            session.add(
                _make_listing(
                    suffix="valid-1",
                    rooms=2,
                    district="Lichtenberg",
                    raw_text="WBS 100-140 erforderlich.",
                    rent_kalt=512,
                    first_seen_at=base_time + timedelta(minutes=4),
                )
            )
            # A second valid listing seen later must not be picked instead.
            session.add(
                _make_listing(
                    suffix="valid-2",
                    rooms=2,
                    district="Pankow",
                    raw_text="WBS 140-220 erforderlich.",
                    rent_kalt=700,
                    first_seen_at=base_time + timedelta(minutes=5),
                )
            )
            session.commit()

        with patch("main.SessionLocal", self.test_session):
            listing = M._select_tour_listing()

        self.assertIsNotNone(listing)
        self.assertEqual(listing.url, f"{SYNTHETIC_BASE_URL}?id=valid-1")

    def test_returns_none_when_no_listing_qualifies(self) -> None:
        with self.test_session() as session:
            session.add(
                _make_listing(
                    suffix="wrong-rooms",
                    rooms=3,
                    district="Mitte",
                    raw_text="WBS 100-140 erforderlich.",
                    rent_kalt=600,
                    first_seen_at=datetime(2026, 1, 1),
                )
            )
            session.commit()

        with patch("main.SessionLocal", self.test_session):
            listing = M._select_tour_listing()

        self.assertIsNone(listing)


class TourFilterSummaryTests(unittest.TestCase):
    def test_prefers_wbs_140_and_rounds_rent_to_a_preset(self) -> None:
        listing = _make_listing(
            suffix="preset-test",
            rooms=2,
            district="Lichtenberg",
            raw_text="WBS 100-140 erforderlich.",
            rent_kalt=512,
            first_seen_at=datetime(2026, 1, 1),
        )

        preferences, wbs_percent = M._tour_filter_summary(listing)

        self.assertEqual(wbs_percent, 140)
        self.assertEqual(preferences.wbs_type, "WBS 140")
        self.assertEqual(preferences.location, ["Lichtenberg"])
        self.assertEqual(preferences.max_rent, 600)  # smallest RENT_PRESET >= 512
        self.assertEqual(preferences.rooms, 2.0)

    def test_falls_back_to_lowest_allowed_percentage_without_140(self) -> None:
        listing = _make_listing(
            suffix="no-140-test",
            rooms=2,
            district="Pankow",
            raw_text="WBS 160-220 erforderlich.",
            rent_kalt=1500,
            first_seen_at=datetime(2026, 1, 1),
        )

        _, wbs_percent = M._tour_filter_summary(listing)

        self.assertEqual(wbs_percent, 160)

    def test_max_rent_beyond_all_presets_rounds_up_to_nearest_hundred(self) -> None:
        self.assertEqual(M._tour_max_rent(1250), 1300)
        self.assertEqual(M._tour_max_rent(None), M.RENT_PRESETS[0])


class TourCandidateMatchesTests(unittest.TestCase):
    """_tour_candidate_matches must reuse the real is_listing_match
    predicate — this is what proves screen 2 shows a genuine result instead
    of a hand-picked one."""

    def setUp(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.test_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        self.addCleanup(engine.dispose)

    def test_only_listings_satisfying_the_real_predicate_are_returned(self) -> None:
        base_time = datetime(2026, 1, 1)
        with self.test_session() as session:
            session.add(
                _make_listing(
                    suffix="matches",
                    rooms=2,
                    district="Lichtenberg",
                    raw_text="WBS 100-140 erforderlich.",
                    rent_kalt=512,
                    first_seen_at=base_time,
                )
            )
            # Wrong district: must not match a Lichtenberg-only filter.
            session.add(
                _make_listing(
                    suffix="wrong-district",
                    rooms=2,
                    district="Mitte",
                    raw_text="WBS 100-140 erforderlich.",
                    rent_kalt=512,
                    first_seen_at=base_time + timedelta(minutes=1),
                )
            )
            # Over budget: must not match a 600 EUR max.
            session.add(
                _make_listing(
                    suffix="too-expensive",
                    rooms=2,
                    district="Lichtenberg",
                    raw_text="WBS 100-140 erforderlich.",
                    rent_kalt=900,
                    first_seen_at=base_time + timedelta(minutes=2),
                )
            )
            session.commit()

        listing = _make_listing(
            suffix="matches",
            rooms=2,
            district="Lichtenberg",
            raw_text="WBS 100-140 erforderlich.",
            rent_kalt=512,
            first_seen_at=base_time,
        )
        preferences, _ = M._tour_filter_summary(listing)

        with patch("main.SessionLocal", self.test_session):
            matches = M._tour_candidate_matches(preferences)

        self.assertEqual([m.url for m in matches], [f"{SYNTHETIC_BASE_URL}?id=matches"])
        self.assertTrue(matches[0].reasons)


class TourStepMessageTests(unittest.IsolatedAsyncioTestCase):
    """Each message in the tour has one purpose: explanation, canonical card,
    or the actions that follow the result."""

    def setUp(self) -> None:
        engine = _in_memory_engine()
        Base.metadata.create_all(engine)
        self.test_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        self.addCleanup(engine.dispose)

        with self.test_session() as session:
            session.add(
                _make_listing(
                    suffix="screen-fixture",
                    rooms=2,
                    district="Lichtenberg",
                    raw_text="WBS 100-140 erforderlich. Kaltmiete: 512,40 Euro.",
                    rent_kalt=512,
                    first_seen_at=datetime(2026, 1, 1),
                )
            )
            session.commit()

    def _user_count(self) -> int:
        with self.test_session() as session:
            return session.scalar(select(func.count(User.user_id))) or 0

    async def test_screen_1_is_ephemeral_and_shows_the_filter_as_text(self) -> None:
        callback = _FakeCallback("tour:1")

        # _send_tour_screen_1 also calls enrich_missing_transport_walk, which
        # imports its own SessionLocal binding in flatfeed.integrations.
        # transit_walk — patching main.SessionLocal alone does not redirect
        # it, so without this second patch the call silently falls through
        # to the real on-disk DB (works locally if data/flatfeed.db happens
        # to exist, fails everywhere else, e.g. a clean CI checkout).
        with patch("main.SessionLocal", self.test_session), patch(
            "flatfeed.integrations.transit_walk.SessionLocal", self.test_session
        ):
            self.assertEqual(self._user_count(), 0)
            await M._send_tour_screen_1(callback)
            # Ephemeral filter: showing step 1 must not write to `users`.
            self.assertEqual(self._user_count(), 0)

        self.assertEqual(len(callback.message.answered), 1)
        text, markup = callback.message.answered[0]
        self.assertIn("Demo 1/2", text)
        self.assertIn("<b>WBS:</b> 140", text)
        self.assertIn("<b>District:</b> Lichtenberg", text)
        self.assertIn("Set the criteria once", text)
        self.assertIn("does not save personal data", text)
        next_button = markup.inline_keyboard[0][0]
        self.assertEqual(next_button.text, "See the matching result")
        self.assertEqual(next_button.callback_data, "tour:2")

    async def test_screen_1_unavailable_copy_does_not_offer_filter_setup(self) -> None:
        callback = _FakeCallback("tour:1")

        with patch("main.enrich_missing_transport_walk"), patch(
            "main._select_tour_listing", return_value=None
        ):
            await M._send_tour_screen_1(callback)

        text, markup = callback.message.answered[0]
        self.assertIn("guided demo is temporarily unavailable", text)
        self.assertNotIn("filter", text.lower())
        self.assertIsNone(markup)

    async def test_screen_2_separates_explanation_canonical_card_and_actions(self) -> None:
        callback = _FakeCallback("tour:2")
        bot = _FakeBot()

        with patch("main.SessionLocal", self.test_session):
            with self.test_session() as session:
                session.add(
                    _make_listing(
                        suffix="screen-fixture-2",
                        rooms=2,
                        district="Lichtenberg",
                        raw_text="WBS 100-140 erforderlich. Kaltmiete: 550 Euro.",
                        rent_kalt=550,
                        first_seen_at=datetime(2026, 1, 2),
                    )
                )
                session.commit()
            selected_listing = M._select_tour_listing()
            preferences, _ = M._tour_filter_summary(selected_listing)
            expected_match = next(
                match
                for match in M._tour_candidate_matches(preferences)
                if match.listing_id == selected_listing.listing_id
            )
            expected_card_text = M.format_match_message(expected_match)
            await M._send_tour_screen_2(callback, bot)

        self.assertEqual(len(callback.message.answered), 2)
        explanation_text, explanation_markup = callback.message.answered[0]
        self.assertIn("Demo 2/2 · Review only the match", explanation_text)
        self.assertNotIn("active match", explanation_text)
        self.assertIn("One synthetic example card follows", explanation_text)
        self.assertIn("does not have to find and verify", explanation_text)
        self.assertNotIn("up to three active listings", explanation_text)
        self.assertIn("• WBS matches", explanation_text)
        self.assertIsNone(explanation_markup)

        self.assertEqual(len(bot.sent_messages), 1)
        card_message = bot.sent_messages[0]
        self.assertEqual(card_message["text"], expected_card_text)
        self.assertNotIn("Demo 2/2", card_message["text"])
        self.assertNotIn("Why this matched", card_message["text"])
        self.assertIn("District:", card_message["text"])
        self.assertIsNone(card_message["reply_markup"])

        follow_up_text, follow_up_markup = callback.message.answered[1]
        self.assertIn("synthetic example", follow_up_text)
        self.assertIn("not implemented", follow_up_text)
        keyboard = follow_up_markup.inline_keyboard
        button_texts = [button.text for row in keyboard for button in row]
        self.assertEqual(
            button_texts,
            [
                "Replay the demo",
                "How reliability works",
                "Read the case study",
            ],
        )

    async def test_screen_3_explains_the_reliability_boundary(self) -> None:
        callback = _FakeCallback("tour:3")

        await M._send_tour_screen_3(callback)

        self.assertEqual(len(callback.message.answered), 1)
        text, markup = callback.message.answered[0]
        self.assertIn("How reliability works", text)
        self.assertIn("user-facing path is deterministic", text)
        self.assertIn("AI checker", text)
        self.assertIn("cannot change listing fields", text)
        self.assertIn("not integrated into this Telegram prototype", text)
        button_texts = [b.text for row in markup.inline_keyboard for b in row]
        self.assertEqual(button_texts, ["Replay the demo", "Read the case study"])


class RetiredTourSaveFilterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        engine = _in_memory_engine()
        Base.metadata.create_all(engine)
        self.test_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        self.addCleanup(engine.dispose)

        with self.test_session() as session:
            session.add(
                _make_listing(
                    suffix="save-fixture",
                    rooms=2,
                    district="Lichtenberg",
                    raw_text="WBS 100-140 erforderlich. Kaltmiete: 512,40 Euro.",
                    rent_kalt=512,
                    first_seen_at=datetime(2026, 1, 1),
                )
            )
            session.commit()

    async def test_old_save_filter_button_cannot_write_user_state(self) -> None:
        callback = _FakeCallback("tour:save_filter")

        with patch("main.SessionLocal", self.test_session):
            with self.test_session() as session:
                self.assertIsNone(session.get(User, 999))

            await M.handle_tour_save_filter(callback)

            with self.test_session() as session:
                self.assertIsNone(session.get(User, 999))

        self.assertEqual(callback.message.answered, [])
        self.assertEqual(
            callback.answered,
            [("Saving filters is not part of this guided prototype.", True)],
        )


class TourEntryPointTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_command_leads_into_the_tour(self) -> None:
        # Plain /start and the ?start=tour deep link both resolve to the
        # same CommandStart() handler and must produce the same screen 0.
        message = _FakeMessage()
        message.from_user = SimpleNamespace(id=999)

        await M.handle_start(message, _FakeState())

        self.assertEqual(len(message.answered), 2)
        intro_text, intro_markup = message.answered[0]
        pitch_text, pitch_markup = message.answered[1]

        self.assertIn("Without FlatFeed", intro_text)
        self.assertIn("With FlatFeed", intro_text)
        self.assertIn("synthetic scenario", intro_text)
        self.assertTrue(intro_markup.remove_keyboard)

        tour_buttons = [
            button.text for row in pitch_markup.inline_keyboard for button in row
        ]
        self.assertIn("Two steps, no typing", pitch_text)
        self.assertEqual(tour_buttons, ["See the product flow"])


if __name__ == "__main__":
    unittest.main()
