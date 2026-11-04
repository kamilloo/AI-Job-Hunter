from decimal import Decimal

from job_hunter.model.TokenPricing import TokenPricing
from job_hunter.cost.map_gemini_billable_tokens import BillableTokens

MILLION = Decimal("1000000")

def estimate_gemini_cost(
    *,
    tokens: BillableTokens,
    pricing: TokenPricing,
) -> Decimal:
    return (
        pricing.input_per_million * tokens.uncached_input_tokens/ MILLION
        + pricing.cached_input_per_million * tokens.cached_input_tokens / MILLION
        + pricing.output_per_million * tokens.output_tokens  / MILLION
    )