from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
import json
import logging
from unittest.mock import Mock

from job_hunter.observability import emit_log, make_log_event
from job_hunter.model.Log import Log


def test_make_log_event_success():
    result = make_log_event(
        "ats_collection_completed",
        component="ats",
        outcome="success",
    )

    assert result.model_dump(exclude_none=True) == {
        "event": "ats_collection_completed",
        "component": "ats",
        "outcome": "success",
        "level": logging.INFO
    }


def test_log_event_retry():
    event = make_log_event(
        "http_retry_scheduled",
        component="gemini",
        outcome="retry",
        attempt=1,
        status_code=503,
    )

    assert event.model_dump(
        mode="json",
        exclude_none=True,
    ) == {
        "event": "http_retry_scheduled",
        "component": "gemini",
        "outcome": "retry",
        "attempt": 1,
        "status_code": 503,
        "level": logging.INFO,
    }

def test_log_event_omits_optional_fields():
    event = make_log_event(
        "ats_collection_completed",
        component="ats",
        outcome="success",
    )

    data = event.model_dump(
        mode="json",
        exclude_none=True,
    )

    assert "attempt" not in data
    assert "status_code" not in data
    assert data["level"] == logging.INFO


def test_log_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        Log(
            event="http_retry_scheduled",
            component="gemini",
            outcome="retry",
            api_key="secret-value",
        )


def test_emit_log_serializes_event_as_json():
    logger = Mock(spec=logging.Logger)

    event = make_log_event(
        "ats_collection_completed",
        component="ats",
        outcome="success",
    )

    emit_log(logger, event)

    logger.log.assert_called_once()

    level, message = logger.log.call_args.args

    assert level == logging.INFO
    assert json.loads(message) == {
        "event": "ats_collection_completed",
        "component": "ats",
        "outcome": "success",
        "level": logging.INFO,
    }

def test_emit_log_uses_warning_level():
    logger = Mock(spec=logging.Logger)

    event = Log(
        event="http_retry_scheduled",
        component="ats",
        outcome="retry",
        attempt=1,
        status_code=503,
        level=logging.WARNING,
    )

    emit_log(logger, event)

    level, message = logger.log.call_args.args

    assert level == logging.WARNING
    assert json.loads(message)["attempt"] == 1
    assert json.loads(message)["status_code"] == 503



def test_cost_event_preserves_decimal_precision():
    event = make_log_event(
        event="gemini_cost_estimated",
        component="gemini",
        outcome="success",
        model="model-a",
        estimated_cost_usd=Decimal("0.00166"),
        level=logging.INFO,
    )

    data = json.loads(
        event.model_dump_json(exclude_none=True)
    )

    assert data == {
        "event": "gemini_cost_estimated",
        "component": "gemini",
        "outcome": "success",
        "model": "model-a",
        "estimated_cost_usd": "0.00166",
        "level": logging.INFO,
    }


def test_cost_event_accepts_zero():
    event = make_log_event(
        event="gemini_cost_estimated",
        component="gemini",
        outcome="success",
        model="model-a",
        estimated_cost_usd=Decimal("0"),
    )

    data = json.loads(event.model_dump_json(exclude_none=True))

    assert data["estimated_cost_usd"] == "0"


@pytest.mark.parametrize(
    "invalid_cost",
    [
        Decimal("-0.01"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_cost_event_rejects_invalid_estimates(invalid_cost):
    with pytest.raises(ValidationError):
        make_log_event(
            event="gemini_cost_estimated",
            component="gemini",
            outcome="success",
            model="model-a",
            estimated_cost_usd=invalid_cost,
        )


def test_existing_events_omit_cost_fields():
    event = make_log_event(
        event="http_retry_scheduled",
        component="gemini",
        outcome="retry",
        attempt=1,
        status_code=503,
        level=logging.WARNING,
    )

    data = json.loads(event.model_dump_json(exclude_none=True))

    assert "model" not in data
    assert "estimated_cost_usd" not in data

def test_log_accepts_operation_id():
    operation_id = str(uuid4())

    event = make_log_event(
        event="operation_completed",
        component="gemini",
        outcome="success",
        duration_ms=100.0,
        operation_id=operation_id,
    )

    assert event.operation_id == operation_id
    assert (
        event.model_dump(mode="json")["operation_id"]
        == operation_id
    )


def test_existing_logs_omit_operation_id():
    event = make_log_event(
        event="operation_completed",
        component="ats",
        outcome="success",
        duration_ms=100.0,
    )

    assert "operation_id" not in event.model_dump(
        exclude_none=True
    )


def test_empty_operation_id_is_rejected():
    with pytest.raises(ValidationError):
        make_log_event(
            event="operation_completed",
            component="gemini",
            outcome="success",
            duration_ms=100.0,
            operation_id="",
        )