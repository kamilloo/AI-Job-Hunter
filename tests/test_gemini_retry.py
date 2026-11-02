import httpx
import pytest

from job_hunter.gemini_retry import gemini_retry_safe


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ConnectError("connection failed"), True),
        (httpx.ConnectTimeout("connection timed out"), True),
        (httpx.ReadTimeout("response timed out"), False),
        (httpx.WriteTimeout("request timed out"), False),
        (httpx.RemoteProtocolError("connection interrupted"), False),
        (httpx.InvalidURL("invalid URL"), False),
        (ValueError("invalid model response"), False),
    ],
)
def test_gemini_retry_safe(error, expected):
    assert gemini_retry_safe(error) is expected