import math

from job_hunter.calculate_backoff import calculate_backoff


def calculate_retry_delay(
    attempt: int,
    retry_after: str | None,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> float:
    fallback = calculate_backoff(
        attempt=attempt,
        base_delay=base_delay,
        max_delay=max_delay,
    )

    if retry_after is None:
        return fallback

    try:
        seconds = float(retry_after)
    except ValueError:
        return fallback

    if not math.isfinite(seconds) or seconds < 0:
        return fallback

    return min(seconds, max_delay)