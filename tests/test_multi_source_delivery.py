import asyncio
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from main import _check_match_source_active, send_match_to_chat, refresh_listing_database
from flatfeed.ingestion.base import SourceIngestionResult
from flatfeed.matching import ListingMatch, format_match_message


def _match(**overrides) -> ListingMatch:
    values = {
        "user_id": 1,
        "listing_id": 42,
        "source_company": "FlatFeed Synthetic",
        "title": "Test",
        "url": "https://demo.flatfeed.local/listings/0001",
        "image_url": None,
        "district": "Spandau",
        "address": "Teststr. 1",
        "postal_code": "13599",
        "floor": "2",
        "rooms": 2.0,
        "required_wbs": None,
        "rent_kalt": 500,
        "rent_warm": 650,
        "s_bahn_minutes": None,
        "u_bahn_minutes": None,
        "reasons": ("test",),
    }
    values.update(overrides)
    return ListingMatch(**values)


class _FakeBot:
    def __init__(self) -> None:
        self.photos = []
        self.messages = []

    async def send_photo(self, **kwargs):
        self.photos.append(kwargs)

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)


class MultiSourceDeliveryTests(unittest.TestCase):
    def test_live_check_is_dispatched_to_listing_source_adapter(self) -> None:
        match = _match()
        adapter = Mock()
        adapter.check_active.return_value = True

        with patch("main.get_source_adapter", return_value=adapter) as get_adapter:
            result = asyncio.run(_check_match_source_active(match))

        self.assertTrue(result)
        get_adapter.assert_called_once_with("FlatFeed Synthetic")
        adapter.check_active.assert_called_once_with(match.url)

    def test_card_shows_postal_code_next_to_address_and_walk_minutes(self) -> None:
        match = _match(
            url="https://example.test/listing",
            district="Mitte",
            address="Teststr. 1",
            postal_code="10115",
            s_bahn_minutes=7,
            u_bahn_minutes=4,
            s_bahn_station="Friedrichstraße",
            u_bahn_station="Stadtmitte",
        )

        message = format_match_message(match)

        self.assertIn("<b>Address:</b> Teststr. 1, 10115 Berlin", message)
        self.assertIn("<b>S-Bahn:</b> 7 min walk to Friedrichstraße", message)
        self.assertIn("<b>U-Bahn:</b> 4 min walk to Stadtmitte", message)

    def test_listing_with_local_photo_is_sent_as_photo_caption(self) -> None:
        image_path = "assets/listing_photos/berlin_tempelhof_alboinplatz_wohnblock.jpg"
        self.assertTrue(Path(image_path).is_file())
        bot = _FakeBot()

        asyncio.run(send_match_to_chat(bot, chat_id=123, match=_match(image_url=image_path)))

        self.assertEqual(len(bot.photos), 1)
        self.assertEqual(bot.photos[0]["chat_id"], 123)
        self.assertIn("<b>District:</b>", bot.photos[0]["caption"])
        self.assertEqual(bot.messages, [])

    def test_missing_listing_photo_falls_back_to_text(self) -> None:
        bot = _FakeBot()

        with patch("main.logger"):
            asyncio.run(
                send_match_to_chat(
                    bot,
                    chat_id=123,
                    match=_match(image_url="assets/listing_photos/missing.jpg"),
                )
            )

        self.assertEqual(bot.photos, [])
        self.assertEqual(len(bot.messages), 1)
        self.assertEqual(bot.messages[0]["chat_id"], 123)

    def test_refresh_aggregates_all_enabled_sources(self) -> None:
        first_adapter = Mock()
        first_adapter.sync.return_value = SourceIngestionResult(
            saved_count=2,
            created_count=1,
            updated_count=1,
            removed_count=0,
            live_urls=(
                "https://demo.flatfeed.local/listings/a1",
                "https://demo.flatfeed.local/listings/a2",
            ),
        )
        second_adapter = Mock()
        second_adapter.sync.return_value = SourceIngestionResult(
            saved_count=1,
            created_count=1,
            updated_count=0,
            removed_count=1,
            live_urls=("https://demo.flatfeed.local/listings/b1",),
        )

        with ExitStack() as stack:
            stack.enter_context(
                patch("main.ACTIVE_SOURCE_COMPANIES", ("Synthetic A", "Synthetic B"))
            )
            stack.enter_context(
                patch(
                    "main.get_source_adapter",
                    side_effect=(first_adapter, second_adapter),
                )
            )
            stack.enter_context(
                patch("main.enrich_missing_transport_walk", return_value=2)
            )
            stack.enter_context(patch("main.record_ingestion_success"))
            stack.enter_context(patch("main.record_ingestion_failure"))
            result = refresh_listing_database(trigger_type="test")

        # parsed_count now equals saved_count: parsing is inline at ingestion,
        # so every saved listing (2 + 1) is already parsed; no LLM pass runs.
        self.assertEqual(result.listings_found, 3)
        self.assertEqual(result.created_count, 2)
        self.assertEqual(result.updated_count, 1)
        self.assertEqual(result.saved_count, 3)
        self.assertEqual(result.removed_count, 1)
        self.assertEqual(result.parsed_count, 3)
        self.assertEqual(result.transport_count, 4)
        self.assertFalse(result.is_partial)
        self.assertEqual(result.collection_error_count, 0)
        self.assertEqual(result.ai_qa_checked_count, 0)
        self.assertEqual(result.ai_qa_alert_review_ids, ())
        first_adapter.sync.assert_called_once_with(limit=None, mark_removed=True)
        second_adapter.sync.assert_called_once_with(limit=None, mark_removed=True)


if __name__ == "__main__":
    unittest.main()
