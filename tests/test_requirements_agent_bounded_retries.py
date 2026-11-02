import asyncio
import json
from unittest.mock import patch, AsyncMock, call

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

def test_invalid_gemini_response_is_not_retried():
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
