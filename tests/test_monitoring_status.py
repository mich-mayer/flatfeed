import unittest

from flatfeed.monitoring import (
    INGESTION_STATUS_FAILED,
    INGESTION_STATUS_PARTIAL_SUCCESS,
    INGESTION_STATUS_SUCCESS,
    NON_SUCCESS_STATUSES,
)


class MonitoringStatusTests(unittest.TestCase):
    def test_partial_success_counts_as_non_success_for_alerting(self) -> None:
        self.assertIn(INGESTION_STATUS_PARTIAL_SUCCESS, NON_SUCCESS_STATUSES)

    def test_success_does_not_count_as_non_success(self) -> None:
        self.assertNotIn(INGESTION_STATUS_SUCCESS, NON_SUCCESS_STATUSES)

    def test_failed_counts_as_non_success(self) -> None:
        self.assertIn(INGESTION_STATUS_FAILED, NON_SUCCESS_STATUSES)


if __name__ == "__main__":
    unittest.main()
