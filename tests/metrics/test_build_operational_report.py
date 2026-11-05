import json
from decimal import Decimal

import pytest

from job_hunter.metrics.build_operational_report import (
    build_operational_report,
)
from job_hunter.observability import make_log_event


def test_builds_report_from_mixed_events():
    events = [
        make_log_event(
            event="operation_completed",
            component="ats",
            outcome="success",
            duration_ms=100.0,
        ),
        make_log_event(
            event="gemini_usage_reported",
            component="gemini",
            outcome="success",
            prompt_tokens=1200,
            output_tokens=300,
            total_tokens=1750,
        ),
        make_log_event(
            event="gemini_cost_estimated",
            component="gemini",
            outcome="success",
            model="model-a",
            estimated_cost_usd=Decimal("0.00166"),
        ),
        make_log_event(
            event="operation_completed",
            component="gemini",
            outcome="failure",
            duration_ms=500.0,
        ),
    ]

    report = json.loads(build_operational_report(iter(events)))

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


def test_empty_stream_produces_empty_report():
    report = json.loads(build_operational_report(iter(())))

    assert report["operations_total"] == 0
    assert report["average_duration_ms"] is None
    assert report["gemini_usage_reports"] == 0
    assert report["gemini_cost_estimates"] == 0
    assert Decimal(report["known_estimated_cost_usd"]) == Decimal("0")


def test_malformed_event_raises_instead_of_returning_partial_report():
    events = [
        make_log_event(
            event="operation_completed",
            component="ats",
            outcome="success",
            duration_ms=100.0,
        ),
        make_log_event(
            event="gemini_cost_estimated",
            component="gemini",
            outcome="success",
            model="model-a",
            # Missing estimated_cost_usd
        ),
    ]

    with pytest.raises(ValueError, match="estimated_cost_usd"):
        build_operational_report(events)


def test_accepts_single_pass_event_generator():
    def events():
        yield make_log_event(
            event="operation_completed",
            component="gemini",
            outcome="success",
            duration_ms=125.0,
        )
        yield make_log_event(
            event="gemini_usage_reported",
            component="gemini",
            outcome="success",
            prompt_tokens=100,
            output_tokens=20,
            total_tokens=120,
        )

    report = json.loads(build_operational_report(events()))

    assert report["operations_total"] == 1
    assert report["total_duration_ms"] == 125.0
    assert report["total_tokens"] == 120