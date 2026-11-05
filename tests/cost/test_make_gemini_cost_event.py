
from decimal import Decimal

from job_hunter.cost.make_gemini_cost_event import (
    make_gemini_cost_event,
)
from job_hunter.model.GeminiUsage import GeminiUsage
from job_hunter.model.TokenPricing import TokenPricing


PRICING = {
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


def test_creates_cost_event():
    event = make_gemini_cost_event(
        usage=make_usage(),
        model="model-a",
        pricing_table=PRICING,
    )

    assert event is not None
    assert event.event == "gemini_cost_estimated"
    assert event.component == "gemini"
    assert event.outcome == "success"
    assert event.model == "model-a"
    assert event.estimated_cost_usd == Decimal("0.00166")


def test_unknown_model_omits_cost_event():
    assert make_gemini_cost_event(
        usage=make_usage(),
        model="unknown-model",
        pricing_table=PRICING,
    ) is None


def test_incomplete_usage_omits_cost_event():
    assert make_gemini_cost_event(
        usage=make_usage(thinking_tokens=None),
        model="model-a",
        pricing_table=PRICING,
    ) is None


def test_missing_usage_omits_cost_event():
    assert make_gemini_cost_event(
        usage=None,
        model="model-a",
        pricing_table=PRICING,
    ) is None

def test_zero_usage_emits_zero_cost_event():
    usage = GeminiUsage(
        prompt_tokens=0,
        output_tokens=0,
        total_tokens=0,
        thinking_tokens=0,
        cached_input_tokens=0,
    )

    event = make_gemini_cost_event(
        usage=usage,
        model="model-a",
        pricing_table=PRICING,
    )

    assert event is not None
    assert event.estimated_cost_usd == Decimal("0")

def test_inconsistent_usage_omits_cost_event():
    event = make_gemini_cost_event(
        usage=make_usage(total_tokens=9999),
        model="model-a",
        pricing_table=PRICING,
    )

    assert event is None