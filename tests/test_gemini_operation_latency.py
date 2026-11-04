import asyncio
import json
import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from job_hunter.agents.requirements_agent import assess_requirements


LOGGER_NAME = "job_hunter.agents.requirements_agent"


def gemini_success_response():
    assessment = {
        "requirements": [],
        "summary": "Insufficient evidence for technical assessment.",
        "confidence": 0.5,
        "technical_fit": "partial",
    }

    return httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"text": json.dumps(assessment)}
                        ]
                    },
                }
            ]
        },
    )


def captured_events(caplog):
    return [
        json.loads(record.message)
        for record in caplog.records
        if record.name == LOGGER_NAME
        and record.message.startswith("{")
    ]


def events_named(events, name):
    return [
        event for event in events
        if event["event"] == name
    ]


# ------------------------------------------------------------
# Test 1: Successful Gemini assessment
# ------------------------------------------------------------

def test_gemini_success_emits_operation_latency(caplog):
    requests = []

    def handler(request):
        requests.append(request)
        return gemini_success_response()

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await assess_requirements(
                {"core_skills": ["python"]},
                "Python backend engineering.",
                api_key="test-secret-key",
                client=client,
            )

    with (
        patch(
            f"{LOGGER_NAME}.perf_counter",
            side_effect=[
                10.000,  # Operation start
                10.000,  # HTTP attempt start
                10.125,  # HTTP attempt end: 125 ms
                10.150,  # Operation end: 25 ms processing
            ],
        ) as mock_clock,
        caplog.at_level(logging.INFO, logger=LOGGER_NAME),
    ):
        result = asyncio.run(scenario())

    events = captured_events(caplog)
    attempt_events = events_named(events, "http_attempt_completed")
    operation_events = events_named(events, "operation_completed")

    assert result.confidence == pytest.approx(0.5)
    assert len(requests) == 1
    assert mock_clock.call_count == 4

    assert len(attempt_events) == 1
    assert attempt_events[0]["outcome"] == "success"
    assert attempt_events[0]["status_code"] == 200
    assert attempt_events[0]["duration_ms"] == pytest.approx(125.0)

    assert len(operation_events) == 1

    assert operation_events[0] == {
        "event": "operation_completed",
        "component": "gemini",
        "outcome": "success",
        "level": logging.INFO,
        "duration_ms": pytest.approx(150.0),
    }

    assert events_named(events, "http_retry_scheduled") == []
    assert events_named(events, "http_request_failed") == []

    assert "test-secret-key" not in caplog.text


# ------------------------------------------------------------
# Test 2: HTTP 503 -> 200 recovery
# ------------------------------------------------------------

def test_gemini_retry_recovery_emits_operation_latency(caplog):
    requests = []

    def handler(request):
        requests.append(request)

        if len(requests) == 1:
            return httpx.Response(
                503,
                json={"error": "secret-response-content"},
            )

        return gemini_success_response()

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await assess_requirements(
                {"core_skills": ["private-candidate-skill"]},
                "Private employer job description.",
                api_key="test-secret-key",
                client=client,
            )

    with (
        patch(
            f"{LOGGER_NAME}.perf_counter",
            side_effect=[
                10.000,  # Operation start
                10.000,  # Attempt 1 start
                10.125,  # Attempt 1 end: 125 ms
                11.125,  # Attempt 2 start after 1-second backoff
                11.375,  # Attempt 2 end: 250 ms
                11.400,  # Operation end: 25 ms processing
            ],
        ) as mock_clock,
        patch(
            f"{LOGGER_NAME}.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        caplog.at_level(logging.INFO, logger=LOGGER_NAME),
    ):
        result = asyncio.run(scenario())

    events = captured_events(caplog)
    attempt_events = events_named(events, "http_attempt_completed")
    retry_events = events_named(events, "http_retry_scheduled")
    failure_events = events_named(events, "http_request_failed")
    operation_events = events_named(events, "operation_completed")

    assert result.confidence == pytest.approx(0.5)
    assert len(requests) == 2
    assert mock_clock.call_count == 6
    mock_sleep.assert_awaited_once_with(1.0)

    assert len(attempt_events) == 2

    assert attempt_events[0]["outcome"] == "failure"
    assert attempt_events[0]["status_code"] == 503
    assert attempt_events[0]["duration_ms"] == pytest.approx(125.0)

    assert attempt_events[1]["outcome"] == "success"
    assert attempt_events[1]["status_code"] == 200
    assert attempt_events[1]["duration_ms"] == pytest.approx(250.0)

    assert len(retry_events) == 1
    assert retry_events[0]["attempt"] == 1

    # Overall assessment recovered successfully.
    assert failure_events == []

    assert len(operation_events) == 1
    assert operation_events[0] == {
        "event": "operation_completed",
        "component": "gemini",
        "outcome": "success",
        "level": logging.INFO,
        "duration_ms": pytest.approx(1400.0),
    }

    for secret in (
        "test-secret-key",
        "private-candidate-skill",
        "Private employer job description.",
        "secret-response-content",
        str(requests[0].url),
    ):
        assert secret not in caplog.text


# ------------------------------------------------------------
# Test 3: ReadTimeout without retry
# ------------------------------------------------------------

def test_gemini_read_timeout_emits_failed_operation_latency(caplog):
    requests = []

    def handler(request):
        requests.append(request)

        raise httpx.ReadTimeout(
            "secret-timeout-message",
            request=request,
        )

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with pytest.raises(httpx.ReadTimeout) as exc_info:
                await assess_requirements(
                    {"core_skills": ["private-candidate-skill"]},
                    "Private employer job description.",
                    api_key="test-secret-key",
                    client=client,
                )

            assert exc_info.value.request is requests[0]

    with (
        patch(
            f"{LOGGER_NAME}.perf_counter",
            side_effect=[
                10.000,  # Operation start
                10.000,  # HTTP attempt start
                10.125,  # HTTP attempt end
                10.150,  # Operation end
            ],
        ) as mock_clock,
        patch(
            f"{LOGGER_NAME}.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        caplog.at_level(logging.INFO, logger=LOGGER_NAME),
    ):
        asyncio.run(scenario())

    events = captured_events(caplog)
    attempt_events = events_named(events, "http_attempt_completed")
    retry_events = events_named(events, "http_retry_scheduled")
    failure_events = events_named(events, "http_request_failed")
    operation_events = events_named(events, "operation_completed")

    assert len(requests) == 1
    assert mock_clock.call_count == 4
    mock_sleep.assert_not_awaited()

    assert len(attempt_events) == 1
    assert attempt_events[0]["outcome"] == "failure"
    assert attempt_events[0]["duration_ms"] == pytest.approx(125.0)
    assert "status_code" not in attempt_events[0]

    assert retry_events == []

    assert len(failure_events) == 1
    assert failure_events[0]["attempt"] == 1
    assert failure_events[0]["level"] == logging.ERROR

    assert len(operation_events) == 1
    assert operation_events[0] == {
        "event": "operation_completed",
        "component": "gemini",
        "outcome": "failure",
        "level": logging.ERROR,
        "duration_ms": pytest.approx(150.0),
    }

    for secret in (
        "test-secret-key",
        "private-candidate-skill",
        "Private employer job description.",
        "secret-timeout-message",
        str(requests[0].url),
    ):
        assert secret not in caplog.text
