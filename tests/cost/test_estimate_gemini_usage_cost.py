from decimal import Decimal

import pytest

from job_hunter.model.GeminiUsage import GeminiUsage
from job_hunter.model.TokenPricing import TokenPricing
from job_hunter.cost.estimate_gemini_usage_cost import (
    estimate_gemini_usage_cost,
)


@pytest.fixture
def pricing_table():
    return {
        "model-a": TokenPricing(
            input_per_million=Decimal("0.50"),
            cached_input_per_million=Decimal("0.10"),
            output_per_million=Decimal("2.00"),
        )
    }


def make_usage(**overrides):
    data = {
        "prompt_tokens": 1200,
        "output_tokens": 300,
        "total_tokens": 1750,
        "thinking_tokens": 250,
        "cached_input_tokens": 100,
    }
    data.update(overrides)
    return GeminiUsage(**data)


def test_estimates_complete_usage(pricing_table):
    result = estimate_gemini_usage_cost(
        usage=make_usage(),
        model="model-a",
        pricing_table=pricing_table,
    )

    assert result == Decimal("0.00166")


def test_missing_usage_returns_none(pricing_table):
    assert estimate_gemini_usage_cost(
        usage=None,
        model="model-a",
        pricing_table=pricing_table,
    ) is None


def test_unknown_model_returns_none(pricing_table):
    assert estimate_gemini_usage_cost(
        usage=make_usage(),
        model="model-unknown",
        pricing_table=pricing_table,
    ) is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"thinking_tokens": None},
        {"cached_input_tokens": None},
        {"total_tokens": 9999},
        {"cached_input_tokens": 1300},
    ],
)
def test_incomplete_or_inconsistent_usage_returns_none(
    pricing_table,
    overrides,
):
    assert estimate_gemini_usage_cost(
        usage=make_usage(**overrides),
        model="model-a",
        pricing_table=pricing_table,
    ) is None


def test_zero_usage_has_zero_cost(pricing_table):
    assert estimate_gemini_usage_cost(
        usage=GeminiUsage(
            prompt_tokens=0,
            output_tokens=0,
            total_tokens=0,
            thinking_tokens=0,
            cached_input_tokens=0,
        ),
        model="model-a",
        pricing_table=pricing_table,
    ) == Decimal("0")
