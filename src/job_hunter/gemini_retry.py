import httpx


def gemini_retry_safe(error: Exception) -> bool:
    return isinstance(
        error,
        (
            httpx.ConnectError,
            httpx.ConnectTimeout,
        ),
    )