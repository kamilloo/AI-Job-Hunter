from collections.abc import Mapping
from decimal import Decimal

from job_hunter.cost.estimate_gemini_cost import estimate_gemini_cost
from job_hunter.cost.map_gemini_billable_tokens import map_gemini_billable_tokens
from job_hunter.cost.resolve_model_pricing import resolve_model_pricing
from job_hunter.model.GeminiUsage import GeminiUsage
from job_hunter.model.TokenPricing import TokenPricing


def estimate_gemini_usage_cost(
    *,
    usage: GeminiUsage | None,
    model: str,
    pricing_table: Mapping[str, TokenPricing],
) -> Decimal | None:
    if usage is None:
        return None
    pricing = resolve_model_pricing(model, pricing_table)
    if pricing is None:
        return None
    try:
        tokens = map_gemini_billable_tokens(usage=usage)
    except ValueError:
        return None
    if tokens is None:
        return None

    return estimate_gemini_cost(
        tokens=tokens,
        pricing=pricing,
)

