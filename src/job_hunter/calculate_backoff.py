import math

def calculate_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
) -> float:
    if not math.isfinite(base_delay) or not math.isfinite(max_delay):
        raise ValueError("delays must be finite")

    if attempt <= 0:
        raise ValueError("attempt must be positive")

    if base_delay <= 0 or max_delay <= 0:
        raise ValueError("delays must be positive")
    if base_delay > max_delay:
        raise ValueError("base_delay cannot be larger than max_delay")

    delay = base_delay * 2 ** (attempt - 1)
    return min(delay, max_delay)
