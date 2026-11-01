from enum import Enum


class HttpErrorCategory(str, Enum):
    PERMANENT = "permanent"
    TRANSIENT = "transient"
    RATE_LIMITED = "rate_limited"


def classify_http_error(status_code: int) -> HttpErrorCategory:
    if status_code == 429:
        return HttpErrorCategory.RATE_LIMITED

    if status_code in {408, 500, 502, 503, 504}:
        return HttpErrorCategory.TRANSIENT

    return HttpErrorCategory.PERMANENT