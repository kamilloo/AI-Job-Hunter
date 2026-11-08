"""No-network tests for the optional SDK execution backend."""
import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from job_hunter.agent import assess_requirements_agent
from job_hunter.agents.requirements_agent import ASSESSMENT_INSTRUCTIONS, build_prompt
from job_hunter.model.RequirementAssessment import TechnicalAssessment


@pytest.mark.parametrize('output', [
    {'requirements': [], 'summary': 'No evidence', 'confidence': 0.2},
    {}, None,
])
def test_sdk_configuration_and_output_validation(monkeypatch, output):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    profile = {'skill_experiences': [{
        'technology': 'Docker', 'years': 2,
        'context': 'Operated Docker containers in production.',
    }]}
    client = object()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=context)
    sdk = SimpleNamespace(
        Agent=MagicMock(),
        Runner=SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(final_output=output))),
        RunConfig=MagicMock(),
        OpenAIChatCompletionsModel=MagicMock(),
    )
    with patch.dict(sys.modules, {'agents': sdk, 'openai': SimpleNamespace(AsyncOpenAI=factory)}):
        if output:
            result = asyncio.run(assess_requirements_agent(profile, 'Employer text', 'test-model'))
            assert isinstance(result, TechnicalAssessment)
        else:
            with pytest.raises(ValueError):
                asyncio.run(assess_requirements_agent(profile, 'Employer text', 'test-model'))
    factory.assert_called_once_with(
        api_key='test-key', base_url='https://generativelanguage.googleapis.com/v1beta/openai/',
        timeout=60, max_retries=0,
    )
    sdk.OpenAIChatCompletionsModel.assert_called_once_with(model='test-model', openai_client=client)
    assert sdk.Agent.call_args.kwargs['output_type'] is TechnicalAssessment
    assert sdk.Agent.call_args.kwargs['instructions'] == ASSESSMENT_INSTRUCTIONS
    sdk.RunConfig.assert_called_once_with(tracing_disabled=True, trace_include_sensitive_data=False)
    assert sdk.Runner.run.call_args.kwargs['max_turns'] == 1
    prompt = sdk.Runner.run.call_args.args[1]
    assert prompt == build_prompt(profile, 'Employer text')
    assert '"E1": "skill_experiences[0].context"' in prompt
    assert prompt.count('Operated Docker containers in production.') == 1
    assert 'copied verbatim' in sdk.Agent.call_args.kwargs['instructions']
    context.__aexit__.assert_awaited_once()


def test_installed_sdk_schema_compatibility():
    # Optional extra is not required for the default test suite.
    agent_output = pytest.importorskip('agents.agent_output')
    schema = agent_output.AgentOutputSchema(TechnicalAssessment)
    assert schema.is_strict_json_schema()
    assert 'requirements' in schema.json_schema()['properties']


def test_missing_sdk_does_not_fall_back(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    with patch.dict(sys.modules, {'agents': None}):
        with pytest.raises(ImportError):
            asyncio.run(assess_requirements_agent({}, 'Employer text', 'test-model'))


def test_actual_sdk_with_in_memory_http(monkeypatch):
    """Exercise SDK serialization and parsing without a network request."""
    pytest.importorskip('agents.agent_output')
    openai = pytest.importorskip('openai')
    import httpx

    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    real_client = openai.AsyncOpenAI
    requests = []

    def respond(request):
        requests.append(request)
        assert request.url.host == 'generativelanguage.googleapis.com'
        assert request.url.path == '/v1beta/openai/chat/completions'
        return httpx.Response(200, json={
            'id': 'mock-completion', 'object': 'chat.completion', 'created': 0,
            'model': 'test-model',
            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {
                'role': 'assistant', 'content': '{"requirements": [], "summary": "No evidence", "confidence": 0.2}',
            }}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20},
        })

    def make_client(**kwargs):
        client = real_client(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
        # Isolate SDK platform discovery, which dispatches to a worker thread.
        client._platform = 'Linux'
        return client

    monkeypatch.setattr(openai, 'AsyncOpenAI', make_client)
    result = asyncio.run(assess_requirements_agent({}, 'Employer text', 'test-model'))
    assert result.summary == 'No evidence'
    assert len(requests) == 1
