import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.stage_pages import SITE_FILES, stage_pages


class PagesArtifactTests(unittest.TestCase):
    def test_only_site_files_are_published(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "docs"
            source.mkdir()
            for name in SITE_FILES:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("site content")
            for name in ("CURRENT_STATUS.md", ".env.local", "assets/retired.png"):
                (source / name).write_text("must not be published")
            output = Path(temp) / "site"
            with patch("scripts.stage_pages.DOCS_DIR", source):
                stage_pages(output)
            published = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()}
            self.assertEqual(published, set(SITE_FILES))
            self.assertTrue(all(p.read_text() == "site content" for p in output.rglob("*") if p.is_file()))

    def test_existing_output_and_source_directory_are_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            sentinel = output / "keep.txt"
            sentinel.write_text("keep")
            with self.assertRaises(FileExistsError):
                stage_pages(output)
            with patch("scripts.stage_pages.DOCS_DIR", output):
                with self.assertRaises(ValueError):
                    stage_pages(output / "nested-output")
            self.assertEqual(sentinel.read_text(), "keep")

    def test_missing_or_symlinked_input_fails_before_creating_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "docs"
            source.mkdir()
            output = Path(temp) / "site"
            with patch("scripts.stage_pages.DOCS_DIR", source):
                with self.assertRaises(ValueError):
                    stage_pages(output)
                self.assertFalse(output.exists())
                external = Path(temp) / "private.txt"
                external.write_text("private")
                (source / SITE_FILES[0]).symlink_to(external)
                with self.assertRaises(ValueError):
                    stage_pages(output)
                self.assertFalse(output.exists())
