import pytest

from job_hunter.cost.map_gemini_billable_tokens import map_gemini_billable_tokens, BillableTokens
from job_hunter.model.GeminiUsage import GeminiUsage


def test_maps_complete_gemini_usage():
    usage = GeminiUsage(
        prompt_tokens=1200,
        output_tokens=300,
        total_tokens=1750,
        thinking_tokens=250,
        cached_input_tokens=100,
    )

    result = map_gemini_billable_tokens(usage)

    assert result == BillableTokens(
        uncached_input_tokens=1100,
        cached_input_tokens=100,
        output_tokens=550,
    )


def test_rejects_cached_tokens_exceeding_prompt():
    usage = GeminiUsage(
        prompt_tokens=100,
        output_tokens=50,
        total_tokens=150,
        thinking_tokens=0,
        cached_input_tokens=200,
    )

    with pytest.raises(ValueError):
        map_gemini_billable_tokens(usage)


def test_unknown_thinking_tokens():
    usage = GeminiUsage(
        prompt_tokens=1200,
        output_tokens=300,
        total_tokens=1750,
        thinking_tokens=None,
        cached_input_tokens=100,
    )

    assert map_gemini_billable_tokens(usage) is None


def test_unknown_cached_tokens():
    usage = GeminiUsage(
        prompt_tokens=1200,
        output_tokens=300,
        total_tokens=1500,
        thinking_tokens=0,
        cached_input_tokens=None,
    )

    assert map_gemini_billable_tokens(usage) is None

def test_rejects_inconsistent_total_tokens():
    usage = GeminiUsage(
        prompt_tokens=1200,
        output_tokens=300,
        total_tokens=9999,
        thinking_tokens=250,
        cached_input_tokens=100,
    )

    with pytest.raises(ValueError, match="inconsistent"):
        map_gemini_billable_tokens(usage)

def test_maps_zero_thinking_and_cached_tokens():
    usage = GeminiUsage(
        prompt_tokens=1200,
        output_tokens=300,
        total_tokens=1500,
        thinking_tokens=0,
        cached_input_tokens=0,
    )

    assert map_gemini_billable_tokens(usage) == BillableTokens(
        uncached_input_tokens=1200,
        cached_input_tokens=0,
        output_tokens=300,
    )