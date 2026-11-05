import logging
from collections.abc import Mapping

from job_hunter.cost.estimate_gemini_usage_cost import estimate_gemini_usage_cost
from job_hunter.model.GeminiUsage import GeminiUsage
from job_hunter.model.Log import Log
from job_hunter.model.TokenPricing import TokenPricing
from job_hunter.observability import make_log_event


def make_gemini_cost_event(
    *,
    usage: GeminiUsage | None,
    model: str,
    pricing_table: Mapping[str, TokenPricing],
) -> Log | None:
    cost = estimate_gemini_usage_cost(
        usage=usage,
        model=model,
        pricing_table=pricing_table,
    )

    if cost is None:
        return None

    return make_log_event(
        event="gemini_cost_estimated",
        component="gemini",
        outcome="success",
        model=model,
        estimated_cost_usd=cost,
        level=logging.INFO,
    )