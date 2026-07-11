import unittest
from datetime import datetime, timedelta
from itertools import count
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from flatfeed.ai_qa import (
    AI_QA_FEEDBACK_PARSER_CORRECT,
    AI_QA_FEEDBACK_PARSER_ERROR,
    AI_QA_FEEDBACK_PENDING,
    AI_QA_FEEDBACK_UNSURE,
    CURRENT_AI_QA_PROMPT_VERSION,
)
from flatfeed.db.models import AIQAReview, Base, Listing

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
        url=f"https://demo.flatfeed.local/listings/{suffix}",
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
        self.assertEqual(listing.url, "https://demo.flatfeed.local/listings/valid-1")

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


class TourRateLineTests(unittest.TestCase):
    def test_zero_reviewed_reports_no_data(self) -> None:
        self.assertEqual(
            M._tour_rate_line(confirmed=0, reviewed=0),
            "No flagged reports have been reviewed yet.",
        )

    def test_small_denominator_shows_count_not_percent(self) -> None:
        line = M._tour_rate_line(confirmed=7, reviewed=11)
        self.assertIn("7 of 11", line)
        self.assertNotIn("%", line)

    def test_large_denominator_shows_percent(self) -> None:
        line = M._tour_rate_line(confirmed=26, reviewed=41)
        self.assertIn("63.4%", line)


class TourFunnelTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.test_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        self.addCleanup(engine.dispose)
        self._listing_ids = count(1)

    def _review(self, **overrides) -> AIQAReview:
        # listing_id + qa_prompt_version is a real unique constraint on this
        # table; give each fixture its own listing_id unless a test needs a
        # specific one, so unrelated fixtures never collide.
        listing_id = overrides.pop("listing_id", None)
        if listing_id is None:
            listing_id = next(self._listing_ids)
        defaults = dict(
            listing_id=listing_id,
            listing_url=f"https://demo.flatfeed.local/listings/{listing_id}",
            source_company=TEST_SOURCE_COMPANY,
            trigger_type="new_listing",
            qa_prompt_version=CURRENT_AI_QA_PROMPT_VERSION,
            raw_text_hash="hash",
            parser_snapshot_hash="hash",
            parser_snapshot={},
            ai_result={},
            risk_score=85,
            confidence=0.7,
            parser_result_correct=False,
            should_alert_admin=True,
            feedback_status=AI_QA_FEEDBACK_PENDING,
        )
        defaults.update(overrides)
        return AIQAReview(**defaults)

    def test_funnel_counts_checked_flagged_reviewed_confirmed(self) -> None:
        with self.test_session() as session:
            session.add(self._review(should_alert_admin=False, risk_score=10))  # checked only
            session.add(self._review())  # flagged, still pending
            session.add(self._review(feedback_status=AI_QA_FEEDBACK_PARSER_ERROR))  # confirmed
            session.add(self._review(feedback_status=AI_QA_FEEDBACK_PARSER_CORRECT))  # false alarm
            session.commit()

        with patch("main.SessionLocal", self.test_session):
            funnel = M._load_tour_funnel()

        self.assertEqual(funnel, {"checked": 4, "flagged": 3, "reviewed": 2, "confirmed": 1})

    def test_funnel_excludes_non_current_prompt_versions(self) -> None:
        # Defense in depth: even if a -demo or stale-version review ever
        # existed in the table, screen 5 (and the dashboard) must ignore it.
        with self.test_session() as session:
            session.add(self._review(qa_prompt_version=f"{CURRENT_AI_QA_PROMPT_VERSION}-demo"))
            session.add(self._review(qa_prompt_version="v1"))
            session.commit()

        with patch("main.SessionLocal", self.test_session):
            funnel = M._load_tour_funnel()

        self.assertEqual(funnel, {"checked": 0, "flagged": 0, "reviewed": 0, "confirmed": 0})


class TourEphemeralTriageTests(unittest.IsolatedAsyncioTestCase):
    """The core Variant-B guarantee: nothing a tour visitor taps is persisted."""

    def setUp(self) -> None:
        # The handlers under test call asyncio.to_thread(...), which runs the
        # query on a different thread. A plain sqlite:///:memory: engine
        # hands that thread a brand-new, empty database, so this needs
        # StaticPool (one shared connection) + check_same_thread=False.
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
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
            self.assertIn("Fault injected", alert_text)
            self.assertIn("AI QA alert", alert_text)
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
                response_text = feedback_callback.message.answered[-1][0]
                self.assertIn("nothing you tap is stored", response_text)


class TourMessageCountTests(unittest.IsolatedAsyncioTestCase):
    """Each tour step should land as one new message, not several — a burst
    of messages pushes the Telegram client's scroll position to the bottom
    of the chat on every single one, forcing the reader to scroll back up."""

    def setUp(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        self.test_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        self.addCleanup(engine.dispose)

        with self.test_session() as session:
            session.add(
                _make_listing(
                    suffix="screen-one-fixture",
                    rooms=2,
                    district="Lichtenberg",
                    raw_text="WBS 100-140 erforderlich. Kaltmiete: 512,40 Euro.",
                    rent_kalt=512,
                    first_seen_at=datetime(2026, 1, 1),
                )
            )
            session.commit()

    async def test_screen_1_is_a_single_card_message_with_step_framing(self) -> None:
        callback = _FakeCallback("tour:1")
        bot = _FakeBot()

        with patch("main.SessionLocal", self.test_session):
            await M._send_tour_screen_1(callback, bot)

        # One tap = one message: the step framing rides in the card's own
        # caption, the Next button hangs on the same message, and nothing is
        # sent on the callback's message thread separately.
        self.assertEqual(len(callback.message.answered), 0)
        self.assertEqual(len(bot.sent_messages), 1)
        card_message = bot.sent_messages[0]
        self.assertIn("Step 1/5", card_message["text"])
        self.assertIn("District:", card_message["text"])
        self.assertIsNotNone(card_message["reply_markup"])
        next_button = card_message["reply_markup"].inline_keyboard[0][0]
        self.assertEqual(next_button.text, "See how it's parsed")
        self.assertEqual(next_button.callback_data, "tour:2")

    async def test_screen_2_sends_a_single_message(self) -> None:
        callback = _FakeCallback("tour:2")

        with patch("main.SessionLocal", self.test_session):
            await M._send_tour_screen_2(callback)

        self.assertEqual(len(callback.message.answered), 1)
        text, markup = callback.message.answered[0]
        self.assertIn("Kaltmiete", text)
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "tour:3")


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
