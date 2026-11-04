import asyncio
import json
import logging
from unittest.mock import AsyncMock, call, patch

import httpx
import pytest
from pydantic import ValidationError

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
            ],
            "usageMetadata": {
                "promptTokenCount": 1200,
                "candidatesTokenCount": 300,
                "totalTokenCount": 1750
            },
        }
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


def test_gemini_success_emits_usage(caplog):
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
        caplog.at_level(logging.INFO, logger="job_hunter.agents.requirements_agent"),
    ):
        result = asyncio.run(scenario())

    events = gemini_events(caplog)
    usage_events = events_named(events, "gemini_usage_reported")

    assert result.summary == (
        "Insufficient evidence for technical assessment."
    )
    assert len(requests) == 1

    assert usage_events == [
        {
            "event": "gemini_usage_reported",
            "component": "gemini",
            "outcome": "success",
            "prompt_tokens": 1200,
            "output_tokens": 300,
            "total_tokens": 1750,
            "level": logging.INFO,
        }
    ]

    assert events_named(events, "http_retry_scheduled") == []
    assert events_named(events, "http_request_failed") == []
    for secret in (
            "test-secret-key",
            "python",
            "Private employer job description.",
            "secret-timeout-message",
            str(requests[0].url),
    ):
        assert secret not in caplog.text


def test_gemini_missing_usage_metadata(caplog):
    def handler(request):
        response = gemini_success_response()
        payload = response.json()
        payload.pop("usageMetadata")

        return httpx.Response(200, json=payload)

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

    with caplog.at_level(
        logging.INFO,
        logger="job_hunter.agents.requirements_agent",
    ):
        result = asyncio.run(scenario())

    events = gemini_events(caplog)

    assert result.confidence == pytest.approx(0.5)
    assert events_named(events, "gemini_usage_reported") == []
    assert events_named(events, "http_retry_scheduled") == []
    assert events_named(events, "http_request_failed") == []


@pytest.mark.parametrize(
    "invalid_metadata",
    [
        {
            "promptTokenCount": "1200",
            "candidatesTokenCount": 300,
            "totalTokenCount": 1500,
        },
        {
            "promptTokenCount": True,
            "candidatesTokenCount": 300,
            "totalTokenCount": 1500,
        },
        {
            "promptTokenCount": -1,
            "candidatesTokenCount": 300,
            "totalTokenCount": 1500,
        },
        {
            "promptTokenCount": 1200,
            "candidatesTokenCount": 300,
            # totalTokenCount missing
        },
    ],
)
def test_gemini_invalid_usage_does_not_break_assessment(
    caplog,
    invalid_metadata,
):
    def handler(request):
        payload = gemini_success_response().json()
        payload["usageMetadata"] = invalid_metadata

        return httpx.Response(200, json=payload)

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

    with caplog.at_level(
        logging.INFO,
        logger="job_hunter.agents.requirements_agent",
    ):
        result = asyncio.run(scenario())

    events = gemini_events(caplog)

    assert result.confidence == pytest.approx(0.5)
    assert events_named(events, "gemini_usage_reported") == []
    assert events_named(events, "http_retry_scheduled") == []
    assert events_named(events, "http_request_failed") == []


def test_gemini_invalid_assessment_still_emits_usage(caplog):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps({
                                        "requirements": [],
                                        "summary": "Invalid assessment",
                                        "confidence": 2.0,
                                        "technical_fit": "partial",
                                    })
                                }
                            ]
                        },
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 1200,
                    "candidatesTokenCount": 300,
                    "totalTokenCount": 1750,
                },
            },
        )

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with pytest.raises(ValidationError):
                await assess_requirements(
                    {"core_skills": ["python"]},
                    "Python backend engineering.",
                    api_key="test-secret-key",
                    client=client,
                )

    with caplog.at_level(
        logging.INFO,
        logger="job_hunter.agents.requirements_agent",
    ):
        asyncio.run(scenario())

    events = gemini_events(caplog)
    usage_events = events_named(events, "gemini_usage_reported")
    operation_events = events_named(events, "operation_completed")

    assert usage_events == [
        {
            "event": "gemini_usage_reported",
            "component": "gemini",
            "outcome": "success",
            "prompt_tokens": 1200,
            "output_tokens": 300,
            "total_tokens": 1750,
            "level": logging.INFO,
        }
    ]

    # The complete assessment failed validation.
    assert len(operation_events) == 1
    assert operation_events[0]["outcome"] == "failure"

    # The HTTP request itself did not fail.
    assert events_named(events, "http_request_failed") == []



