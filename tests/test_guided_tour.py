import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from flatfeed.ai_qa import (
    AI_QA_FEEDBACK_PARSER_CORRECT,
    AI_QA_FEEDBACK_PARSER_ERROR,
    AI_QA_FEEDBACK_UNSURE,
)
from flatfeed.db.models import AIQAReview, Base, Listing, User
from synthetic.generator import SYNTHETIC_BASE_URL
from synthetic.golden_set import load_golden_set

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


class TourEphemeralTriageTests(unittest.IsolatedAsyncioTestCase):
    """The core Variant-B guarantee: nothing a tour visitor taps is persisted."""

    def setUp(self) -> None:
        # The handlers under test call asyncio.to_thread(...), which runs the
        # query on a different thread. A plain sqlite:///:memory: engine
        # hands that thread a brand-new, empty database, so this needs
        # StaticPool (one shared connection) + check_same_thread=False.
        engine = _in_memory_engine()
        Base.metadata.create_all(engine)
        self.test_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        self.addCleanup(engine.dispose)

        with self.test_session() as session:
            session.add(
                _make_listing(
                    suffix="tour-fixture",
                    rooms=2,
                    district="Lichtenberg",
                    raw_text="WBS 100-140 erforderlich. Kaltmiete: 512,40 Euro.",
                    rent_kalt=512,
                    first_seen_at=datetime(2026, 1, 1),
                )
            )
            session.commit()

    def _review_count(self) -> int:
        with self.test_session() as session:
            return len(list(session.scalars(select(AIQAReview))))

    async def test_inject_then_all_three_triage_outcomes_write_zero_reviews(self) -> None:
        with patch("main.SessionLocal", self.test_session):
            self.assertEqual(self._review_count(), 0)

            inject_callback = _FakeCallback("tour:inject")
            await M._send_tour_inject(inject_callback)
            self.assertEqual(self._review_count(), 0)

            # Exactly one message: the fault note, the alert, and the triage
            # keyboard all land together, so a single button tap produces a
            # single new message (no scroll-away avalanche in the client).
            self.assertEqual(len(inject_callback.message.answered), 1)
            alert_text, alert_markup = inject_callback.message.answered[-1]
            self.assertIn("Simulated parser fault", alert_text)
            self.assertIn("AI QA alert", alert_text)
            # Cost and confidence read as production/model-calibrated
            # numbers; the tour must not imply either.
            self.assertNotIn("Check cost", alert_text)
            self.assertNotIn("AI confidence", alert_text)
            triage_labels = [
                button.text for row in alert_markup.inline_keyboard for button in row
            ]
            self.assertEqual(triage_labels, ["Parser error", "Parser correct", "Borderline / unsure"])

            for status in (
                AI_QA_FEEDBACK_PARSER_ERROR,
                AI_QA_FEEDBACK_PARSER_CORRECT,
                AI_QA_FEEDBACK_UNSURE,
            ):
                feedback_callback = _FakeCallback(f"tour_fb:{status}")
                await M._send_tour_feedback_response(feedback_callback, status)
                self.assertEqual(self._review_count(), 0)
                # The tour must not grade the visitor's choice — every label
                # gets the same neutral, fact-revealing response.
                response_text = feedback_callback.message.answered[-1][0]
                self.assertIn("Recorded for this demo only", response_text)
                self.assertIn("nothing you tap is stored", response_text)
                self.assertIn("<b>Parser error</b> is the label an admin would confirm", response_text)
                self.assertNotIn("Correct —", response_text)
                self.assertNotIn("Noted.", response_text)


class TourStepMessageTests(unittest.IsolatedAsyncioTestCase):
    """Each tour step should land as one new message, not several — a burst
    of messages pushes the Telegram client's scroll position to the bottom
    of the chat on every single one, forcing the reader to scroll back up."""

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

        with patch("main.SessionLocal", self.test_session):
            self.assertEqual(self._user_count(), 0)
            await M._send_tour_screen_1(callback)
            # Ephemeral filter: showing step 1 must not write to `users`.
            self.assertEqual(self._user_count(), 0)

        self.assertEqual(len(callback.message.answered), 1)
        text, markup = callback.message.answered[0]
        self.assertIn("Step 1/5", text)
        self.assertIn("<b>WBS:</b> 140", text)
        self.assertIn("<b>District:</b> Lichtenberg", text)
        self.assertIn("temporary", text)
        next_button = markup.inline_keyboard[0][0]
        self.assertEqual(next_button.text, "Find matches")
        self.assertEqual(next_button.callback_data, "tour:2")

    async def test_screen_2_uses_real_matching_and_sends_one_card(self) -> None:
        callback = _FakeCallback("tour:2")
        bot = _FakeBot()

        with patch("main.SessionLocal", self.test_session):
            await M._send_tour_screen_2(callback, bot)

        # One tap = one message: the step framing, the "1 of N" result, and
        # the Next button all ride in the card's own caption.
        self.assertEqual(len(callback.message.answered), 0)
        self.assertEqual(len(bot.sent_messages), 1)
        card_message = bot.sent_messages[0]
        self.assertIn("Step 2/5", card_message["text"])
        self.assertIn("1 of 1 active match", card_message["text"])
        self.assertIn("Why it matched", card_message["text"])
        self.assertIn("District:", card_message["text"])
        next_button = card_message["reply_markup"].inline_keyboard[0][0]
        self.assertEqual(next_button.text, "How does it work?")
        self.assertEqual(next_button.callback_data, "tour:3")

    async def test_screen_3_explains_the_pipeline_and_privacy(self) -> None:
        callback = _FakeCallback("tour:3")

        await M._send_tour_screen_3(callback)

        self.assertEqual(len(callback.message.answered), 1)
        text, markup = callback.message.answered[0]
        self.assertIn("Step 3/5", text)
        for word in ("Collect:", "Normalize:", "Verify:", "Match:", "Deliver:"):
            self.assertIn(word, text)
        self.assertIn("/delete", text)
        next_button = markup.inline_keyboard[0][0]
        self.assertEqual(next_button.text, "Where AI helps")
        self.assertEqual(next_button.callback_data, "tour:4")

    async def test_screen_4_introduces_the_ai_layer(self) -> None:
        callback = _FakeCallback("tour:4")

        await M._send_tour_screen_4(callback)

        self.assertEqual(len(callback.message.answered), 1)
        text, markup = callback.message.answered[0]
        self.assertIn("Step 4/5", text)
        self.assertIn("cannot change listings, matches or cards", text)
        next_button = markup.inline_keyboard[0][0]
        self.assertEqual(next_button.text, "Simulate a parser fault")
        self.assertEqual(next_button.callback_data, "tour:inject")

    async def test_screen_5_shows_evidence_not_a_funnel(self) -> None:
        callback = _FakeCallback("tour:5")

        await M._send_tour_screen_5(callback)

        self.assertEqual(len(callback.message.answered), 1)
        text, markup = callback.message.answered[0]
        self.assertIn("Step 5/5", text)
        self.assertIn("Working now", text)
        self.assertIn("Measured on synthetic data", text)
        self.assertIn("Not yet proven", text)
        self.assertIn(f"{len(load_golden_set())} listings", text)
        self.assertNotIn("Checked by AI", text)
        self.assertNotIn("Flagged as risky", text)

        button_texts = [b.text for row in markup.inline_keyboard for b in row]
        self.assertIn("Use this demo filter", button_texts)
        self.assertIn("Set up my own filter", button_texts)
        self.assertIn("Read the case study", button_texts)


class TourSaveFilterTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_save_filter_writes_the_derived_preferences_once(self) -> None:
        callback = _FakeCallback("tour:save_filter")

        with patch("main.SessionLocal", self.test_session):
            with self.test_session() as session:
                self.assertIsNone(session.get(User, 999))

            await M.handle_tour_save_filter(callback)

            with self.test_session() as session:
                user = session.get(User, 999)
                self.assertIsNotNone(user)
                self.assertEqual(user.parsed_preferences["wbs_type"], "WBS 140")
                self.assertEqual(user.parsed_preferences["location"], ["Lichtenberg"])
                self.assertEqual(user.parsed_preferences["max_rent"], 600)

        confirmation_text = callback.message.answered[-1][0]
        self.assertIn("Saved", confirmation_text)


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

        self.assertIn("FlatFeed", intro_text)
        self.assertIn("/delete", intro_text)
        self.assertIsNotNone(intro_markup)  # persistent reply keyboard is attached

        tour_buttons = [
            button.text for row in pitch_markup.inline_keyboard for button in row
        ]
        self.assertEqual(tour_buttons, ["Start the tour", "Skip the tour"])


if __name__ == "__main__":
    unittest.main()
