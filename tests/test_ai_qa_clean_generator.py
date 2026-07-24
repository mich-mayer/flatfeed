from __future__ import annotations

import json
import random
import re
import unittest

from eval.ai_qa_clean_generator import (
    CLEAN_AI_QA_SEED,
    FORMAT_VARIANTS,
    generate_clean_ai_qa_cases,
)
from flatfeed.listing_metadata import BERLIN_DISTRICTS
from flatfeed.wbs_rules import (
    display_wbs_requirement,
    extract_wbs_requirement,
)


def _money_to_cents(value: str) -> int:
    match = re.fullmatch(r"(\d{1,3}(?:\.\d{3})*|\d+),(\d{2}) EUR", value)
    if match is None:
        raise AssertionError(f"Unexpected money value: {value}")
    euros = int(match.group(1).replace(".", ""))
    return euros * 100 + int(match.group(2))


class CleanAIQAGeneratorTests(unittest.TestCase):
    def test_same_seed_creates_identical_cases(self) -> None:
        first = generate_clean_ai_qa_cases(count=100, seed=CLEAN_AI_QA_SEED)
        second = generate_clean_ai_qa_cases(count=100, seed=CLEAN_AI_QA_SEED)

        self.assertEqual(first, second)
        self.assertNotEqual(
            first,
            generate_clean_ai_qa_cases(count=100, seed=CLEAN_AI_QA_SEED + 1),
        )

    def test_generator_does_not_change_global_random_state(self) -> None:
        random.seed(4815)
        expected = random.random()
        random.seed(4815)

        generate_clean_ai_qa_cases(count=20)

        self.assertEqual(random.random(), expected)

    def test_cases_have_required_fields_and_json_compatible_snapshots(self) -> None:
        cases = generate_clean_ai_qa_cases(count=100)

        self.assertEqual(len(cases), 100)
        self.assertEqual(len({case.case_id for case in cases}), 100)
        for case in cases:
            with self.subTest(case_id=case.case_id):
                self.assertRegex(case.case_id, r"^clean-\d{4}-[0-9a-f]{10}$")
                self.assertTrue(case.title.strip())
                self.assertTrue(case.raw_text.strip())
                self.assertIn(case.format_variant, FORMAT_VARIANTS)

                snapshot = case.parser_snapshot
                self.assertEqual(
                    set(snapshot.as_dict()),
                    {
                        "required_wbs",
                        "display_wbs",
                        "rooms",
                        "floor",
                        "address",
                        "postal_code",
                        "district",
                        "rent_kalt",
                        "rent_warm",
                    },
                )
                self.assertTrue(snapshot.display_wbs)
                self.assertTrue(snapshot.address)
                self.assertTrue(snapshot.postal_code)
                self.assertTrue(snapshot.district)
                self.assertTrue(snapshot.floor)
                self.assertTrue(snapshot.rent_kalt)
                self.assertTrue(snapshot.rent_warm)
                self.assertGreater(snapshot.rooms, 0)

                serialized = json.dumps(
                    snapshot.as_dict(),
                    ensure_ascii=False,
                    sort_keys=True,
                )
                self.assertEqual(
                    json.loads(serialized),
                    snapshot.as_dict(),
                )

    def test_snapshot_values_stay_within_admissible_ranges(self) -> None:
        for case in generate_clean_ai_qa_cases(count=240):
            with self.subTest(case_id=case.case_id):
                snapshot = case.parser_snapshot
                kalt_cents = _money_to_cents(snapshot.rent_kalt)
                warm_cents = _money_to_cents(snapshot.rent_warm)

                self.assertIn(snapshot.district, BERLIN_DISTRICTS)
                self.assertRegex(snapshot.postal_code, r"^(?:1[0-3]\d{3}|14[01]\d{2})$")
                self.assertGreaterEqual(snapshot.rooms, 1.0)
                self.assertLessEqual(snapshot.rooms, 5.0)
                self.assertIn(
                    snapshot.floor,
                    {"EG", "Hochparterre", "1", "2", "3", "4", "5", "6", "7", "DG"},
                )
                self.assertGreaterEqual(kalt_cents, 40_000)
                self.assertLessEqual(kalt_cents, 140_000)
                self.assertGreater(warm_cents, kalt_cents)
                self.assertLessEqual(warm_cents, 175_000)

    def test_generated_cases_are_clean_by_construction(self) -> None:
        for case in generate_clean_ai_qa_cases(count=100):
            with self.subTest(case_id=case.case_id):
                snapshot = case.parser_snapshot
                requirement = extract_wbs_requirement(case.raw_text)

                self.assertEqual(snapshot.required_wbs, requirement.required_wbs)
                self.assertEqual(
                    snapshot.display_wbs,
                    display_wbs_requirement(requirement),
                )
                self.assertIn(snapshot.address, case.raw_text)
                self.assertIn(snapshot.postal_code, case.raw_text)
                self.assertIn(snapshot.district, case.raw_text)
                room_text = (
                    str(int(snapshot.rooms))
                    if snapshot.rooms.is_integer()
                    else str(snapshot.rooms).replace(".", ",")
                )
                self.assertRegex(
                    case.raw_text,
                    rf"(?:{re.escape(room_text)}\s*-?\s*Zimmer"
                    rf"|Zimmer(?:anzahl)?\s*(?::|\n|\s{{2,}})\s*"
                    rf"{re.escape(room_text)})",
                )
                floor_text = {
                    "EG": "Erdgeschoss",
                    "DG": "Dachgeschoss",
                }.get(snapshot.floor, snapshot.floor)
                self.assertRegex(
                    case.raw_text,
                    rf"(?:Etage|Geschoss|Stockwerk)"
                    rf"(?:\s+liegt\s+bei)?\s*(?::|\n|\s)\s*"
                    rf"{re.escape(floor_text)}",
                )
                self.assertIn(
                    snapshot.rent_kalt.replace(" EUR", ""),
                    case.raw_text,
                )
                self.assertIn(
                    snapshot.rent_warm.replace(" EUR", ""),
                    case.raw_text,
                )

    def test_large_sample_has_required_diversity(self) -> None:
        cases = generate_clean_ai_qa_cases(count=120)
        snapshots = [case.parser_snapshot for case in cases]

        self.assertEqual(
            {snapshot.district for snapshot in snapshots},
            set(BERLIN_DISTRICTS),
        )
        self.assertGreaterEqual(len({snapshot.address for snapshot in snapshots}), 100)
        self.assertGreaterEqual(len({snapshot.postal_code for snapshot in snapshots}), 20)
        self.assertEqual(
            {snapshot.rooms for snapshot in snapshots},
            {1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0},
        )
        self.assertEqual(
            {snapshot.floor for snapshot in snapshots},
            {"EG", "Hochparterre", "1", "2", "3", "4", "5", "6", "7", "DG"},
        )
        self.assertGreaterEqual(len({snapshot.rent_kalt for snapshot in snapshots}), 110)
        self.assertGreaterEqual(len({snapshot.display_wbs for snapshot in snapshots}), 7)
        self.assertEqual(
            {case.format_variant for case in cases},
            set(FORMAT_VARIANTS),
        )

    def test_invalid_arguments_are_rejected(self) -> None:
        self.assertEqual(generate_clean_ai_qa_cases(count=0), [])
        with self.assertRaisesRegex(ValueError, "count must be non-negative"):
            generate_clean_ai_qa_cases(count=-1)
        with self.assertRaisesRegex(TypeError, "seed must be an integer"):
            generate_clean_ai_qa_cases(count=1, seed=True)
        with self.assertRaisesRegex(TypeError, "count must be an integer"):
            generate_clean_ai_qa_cases(count=True)


if __name__ == "__main__":
    unittest.main()
