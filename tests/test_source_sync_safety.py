import unittest

from flatfeed.ingestion.base import should_mark_missing_removed


class SourceSyncSafetyTests(unittest.TestCase):
    def test_full_unlimited_sync_marks_missing_removed_by_default(self) -> None:
        self.assertTrue(
            should_mark_missing_removed(
                limit=None,
                mark_removed=None,
                collection_errors=(),
            )
        )

    def test_limited_sync_does_not_mark_missing_removed_by_default(self) -> None:
        self.assertFalse(
            should_mark_missing_removed(
                limit=10,
                mark_removed=None,
                collection_errors=(),
            )
        )

    def test_explicit_mark_removed_is_disabled_for_partial_sync(self) -> None:
        self.assertFalse(
            should_mark_missing_removed(
                limit=None,
                mark_removed=True,
                collection_errors=("project_page_fetch_failed url=https://example.test",),
            )
        )

    def test_explicit_mark_removed_false_stays_false(self) -> None:
        self.assertFalse(
            should_mark_missing_removed(
                limit=None,
                mark_removed=False,
                collection_errors=(),
            )
        )


if __name__ == "__main__":
    unittest.main()
