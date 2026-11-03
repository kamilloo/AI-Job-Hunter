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
