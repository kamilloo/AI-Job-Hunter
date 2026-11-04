from decimal import Decimal

import pytest
from pydantic import ValidationError

from job_hunter.model.TokenPricing import TokenPricing
from job_hunter.cost.estimate_token_cost import estimate_token_cost


def make_pricing():
    return TokenPricing(
        input_per_million=Decimal("0.50"),
        cached_input_per_million=Decimal("0.10"),
        output_per_million=Decimal("2.00"),
    )


def test_estimate_token_cost():
    result = estimate_token_cost(
        input_tokens=1200,
        output_tokens=300,
        pricing=make_pricing(),
    )

    assert result == Decimal("0.0012")
    assert isinstance(result, Decimal)


def test_estimate_token_cost_zero_usage():
    result = estimate_token_cost(
        input_tokens=0,
        output_tokens=0,
        pricing=make_pricing(),
    )

    assert result == Decimal("0")


def test_estimate_token_cost_preserves_precision():
    result = estimate_token_cost(
        input_tokens=1,
        output_tokens=1,
        pricing=TokenPricing(
            input_per_million=Decimal("0.123456"),
            cached_input_per_million=Decimal("0.0"),
            output_per_million=Decimal("0.654321"),
        ),
    )

    assert result == Decimal("0.000000777777")


@pytest.mark.parametrize(
    ("input_tokens", "output_tokens"),
    [
        (-1, 100),
        (100, -1),
        (True, 100),
        (100, False),
        (1.5, 100),
        ("100", 100),
    ],
)
def test_estimate_token_cost_rejects_invalid_usage(
    input_tokens,
    output_tokens,
):
    with pytest.raises(ValueError):
        estimate_token_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            pricing=make_pricing(),
        )


@pytest.mark.parametrize(
    "invalid_price",
    [
        Decimal("-0.01"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        Decimal("-1"),
    ],
)
def test_token_pricing_rejects_invalid_prices(invalid_price):
    with pytest.raises(ValidationError):
        TokenPricing(
            input_per_million=invalid_price,
            cached_input_per_million=Decimal("0.10"),
            output_per_million=Decimal("2.00"),
        )


def test_token_pricing_rejects_extra_fields():
    with pytest.raises(ValidationError):
        TokenPricing(
            input_per_million=Decimal("0.50"),
            cached_input_per_million=Decimal("0.10"),
            output_per_million=Decimal("2.00"),
            api_key="secret",
        )


def test_token_pricing_accepts_zero_prices():
    pricing = TokenPricing(
        input_per_million=Decimal("0"),
        output_per_million=Decimal("0"),
        cached_input_per_million=Decimal("0"),
    )

    assert pricing.input_per_million == Decimal("0")
    assert pricing.output_per_million == Decimal("0")
    assert pricing.cached_input_per_million == Decimal("0")

