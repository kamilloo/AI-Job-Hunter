import pytest

from job_hunter.classify_http_error import classify_http_error, FailureCategory

@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, FailureCategory.PERMANENT),
        (401, FailureCategory.PERMANENT),
        (403, FailureCategory.PERMANENT),
        (404, FailureCategory.PERMANENT),
        (408, FailureCategory.TRANSIENT),
        (422, FailureCategory.PERMANENT),
        (429, FailureCategory.RATE_LIMITED),
        (500, FailureCategory.TRANSIENT),
        (501, FailureCategory.PERMANENT),
        (502, FailureCategory.TRANSIENT),
        (503, FailureCategory.TRANSIENT),
        (504, FailureCategory.TRANSIENT),
    ],
)
def test_classify_http_error(status_code, expected):
    assert classify_http_error(status_code) == expected

