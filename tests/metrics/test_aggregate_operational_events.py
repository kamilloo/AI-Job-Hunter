
import logging
from decimal import Decimal

import pytest

from job_hunter.metrics.aggregate_operational_events import aggregate_operational_events
from job_hunter.observability import make_log_event


def test_empty_events_return_empty_summary():
    result = aggregate_operational_events([])

    assert result.operations_total == 0
    assert result.operations_succeeded == 0
    assert result.operations_failed == 0
    assert result.total_duration_ms == 0.0
    assert result.average_duration_ms is None
    assert result.gemini_usage_reports == 0
    assert result.gemini_cost_estimates == 0
    assert result.known_estimated_cost_usd == Decimal("0")


def test_aggregates_successful_and_failed_operations():
    events = [
        make_log_event(
            event="operation_completed",
            component="ats",
            outcome="success",
            duration_ms=100.0,
            level=logging.INFO,
        ),
        make_log_event(
            event="operation_completed",
            component="gemini",
            outcome="success",
            duration_ms=300.0,
            level=logging.INFO,
        ),
        make_log_event(
            event="operation_completed",
            component="gemini",
            outcome="failure",
            duration_ms=500.0,
            level=logging.ERROR,
        ),
    ]

    result = aggregate_operational_events(events)

    assert result.operations_total == 3
    assert result.operations_succeeded == 2
    assert result.operations_failed == 1
    assert result.total_duration_ms == 900.0
    assert result.average_duration_ms == pytest.approx(300.0)


def test_http_attempts_and_retries_do_not_affect_operation_latency():
    events = [
        make_log_event(
            event="http_attempt_completed",
            component="gemini",
            outcome="failure",
            attempt=1,
            status_code=503,
            duration_ms=50.0,
            level=logging.WARNING,
        ),
        make_log_event(
            event="http_retry_scheduled",
            component="gemini",
            outcome="retry",
            attempt=1,
            status_code=503,
            level=logging.WARNING,
        ),
        make_log_event(
            event="http_attempt_completed",
            component="gemini",
            outcome="success",
            attempt=2,
            status_code=200,
            duration_ms=100.0,
            level=logging.INFO,
        ),
        make_log_event(
            event="operation_completed",
            component="gemini",
            outcome="success",
            duration_ms=1150.0,
            level=logging.INFO,
        ),
    ]

    result = aggregate_operational_events(events)

    assert result.operations_total == 1
    assert result.operations_succeeded == 1
    assert result.operations_failed == 0
    assert result.total_duration_ms == 1150.0
    assert result.average_duration_ms == 1150.0


def test_unrelated_events_are_ignored():
    events = [
        make_log_event(
            event="discovery_completed",
            component="discovery",
            outcome="partial",
            level=logging.WARNING,
        ),
        make_log_event(
            event="http_request_failed",
            component="ats",
            outcome="failure",
            level=logging.ERROR,
        ),
    ]

    result = aggregate_operational_events(events)

    assert result.operations_total == 0
    assert result.average_duration_ms is None


def test_accepts_single_pass_generator():
    events = (
        make_log_event(
            event="operation_completed",
            component="ats",
            outcome="success",
            duration_ms=duration,
        )
        for duration in (100.0, 200.0, 300.0)
    )

    result = aggregate_operational_events(events)

    assert result.operations_total == 3
    assert result.total_duration_ms == 600.0
    assert result.average_duration_ms == 200.0


def test_rejects_operation_without_duration():
    event = make_log_event(
        event="operation_completed",
        component="gemini",
        outcome="success",
    )

    with pytest.raises(ValueError, match="missing duration_ms"):
        aggregate_operational_events([event])

def test_rejects_operation_with_invalid_outcome():
    event = make_log_event(
        event="operation_completed",
        component="gemini",
        outcome="retry",
        duration_ms=100.0,
    )

    with pytest.raises(ValueError, match="invalid outcome"):
        aggregate_operational_events([event])

def test_aggregates_gemini_token_usage():
    events = [
        make_log_event(
            event="gemini_usage_reported",
            component="gemini",
            outcome="success",
            prompt_tokens=1200,
            output_tokens=300,
            total_tokens=1750,
            level=logging.INFO,
        ),
        make_log_event(
            event="gemini_usage_reported",
            component="gemini",
            outcome="success",
            prompt_tokens=500,
            output_tokens=100,
            total_tokens=650,
            level=logging.INFO,
        ),
    ]

    result = aggregate_operational_events(events)

    assert result.gemini_usage_reports == 2
    assert result.prompt_tokens == 1700
    assert result.output_tokens == 400
    assert result.total_tokens == 2400

    assert result.operations_total == 0
    assert result.gemini_cost_estimates == 0
    assert result.known_estimated_cost_usd == Decimal("0")


def test_aggregates_estimated_costs_with_decimal_precision():
    events = [
        make_log_event(
            event="gemini_cost_estimated",
            component="gemini",
            outcome="success",
            model="model-a",
            estimated_cost_usd=Decimal("0.00166"),
        ),
        make_log_event(
            event="gemini_cost_estimated",
            component="gemini",
            outcome="success",
            model="model-a",
            estimated_cost_usd=Decimal("0.00000003"),
        ),
    ]

    result = aggregate_operational_events(events)

    assert result.gemini_cost_estimates == 2
    assert result.known_estimated_cost_usd == Decimal("0.00166003")
    assert result.gemini_usage_reports == 0
    assert result.operations_total == 0


def test_zero_cost_counts_as_observed_estimate():
    events = [
        make_log_event(
            event="gemini_cost_estimated",
            component="gemini",
            outcome="success",
            model="model-a",
            estimated_cost_usd=Decimal("0"),
        ),
    ]

    result = aggregate_operational_events(events)

    assert result.gemini_cost_estimates == 1
    assert result.known_estimated_cost_usd == Decimal("0")


def test_mixed_events_are_aggregated_without_double_counting():
    events = [
        make_log_event(
            event="http_attempt_completed",
            component="gemini",
            outcome="failure",
            duration_ms=50.0,
            attempt=1,
            status_code=503,
        ),
        make_log_event(
            event="http_retry_scheduled",
            component="gemini",
            outcome="retry",
            attempt=1,
            status_code=503,
        ),
        make_log_event(
            event="http_attempt_completed",
            component="gemini",
            outcome="success",
            duration_ms=100.0,
            attempt=2,
            status_code=200,
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
            outcome="success",
            duration_ms=1150.0,
        ),
        make_log_event(
            event="operation_completed",
            component="ats",
            outcome="failure",
            duration_ms=200.0,
        ),
    ]

    result = aggregate_operational_events(events)

    assert result.operations_total == 2
    assert result.operations_succeeded == 1
    assert result.operations_failed == 1
    assert result.total_duration_ms == 1350.0
    assert result.average_duration_ms == pytest.approx(675.0)

    assert result.gemini_usage_reports == 1
    assert result.prompt_tokens == 1200
    assert result.output_tokens == 300
    assert result.total_tokens == 1750

    assert result.gemini_cost_estimates == 1
    assert result.known_estimated_cost_usd == Decimal("0.00166")


@pytest.mark.parametrize(
    "missing_field",
    [
        "prompt_tokens",
        "output_tokens",
        "total_tokens",
    ],
)
def test_rejects_incomplete_usage_event(missing_field):
    fields = {
        "prompt_tokens": 1200,
        "output_tokens": 300,
        "total_tokens": 1750,
    }
    del fields[missing_field]

    event = make_log_event(
        event="gemini_usage_reported",
        component="gemini",
        outcome="success",
        **fields,
    )

    with pytest.raises(ValueError, match=missing_field):
        aggregate_operational_events([event])


def test_rejects_cost_event_without_estimate():
    event = make_log_event(
        event="gemini_cost_estimated",
        component="gemini",
        outcome="success",
        model="model-a",
    )

    with pytest.raises(
        ValueError,
        match="estimated_cost_usd",
    ):
        aggregate_operational_events([event])

def test_failed_assessment_can_still_have_billable_usage():
    events = [
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
            duration_ms=400.0,
        ),
    ]

    result = aggregate_operational_events(events)

    assert result.operations_total == 1
    assert result.operations_failed == 1
    assert result.gemini_usage_reports == 1
    assert result.gemini_cost_estimates == 1
    assert result.known_estimated_cost_usd == Decimal("0.00166")

def test_interleaved_events_have_order_independent_totals():
    events = [
        make_log_event(
            event="gemini_usage_reported",
            component="gemini",
            outcome="success",
            prompt_tokens=1200,
            output_tokens=300,
            total_tokens=1750,
        ),
        make_log_event(
            event="operation_completed",
            component="ats",
            outcome="success",
            duration_ms=150.0,
        ),
        make_log_event(
            event="http_attempt_completed",
            component="gemini",
            outcome="failure",
            duration_ms=50.0,
            attempt=1,
            status_code=503,
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
            duration_ms=450.0,
        ),
        make_log_event(
            event="discovery_completed",
            component="discovery",
            outcome="partial",
        ),
    ]

    forward = aggregate_operational_events(events)
    reversed_order = aggregate_operational_events(reversed(events))

    assert forward == reversed_order

    assert forward.operations_total == 2
    assert forward.operations_succeeded == 1
    assert forward.operations_failed == 1
    assert forward.total_duration_ms == 600.0

    assert forward.gemini_usage_reports == 1
    assert forward.prompt_tokens == 1200
    assert forward.output_tokens == 300
    assert forward.total_tokens == 1750

    assert forward.gemini_cost_estimates == 1
    assert forward.known_estimated_cost_usd == Decimal("0.00166")


def test_mixed_event_generator_is_consumed_once():
    events = [
        make_log_event(
            event="operation_completed",
            component="gemini",
            outcome="success",
            duration_ms=250.0,
        ),
        make_log_event(
            event="gemini_usage_reported",
            component="gemini",
            outcome="success",
            prompt_tokens=500,
            output_tokens=100,
            total_tokens=650,
        ),
        make_log_event(
            event="gemini_cost_estimated",
            component="gemini",
            outcome="success",
            model="model-a",
            estimated_cost_usd=Decimal("0.00042"),
        ),
    ]

    class SinglePassEvents:
        def __init__(self, values):
            self.values = values
            self.iterations = 0

        def __iter__(self):
            self.iterations += 1

            if self.iterations > 1:
                raise AssertionError(
                    "Event stream was iterated more than once"
                )

            yield from self.values

    stream = SinglePassEvents(events)

    summary = aggregate_operational_events(stream)

    assert stream.iterations == 1
    assert summary.operations_total == 1
    assert summary.total_duration_ms == 250.0
    assert summary.gemini_usage_reports == 1
    assert summary.total_tokens == 650
    assert summary.gemini_cost_estimates == 1
    assert summary.known_estimated_cost_usd == Decimal("0.00042")


def test_missing_cost_estimate_does_not_hide_observed_usage():
    events = [
        make_log_event(
            event="gemini_usage_reported",
            component="gemini",
            outcome="success",
            prompt_tokens=1200,
            output_tokens=300,
            total_tokens=1500,
        ),
        make_log_event(
            event="operation_completed",
            component="gemini",
            outcome="success",
            duration_ms=300.0,
        ),
    ]

    summary = aggregate_operational_events(events)

    assert summary.operations_total == 1
    assert summary.gemini_usage_reports == 1
    assert summary.prompt_tokens == 1200
    assert summary.total_tokens == 1500

    assert summary.gemini_cost_estimates == 0
    assert summary.known_estimated_cost_usd == Decimal("0")

    # No estimate was observed. The actual cost is unknown,
    # not necessarily zero.


def test_malformed_event_after_valid_events_raises():
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

    with pytest.raises(
        ValueError,
        match="gemini_cost_estimated missing estimated_cost_usd",
    ):
        aggregate_operational_events(events)

def test_failed_gemini_operation_can_have_known_cost():
    events = [
        make_log_event(
            event="gemini_usage_reported",
            component="gemini",
            outcome="success",
            prompt_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
        ),
        make_log_event(
            event="gemini_cost_estimated",
            component="gemini",
            outcome="success",
            model="model-a",
            estimated_cost_usd=Decimal("0.0009"),
        ),
        make_log_event(
            event="operation_completed",
            component="gemini",
            outcome="failure",
            duration_ms=400.0,
            level=logging.ERROR,
        ),
    ]

    summary = aggregate_operational_events(events)

    assert summary.operations_failed == 1
    assert summary.gemini_usage_reports == 1
    assert summary.gemini_cost_estimates == 1
    assert summary.known_estimated_cost_usd == Decimal("0.0009")