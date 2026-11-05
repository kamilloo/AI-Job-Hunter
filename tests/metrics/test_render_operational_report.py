import json
from decimal import Decimal

from job_hunter.metrics.render_operational_report import (
    render_operational_report,
)
from job_hunter.model.OperationalSummary import OperationalSummary


def make_summary(**overrides):
    values = {
        "operations_total": 2,
        "operations_succeeded": 1,
        "operations_failed": 1,
        "total_duration_ms": 600.0,
        "average_duration_ms": 300.0,
        "gemini_usage_reports": 1,
        "prompt_tokens": 1200,
        "output_tokens": 300,
        "total_tokens": 1750,
        "gemini_cost_estimates": 1,
        "known_estimated_cost_usd": Decimal("0.00166"),
    }
    values.update(overrides)
    return OperationalSummary(**values)


def test_renders_complete_json_report():
    result = render_operational_report(make_summary())

    assert json.loads(result) == {
        "operations_total": 2,
        "operations_succeeded": 1,
        "operations_failed": 1,
        "total_duration_ms": 600.0,
        "average_duration_ms": 300.0,
        "gemini_usage_reports": 1,
        "prompt_tokens": 1200,
        "output_tokens": 300,
        "total_tokens": 1750,
        "gemini_cost_estimates": 1,
        "known_estimated_cost_usd": "0.00166",
    }


def test_preserves_decimal_precision():
    expected = Decimal("0.000000000123456789")

    summary = make_summary(
        known_estimated_cost_usd=expected
    )

    result = json.loads(render_operational_report(summary))

    assert isinstance(result["known_estimated_cost_usd"], str)
    assert Decimal(result["known_estimated_cost_usd"]) == expected


def test_zero_metrics_remain_visible():
    summary = make_summary(
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

    result = json.loads(render_operational_report(summary))

    assert result["operations_total"] == 0
    assert result["average_duration_ms"] is None
    assert result["gemini_cost_estimates"] == 0
    assert result["known_estimated_cost_usd"] == "0"


def test_output_is_deterministic():
    summary = make_summary()

    assert render_operational_report(
        summary
    ) == render_operational_report(summary)
