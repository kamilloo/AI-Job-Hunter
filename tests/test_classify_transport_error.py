import httpx
import pytest

from job_hunter.classify_transport_error import classify_transport_error
from job_hunter.classify_http_error import FailureCategory


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ConnectTimeout("timeout"), FailureCategory.TRANSIENT),
        (httpx.ReadTimeout("timeout"), FailureCategory.TRANSIENT),
        (httpx.ConnectError("connection failed"), FailureCategory.TRANSIENT),
        (httpx.RemoteProtocolError("invalid response"), FailureCategory.TRANSIENT),
        (httpx.InvalidURL("invalid URL"), FailureCategory.PERMANENT),
        (ValueError("invalid input"), FailureCategory.PERMANENT),
    ],
)
def test_classify_transport_error(error, expected):
    assert classify_transport_error(error) == expected