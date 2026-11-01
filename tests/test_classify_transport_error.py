import httpx
import pytest

from job_hunter.classify_transport_error import classify_transport_error, HttpTransportCategory


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ConnectTimeout("timeout"), HttpTransportCategory.TRANSIENT),
        (httpx.ReadTimeout("timeout"), HttpTransportCategory.TRANSIENT),
        (httpx.ConnectError("connection failed"), HttpTransportCategory.TRANSIENT),
        (httpx.RemoteProtocolError("invalid response"), HttpTransportCategory.TRANSIENT),
        (httpx.InvalidURL("invalid URL"), HttpTransportCategory.PERMANENT),
        (ValueError("invalid input"), HttpTransportCategory.PERMANENT),
    ],
)
def test_classify_transport_error(error, expected):
    assert classify_transport_error(error) == expected