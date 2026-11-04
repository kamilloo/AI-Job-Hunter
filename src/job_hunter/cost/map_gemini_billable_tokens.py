from pydantic import BaseModel, ConfigDict, Field

from job_hunter.model.GeminiUsage import GeminiUsage


class BillableTokens(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    uncached_input_tokens: int = Field(ge=0, strict=True)
    cached_input_tokens: int = Field(ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)


def map_gemini_billable_tokens(
    usage: GeminiUsage,
) -> BillableTokens | None:

    if (
        usage.cached_input_tokens is not None
        and usage.cached_input_tokens > usage.prompt_tokens
    ):
        raise ValueError(
            "Cached input tokens cannot exceed prompt tokens"
        )

    if (
        usage.cached_input_tokens is None
        or usage.thinking_tokens is None
    ):
        return None

    expected_total = (
        usage.prompt_tokens
        + usage.output_tokens
        + usage.thinking_tokens
    )

    if usage.total_tokens != expected_total:
        raise ValueError(
            "Gemini token totals are inconsistent"
        )

    return BillableTokens(
        uncached_input_tokens=(
            usage.prompt_tokens - usage.cached_input_tokens
        ),
        cached_input_tokens=usage.cached_input_tokens,
        output_tokens=(
            usage.output_tokens + usage.thinking_tokens
        ),
    )