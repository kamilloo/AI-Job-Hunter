import httpx
from job_hunter.classify_http_error import FailureCategory


def classify_transport_error(error: Exception) -> FailureCategory:
    if isinstance(
        error,
        (
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ),
    ):
        return FailureCategory.TRANSIENT

    return FailureCategory.PERMANENT
