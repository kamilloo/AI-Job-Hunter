import pytest

from job_hunter.collectors.calculate_discovery_status import calculate_discovery_status


@pytest.mark.parametrize(
    ("total_sources", "failed_sources", "expected"),
    [
        (3, 0, "complete"),
        (3, 1, "partial"),
        (3, 2, "partial"),
        (3, 3, "failed"),
        (1, 1, "failed"),
        (1, 0, "complete"),
        (0, 0, "no_sources"),
    ],
)
def test_calculate_discovery_status(
    total_sources,
    failed_sources,
    expected,
):
    assert calculate_discovery_status(
        total_sources=total_sources,
        failed_sources=failed_sources,
    ) == expected

@pytest.mark.parametrize(
    ("total_sources", "failed_sources"),
    [
        (-1, 0),
        (1, -1),
        (1, 2),
        (0, 1),
    ],
)
def test_calculate_discovery_status_rejects_invalid_counts(
    total_sources,
    failed_sources,
):
    with pytest.raises(ValueError):
        calculate_discovery_status(
            total_sources=total_sources,
            failed_sources=failed_sources,
        )