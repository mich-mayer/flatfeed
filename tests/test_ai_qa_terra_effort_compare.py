from __future__ import annotations

import json
import unittest

from eval.ai_qa_terra_effort_compare import compare_terra_efforts


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


class TerraEffortComparisonTests(unittest.TestCase):
    def test_low_advances_only_when_all_absolute_criteria_pass(self) -> None:
        truth = [
            *(_truth(f"wbs-{index}", "display_wbs") for index in range(20)),
            *(_truth(f"clean-{index}", None) for index in range(16)),
            *(_truth(f"rooms-{index}", "rooms") for index in range(12)),
        ]
        none = []
        low = []
        for row in truth:
            case_id = str(row["case_id"])
            expected = (
                None
                if row["case_type"] == "clean"
                else "wbs" if row["corrupted_field"] == "display_wbs" else "rooms"
            )
            none.append(
                _prediction(case_id, expected is not None, expected)
            )
            low.append(
                _prediction(case_id, expected is not None, expected)
            )
        result = compare_terra_efforts(
            truth_rows=truth,
            none_rows=none,
            low_rows=low,
        )
        self.assertEqual(
            result["decision"],
            "advance_terra_low_to_fresh_calibration_contract",
        )

    def test_low_stops_when_false_alert_limit_fails(self) -> None:
        truth = [_truth(f"clean-{index}", None) for index in range(2)]
        result = compare_terra_efforts(
            truth_rows=truth,
            none_rows=[
                _prediction(str(row["case_id"]), False, None) for row in truth
            ],
            low_rows=[
                _prediction(str(row["case_id"]), True, "wbs") for row in truth
            ],
        )
        self.assertEqual(result["decision"], "stop_terra")


if __name__ == "__main__":
    unittest.main()
