import pytest

from job_hunter.calculate_retry_delay import calculate_retry_delay


@pytest.mark.parametrize(
    ("attempt", "retry_after", "expected"),
    [
        (1, "5", 5.0),
        (1, None, 1.0),
        (2, "invalid", 2.0),
        (1, "-3", 1.0),
        (1, "120", 30.0),
        (2, "0", 0.0),
        (1, "nan", 1.0),
        (1, "inf", 1.0),
    ],
)
def test_calculate_retry_delay(attempt, retry_after, expected):
    assert calculate_retry_delay(attempt, retry_after) == expected

def test_calculate_retry_delay_rejects_invalid_attempt():
    with pytest.raises(ValueError):
        calculate_retry_delay(
            attempt=0,
            retry_after="5",
        )