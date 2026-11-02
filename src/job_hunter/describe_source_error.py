import httpx

from job_hunter.classify_http_error import classify_http_error
from job_hunter.classify_transport_error import classify_transport_error

import httpx

from job_hunter.classify_http_error import (
    FailureCategory,
    classify_http_error,
)
from job_hunter.classify_transport_error import classify_transport_error


def describe_source_error(
    provider: str,
    board: str,
    error: Exception,
) -> dict:
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        category = classify_http_error(status_code)
    elif isinstance(error, httpx.HTTPError):
        status_code = None
        category = classify_transport_error(error)
    else:
        status_code = None
        category = FailureCategory.PERMANENT

    return {
        "provider": provider,
        "board": board,
        "error_type": type(error).__name__,
        "category": category.value,
        "status_code": status_code,
    }