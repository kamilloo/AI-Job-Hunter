
from decimal import Decimal

import pytest
from pydantic import ValidationError

from job_hunter.model.OperationalSummary import OperationalSummary


def empty_summary() -> OperationalSummary:
    return OperationalSummary(
        operations_total=0,
        operations_succeeded=0,
        operations_failed=0,
        total_duration_ms=0.0,
        average_duration_ms=None,
        gemini_usage_reports=0,
        prompt_tokens=0,
        output_tokens=0,
        total_tokens=0,
        gemini_cost_estimates=0,
        known_estimated_cost_usd=Decimal("0"),
    )


def test_empty_summary_is_valid():
    summary = empty_summary()

    assert summary.operations_total == 0
    assert summary.average_duration_ms is None
    assert summary.known_estimated_cost_usd == Decimal("0")


def test_summary_serializes_decimal_cost_as_string():
    summary = empty_summary().model_copy(
        update={
            "gemini_cost_estimates": 1,
            "known_estimated_cost_usd": Decimal("0.00166"),
        }
    )

    serialized = summary.model_dump(mode="json")

    assert serialized["known_estimated_cost_usd"] == "0.00166"


@pytest.mark.parametrize(
    "field,value",
    [
        ("operations_total", -1),
        ("gemini_usage_reports", -1),
        ("prompt_tokens", -1),
        ("gemini_cost_estimates", -1),
        ("total_duration_ms", float("nan")),
        ("total_duration_ms", float("inf")),
        ("known_estimated_cost_usd", Decimal("-0.01")),
        ("known_estimated_cost_usd", Decimal("NaN")),
    ],
)
def test_summary_rejects_invalid_metrics(field, value):
    values = empty_summary().model_dump()
    values[field] = value

    with pytest.raises(ValidationError):
        OperationalSummary(**values)
