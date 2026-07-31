import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DemoListingPageTests(unittest.TestCase):
    def test_page_keeps_case_study_exit_without_looping_back_to_the_bot(self) -> None:
        html = (PROJECT_ROOT / "docs" / "demo-listing.html").read_text(
            encoding="utf-8"
        )

        self.assertIn("Read the case study", html)
        self.assertIn("product decisions, evaluation results", html)
        self.assertNotIn("t.me/FlatFeedBot", html)
        self.assertNotIn("Try the guided tour", html)


if __name__ == "__main__":
    unittest.main()
