from __future__ import annotations

from pathlib import Path


LISTING_PHOTO_ASSETS: tuple[str, ...] = (
    "assets/listing_photos/berlin_tempelhof_alboinplatz_wohnblock.jpg",
    "assets/listing_photos/berlin_hohenschoenhausen_suermondtstr_wohnblock.jpg",
    "assets/listing_photos/berlin_wilmersdorf_binger_strasse_wohnblock.jpg",
    "assets/listing_photos/berlin_wedding_ostender_strasse_wohnblock.jpg",
    "assets/listing_photos/berlin_mitte_memhardstrasse_wohnblock.jpg",
)


def listing_photo_for_index(index: int) -> str:
    return LISTING_PHOTO_ASSETS[(index - 1) % len(LISTING_PHOTO_ASSETS)]


def listing_photo_assets_exist(project_root: Path) -> bool:
    return all((project_root / path).is_file() for path in LISTING_PHOTO_ASSETS)
