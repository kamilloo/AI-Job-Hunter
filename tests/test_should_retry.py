import pytest

from job_hunter.classify_http_error import FailureCategory
from job_hunter.should_retry import should_retry


@pytest.mark.parametrize(
    ("category", "attempt", "max_attempts", "retry_safe", "expected"),
    [
        (FailureCategory.TRANSIENT, 1, 3, True, True),
        (FailureCategory.RATE_LIMITED, 2, 3, True, True),
        (FailureCategory.PERMANENT, 1, 3, True, False),
        (FailureCategory.TRANSIENT, 1, 3, False, False),
        (FailureCategory.RATE_LIMITED, 1, 3, False, False),
        (FailureCategory.TRANSIENT, 3, 3, True, False),
        (FailureCategory.TRANSIENT, 4, 3, True, False),
        (FailureCategory.TRANSIENT, 1, 1, True, False),
    ],
)
def test_should_retry(
    category, attempt, max_attempts, retry_safe, expected
):
    assert should_retry(
        category=category,
        attempt=attempt,
        max_attempts=max_attempts,
        retry_safe=retry_safe,
    ) is expected

@pytest.mark.parametrize(
    ("attempt", "max_attempts"),
    [
        (-1, 3),
        (1, -1),
        (0, 3),
        (1, 0),
    ],
)
def test_should_retry_rejects_invalid_attempts(attempt, max_attempts):
    with pytest.raises(ValueError):
        should_retry(
            category=FailureCategory.TRANSIENT,
            attempt=attempt,
            max_attempts=max_attempts,
            retry_safe=True,
        )
