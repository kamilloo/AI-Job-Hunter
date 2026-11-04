import asyncio
import json
import logging
from unittest.mock import AsyncMock, call, patch

import httpx
import pytest

from job_hunter.agents.requirements_agent import assess_requirements


def gemini_success_response():
    """Minimal valid Gemini response for TechnicalAssessment."""
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


def gemini_events(caplog):
    """Read structured events from the Gemini logger."""
    return [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.agents.requirements_agent"
        and record.message.startswith("{")
    ]


def events_named(events, name):
    return [
        event for event in events
        if event["event"] == name
    ]


def test_gemini_success_emits_attempt_latency(caplog):
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
            "job_hunter.agents.requirements_agent.perf_counter",
            side_effect=[10.0, 10.125],
        ) as mock_clock,
        caplog.at_level(logging.INFO, logger="job_hunter.agents.requirements_agent"),
    ):
        result = asyncio.run(scenario())

    events = gemini_events(caplog)
    latency_events = events_named(events, "http_attempt_completed")

    assert result.summary == (
        "Insufficient evidence for technical assessment."
    )
    assert len(requests) == 1
    assert mock_clock.call_count == 2

    assert latency_events == [
        {
            "event": "http_attempt_completed",
            "component": "gemini",
            "outcome": "success",
            "attempt": 1,
            "status_code": 200,
            "level": logging.INFO,
            "duration_ms": pytest.approx(125.0),
        }
    ]

    assert events_named(events, "http_retry_scheduled") == []
    assert events_named(events, "http_request_failed") == []
    assert "test-secret-key" not in caplog.text


def test_gemini_http_503_recovery_emits_attempt_latency(caplog):
    requests = []

    def handler(request):
        requests.append(request)

        if len(requests) == 1:
            return httpx.Response(
                503,
                json={"error": "secret-error-response"},
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
            "job_hunter.agents.requirements_agent.perf_counter",
            side_effect=[
                10.0, 10.125,  # Attempt 1: 125 ms
                20.0, 20.250,  # Attempt 2: 250 ms
            ],
        ) as mock_clock,
        patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        caplog.at_level(logging.INFO, logger="job_hunter.agents.requirements_agent"),
    ):
        result = asyncio.run(scenario())

    events = gemini_events(caplog)
    latency_events = events_named(events, "http_attempt_completed")
    retries = events_named(events, "http_retry_scheduled")
    failures = events_named(events, "http_request_failed")

    assert result.confidence == pytest.approx(0.5)
    assert len(requests) == 2
    assert mock_clock.call_count == 4
    mock_sleep.assert_awaited_once_with(1.0)

    assert len(latency_events) == 2

    first, second = latency_events

    assert first == {
        "event": "http_attempt_completed",
        "component": "gemini",
        "outcome": "failure",
        "attempt": 1,
        "status_code": 503,
        "level": logging.WARNING,
        "duration_ms": pytest.approx(125.0),
    }

    assert second == {
        "event": "http_attempt_completed",
        "component": "gemini",
        "outcome": "success",
        "attempt": 2,
        "status_code": 200,
        "level": logging.INFO,
        "duration_ms": pytest.approx(250.0),
    }

    assert retries == [
        {
            "event": "http_retry_scheduled",
            "component": "gemini",
            "outcome": "retry",
            "attempt": 1,
            "status_code": 503,
            "level": logging.WARNING,
        }
    ]

    # The overall request recovered successfully.
    assert failures == []

    for secret in (
        "test-secret-key",
        "private-candidate-skill",
        "Private employer job description.",
        "secret-error-response",
        str(requests[0].url),
    ):
        assert secret not in caplog.text


def test_gemini_read_timeout_emits_attempt_latency(caplog):
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
            "job_hunter.agents.requirements_agent.perf_counter",
            side_effect=[10.0, 10.125],
        ) as mock_clock,
        patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        caplog.at_level(logging.INFO, logger="job_hunter.agents.requirements_agent"),
    ):
        asyncio.run(scenario())

    events = gemini_events(caplog)
    latency_events = events_named(events, "http_attempt_completed")
    retries = events_named(events, "http_retry_scheduled")
    failures = events_named(events, "http_request_failed")

    assert len(requests) == 1
    assert mock_clock.call_count == 2
    mock_sleep.assert_not_awaited()

    assert len(latency_events) == 1
    assert latency_events[0] == {
        "event": "http_attempt_completed",
        "component": "gemini",
        "outcome": "failure",
        "attempt": 1,
        "level": logging.WARNING,
        "duration_ms": pytest.approx(125.0),
    }

    # ReadTimeout is unsafe to retry for Gemini.
    assert retries == []

    assert failures == [
        {
            "event": "http_request_failed",
            "component": "gemini",
            "outcome": "failure",
            "attempt": 1,
            "level": logging.ERROR,
        }
    ]

    # No HTTP response means no status_code.
    assert "status_code" not in latency_events[0]

    for secret in (
        "test-secret-key",
        "private-candidate-skill",
        "Private employer job description.",
        "secret-timeout-message",
        str(requests[0].url),
    ):
        assert secret not in caplog.text
