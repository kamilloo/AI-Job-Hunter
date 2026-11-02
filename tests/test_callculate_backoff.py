import pytest

from job_hunter.calculate_backoff import calculate_backoff


@pytest.mark.parametrize(
    ("attempt", "expected"),
    [
        (1, 1.0),
        (2, 2.0),
        (3, 4.0),
        (4, 8.0),
        (5, 8.0),
    ],
)
def test_calculate_backoff(attempt, expected):
    assert calculate_backoff(attempt) == expected


@pytest.mark.parametrize(
    ("attempt", "base_delay", "max_delay"),
    [
        (0, 1.0, 8.0),
        (-1, 1.0, 8.0),
        (1, 0.0, 8.0),
        (1, -1.0, 8.0),
        (1, 1.0, 0.0),
        (1, 1.0, -8.0),
    ],
)
def test_calculate_backoff_rejects_invalid_configuration(
    attempt, base_delay, max_delay
):
    with pytest.raises(ValueError):
        calculate_backoff(attempt, base_delay, max_delay)

@pytest.mark.parametrize(
    ("base_delay", "max_delay"),
    [
        (float("nan"), 8.0),
        (float("inf"), 8.0),
        (1.0, float("nan")),
        (1.0, float("inf")),
    ],
)
def test_calculate_backoff_rejects_nonfinite_delays(
    base_delay, max_delay
):
    with pytest.raises(ValueError):
        calculate_backoff(
            attempt=1,
            base_delay=base_delay,
            max_delay=max_delay,
        )