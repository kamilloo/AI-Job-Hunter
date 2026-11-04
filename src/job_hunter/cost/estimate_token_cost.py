from decimal import Decimal

from job_hunter.model.TokenPricing import TokenPricing

MILLION = Decimal("1000000")

def estimate_token_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    pricing: TokenPricing,
) -> Decimal:
    if type(input_tokens) is not int or type(output_tokens) is not int:
        raise ValueError("Token counts must be integers")
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts must be non-negative")
    return (
        pricing.input_per_million * input_tokens / MILLION
        + pricing.output_per_million * output_tokens / MILLION
    )
