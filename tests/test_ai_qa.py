import unittest
from dataclasses import dataclass
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from flatfeed.ai_qa import (
    AI_QA_FEEDBACK_PARSER_CORRECT,
    AI_QA_FEEDBACK_PARSER_ERROR,
    AI_QA_FEEDBACK_PENDING,
    AI_QA_TRIGGER_NEW_LISTING,
    CURRENT_AI_QA_PROMPT_VERSION,
    _apply_deterministic_guardrails,
    _normalize_ai_result,
    build_demo_fault_parser_snapshot,
    build_parser_snapshot,
    get_ai_qa_status,
    load_flagged_ai_qa_reviews,
    run_ai_qa_demo_check_for_listing,
    run_ai_qa_for_unreviewed_active_listings,
    update_ai_qa_feedback,
)
from flatfeed.db.models import AIQAReview, APILog, Base, Listing
from main import _format_ai_qa_review, _format_wbs_source_interpretation, _issue_lines


TEST_SOURCE_COMPANY = "FlatFeed Synthetic"


@dataclass(frozen=True)
class FakeSettings:
    ai_qa_enabled: bool = True
    ai_qa_provider: str = "openai"
    openai_api_key: str = "test-key"
    ai_qa_daily_max_cost_usd: float = 1.0
    ai_qa_alert_risk_threshold: int = 75
    ai_qa_max_listing_chars: int = 6000
    ai_qa_backfill_batch_size: int = 10
    ai_qa_concurrency: int = 3
    ai_qa_model: str = "gpt-5.4-mini"
    openai_input_price_per_1m: float = 0.75
    openai_output_price_per_1m: float = 4.50


class AIQAServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)

    def make_listing(self, suffix: str = "test") -> Listing:
        return Listing(
            source_company=TEST_SOURCE_COMPANY,
            url=f"https://demo.flatfeed.local/listings/{suffix}",
            title="3-Zimmer-Wohnung (WBS 100-140)",
            raw_text="WBS 100-140 erforderlich. Kaltmiete: 650,00 €. Warmmiete: 800,00 €.",
            rooms=3,
            rent_kalt=650,
            rent_warm=800,
            source_active=True,
            status="parsed",
        )

    def fake_ai_result(self, *args, **kwargs):
        return (
            {
                "parser_result_correct": False,
                "risk_score": 87,
                "confidence": 0.91,
                "issues": [
                    {
                        "field": "wbs",
                        "severity": "high",
                        "parser_value": "No WBS required",
                        "ai_value": "100, 140",
                        "reason": "Title contains WBS 100-140.",
                    }
                ],
                "suggested_values": {"wbs_required": True, "wbs_allowed_values": [100, 140]},
                "wbs_source_interpretation": {
                    "kind": "specific_wbs_values",
                    "evidence": "WBS 100-140 erforderlich",
                    "specific_values_found": [100, 140],
                    "explanation": "The source explicitly names WBS 100-140.",
                },
                "should_alert_admin": True,
            },
            100,
            50,
            0.000045,
        )

    def test_review_is_saved_and_alert_review_id_returned(self) -> None:
        with self.Session() as session:
            listing = self.make_listing()
            session.add(listing)
            session.commit()

            with patch("flatfeed.ai_qa.get_settings", return_value=FakeSettings()), patch(
                "flatfeed.ai_qa._call_openai_ai_qa",
                side_effect=self.fake_ai_result,
            ):
                result = run_ai_qa_for_unreviewed_active_listings(
                    session,
                    source_company=TEST_SOURCE_COMPANY,
                    removed_status="removed_from_source",
                    trigger_type=AI_QA_TRIGGER_NEW_LISTING,
                )

            self.assertEqual(result.checked_count, 1)
            self.assertEqual(len(result.alert_review_ids), 1)
            review = session.scalar(select(AIQAReview))
            self.assertIsNotNone(review)
            self.assertEqual(review.feedback_status, AI_QA_FEEDBACK_PENDING)
            self.assertEqual(review.risk_score, 87)
            self.assertFalse(review.parser_result_correct)
            self.assertEqual(session.scalar(select(APILog.endpoint_type)), "ai_qa")

    def test_flagged_review_loader_prioritizes_pending_alerts_then_falls_back(self) -> None:
        with self.Session() as session:
            high_listing = self.make_listing("high")
            low_listing = self.make_listing("low")
            reviewed_listing = self.make_listing("reviewed")
            fallback_listing = self.make_listing("fallback")
            session.add_all([high_listing, low_listing, reviewed_listing, fallback_listing])
            session.flush()

            high_flagged = AIQAReview(
                listing_id=high_listing.listing_id,
                listing_url=high_listing.url,
                source_company=high_listing.source_company,
                trigger_type="initial_backfill",
                qa_prompt_version=CURRENT_AI_QA_PROMPT_VERSION,
                raw_text_hash="high",
                parser_snapshot_hash="high",
                parser_snapshot={},
                ai_result={},
                risk_score=92,
                confidence=0.8,
                parser_result_correct=False,
                should_alert_admin=True,
                feedback_status=AI_QA_FEEDBACK_PENDING,
            )
            low_flagged = AIQAReview(
                listing_id=low_listing.listing_id,
                listing_url=low_listing.url,
                source_company=low_listing.source_company,
                trigger_type="initial_backfill",
                qa_prompt_version=CURRENT_AI_QA_PROMPT_VERSION,
                raw_text_hash="low",
                parser_snapshot_hash="low",
                parser_snapshot={},
                ai_result={},
                risk_score=80,
                confidence=0.8,
                parser_result_correct=False,
                should_alert_admin=True,
                feedback_status=AI_QA_FEEDBACK_PENDING,
            )
            reviewed_flagged = AIQAReview(
                listing_id=reviewed_listing.listing_id,
                listing_url=reviewed_listing.url,
                source_company=reviewed_listing.source_company,
                trigger_type="initial_backfill",
                qa_prompt_version=CURRENT_AI_QA_PROMPT_VERSION,
                raw_text_hash="reviewed",
                parser_snapshot_hash="reviewed",
                parser_snapshot={},
                ai_result={},
                risk_score=99,
                confidence=0.8,
                parser_result_correct=False,
                should_alert_admin=True,
                feedback_status=AI_QA_FEEDBACK_PARSER_CORRECT,
            )
            pending_fallback = AIQAReview(
                listing_id=fallback_listing.listing_id,
                listing_url=fallback_listing.url,
                source_company=fallback_listing.source_company,
                trigger_type="initial_backfill",
                qa_prompt_version=CURRENT_AI_QA_PROMPT_VERSION,
                raw_text_hash="fallback",
                parser_snapshot_hash="fallback",
                parser_snapshot={},
                ai_result={},
                risk_score=98,
                confidence=0.8,
                parser_result_correct=True,
                should_alert_admin=False,
                feedback_status=AI_QA_FEEDBACK_PENDING,
            )
            session.add_all([low_flagged, high_flagged, reviewed_flagged, pending_fallback])
            session.commit()

            reviews = load_flagged_ai_qa_reviews(session, limit=10)

            self.assertEqual(
                [review.listing_url for review in reviews],
                [high_flagged.listing_url, low_flagged.listing_url],
            )

            high_flagged.feedback_status = AI_QA_FEEDBACK_PARSER_CORRECT
            low_flagged.feedback_status = AI_QA_FEEDBACK_PARSER_CORRECT
            session.commit()

            reviews = load_flagged_ai_qa_reviews(session, limit=10)

            self.assertEqual([review.listing_url for review in reviews], [pending_fallback.listing_url])

    def test_listing_is_not_reviewed_twice(self) -> None:
        with self.Session() as session:
            listing = self.make_listing()
            session.add(listing)
            session.commit()

            with patch("flatfeed.ai_qa.get_settings", return_value=FakeSettings()), patch(
                "flatfeed.ai_qa._call_openai_ai_qa",
                side_effect=self.fake_ai_result,
            ) as ai_call:
                first = run_ai_qa_for_unreviewed_active_listings(
                    session,
                    source_company=TEST_SOURCE_COMPANY,
                    removed_status="removed_from_source",
                    trigger_type=AI_QA_TRIGGER_NEW_LISTING,
                )
                second = run_ai_qa_for_unreviewed_active_listings(
                    session,
                    source_company=TEST_SOURCE_COMPANY,
                    removed_status="removed_from_source",
                    trigger_type=AI_QA_TRIGGER_NEW_LISTING,
                )

            self.assertEqual(first.checked_count, 1)
            self.assertEqual(second.checked_count, 0)
            self.assertEqual(ai_call.call_count, 1)

    def test_listing_can_be_reviewed_again_with_new_prompt_version(self) -> None:
        with self.Session() as session:
            listing = self.make_listing()
            session.add(listing)
            session.commit()
            session.add(
                AIQAReview(
                    listing_id=listing.listing_id,
                    listing_url=listing.url,
                    source_company=listing.source_company,
                    trigger_type="initial_backfill",
                    qa_prompt_version="v1",
                    raw_text_hash="old",
                    parser_snapshot_hash="old",
                    parser_snapshot={},
                    ai_result={},
                    risk_score=99,
                    confidence=0.9,
                    parser_result_correct=False,
                    should_alert_admin=True,
                    feedback_status=AI_QA_FEEDBACK_PENDING,
                )
            )
            session.commit()

            with patch("flatfeed.ai_qa.get_settings", return_value=FakeSettings()), patch(
                "flatfeed.ai_qa._call_openai_ai_qa",
                side_effect=self.fake_ai_result,
            ):
                result = run_ai_qa_for_unreviewed_active_listings(
                    session,
                    source_company=TEST_SOURCE_COMPANY,
                    removed_status="removed_from_source",
                    trigger_type=AI_QA_TRIGGER_NEW_LISTING,
                )

            versions = set(session.scalars(select(AIQAReview.qa_prompt_version)))
            self.assertEqual(result.checked_count, 1)
            self.assertEqual(versions, {"v1", CURRENT_AI_QA_PROMPT_VERSION})

    def test_batch_limit_reports_remaining_unreviewed_count(self) -> None:
        with self.Session() as session:
            session.add_all([self.make_listing("one"), self.make_listing("two")])
            session.commit()

            with patch("flatfeed.ai_qa.get_settings", return_value=FakeSettings()), patch(
                "flatfeed.ai_qa._call_openai_ai_qa",
                side_effect=self.fake_ai_result,
            ):
                result = run_ai_qa_for_unreviewed_active_listings(
                    session,
                    source_company=TEST_SOURCE_COMPANY,
                    removed_status="removed_from_source",
                    trigger_type=AI_QA_TRIGGER_NEW_LISTING,
                    limit=1,
                )

            self.assertEqual(result.total_unreviewed_before, 2)
            self.assertEqual(result.checked_count, 1)
            self.assertEqual(result.remaining_unreviewed_count, 1)
            self.assertEqual(result.stop_reason, "batch_limit_reached")

    def test_disabled_ai_qa_skips_without_error(self) -> None:
        with self.Session() as session:
            session.add(self.make_listing())
            session.commit()

            with patch(
                "flatfeed.ai_qa.get_settings",
                return_value=FakeSettings(ai_qa_enabled=False),
            ):
                result = run_ai_qa_for_unreviewed_active_listings(
                    session,
                    source_company=TEST_SOURCE_COMPANY,
                    removed_status="removed_from_source",
                    trigger_type=AI_QA_TRIGGER_NEW_LISTING,
                )

            self.assertEqual(result.checked_count, 0)
            self.assertEqual(result.skipped_reason, "disabled")

    def test_ai_qa_status_counts_current_version_and_active_listings(self) -> None:
        with self.Session() as session:
            reviewed = self.make_listing("reviewed")
            old_version_only = self.make_listing("old-version")
            removed = self.make_listing("removed")
            removed.source_active = False
            removed.status = "removed_from_source"
            removed_status_still_active = self.make_listing("removed-status-still-active")
            removed_status_still_active.source_active = True
            removed_status_still_active.status = "removed_from_source"
            session.add_all([reviewed, old_version_only, removed, removed_status_still_active])
            session.commit()
            session.add_all(
                [
                    AIQAReview(
                        listing_id=reviewed.listing_id,
                        listing_url=reviewed.url,
                        source_company=reviewed.source_company,
                        trigger_type="initial_backfill",
                        qa_prompt_version=CURRENT_AI_QA_PROMPT_VERSION,
                        raw_text_hash="current",
                        parser_snapshot_hash="current",
                        parser_snapshot={},
                        ai_result={},
                        risk_score=80,
                        confidence=0.9,
                        parser_result_correct=False,
                        should_alert_admin=True,
                        feedback_status=AI_QA_FEEDBACK_PENDING,
                        total_cost_usd=0.01,
                    ),
                    AIQAReview(
                        listing_id=old_version_only.listing_id,
                        listing_url=old_version_only.url,
                        source_company=old_version_only.source_company,
                        trigger_type="initial_backfill",
                        qa_prompt_version="v1",
                        raw_text_hash="old",
                        parser_snapshot_hash="old",
                        parser_snapshot={},
                        ai_result={},
                        risk_score=20,
                        confidence=0.9,
                        parser_result_correct=True,
                        should_alert_admin=False,
                        feedback_status=AI_QA_FEEDBACK_PENDING,
                        total_cost_usd=0.02,
                    ),
                ]
            )
            session.commit()

            with patch("flatfeed.ai_qa.get_settings", return_value=FakeSettings()):
                status = get_ai_qa_status(
                    session,
                    source_company=TEST_SOURCE_COMPANY,
                    removed_status="removed_from_source",
                )

            self.assertEqual(status.active_listings_count, 2)
            self.assertEqual(status.reviewed_active_count, 1)
            self.assertEqual(status.unreviewed_active_count, 1)
            self.assertEqual(status.pending_alerts_count, 1)
            self.assertEqual(status.total_reviews_count, 1)
            self.assertEqual(status.checks_today, 2)
            self.assertAlmostEqual(status.cost_today_usd, 0.03)

    def test_backfill_ignores_removed_status_even_if_source_active_is_true(self) -> None:
        with self.Session() as session:
            active = self.make_listing("active")
            removed_status_still_active = self.make_listing("removed-status-still-active")
            removed_status_still_active.source_active = True
            removed_status_still_active.status = "removed_from_source"
            session.add_all([active, removed_status_still_active])
            session.commit()

            with patch("flatfeed.ai_qa.get_settings", return_value=FakeSettings()), patch(
                "flatfeed.ai_qa._call_openai_ai_qa",
                side_effect=self.fake_ai_result,
            ):
                result = run_ai_qa_for_unreviewed_active_listings(
                    session,
                    source_company=TEST_SOURCE_COMPANY,
                    removed_status="removed_from_source",
                    trigger_type=AI_QA_TRIGGER_NEW_LISTING,
                )

            reviewed_urls = set(session.scalars(select(AIQAReview.listing_url)))
            self.assertEqual(result.total_unreviewed_before, 1)
            self.assertEqual(result.checked_count, 1)
            self.assertIn(active.url, reviewed_urls)
            self.assertNotIn(removed_status_still_active.url, reviewed_urls)

    def test_feedback_updates_review_status(self) -> None:
        with self.Session() as session:
            listing = self.make_listing()
            session.add(listing)
            session.commit()

            with patch("flatfeed.ai_qa.get_settings", return_value=FakeSettings()), patch(
                "flatfeed.ai_qa._call_openai_ai_qa",
                side_effect=self.fake_ai_result,
            ):
                run_ai_qa_for_unreviewed_active_listings(
                    session,
                    source_company=TEST_SOURCE_COMPANY,
                    removed_status="removed_from_source",
                    trigger_type=AI_QA_TRIGGER_NEW_LISTING,
                )
            review = session.scalar(select(AIQAReview))

            updated = update_ai_qa_feedback(
                session,
                review_id=review.review_id,
                feedback_status=AI_QA_FEEDBACK_PARSER_ERROR,
                admin_user_id=123,
            )

            self.assertTrue(updated)
            self.assertEqual(review.feedback_status, AI_QA_FEEDBACK_PARSER_ERROR)
            self.assertEqual(review.feedback_by, 123)
            self.assertIsNotNone(review.feedback_at)

    def test_ai_qa_does_not_mutate_listing_or_parser_snapshot(self) -> None:
        with self.Session() as session:
            listing = self.make_listing()
            session.add(listing)
            session.commit()
            before_snapshot = build_parser_snapshot(listing)

            with patch("flatfeed.ai_qa.get_settings", return_value=FakeSettings()), patch(
                "flatfeed.ai_qa._call_openai_ai_qa",
                side_effect=self.fake_ai_result,
            ):
                run_ai_qa_for_unreviewed_active_listings(
                    session,
                    source_company=TEST_SOURCE_COMPANY,
                    removed_status="removed_from_source",
                    trigger_type=AI_QA_TRIGGER_NEW_LISTING,
                )

            self.assertEqual(build_parser_snapshot(listing), before_snapshot)
            self.assertEqual(listing.rooms, 3)
            self.assertEqual(listing.rent_kalt, 650)
            self.assertEqual(listing.rent_warm, 800)

    def test_demo_fault_snapshot_does_not_leak_demo_marker_to_model_input(self) -> None:
        listing = self.make_listing()

        snapshot, fault = build_demo_fault_parser_snapshot(
            listing,
            fault_type="rooms",
        )

        self.assertEqual(fault["field"], "rooms")
        self.assertNotIn("demo_fault_injection", snapshot)
        self.assertNotEqual(snapshot["rooms"], build_parser_snapshot(listing)["rooms"])

    def test_mock_ai_qa_catches_demo_room_fault(self) -> None:
        listing = self.make_listing()

        with patch(
            "flatfeed.ai_qa.get_settings",
            return_value=FakeSettings(ai_qa_provider="mock"),
        ):
            result = run_ai_qa_demo_check_for_listing(
                listing,
                provider="mock",
                fault_type="rooms",
            )

        fields = {issue["field"] for issue in result.ai_result["issues"]}
        self.assertIn("rooms", fields)
        self.assertTrue(result.ai_result["should_alert_admin"])
        self.assertTrue(result.ai_result["demo_fault_injection"]["demo_fault_injection"])
        self.assertEqual(result.total_cost_usd, 0.0)

    def test_mock_ai_qa_catches_demo_rent_fault(self) -> None:
        listing = self.make_listing()

        with patch(
            "flatfeed.ai_qa.get_settings",
            return_value=FakeSettings(ai_qa_provider="mock"),
        ):
            result = run_ai_qa_demo_check_for_listing(
                listing,
                provider="mock",
                fault_type="rent_kalt",
            )

        fields = {issue["field"] for issue in result.ai_result["issues"]}
        self.assertIn("rent_kalt", fields)
        self.assertTrue(result.ai_result["should_alert_admin"])

    def test_string_ai_qa_issues_are_displayed(self) -> None:
        review = AIQAReview(
            ai_result={
                "issues": [
                    "The parser says WBS is not required, but the title says WBS 100-140."
                ]
            }
        )

        self.assertEqual(
            _issue_lines(review),
            ["AI did not identify a specific field. Manual review is needed."],
        )

    def test_ai_qa_review_text_hides_demo_injection_details(self) -> None:
        listing = self.make_listing()

        class FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def get(self, model, listing_id):
                return listing

        with patch(
            "flatfeed.ai_qa.get_settings",
            return_value=FakeSettings(ai_qa_provider="mock"),
        ):
            result = run_ai_qa_demo_check_for_listing(
                listing,
                provider="mock",
                fault_type="wbs",
            )
        review = AIQAReview(
            listing_id=1,
            listing_url=listing.url,
            qa_prompt_version=f"{CURRENT_AI_QA_PROMPT_VERSION}-demo",
            parser_snapshot=result.parser_snapshot,
            ai_result=result.ai_result,
            risk_score=result.ai_result["risk_score"],
            confidence=result.ai_result["confidence"],
            parser_result_correct=result.ai_result["parser_result_correct"],
            should_alert_admin=result.ai_result["should_alert_admin"],
            feedback_status=AI_QA_FEEDBACK_PENDING,
            total_cost_usd=0.0,
        )

        with patch("main.SessionLocal", return_value=FakeSession()):
            text = _format_ai_qa_review(review, alert=True)

        self.assertNotIn("Demo fault injection", text)
        self.assertNotIn("transient demo", text)
        self.assertNotIn("Mock QA re-read", text)
        self.assertNotIn("Parser is likely correct", text)
        self.assertIn("<b>Mismatch</b>", text)
        self.assertIn("In listing: WBS 100-140", text)
        self.assertIn("Parser: No WBS required", text)
        self.assertIn("Why: The text states a different WBS condition.", text)
        self.assertIn("Choose a decision with the buttons below.", text)

    def test_wbs_source_interpretation_is_normalized_and_displayed(self) -> None:
        result = _normalize_ai_result(
            {
                "parser_result_correct": True,
                "risk_score": 10,
                "confidence": 0.9,
                "issues": [],
                "suggested_values": {},
                "wbs_source_interpretation": {
                    "kind": "generic_wbs_required",
                    "evidence": "WBS erforderlich",
                    "specific_values_found": [],
                    "explanation": "The source requires WBS but gives no percentage.",
                },
                "should_alert_admin": False,
            },
            alert_threshold=75,
        )
        review = AIQAReview(ai_result=result)

        self.assertEqual(
            result["wbs_source_interpretation"]["kind"],
            "generic_wbs_required",
        )
        self.assertIn(
            "WBS required, type unknown",
            _format_wbs_source_interpretation(review),
        )

    def test_guardrails_suppress_false_no_wbs_issue(self) -> None:
        listing = Listing(
            title="2-Zimmer-Wohnung freifinanziert",
            raw_text="2-Zimmer-Wohnung freifinanziert. Kaltmiete: 825,00 €.",
            parsed_constraints={},
        )
        snapshot = build_parser_snapshot(listing)
        ai_result = {
            "parser_result_correct": False,
            "risk_score": 80,
            "confidence": 1.0,
            "issues": [
                {
                    "field": "display_wbs",
                    "parser_value": "No WBS required",
                    "ai_value": "WBS required",
                    "reason": "The text is freifinanziert.",
                    "severity": "high",
                }
            ],
            "suggested_values": {},
            "should_alert_admin": True,
        }

        result = _apply_deterministic_guardrails(
            listing=listing,
            parser_snapshot=snapshot,
            ai_result=ai_result,
            alert_threshold=75,
        )

        self.assertEqual(result["risk_score"], 20)
        self.assertTrue(result["parser_result_correct"])
        self.assertFalse(result["should_alert_admin"])
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["guardrails"]["suppressed_wbs_issues"], 1)

    def test_guardrails_suppress_false_range_issue_when_display_matches(self) -> None:
        listing = Listing(
            title="Neue Wohnung mit WBS 140-180!",
            raw_text="Neue Wohnung mit WBS 140-180! Kaltmiete: 533,00 €.",
            parsed_constraints={},
        )
        snapshot = build_parser_snapshot(listing)
        ai_result = {
            "parser_result_correct": False,
            "risk_score": 80,
            "confidence": 1.0,
            "issues": [
                {
                    "field": "display_wbs",
                    "parser_value": "140, 160, 180",
                    "ai_value": "140, 180",
                    "reason": "AI incorrectly thinks 160 is excluded.",
                    "severity": "high",
                }
            ],
            "suggested_values": {},
            "should_alert_admin": True,
        }

        result = _apply_deterministic_guardrails(
            listing=listing,
            parser_snapshot=snapshot,
            ai_result=ai_result,
            alert_threshold=75,
        )

        self.assertEqual(result["risk_score"], 20)
        self.assertTrue(result["parser_result_correct"])
        self.assertFalse(result["should_alert_admin"])
        self.assertEqual(result["issues"], [])

    def test_guardrails_suppress_generic_wbs_type_unspecified_issue(self) -> None:
        listing = Listing(
            title="2-Zimmer-Wohnung",
            raw_text="Für die Anmietung der Wohnung ist ein WBS erforderlich.",
            parsed_constraints={},
        )
        snapshot = build_parser_snapshot(listing)
        self.assertEqual(snapshot["display_wbs"], "WBS required, type unknown")
        ai_result = {
            "parser_result_correct": False,
            "risk_score": 82,
            "confidence": 0.95,
            "issues": [
                {
                    "field": "display_wbs",
                    "parser_value": "WBS required, type unknown",
                    "ai_value": "WBS type should be specified",
                    "reason": "The text says WBS is required.",
                    "severity": "high",
                }
            ],
            "suggested_values": {},
            "should_alert_admin": True,
        }

        result = _apply_deterministic_guardrails(
            listing=listing,
            parser_snapshot=snapshot,
            ai_result=ai_result,
            alert_threshold=75,
        )

        self.assertEqual(result["risk_score"], 20)
        self.assertTrue(result["parser_result_correct"])
        self.assertFalse(result["should_alert_admin"])
        self.assertEqual(result["issues"], [])


if __name__ == "__main__":
    unittest.main()
