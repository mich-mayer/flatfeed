from __future__ import annotations

from typing import Optional

from flatfeed.config import get_settings


def calculate_openai_cost_usd(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    input_price_per_1m: Optional[float] = None,
    output_price_per_1m: Optional[float] = None,
) -> float:
    settings = get_settings()
    input_price = input_price_per_1m or settings.openai_input_price_per_1m
    output_price = output_price_per_1m or settings.openai_output_price_per_1m

    return (prompt_tokens / 1_000_000 * input_price) + (
        completion_tokens / 1_000_000 * output_price
    )
