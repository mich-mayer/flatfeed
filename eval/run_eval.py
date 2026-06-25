from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import os
import re
from typing import Any

from synthetic.generator import generate_synthetic_listings
from synthetic.golden_set import GOLDEN_SET_SEED, load_golden_set
from flatfeed.ai_qa import run_ai_qa_check_for_listing
from flatfeed.config import get_settings
from flatfeed.db.models import Listing
from flatfeed.listing_status import PARSED_STATUS
from flatfeed.matching import KALT_RENT_LABELS, WARM_RENT_LABELS, extract_rent_display
from flatfeed.parser import parse_listing_from_text
from eval.report import format_json_report, format_text_report


FIELDS = (
    "display_wbs",
    "allowed_wbs",
    "rent_kalt_cents",
    "rent_warm_cents",
    "rooms",
    "floor",
    "bezirk",
    "postal_code",
    "seniors_only",
    "exchange_only",
    "family_only",
)


def _euros_to_cents(value: int | None) -> int | None:
    return value * 100 if value is not None else None


def _display_price_to_cents(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d+(?:,\d{1,2})?", value)
    if match is None:
        return None
    try:
        return int(Decimal(match.group(0).replace(",", ".")) * 100)
    except InvalidOperation:
        return None


def _rent_cents_from_text_or_source(
    *,
    raw_text: str,
    labels: tuple[str, ...],
    source_value: int | None,
) -> int | None:
    return _display_price_to_cents(extract_rent_display(raw_text, labels)) or _euros_to_cents(
        source_value
    )


def _parser_values(listing) -> dict[str, Any]:
    parsed = parse_listing_from_text(
        url=listing.url,
        title=listing.title,
        raw_text=listing.raw_text,
        latitude=listing.truth_lat,
        longitude=listing.truth_lon,
    )
    constraints = parsed.hidden_constraints
    source = parsed.source_listing
    return {
        "display_wbs": parsed.display_wbs,
        "allowed_wbs": parsed.wbs_requirement.allowed_percentages,
        "rent_kalt_cents": _rent_cents_from_text_or_source(
            raw_text=listing.raw_text,
            labels=KALT_RENT_LABELS,
            source_value=source.rent_kalt,
        ),
        "rent_warm_cents": _rent_cents_from_text_or_source(
            raw_text=listing.raw_text,
            labels=WARM_RENT_LABELS,
            source_value=source.rent_warm,
        ),
        "rooms": source.rooms,
        "floor": source.floor,
        "bezirk": source.district,
        "postal_code": source.postal_code,
        "seniors_only": bool(constraints.get("seniors_only")),
        "exchange_only": bool(constraints.get("exchange_only_tauschwohnung")),
        "family_only": bool(constraints.get("family_only")),
    }


def _truth_values(listing) -> dict[str, Any]:
    return {
        "display_wbs": listing.truth_wbs_display,
        "allowed_wbs": listing.truth_wbs_allowed,
        "rent_kalt_cents": listing.truth_rent_kalt_cents,
        "rent_warm_cents": listing.truth_rent_warm_cents,
        "rooms": listing.truth_rooms,
        "floor": listing.truth_floor,
        "bezirk": listing.truth_bezirk,
        "postal_code": listing.truth_postal_code,
        "seniors_only": listing.truth_seniors_only,
        "exchange_only": listing.truth_exchange_only,
        "family_only": listing.truth_family_only,
    }


def _listing_model(listing) -> Listing:
    parsed = parse_listing_from_text(
        url=listing.url,
        title=listing.title,
        raw_text=listing.raw_text,
        latitude=listing.truth_lat,
        longitude=listing.truth_lon,
    )
    source = parsed.source_listing
    return Listing(
        source_company="FlatFeed Synthetic",
        url=listing.url,
        title=listing.title,
        raw_text=listing.raw_text,
        address=source.address,
        postal_code=source.postal_code,
        district=source.district,
        floor=source.floor,
        rooms=source.rooms,
        rent_kalt=source.rent_kalt,
        rent_warm=source.rent_warm,
        latitude=listing.truth_lat,
        longitude=listing.truth_lon,
        parsed_constraints=parsed.hidden_constraints,
        source_active=True,
        status=PARSED_STATUS,
    )


def run_eval(*, seed: int | None = None, provider: str = "mock") -> dict[str, Any]:
    if provider:
        os.environ["AI_QA_PROVIDER"] = provider
        get_settings.cache_clear()
    listings = load_golden_set() if seed is None else generate_synthetic_listings(seed=seed)
    field_correct = Counter()
    field_total = Counter()
    misses_by_tag = Counter()
    exact_correct = 0
    caught_error_fields = 0
    missed_error_fields = 0
    false_alert_fields = 0
    quiet_correct_fields = 0
    total_cost = 0.0
    field_misses: dict[str, int] = defaultdict(int)

    for listing in listings:
        parser_values = _parser_values(listing)
        truth_values = _truth_values(listing)
        listing_exact = True
        wrong_fields = set()
        for field in FIELDS:
            field_total[field] += 1
            if parser_values[field] == truth_values[field]:
                field_correct[field] += 1
            else:
                listing_exact = False
                wrong_fields.add(field)
                field_misses[field] += 1
                for tag in listing.case_tags:
                    misses_by_tag[tag] += 1
        if listing_exact:
            exact_correct += 1

        model = _listing_model(listing)
        ai_result, _prompt_tokens, _completion_tokens, cost = run_ai_qa_check_for_listing(
            model,
            provider=provider,
        )
        total_cost += cost
        issue_fields = {
            str(issue.get("field") or "").lower()
            for issue in ai_result.get("issues", [])
            if isinstance(issue, dict)
        }
        for field in FIELDS:
            flagged = any(field_alias in issue_fields for field_alias in _field_aliases(field))
            if field in wrong_fields and flagged:
                caught_error_fields += 1
            elif field in wrong_fields:
                missed_error_fields += 1
            elif flagged:
                false_alert_fields += 1
            else:
                quiet_correct_fields += 1

    total_fields = sum(field_total.values())
    correct_fields = sum(field_correct.values())
    caught_denominator = caught_error_fields + missed_error_fields
    false_denominator = false_alert_fields + quiet_correct_fields
    precision_denominator = caught_error_fields + false_alert_fields
    return {
        "listing_count": len(listings),
        "qa_provider": provider,
        "total_cost_usd": total_cost,
        "parser": {
            "field_accuracy": correct_fields / total_fields if total_fields else 0.0,
            "exact_listing_accuracy": exact_correct / len(listings) if listings else 0.0,
            "by_field": {
                field: field_correct[field] / field_total[field]
                for field in FIELDS
                if field_total[field]
            },
            "misses_by_field": dict(field_misses),
            "misses_by_tag": dict(misses_by_tag),
        },
        "qa": {
            "caught_error_fields": caught_error_fields,
            "missed_error_fields": missed_error_fields,
            "false_alert_fields": false_alert_fields,
            "quiet_correct_fields": quiet_correct_fields,
            "caught_error_rate": (
                caught_error_fields / caught_denominator
                if caught_denominator
                else 0.0
            ),
            "false_alert_rate": (
                false_alert_fields / false_denominator
                if false_denominator
                else 0.0
            ),
            "alert_precision": (
                caught_error_fields / precision_denominator
                if precision_denominator
                else 0.0
            ),
        },
    }


def _field_aliases(field: str) -> tuple[str, ...]:
    aliases = {
        "display_wbs": ("display_wbs", "wbs", "required_wbs"),
        "allowed_wbs": ("display_wbs", "wbs", "required_wbs"),
        "rent_kalt_cents": ("rent_kalt", "kalt"),
        "rent_warm_cents": ("rent_warm", "warm"),
        "bezirk": ("district", "bezirk"),
        "exchange_only": ("exchange_only", "exchange_only_tauschwohnung"),
        "family_only": ("family_only",),
        "seniors_only": ("seniors_only",),
    }
    return aliases.get(field, (field,))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FlatFeed parser and AI QA eval.")
    parser.add_argument("--seed", type=int, default=None, help="Synthetic generation seed.")
    parser.add_argument(
        "--provider",
        choices=("mock", "openai"),
        default="mock",
        help="AI QA provider for controller evaluation.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    args = parser.parse_args()
    report = run_eval(seed=args.seed if args.seed is not None else GOLDEN_SET_SEED, provider=args.provider)
    print(format_json_report(report) if args.json else format_text_report(report))


if __name__ == "__main__":
    main()
