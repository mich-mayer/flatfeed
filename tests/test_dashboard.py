import unittest
from itertools import count
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from flatfeed.ai_qa import AI_QA_FEEDBACK_PENDING, CURRENT_AI_QA_PROMPT_VERSION
from flatfeed.dashboard import streamlit_app as dashboard
from flatfeed.db.models import AIQAReview, Base


TEST_SOURCE_COMPANY = "FlatFeed Synthetic"


class FmtShareTests(unittest.TestCase):
    def test_zero_denominator_reports_no_data(self) -> None:
        self.assertEqual(dashboard.fmt_share(0, 0), "no data")

    def test_small_denominator_shows_count_not_percent(self) -> None:
        result = dashboard.fmt_share(7, 11)
        self.assertEqual(result, "7 of 11")
        self.assertNotIn("%", result)

    def test_denominator_at_threshold_shows_percent(self) -> None:
        # 20 is the documented cutoff (fmt_share docstring / DESIGN_CONTENT_SYSTEM
        # small-number rule) — exactly 20 must already read as a percent.
        result = dashboard.fmt_share(10, 20)
        self.assertEqual(result, "50.0%")

    def test_large_denominator_shows_percent(self) -> None:
        self.assertEqual(dashboard.fmt_share(26, 41), "63.4%")


class DemoVersionExclusionTests(unittest.TestCase):
    """The dashboard must only ever report a curated evaluation history —
    any review written under a "<version>-demo" prompt version (the shape a
    non-persisting demo/tour artifact would use, if one ever existed) must
    never appear in any dashboard query, including version comparison."""

    def setUp(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.test_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        self.addCleanup(engine.dispose)
        self._listing_ids = count(1)

    def _review(self, **overrides) -> AIQAReview:
        listing_id = overrides.pop("listing_id", None)
        if listing_id is None:
            listing_id = next(self._listing_ids)
        defaults = dict(
            listing_id=listing_id,
            listing_url=f"https://mich-mayer.github.io/flatfeed/demo-listing.html?id={listing_id}",
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

    def test_load_review_rows_excludes_demo_suffixed_versions(self) -> None:
        with self.test_session() as session:
            session.add(self._review())  # real, current version: kept
            session.add(self._review(qa_prompt_version="v7"))  # real, older version: kept
            session.add(
                self._review(qa_prompt_version=f"{CURRENT_AI_QA_PROMPT_VERSION}-demo")
            )  # demo-shaped: excluded
            session.add(self._review(qa_prompt_version="v7-demo"))  # demo-shaped: excluded
            session.commit()

        with patch("flatfeed.dashboard.streamlit_app.SessionLocal", self.test_session):
            frame = dashboard._load_review_rows()

        self.assertEqual(len(frame), 2)
        self.assertTrue(
            all(not str(v).endswith("-demo") for v in frame["qa_prompt_version"])
        )

    def test_version_comparison_also_excludes_demo_versions(self) -> None:
        with self.test_session() as session:
            session.add(self._review(qa_prompt_version="v7"))
            session.add(self._review(qa_prompt_version=f"{CURRENT_AI_QA_PROMPT_VERSION}-demo"))
            session.commit()

        with patch("flatfeed.dashboard.streamlit_app.SessionLocal", self.test_session):
            frame = dashboard._load_review_rows()

        self.assertEqual(sorted(frame["qa_prompt_version"].unique()), ["v7"])


if __name__ == "__main__":
    unittest.main()
