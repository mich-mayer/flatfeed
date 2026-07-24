from __future__ import annotations

import json
import unittest

from eval.ai_qa_luna_effort_compare import compare_efforts


def _truth(case_id: str, field: str | None) -> dict[str, object]:
    return {
        "case_id": case_id,
        "case_type": "clean" if field is None else "corrupted",
        "corrupted_field": field,
        "expected_value": "expected" if field is not None else None,
        "corrupted_value": "corrupted" if field is not None else None,
        "corruption_type": "test" if field is not None else None,
    }


def _prediction(case_id: str, has_error: bool, field: str | None) -> dict[str, object]:
    return {
        "case_id": case_id,
        "status": "completed",
        "raw_output": json.dumps({"has_error": has_error, "error_field": field}),
        "latency_ms": 1.0,
        "latency_mode": "synchronous_case",
        "retry_count": 0,
    }


class LunaEffortComparisonTests(unittest.TestCase):
    def test_low_advances_only_with_two_more_wbs_and_no_regressions(self) -> None:
        truth = [
            *(_truth(f"wbs-{index}", "display_wbs") for index in range(3)),
            _truth("clean", None),
            _truth("rooms", "rooms"),
        ]
        none = [
            _prediction("wbs-0", True, "wbs"),
            _prediction("wbs-1", False, None),
            _prediction("wbs-2", False, None),
            _prediction("clean", False, None),
            _prediction("rooms", True, "rooms"),
        ]
        low = [
            _prediction("wbs-0", True, "wbs"),
            _prediction("wbs-1", True, "wbs"),
            _prediction("wbs-2", True, "wbs"),
            _prediction("clean", False, None),
            _prediction("rooms", True, "rooms"),
        ]
        result = compare_efforts(truth_rows=truth, none_rows=none, low_rows=low)
        self.assertEqual(
            result["decision"],
            "advance_low_to_fresh_calibration_contract",
        )

    def test_low_stops_when_it_adds_a_false_alert(self) -> None:
        truth = [_truth("clean", None)]
        result = compare_efforts(
            truth_rows=truth,
            none_rows=[_prediction("clean", False, None)],
            low_rows=[_prediction("clean", True, "wbs")],
        )
        self.assertEqual(result["decision"], "stop_luna")


if __name__ == "__main__":
    unittest.main()
