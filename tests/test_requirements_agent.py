import asyncio
import json
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

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


def run_response(body, status=200):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json=body)
        )) as client:
            return await assess_requirements(PROFILE, DESCRIPTION, "gemini-test", api_key="test-key", client=client)
    return asyncio.run(scenario())


def response(result=RESULT, finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {
        "parts": [{"text": json.dumps(result)}],
    }}]}


def test_request_schema_prompt_and_validated_result():
    async def scenario():
        def handler(request):
            assert request.headers["x-goog-api-key"] == "test-key"
            assert "test-key" not in str(request.url)
            assert request.url.path.endswith("/gemini-test:generateContent")
            payload = json.loads(request.content)
            assert payload["generationConfig"]["responseJsonSchema"] == TechnicalAssessment.model_json_schema()
            assert payload["generationConfig"]["responseMimeType"] == "application/json"
            assert payload["systemInstruction"]["parts"][0]["text"] == ASSESSMENT_INSTRUCTIONS
            assert payload["contents"][0]["parts"][0]["text"] == build_prompt(PROFILE, DESCRIPTION)
            prompt = payload["contents"][0]["parts"][0]["text"]
            assert "Elasticsearch" in prompt
            assert "PostgreSQL" in prompt
            assert "production" in prompt
            assert "years" in prompt
            assert "Transferred cached profiles from PostgreSQL to Elasticsearch" in payload["contents"][0]["parts"][0]["text"]
            return httpx.Response(200, json=response())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await assess_requirements(PROFILE, DESCRIPTION, "gemini-test", api_key="test-key", client=client)
            assert not client.is_closed
            assert isinstance(result, TechnicalAssessment)
            assert result.requirements[0].status == RequirementStatus.unknown
    asyncio.run(scenario())


@pytest.mark.parametrize("body", [
    {}, {"candidates": []}, response(finish="MAX_TOKENS"),
    {"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]},
])
def test_missing_or_incomplete_assessment_fails(body):
    with pytest.raises(ValueError):
        run_response(body)


def test_invalid_structured_output_fails_validation():
    with pytest.raises(ValidationError):
        run_response(response({"requirements": [], "summary": "Invalid", "confidence": 2}))


def test_http_error_is_propagated():
    with pytest.raises(httpx.HTTPStatusError):
        run_response({"error": "Rate limited"}, status=429)


def test_missing_key_fails_before_request():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            asyncio.run(assess_requirements(PROFILE, DESCRIPTION))


def test_environment_configuration():
    async def scenario():
        def handler(request):
            assert request.headers["x-goog-api-key"] == "env-key"
            assert request.url.path.endswith("/gemini-env:generateContent")
            return httpx.Response(200, json=response())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await assess_requirements(PROFILE, DESCRIPTION, client=client)
    with patch.dict("os.environ", {"GEMINI_API_KEY": "env-key", "GEMINI_MODEL": "gemini-env"}):
        assert asyncio.run(scenario()).confidence == 0.8


@pytest.mark.parametrize("description,model", [(" ", "gemini-test"), (DESCRIPTION, "../invalid")])
def test_invalid_inputs_fail_before_request(description, model):
    with pytest.raises(ValueError):
        asyncio.run(assess_requirements(PROFILE, description, model, api_key="test-key"))
