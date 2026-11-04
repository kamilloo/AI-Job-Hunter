from collections.abc import Mapping
from typing import Any

from job_hunter.model.GeminiUsage import GeminiUsage


def extract_gemini_usage(
    metadata: Mapping[str, Any] | None,
) -> GeminiUsage | None:
    required = (
        "promptTokenCount",
        "candidatesTokenCount",
        "totalTokenCount",
    )

    if not metadata or not all(key in metadata for key in required):
        return None

    return GeminiUsage(
        prompt_tokens=metadata["promptTokenCount"],
        output_tokens=metadata["candidatesTokenCount"],
        total_tokens=metadata["totalTokenCount"],
    )