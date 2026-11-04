import asyncio
import json
from unittest.mock import patch, AsyncMock, call
import logging

import httpx
import pytest

from job_hunter.agents.requirements_agent import (
    ASSESSMENT_INSTRUCTIONS,
    assess_requirements,
    build_prompt,
)
from job_hunter.model.RequirementAssessment import TechnicalAssessment, RequirementStatus


SKILL_EXPERIENCE = {
        "technology": "Elasticsearch",
        "context": "Transferred cached profiles from PostgreSQL to Elasticsearch",
        "production": "true",
        "years": 2
    }

PROFILE = {"core_skills": ["PHP"], "transferable_languages": ["Go"], "skill_experiences": [SKILL_EXPERIENCE]}
DESCRIPTION = "Professional production Go experience required. SQL preferred."
RESULT = {
    "requirements": [{
        "name": "Production Go", "mandatory": True, "status": "unknown",
        "job_evidence": "Professional production Go experience required.",
        "candidate_evidence": "",
        "explanation": "Transferable language does not establish production experience.",
    }],
    "summary": "Production Go evidence is missing.", "confidence": 0.8,
}

def response(result=RESULT, finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {
        "parts": [{"text": json.dumps(result)}],
    }}]}

def test_bounded_retries():
    async def scenario():
        requests = []

        assessment = {
            "requirements": [],
            "summary": "No technical requirements found.",
            "confidence": 0.9,
        }

        def handler(request):
            requests.append(request)

            if len(requests) == 1:
                return httpx.Response(503)

            return httpx.Response(
                200,
                json={
                    "candidates": [{
                        "finishReason": "STOP",
                        "content": {
                            "parts": [{"text": json.dumps(assessment)}]
                        },
                    }]
                },
            )

        transport = httpx.MockTransport(handler)

        with patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(transport=transport) as client:
                result = await assess_requirements(
                    {"core_skills": ["Python"]},
                    "Python experience required.",
                    api_key="test-key",
                    client=client,
                )

        assert len(requests) == 2
        assert result.summary == "No technical requirements found."
        assert result.confidence == 0.9
        assert all(request.method == "POST" for request in requests)

        mock_sleep.assert_awaited_once_with(1.0)

    asyncio.run(scenario())

def test_gemini_does_not_retry_read_timeout():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
            raise httpx.ReadTimeout("Response timed out")

        with patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                with pytest.raises(httpx.ReadTimeout):
                    await assess_requirements(
                        {"core_skills": ["Python"]},
                        "Python experience required.",
                        api_key="test-key",
                        client=client,
                    )

            assert len(requests) == 1
            mock_sleep.assert_not_awaited()

    asyncio.run(scenario())

def test_permanent_error_never_retry():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(400, json={"error": {"message": "Bad Request"}})

        with patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await assess_requirements(
                        {"core_skills": ["Python"]},
                        "Python experience required.",
                        api_key="test-key",
                        client=client,
                    )

            assert len(requests) == 1
            mock_sleep.assert_not_awaited()

    asyncio.run(scenario())

def test_connection_failures_can_recover_within_two_attempts():
    requests = []
    async def scenario():
        def handler(request):
            requests.append(request)
            if len(requests) < 2:
                raise httpx.ConnectTimeout("Failed to connect")
            return httpx.Response(200, json=response())

        with patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                result = await assess_requirements(
                    {"core_skills": ["Python"]},
                    "Python experience required.",
                    api_key="test-key",
                    client=client,
                )
                assert result.confidence == 0.8

            assert len(requests) == 2
            mock_sleep.assert_awaited_once_with(1.0)

    asyncio.run(scenario())

def test_invalid_gemini_response_is_not_retried(caplog):
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)

            return httpx.Response(
                200,
                json={
                    "candidates": [{
                        "finishReason": "STOP",
                        "content": {
                            "parts": [{"text": "not valid JSON"}]
                        },
                    }]
                },
            )

        with patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                with pytest.raises(ValueError):
                    await assess_requirements(
                        {"core_skills": ["Python"]},
                        "Python experience required.",
                        api_key="test-key",
                        client=client,
                    )

            assert len(requests) == 1
            mock_sleep.assert_not_awaited()

    asyncio.run(scenario())

    assert "http_request_failed" not in caplog.text
    assert "http_retry_scheduled" not in caplog.text


def test_ratelimit_delay_is_honored():
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "5"},
                json={"error": {"message": "Rate limit exceeded"}},
            )

        return httpx.Response(
            200,
            json=response(),
        )
    async def scenario():
        with patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                await assess_requirements(
                    {"core_skills": ["Python"]},
                    "Python experience required.",
                    api_key="test-key",
                    client=client,
                )

            assert len(requests) == 2
            mock_sleep.assert_awaited_once_with(5.0)
    asyncio.run(scenario())

def test_retry_exhaustion_propagates_the_final_exception():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(503)
    async def scenario():
        with patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                with pytest.raises(httpx.HTTPStatusError) as exc:
                    await assess_requirements(
                        {"core_skills": ["Python"]},
                        "Python experience required.",
                        api_key="test-key",
                        client=client,
                    )

            assert len(requests) == 2
            assert exc.value.response.status_code == 503
            assert mock_sleep.call_count == 1
            assert all(call.args[0] == 1.0 for call in mock_sleep.call_args_list)

    asyncio.run(scenario())

def test_gemini_retry_emits_structured_warning(caplog):
    requests = []

    def handler(request):
        requests.append(request)

        if len(requests) == 1:
            return httpx.Response(503)

        return httpx.Response(200, json=response())

    async def scenario():
        with patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                await assess_requirements(
                    {"core_skills": ["Python"]},
                    "Python experience required.",
                    api_key="test-secret-key",
                    client=client,
                )

    with caplog.at_level(
        logging.WARNING,
        logger="job_hunter.agents.requirements_agent",
    ):
        asyncio.run(scenario())

    retry_events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.agents.requirements_agent"
        and record.message.startswith("{")
    ]

    assert len(requests) == 2
    assert len(retry_events) == 2

    event = retry_events[1]

    assert event["event"] == "http_retry_scheduled"
    assert event["component"] == "gemini"
    assert event["outcome"] == "retry"
    assert event["attempt"] == 1
    assert event["status_code"] == 503
    assert event["level"] == logging.WARNING

    # Verify sensitive data is absent.
    assert "test-secret-key" not in caplog.text
    assert "Python experience required." not in caplog.text

def test_gemini_read_timeout_emits_no_retry_event(caplog):
    requests = []

    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout("response timed out")

    async def scenario():
        with patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                with pytest.raises(httpx.ReadTimeout):
                    await assess_requirements(
                        {"core_skills": ["Python"]},
                        "Python experience required.",
                        api_key="test-secret-key",
                        client=client,
                    )

            mock_sleep.assert_not_awaited()

    with caplog.at_level(
        logging.WARNING,
        logger="job_hunter.agents.requirements_agent",
    ):
        asyncio.run(scenario())

    assert len(requests) == 1
    assert "http_retry_scheduled" not in caplog.text


def test_gemini_retry_exhaustion_emits_terminal_failure(caplog):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(503)

    async def scenario():
        with patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await assess_requirements(
                        {"core_skills": ["Python"]},
                        "Python experience required.",
                        api_key="test-secret-key",
                        client=client,
                    )

            mock_sleep.assert_awaited_once_with(1.0)

    with caplog.at_level(
        logging.WARNING,
        logger="job_hunter.agents.requirements_agent",
    ):
        asyncio.run(scenario())

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.agents.requirements_agent"
        and record.message.startswith("{")
    ]

    retries = [
        event for event in events
        if event["event"] == "http_retry_scheduled"
    ]
    failures = [
        event for event in events
        if event["event"] == "http_request_failed"
    ]

    assert len(requests) == 2
    assert len(retries) == 1
    assert len(failures) == 1

    failure = failures[0]

    assert failure["component"] == "gemini"
    assert failure["outcome"] == "failure"
    assert failure["attempt"] == 2
    assert failure["status_code"] == 503
    assert failure["level"] == logging.ERROR

    assert "test-secret-key" not in caplog.text
    assert "Python experience required." not in caplog.text
    assert str(requests[0].url) not in caplog.text


@pytest.mark.parametrize(
    "status_code, error_type, attempts, retry_count",
    [
        pytest.param(400, httpx.HTTPStatusError, 1, 0, id="http-400"),
        pytest.param(None, httpx.ReadTimeout, 1, 0, id="read-timeout"),
        pytest.param(None, httpx.ConnectError, 2, 1, id="connect-error-exhausted"),
    ],
)
def test_gemini_terminal_failure_events(
    caplog, status_code, error_type, attempts, retry_count,
):
    requests = []

    def handler(request):
        requests.append(request)
        if status_code is not None:
            return httpx.Response(
                status_code,
                json={"error": "secret-response-content"},
            )
        raise error_type("secret-exception-content", request=request)

    async def scenario():
        with patch(
            "job_hunter.agents.requirements_agent.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                with pytest.raises(error_type) as exc_info:
                    await assess_requirements(
                        {"core_skills": ["private-candidate-skill"]},
                        "Private employer job description.",
                        api_key="test-secret-key",
                        client=client,
                    )

            assert exc_info.value.request is requests[-1]
            if status_code is not None:
                assert exc_info.value.response.status_code == status_code
            if retry_count:
                mock_sleep.assert_awaited_once_with(1.0)
            else:
                mock_sleep.assert_not_called()
                mock_sleep.assert_not_awaited()

    with caplog.at_level(
        logging.WARNING,
        logger="job_hunter.agents.requirements_agent",
    ):
        asyncio.run(scenario())

    records = [
        record for record in caplog.records
        if record.name == "job_hunter.agents.requirements_agent"
    ]
    events = [json.loads(record.message) for record in records]
    retries = [event for event in events if event["event"] == "http_retry_scheduled"]
    failures = [event for event in events if event["event"] == "http_request_failed"]

    assert len(requests) == attempts
    assert len(retries) == retry_count
    expected_failure = {
        "event": "http_request_failed",
        "component": "gemini",
        "outcome": "failure",
        "attempt": attempts,
        "level": logging.ERROR,
    }
    if status_code is not None:
        expected_failure["status_code"] = status_code
    assert failures == [expected_failure]
    operations = [event for event in events if event["event"] == "operation_completed"]
    assert len(operations) == 1
    operation = operations[0]
    assert events[-1] == operation
    assert operation["component"] == "gemini"
    assert operation["outcome"] == "failure"
    assert operation["level"] == logging.ERROR
    assert operation["duration_ms"] >= 0
    assert records[-1].levelno == logging.ERROR
    if retries:
        assert retries == [{
            "event": "http_retry_scheduled",
            "component": "gemini",
            "outcome": "retry",
            "attempt": 1,
            "level": logging.WARNING,
        }]
        assert records[0].levelno == logging.WARNING

    for sensitive_value in (
        "test-secret-key",
        "private-candidate-skill",
        "Private employer job description.",
        "secret-response-content",
        "secret-exception-content",
        ASSESSMENT_INSTRUCTIONS,
        str(requests[0].url),
    ):
        assert sensitive_value not in caplog.text
