from decimal import Decimal

import pytest

from job_hunter.model.TokenPricing import TokenPricing
from job_hunter.cost.resolve_model_pricing import resolve_model_pricing


@pytest.fixture
def pricing_table():
    return {
        "model-a": TokenPricing(
            input_per_million=Decimal("0.50"),
            cached_input_per_million=Decimal("0.10"),
            output_per_million=Decimal("2.00"),
        ),
        "model-b": TokenPricing(
            input_per_million=Decimal("1.00"),
            cached_input_per_million=Decimal("0.25"),
            output_per_million=Decimal("4.00"),
        ),
    }


def test_resolve_known_model(pricing_table):
    result = resolve_model_pricing("model-a", pricing_table)

    assert result == pricing_table["model-a"]


def test_resolve_different_model(pricing_table):
    result = resolve_model_pricing("model-b", pricing_table)

    assert result == pricing_table["model-b"]


def test_unknown_model_has_no_estimate(pricing_table):
    assert resolve_model_pricing("unknown-model", pricing_table) is None


@pytest.mark.parametrize("model", ["", " ", "\t"])
def test_rejects_blank_model_id(model, pricing_table):
    with pytest.raises(ValueError):
        resolve_model_pricing(model, pricing_table)


def test_empty_pricing_table():
    assert resolve_model_pricing("model-a", {}) is None

def test_unknown_gemini_model_returns_none(pricing_table):
    assert (
        resolve_model_pricing(
            "gemini-future-model",
            pricing_table,
        )
        is None
    )