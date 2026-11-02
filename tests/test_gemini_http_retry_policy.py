import pytest

from job_hunter.classify_http_error import classify_http_error
from job_hunter.should_retry import should_retry


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, False),
        (401, False),
        (403, False),
        (429, True),
        (500, True),
        (503, True),
    ],
)
def test_gemini_http_retry_policy(status, expected):
    category = classify_http_error(status)

    assert should_retry(
        category=category,
        attempt=1,
        max_attempts=2,
        retry_safe=True,
    ) is expected