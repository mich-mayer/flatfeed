from __future__ import annotations

import json
import random
import re
import unittest

from eval.ai_qa_clean_generator import generate_clean_ai_qa_cases
from eval.ai_qa_corruptions import (
    CONTROLLED_ERROR_SEED,
    CORRUPTION_FIELDS,
    build_clean_ai_qa_eval_case,
    build_corrupted_ai_qa_eval_case,
    generate_controlled_ai_qa_cases,
)
from flatfeed.listing_metadata import BERLIN_DISTRICTS


_MONEY_RE = re.compile(r"^(\d{1,3}(?:\.\d{3})*|\d+),(\d{2}) EUR$")


def _money_to_cents(value: str) -> int:
    match = _MONEY_RE.fullmatch(value)
    if match is None:
        raise AssertionError(f"Unexpected money value: {value}")
    euros = int(match.group(1).replace(".", ""))
    return euros * 100 + int(match.group(2))


def _changed_snapshot_fields(
    clean_snapshot: dict[str, object],
    corrupted_snapshot: dict[str, object],
) -> set[str]:
    return {
        field
        for field, expected in clean_snapshot.items()
        if corrupted_snapshot[field] != expected
    }


class AIQACorruptionTests(unittest.TestCase):
    def test_every_supported_corruption_changes_exactly_one_field(self) -> None:
        clean_cases = generate_clean_ai_qa_cases(count=len(CORRUPTION_FIELDS))

        for clean_case, corruption_field in zip(clean_cases, CORRUPTION_FIELDS):
            with self.subTest(corruption_field=corruption_field):
                result = build_corrupted_ai_qa_eval_case(
                    clean_case,
                    corruption_field=corruption_field,
                )
                clean_snapshot = clean_case.parser_snapshot.as_dict()
                corrupted_snapshot = result.model_input.parser_snapshot.as_dict()
                changed_fields = _changed_snapshot_fields(
                    clean_snapshot,
                    corrupted_snapshot,
                )

                self.assertEqual(len(changed_fields), 1)
                changed_field = next(iter(changed_fields))
                answer_key = result.answer_key
                self.assertEqual(answer_key.case_type, "corrupted")
                self.assertEqual(answer_key.corrupted_field, changed_field)
                self.assertEqual(
                    answer_key.expected_value,
                    clean_snapshot[changed_field],
                )
                self.assertEqual(
                    answer_key.corrupted_value,
                    corrupted_snapshot[changed_field],
                )
                self.assertNotEqual(
                    answer_key.expected_value,
                    answer_key.corrupted_value,
                )
                self.assertTrue(answer_key.corruption_type)
                self.assertEqual(result.model_input.raw_text, clean_case.raw_text)

    def test_unchanged_fields_remain_identical_across_many_cases(self) -> None:
        clean_cases = generate_clean_ai_qa_cases(count=140)

        for index, clean_case in enumerate(clean_cases):
            corruption_field = CORRUPTION_FIELDS[index % len(CORRUPTION_FIELDS)]
            result = build_corrupted_ai_qa_eval_case(
                clean_case,
                corruption_field=corruption_field,
                seed=CONTROLLED_ERROR_SEED + index,
            )
            expected = clean_case.parser_snapshot.as_dict()
            actual = result.model_input.parser_snapshot.as_dict()
            changed_field = result.answer_key.corrupted_field

            with self.subTest(
                case_id=result.answer_key.case_id,
                corruption_field=corruption_field,
            ):
                self.assertIsNotNone(changed_field)
                for field, expected_value in expected.items():
                    if field == changed_field:
                        self.assertNotEqual(actual[field], expected_value)
                    else:
                        self.assertEqual(actual[field], expected_value)

    def test_clean_case_has_separate_empty_answer_key(self) -> None:
        clean_case = generate_clean_ai_qa_cases(count=1)[0]

        result = build_clean_ai_qa_eval_case(clean_case)

        self.assertEqual(
            result.model_input.parser_snapshot,
            clean_case.parser_snapshot,
        )
        self.assertEqual(result.model_input.raw_text, clean_case.raw_text)
        self.assertEqual(
            result.answer_key.as_dict(),
            {
                "case_id": clean_case.case_id,
                "case_type": "clean",
                "corrupted_field": None,
                "expected_value": None,
                "corrupted_value": None,
                "corruption_type": None,
            },
        )

    def test_answer_key_is_not_present_in_model_input(self) -> None:
        clean_case = generate_clean_ai_qa_cases(count=1)[0]
        result = build_corrupted_ai_qa_eval_case(
            clean_case,
            corruption_field="rooms",
        )

        model_payload = result.model_input.as_dict()
        serialized_model_payload = json.dumps(
            model_payload,
            ensure_ascii=False,
            sort_keys=True,
        )
        serialized_answer_key = json.dumps(
            result.answer_key.as_dict(),
            ensure_ascii=False,
            sort_keys=True,
        )

        self.assertEqual(set(model_payload), {"raw_text", "parser_snapshot"})
        self.assertNotIn("required_wbs", model_payload["parser_snapshot"])
        for forbidden_key in result.answer_key.as_dict():
            self.assertNotIn(f'"{forbidden_key}"', serialized_model_payload)
        self.assertNotIn(result.answer_key.case_id, serialized_model_payload)
        self.assertIn('"corrupted_field"', serialized_answer_key)

    def test_wbs_model_input_has_only_one_wbs_representation(self) -> None:
        clean_case = generate_clean_ai_qa_cases(count=1)[0]
        result = build_corrupted_ai_qa_eval_case(
            clean_case,
            corruption_field="wbs",
        )

        snapshot = result.model_input.as_dict()["parser_snapshot"]

        self.assertIn("display_wbs", snapshot)
        self.assertNotIn("required_wbs", snapshot)
        self.assertEqual(result.answer_key.corrupted_field, "display_wbs")

    def test_corruption_is_reproducible_for_the_same_seed(self) -> None:
        clean_cases = generate_clean_ai_qa_cases(count=70)
        corruption_fields = [
            CORRUPTION_FIELDS[index % len(CORRUPTION_FIELDS)]
            for index in range(len(clean_cases))
        ]

        first = generate_controlled_ai_qa_cases(
            clean_cases,
            corruption_fields=corruption_fields,
            seed=CONTROLLED_ERROR_SEED,
        )
        second = generate_controlled_ai_qa_cases(
            clean_cases,
            corruption_fields=corruption_fields,
            seed=CONTROLLED_ERROR_SEED,
        )
        different_seed = generate_controlled_ai_qa_cases(
            clean_cases,
            corruption_fields=corruption_fields,
            seed=CONTROLLED_ERROR_SEED + 1,
        )

        self.assertEqual(first, second)
        self.assertNotEqual(first, different_seed)

    def test_corrupted_values_remain_plausible(self) -> None:
        clean_cases = generate_clean_ai_qa_cases(count=210)
        allowed_wbs_values = {
            "No WBS required",
            "WBS required, type unknown",
            "100",
            "100, 140",
            "100, 140, 160, 180",
            "100, 140, 160, 180, 220",
            "140, 160, 180, 220",
            "160, 180, 220",
        }
        allowed_floors = {
            "EG",
            "Hochparterre",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "DG",
        }

        for index, clean_case in enumerate(clean_cases):
            corruption_field = CORRUPTION_FIELDS[index % len(CORRUPTION_FIELDS)]
            result = build_corrupted_ai_qa_eval_case(
                clean_case,
                corruption_field=corruption_field,
                seed=CONTROLLED_ERROR_SEED + index,
            )
            answer_key = result.answer_key
            value = answer_key.corrupted_value

            with self.subTest(
                corruption_field=corruption_field,
                case_id=answer_key.case_id,
            ):
                if answer_key.corrupted_field == "display_wbs":
                    self.assertIn(value, allowed_wbs_values)
                elif answer_key.corrupted_field in {"rent_kalt", "rent_warm"}:
                    cents = _money_to_cents(str(value))
                    self.assertGreaterEqual(cents, 30_000)
                    self.assertLessEqual(cents, 200_000)
                elif answer_key.corrupted_field == "rooms":
                    self.assertGreaterEqual(float(value), 1.0)
                    self.assertLessEqual(float(value), 5.0)
                elif answer_key.corrupted_field == "address":
                    self.assertRegex(str(value), r"\d+[a-zA-Z]?$")
                elif answer_key.corrupted_field == "postal_code":
                    self.assertRegex(str(value), r"^(?:1[0-3]\d{3}|14[01]\d{2})$")
                elif answer_key.corrupted_field == "district":
                    self.assertIn(value, BERLIN_DISTRICTS)
                elif answer_key.corrupted_field == "floor":
                    self.assertIn(value, allowed_floors)
                else:
                    self.fail(
                        f"Unexpected corrupted field: {answer_key.corrupted_field}"
                    )

    def test_address_category_can_change_address_or_postal_code(self) -> None:
        clean_case = generate_clean_ai_qa_cases(count=1)[0]
        changed_fields = {
            build_corrupted_ai_qa_eval_case(
                clean_case,
                corruption_field="address_postal_code",
                seed=seed,
            ).answer_key.corrupted_field
            for seed in range(40)
        }

        self.assertEqual(changed_fields, {"address", "postal_code"})

    def test_batch_supports_clean_and_corrupted_cases(self) -> None:
        clean_cases = generate_clean_ai_qa_cases(count=4)
        results = generate_controlled_ai_qa_cases(
            clean_cases,
            corruption_fields=(None, "wbs", None, "rent_warm"),
        )

        self.assertEqual(
            [result.answer_key.case_type for result in results],
            ["clean", "corrupted", "clean", "corrupted"],
        )
        self.assertEqual(
            [result.answer_key.corrupted_field for result in results],
            [None, "display_wbs", None, "rent_warm"],
        )

    def test_corruption_generator_does_not_change_global_random_state(self) -> None:
        clean_case = generate_clean_ai_qa_cases(count=1)[0]
        random.seed(817)
        expected = random.random()
        random.seed(817)

        build_corrupted_ai_qa_eval_case(
            clean_case,
            corruption_field="district",
        )

        self.assertEqual(random.random(), expected)

    def test_invalid_arguments_are_rejected(self) -> None:
        clean_case = generate_clean_ai_qa_cases(count=1)[0]

        with self.assertRaisesRegex(ValueError, "unsupported corruption_field"):
            build_corrupted_ai_qa_eval_case(
                clean_case,
                corruption_field="not_a_field",
            )
        with self.assertRaisesRegex(TypeError, "seed must be an integer"):
            build_corrupted_ai_qa_eval_case(
                clean_case,
                corruption_field="rooms",
                seed=True,
            )
        with self.assertRaisesRegex(ValueError, "must have equal length"):
            generate_controlled_ai_qa_cases(
                [clean_case],
                corruption_fields=(),
            )


if __name__ == "__main__":
    unittest.main()
