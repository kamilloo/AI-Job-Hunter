import pytest

from job_hunter.latency.elapsed_ms import elapsed_ms


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (1.0, 1.125, 125.0),
        (10.0, 10.0, 0.0),
        (5.0, 5.5, 500.0),
    ],
)
def test_elapsed_ms(start, end, expected):
    assert elapsed_ms(start, end) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (2.0, 1.0),
        (-1.0, 1.0),
        (float("nan"), 1.0),
        (1.0, float("inf")),
    ],
)
def test_elapsed_ms_rejects_invalid_timestamps(start, end):
    with pytest.raises(ValueError):
        elapsed_ms(start, end)

def test_elapsed_ms_accepts_zero_start():
    assert elapsed_ms(0.0, 0.25) == pytest.approx(250.0)