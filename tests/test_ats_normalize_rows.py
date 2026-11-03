import pytest

from job_hunter.collectors.normalize_rows import normalize_rows


def test_normalize_rows_preserves_valid_jobs_and_counts_invalid():
    valid = {
        "id": 123,
        "title": "Backend Engineer",
        "absolute_url": "https://example.com/jobs/123",
        "location": {"name": "Remote - Poland"},
        "content": "Python backend development.",
    }

    invalid = {
        "id": 456,
        # Missing title and absolute_url
    }

    result = normalize_rows(
        provider="greenhouse",
        slug="example",
        company="Example",
        rows=[valid, invalid],
    )

    assert len(result.jobs) == 1
    assert result.jobs[0].title == "Backend Engineer"
    assert result.skipped_invalid == 1


def test_normalize_rows_excludes_unlisted_ashby_jobs_without_error():
    unlisted = {
        "isListed": False,
    }

    result = normalize_rows(
        provider="ashby",
        slug="example",
        company="Example",
        rows=[unlisted],
    )

    assert result.jobs == []
    assert result.skipped_invalid == 0

def test_normalize_rows_counts_multiple_invalid_records():
    rows = [
        {"id": 1},
        {"id": 2},
        {"id": 3},
    ]

    result = normalize_rows(
        provider="greenhouse",
        slug="example",
        company="Example",
        rows=rows,
    )

    assert result.jobs == []
    assert result.skipped_invalid == 3