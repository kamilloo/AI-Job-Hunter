import asyncio
import json
import logging
from decimal import Decimal
from unittest.mock import AsyncMock, call, patch

import httpx
import pytest
from pydantic import ValidationError

from job_hunter.agents.requirements_agent import assess_requirements
from job_hunter.model.TokenPricing import TokenPricing


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


LOGGER_NAME = "job_hunter.agents.requirements_agent"


def test_gemini_emits_estimated_cost_with_configured_pricing(caplog):
    requests = []

    def handler(request):
        requests.append(request)

        payload = gemini_success_response().json()
        payload["usageMetadata"] = {
            "promptTokenCount": 1200,
            "candidatesTokenCount": 300,
            "totalTokenCount": 1750,
            "thoughtsTokenCount": 250,
            "cachedContentTokenCount": 100,
        }

        return httpx.Response(200, json=payload)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await assess_requirements(
                {"core_skills": ["private-candidate-skill"]},
                "Private employer job description.",
                model="model-a",
                api_key="test-secret-key",
                client=client,
            )

    test_pricing = {
        "model-a": TokenPricing(
            input_per_million=Decimal("0.50"),
            cached_input_per_million=Decimal("0.10"),
            output_per_million=Decimal("2.00"),
        )
    }

    with (
        patch.dict(
            "job_hunter.cost.pricing_config.GEMINI_PRICING_TABLE",
            test_pricing,
            clear=True,
        ),
        caplog.at_level(logging.INFO, logger=LOGGER_NAME),
    ):
        result = asyncio.run(scenario())

    events = gemini_events(caplog)
    usage_events = events_named(events, "gemini_usage_reported")
    cost_events = events_named(events, "gemini_cost_estimated")
    operation_events = events_named(events, "operation_completed")

    assert result.confidence == pytest.approx(0.5)
    assert len(requests) == 1

    assert len(usage_events) == 1
    assert cost_events == [
        {
            "event": "gemini_cost_estimated",
            "component": "gemini",
            "outcome": "success",
            "model": "model-a",
            "estimated_cost_usd": "0.00166",
            "level": logging.INFO,
        }
    ]

    assert len(operation_events) == 1
    assert operation_events[0]["outcome"] == "success"

    event_names = [event["event"] for event in events]

    assert event_names.index("gemini_usage_reported") < (
        event_names.index("gemini_cost_estimated")
    )
    assert event_names.index("gemini_cost_estimated") < (
        event_names.index("operation_completed")
    )

    for secret in (
        "test-secret-key",
        "private-candidate-skill",
        "Private employer job description.",
        str(requests[0].url),
    ):
        assert secret not in caplog.text


def complete_usage_metadata():
    return {
        "promptTokenCount": 1200,
        "candidatesTokenCount": 300,
        "totalTokenCount": 1750,
        "thoughtsTokenCount": 250,
        "cachedContentTokenCount": 100,
    }


def test_pricing_table():
    return {
        "model-a": TokenPricing(
            input_per_million=Decimal("0.50"),
            cached_input_per_million=Decimal("0.10"),
            output_per_million=Decimal("2.00"),
        )
    }


def test_gemini_unknown_pricing_omits_cost_event(caplog):
    requests = []

    def handler(request):
        requests.append(request)

        payload = gemini_success_response().json()
        payload["usageMetadata"] = complete_usage_metadata()

        return httpx.Response(200, json=payload)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await assess_requirements(
                {"core_skills": ["private-candidate-skill"]},
                "Private employer job description.",
                model="model-unknown",
                api_key="test-secret-key",
                client=client,
            )

    with (
        patch.dict(
            "job_hunter.cost.pricing_config.GEMINI_PRICING_TABLE",
            test_pricing_table(),
            clear=True,
        ),
        caplog.at_level(logging.INFO, logger=LOGGER_NAME),
    ):
        result = asyncio.run(scenario())

    events = gemini_events(caplog)

    assert result.confidence == pytest.approx(0.5)
    assert len(requests) == 1

    assert len(events_named(events, "gemini_usage_reported")) == 1
    assert events_named(events, "gemini_cost_estimated") == []

    operation_events = events_named(events, "operation_completed")
    assert len(operation_events) == 1
    assert operation_events[0]["outcome"] == "success"

    assert events_named(events, "http_retry_scheduled") == []
    assert events_named(events, "http_request_failed") == []


def test_gemini_incomplete_usage_omits_cost_event(caplog):
    requests = []

    def handler(request):
        requests.append(request)

        payload = gemini_success_response().json()

        # Core token counts are present, but thinking
        # and cached-token accounting is incomplete.
        payload["usageMetadata"] = {
            "promptTokenCount": 1200,
            "candidatesTokenCount": 300,
            "totalTokenCount": 1500,
        }

        return httpx.Response(200, json=payload)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await assess_requirements(
                {"core_skills": ["python"]},
                "Python backend engineering.",
                model="model-a",
                api_key="test-secret-key",
                client=client,
            )

    with (
        patch.dict(
            "job_hunter.cost.pricing_config.GEMINI_PRICING_TABLE",
            test_pricing_table(),
            clear=True,
        ),
        caplog.at_level(logging.INFO, logger=LOGGER_NAME),
    ):
        result = asyncio.run(scenario())

    events = gemini_events(caplog)

    assert result.confidence == pytest.approx(0.5)
    assert len(requests) == 1

    usage_events = events_named(events, "gemini_usage_reported")
    cost_events = events_named(events, "gemini_cost_estimated")
    operation_events = events_named(events, "operation_completed")

    assert len(usage_events) == 1
    assert usage_events[0]["prompt_tokens"] == 1200
    assert usage_events[0]["output_tokens"] == 300
    assert usage_events[0]["total_tokens"] == 1500

    # Do not assume missing billing categories equal zero.
    assert cost_events == []

    assert len(operation_events) == 1
    assert operation_events[0]["outcome"] == "success"


def test_gemini_invalid_assessment_still_emits_cost(caplog):
    requests = []

    def handler(request):
        requests.append(request)

        payload = gemini_success_response().json()
        payload["usageMetadata"] = complete_usage_metadata()

        # The HTTP request succeeds, but this assessment
        # violates TechnicalAssessment validation.
        invalid_assessment = {
            "requirements": [],
            "summary": "Invalid assessment",
            "confidence": 2.0,
            "technical_fit": "partial",
        }

        payload["candidates"][0]["content"]["parts"] = [
            {"text": json.dumps(invalid_assessment)}
        ]

        return httpx.Response(200, json=payload)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with pytest.raises(ValidationError):
                await assess_requirements(
                    {"core_skills": ["private-candidate-skill"]},
                    "Private employer job description.",
                    model="model-a",
                    api_key="test-secret-key",
                    client=client,
                )

    with (
        patch.dict(
            "job_hunter.cost.pricing_config.GEMINI_PRICING_TABLE",
            test_pricing_table(),
            clear=True,
        ),
        caplog.at_level(logging.INFO, logger=LOGGER_NAME),
    ):
        asyncio.run(scenario())

    events = gemini_events(caplog)

    attempt_events = events_named(events, "http_attempt_completed")
    usage_events = events_named(events, "gemini_usage_reported")
    cost_events = events_named(events, "gemini_cost_estimated")
    operation_events = events_named(events, "operation_completed")

    assert len(requests) == 1

    # HTTP succeeded even though assessment validation failed.
    assert len(attempt_events) == 1
    assert attempt_events[0]["outcome"] == "success"
    assert attempt_events[0]["status_code"] == 200

    assert len(usage_events) == 1

    assert cost_events == [
        {
            "event": "gemini_cost_estimated",
            "component": "gemini",
            "outcome": "success",
            "model": "model-a",
            "estimated_cost_usd": "0.00166",
            "level": logging.INFO,
        }
    ]

    # The complete assessment operation failed.
    assert len(operation_events) == 1
    assert operation_events[0]["outcome"] == "failure"
    assert operation_events[0]["level"] == logging.ERROR

    assert events_named(events, "http_retry_scheduled") == []
    assert events_named(events, "http_request_failed") == []

    event_names = [event["event"] for event in events]

    assert event_names.index("gemini_usage_reported") < (
        event_names.index("gemini_cost_estimated")
    )
    assert event_names.index("gemini_cost_estimated") < (
        event_names.index("operation_completed")
    )

    for secret in (
        "test-secret-key",
        "private-candidate-skill",
        "Private employer job description.",
        str(requests[0].url),
    ):
        assert secret not in caplog.text


@pytest.mark.parametrize(
    "invalid_metadata",
    [
        {
            "promptTokenCount": "1200",
            "candidatesTokenCount": 300,
            "totalTokenCount": 1750,
            "thoughtsTokenCount": 250,
            "cachedContentTokenCount": 100,
        },
        {
            "promptTokenCount": True,
            "candidatesTokenCount": 300,
            "totalTokenCount": 1750,
            "thoughtsTokenCount": 250,
            "cachedContentTokenCount": 100,
        },
        {
            "promptTokenCount": -1,
            "candidatesTokenCount": 300,
            "totalTokenCount": 1750,
            "thoughtsTokenCount": 250,
            "cachedContentTokenCount": 100,
        },
        {
            "promptTokenCount": 1200,
            "candidatesTokenCount": 300,
            "totalTokenCount": 1750,
            "thoughtsTokenCount": "250",
            "cachedContentTokenCount": 100,
        },
    ],
)
def test_gemini_malformed_usage_omits_cost_event(
    caplog,
    invalid_metadata,
):
    requests = []

    def handler(request):
        requests.append(request)

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
                model="model-a",
                api_key="test-secret-key",
                client=client,
            )

    with (
        patch.dict(
            "job_hunter.cost.pricing_config.GEMINI_PRICING_TABLE",
            test_pricing_table(),
            clear=True,
        ),
        caplog.at_level(logging.INFO, logger=LOGGER_NAME),
    ):
        result = asyncio.run(scenario())

    events = gemini_events(caplog)

    assert result.confidence == pytest.approx(0.5)
    assert len(requests) == 1

    # Invalid usage metadata must not invalidate the assessment.
    assert events_named(events, "gemini_usage_reported") == []
    assert events_named(events, "gemini_cost_estimated") == []

    operation_events = events_named(events, "operation_completed")
    assert len(operation_events) == 1
    assert operation_events[0]["outcome"] == "success"

    assert events_named(events, "http_retry_scheduled") == []
    assert events_named(events, "http_request_failed") == []

