import math


def elapsed_ms(start: float, end: float) -> float:
    if not math.isfinite(start) or not math.isfinite(end):
        raise ValueError("timestamps must be finite")

    if start < 0 or end < 0:
        raise ValueError("timestamps must be non-negative")

    if end < start:
        raise ValueError("end cannot precede start")

    return (end - start) * 1000