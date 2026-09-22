"""Build a site-only GitHub Pages artifact without publishing project notes."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
SITE_FILES = (
    "index.html",
    "case-study.html",
    "demo-listing.html",
    "styles.css",
    "carousel.js",
    "terms.js",
    "favicon.ico",
    "flatfeed-favicon.png",
    "assets/flatfeed-logo-mark.png",
    "assets/flatfeed-flow-01-start.png",
    "assets/flatfeed-flow-02-wbs.png",
    "assets/flatfeed-flow-03-district.png",
    "assets/flatfeed-flow-04-rent.png",
    "assets/flatfeed-flow-05-rooms.png",
    "assets/flatfeed-flow-06-saved-filter.png",
    "assets/flatfeed-flow-07-listing.png",
)


def stage_pages(destination: Path) -> tuple[str, ...]:
    """Copy the explicit allowlist into a new directory; never overwrite one."""
    destination = destination.resolve()
    source_root = DOCS_DIR.resolve()
    if destination == source_root or source_root in destination.parents:
        raise ValueError("Pages output must be outside the docs source directory")
    if destination.exists():
        raise FileExistsError("Pages output must be a new directory")

    # Validate the complete input set before creating the artifact.
    for name in SITE_FILES:
        source = DOCS_DIR / name
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Required site file is missing or symlinked: {name}")
        if source_root not in source.resolve().parents:
            raise ValueError(f"Site file resolves outside docs: {name}")

    destination.mkdir(parents=True)
    for name in SITE_FILES:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DOCS_DIR / name, target)
    return SITE_FILES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="New output directory")
    args = parser.parse_args()
    try:
        files = stage_pages(args.destination)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Cannot stage Pages: {exc}\n")
    print(f"Staged {len(files)} site files in {args.destination}")


if __name__ == "__main__":
    main()
