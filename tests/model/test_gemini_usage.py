import pytest
from pydantic import ValidationError

from job_hunter.model.GeminiUsage import GeminiUsage


def test_gemini_usage_accepts_valid_counts():
    usage = GeminiUsage(
        prompt_tokens=1200,
        output_tokens=300,
        total_tokens=1500,
    )

    assert usage.prompt_tokens == 1200
    assert usage.output_tokens == 300
    assert usage.total_tokens == 1500


def test_gemini_usage_accepts_zero_counts():
    usage = GeminiUsage(
        prompt_tokens=0,
        output_tokens=0,
        total_tokens=0,
    )

    assert usage.total_tokens == 0


def test_gemini_usage_allows_additional_token_categories():
    usage = GeminiUsage(
        prompt_tokens=1200,
        output_tokens=300,
        total_tokens=1750,
    )

    # Additional 250 tokens may come from thinking.
    assert usage.total_tokens == 1750


@pytest.mark.parametrize(
    "invalid_value",
    [
        -1,
        1.5,
        True,
        False,
        "1200",
        None,
    ],
)
def test_gemini_usage_rejects_invalid_token_counts(invalid_value):
    for field in (
        "prompt_tokens",
        "output_tokens",
        "total_tokens",
    ):
        data = {
            "prompt_tokens": 1200,
            "output_tokens": 300,
            "total_tokens": 1500,
        }
        data[field] = invalid_value

        with pytest.raises(ValidationError):
            GeminiUsage(**data)


def test_gemini_usage_rejects_missing_fields():
    with pytest.raises(ValidationError):
        GeminiUsage(
            prompt_tokens=1200,
            output_tokens=300,
        )


def test_gemini_usage_rejects_extra_fields():
    with pytest.raises(ValidationError):
        GeminiUsage(
            prompt_tokens=1200,
            output_tokens=300,
            total_tokens=1500,
            api_key="must-not-be-stored",
        )
