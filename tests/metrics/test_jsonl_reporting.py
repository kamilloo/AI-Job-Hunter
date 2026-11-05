import json
from decimal import Decimal

import pytest

from job_hunter.metrics.build_operational_report import (
    build_operational_report,
)
from job_hunter.metrics.parse_log_lines import parse_log_lines
from job_hunter.observability import make_log_event


def json_line(**kwargs):
    return make_log_event(
        **kwargs
    ).model_dump_json(exclude_none=True)


def test_jsonl_reporting_end_to_end():
    lines = [
        json_line(
            event="operation_completed",
            component="ats",
            outcome="success",
            duration_ms=100.0,
        ),
        json_line(
            event="gemini_usage_reported",
            component="gemini",
            outcome="success",
            prompt_tokens=1200,
            output_tokens=300,
            total_tokens=1750,
        ),
        json_line(
            event="gemini_cost_estimated",
            component="gemini",
            outcome="success",
            model="model-a",
            estimated_cost_usd=Decimal("0.00166"),
        ),
        json_line(
            event="operation_completed",
            component="gemini",
            outcome="failure",
            duration_ms=500.0,
        ),
    ]

    report = json.loads(
        build_operational_report(parse_log_lines(iter(lines)))
    )

    assert report["operations_total"] == 2
    assert report["operations_succeeded"] == 1
    assert report["operations_failed"] == 1
    assert report["total_duration_ms"] == 600.0
    assert report["average_duration_ms"] == 300.0

    assert report["gemini_usage_reports"] == 1
    assert report["prompt_tokens"] == 1200
    assert report["output_tokens"] == 300
    assert report["total_tokens"] == 1750

    assert report["gemini_cost_estimates"] == 1
    assert Decimal(report["known_estimated_cost_usd"]) == Decimal("0.00166")


def test_jsonl_reporting_rejects_invalid_record_midstream():
    lines = [
        json_line(
            event="operation_completed",
            component="ats",
            outcome="success",
            duration_ms=100.0,
        ),
        "{invalid json",
        json_line(
            event="operation_completed",
            component="gemini",
            outcome="success",
            duration_ms=200.0,
        ),
    ]

    with pytest.raises(ValueError, match=r"line 2"):
        build_operational_report(parse_log_lines(lines))


def test_jsonl_reporting_preserves_small_decimal_cost():
    expected_cost = Decimal("0.000000000123456789")

    lines = [
        json_line(
            event="gemini_cost_estimated",
            component="gemini",
            outcome="success",
            model="model-a",
            estimated_cost_usd=expected_cost,
        ),
    ]

    report = json.loads(
        build_operational_report(parse_log_lines(lines))
    )

    assert report["gemini_cost_estimates"] == 1
    assert Decimal(report["known_estimated_cost_usd"]) == expected_cost
