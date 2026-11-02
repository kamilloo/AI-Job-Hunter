from enum import Enum


class FailureCategory(str, Enum):
    PERMANENT = "permanent"
    TRANSIENT = "transient"
    RATE_LIMITED = "rate_limited"


def classify_http_error(status_code: int) -> FailureCategory:
    if status_code == 429:
        return FailureCategory.RATE_LIMITED

    if status_code in {408, 500, 502, 503, 504}:
        return FailureCategory.TRANSIENT

    return FailureCategory.PERMANENT