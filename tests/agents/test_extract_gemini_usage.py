
import pytest
from pydantic import ValidationError

from job_hunter.agents.extract_gemini_usage import extract_gemini_usage
from job_hunter.model.GeminiUsage import GeminiUsage


def test_extract_gemini_usage_valid():
    usage = extract_gemini_usage({
        "promptTokenCount": 1200,
        "candidatesTokenCount": 300,
        "totalTokenCount": 1750,
        "cachedContentTokenCount": 100,
    })

    assert usage == GeminiUsage(
        prompt_tokens=1200,
        output_tokens=300,
        total_tokens=1750,
    )


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {},
        {"promptTokenCount": 1200},
        {
            "promptTokenCount": 1200,
            "candidatesTokenCount": 300,
        },
    ],
)
def test_extract_gemini_usage_missing_metadata(metadata):
    assert extract_gemini_usage(metadata) is None


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("promptTokenCount", -1),
        ("candidatesTokenCount", True),
        ("totalTokenCount", "1500"),
        ("promptTokenCount", 1.5),
    ],
)
def test_extract_gemini_usage_invalid(field, invalid):
    metadata = {
        "promptTokenCount": 1200,
        "candidatesTokenCount": 300,
        "totalTokenCount": 1500,
    }
    metadata[field] = invalid

    with pytest.raises(ValidationError):
        extract_gemini_usage(metadata)


def test_extract_gemini_usage_zero_counts():
    usage = extract_gemini_usage({
        "promptTokenCount": 0,
        "candidatesTokenCount": 0,
        "totalTokenCount": 0,
    })

    assert usage == GeminiUsage(
        prompt_tokens=0,
        output_tokens=0,
        total_tokens=0,
    )
