import json
from decimal import Decimal

import pytest

from job_hunter.metrics.parse_log_lines import parse_log_lines
from job_hunter.observability import make_log_event


def to_json_line(**kwargs):
    return make_log_event(
        **kwargs
    ).model_dump_json(exclude_none=True)


def test_parses_valid_operation_event():
    line = to_json_line(
        event="operation_completed",
        component="gemini",
        outcome="success",
        duration_ms=125.0,
    )

    events = list(parse_log_lines([line]))

    assert len(events) == 1
    assert events[0].event == "operation_completed"
    assert events[0].component == "gemini"
    assert events[0].duration_ms == 125.0


def test_parses_cost_event_preserving_decimal_precision():
    cost = Decimal("0.000000000123456789")

    line = to_json_line(
        event="gemini_cost_estimated",
        component="gemini",
        outcome="success",
        model="model-a",
        estimated_cost_usd=cost,
    )

    events = list(parse_log_lines([line]))

    assert len(events) == 1
    assert events[0].estimated_cost_usd == cost


def test_skips_blank_lines():
    line = to_json_line(
        event="operation_completed",
        component="ats",
        outcome="success",
        duration_ms=100.0,
    )

    events = list(
        parse_log_lines([
            "",
            "  ",
            "\t",
            line,
            "\n",
        ])
    )

    assert len(events) == 1
    assert events[0].event == "operation_completed"


@pytest.mark.parametrize(
    "invalid_line",
    [
        "{invalid json",
        "[]",
        '"not an object"',
        "42",
        "null",
        '{"event":"operation_completed"}',
        '{"event":"operation_completed","unknown_field":123}',
    ],
)
def test_invalid_records_raise_with_line_number(invalid_line):
    lines = [
        "",
        to_json_line(
            event="operation_completed",
            component="ats",
            outcome="success",
            duration_ms=100.0,
        ),
        invalid_line,
    ]

    with pytest.raises(ValueError, match=r"line 3"):
        list(parse_log_lines(lines))


def test_empty_input_returns_no_events():
    assert list(parse_log_lines([])) == []


def test_accepts_generator_input():
    def lines():
        yield to_json_line(
            event="operation_completed",
            component="ats",
            outcome="success",
            duration_ms=100.0,
        )
        yield to_json_line(
            event="gemini_cost_estimated",
            component="gemini",
            outcome="success",
            model="model-a",
            estimated_cost_usd=Decimal("0.00166"),
        )

    events = list(parse_log_lines(lines()))

    assert len(events) == 2
    assert events[0].event == "operation_completed"
    assert events[1].event == "gemini_cost_estimated"
