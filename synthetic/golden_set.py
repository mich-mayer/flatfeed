from __future__ import annotations

from synthetic.generator import SyntheticListing, generate_synthetic_listings


GOLDEN_SET_SEED = 20260623


def load_golden_set() -> list[SyntheticListing]:
    return generate_synthetic_listings(seed=GOLDEN_SET_SEED)
