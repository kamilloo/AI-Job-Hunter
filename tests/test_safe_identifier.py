import pytest

from job_hunter.safe_identifier import safe_identifier


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("greenhouse", "greenhouse"),
        ("greenhouse:example:123", "greenhouse:example:123"),
        ("broken\n## Injected heading", "invalid"),
        ("board/other", "invalid"),
        ("", "invalid"),
        (None, "invalid"),
    ],
)
def test_safe_identifier(value, expected):
    assert safe_identifier(value) == expected