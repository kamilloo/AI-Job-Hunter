
from decimal import Decimal

import pytest
from pydantic import ValidationError

from job_hunter.model.TokenPricing import TokenPricing
from job_hunter.cost.map_gemini_billable_tokens import BillableTokens
from job_hunter.cost.estimate_gemini_cost import estimate_gemini_cost


def make_pricing():
    return TokenPricing(
        input_per_million=Decimal("0.50"),
        cached_input_per_million=Decimal("0.10"),
        output_per_million=Decimal("2.00"),
    )


def test_estimate_gemini_cost_with_cached_input():
    tokens = BillableTokens(
        uncached_input_tokens=1100,
        cached_input_tokens=100,
        output_tokens=550,
    )

    result = estimate_gemini_cost(
        tokens=tokens,
        pricing=make_pricing(),
    )

    # 1100 * 0.50 / 1M = 0.00055
    # 100 * 0.10 / 1M  = 0.00001
    # 550 * 2.00 / 1M = 0.00110
    assert result == Decimal("0.00166")


def test_estimate_gemini_cost_without_cached_input():
    tokens = BillableTokens(
        uncached_input_tokens=1200,
        cached_input_tokens=0,
        output_tokens=300,
    )

    assert estimate_gemini_cost(
        tokens=tokens,
        pricing=make_pricing(),
    ) == Decimal("0.0012")


def test_estimate_gemini_cost_zero_usage():
    tokens = BillableTokens(
        uncached_input_tokens=0,
        cached_input_tokens=0,
        output_tokens=0,
    )

    assert estimate_gemini_cost(
        tokens=tokens,
        pricing=make_pricing(),
    ) == Decimal("0")


@pytest.mark.parametrize(
    "invalid_price",
    [
        Decimal("-0.01"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_token_pricing_rejects_invalid_cached_rate(invalid_price):
    with pytest.raises(ValidationError):
        TokenPricing(
            input_per_million=Decimal("0.50"),
            cached_input_per_million=invalid_price,
            output_per_million=Decimal("2.00"),
        )


def test_token_pricing_requires_cached_rate():
    with pytest.raises(ValidationError):
        TokenPricing(
            input_per_million=Decimal("0.50"),
            output_per_million=Decimal("2.00"),
        )
