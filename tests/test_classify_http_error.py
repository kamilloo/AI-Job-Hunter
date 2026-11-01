import pytest

from job_hunter.classify_http_error import classify_http_error, HttpErrorCategory

@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, HttpErrorCategory.PERMANENT),
        (401, HttpErrorCategory.PERMANENT),
        (403, HttpErrorCategory.PERMANENT),
        (404, HttpErrorCategory.PERMANENT),
        (408, HttpErrorCategory.TRANSIENT),
        (422, HttpErrorCategory.PERMANENT),
        (429, HttpErrorCategory.RATE_LIMITED),
        (500, HttpErrorCategory.TRANSIENT),
        (501, HttpErrorCategory.PERMANENT),
        (502, HttpErrorCategory.TRANSIENT),
        (503, HttpErrorCategory.TRANSIENT),
        (504, HttpErrorCategory.TRANSIENT),
    ],
)
def test_classify_http_error(status_code, expected):
    assert classify_http_error(status_code) == expected

