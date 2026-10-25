import pytest

from job_hunter.classify_location import classify_location
from job_hunter.models import Eligibility


@pytest.mark.parametrize(
    "location, description, expected",
    [
        (
            "France",
            "Remote within France only.",
            Eligibility.rejected,
        ),
        (
            "Paris, France",
            "Candidates must reside in France.",
            Eligibility.rejected,
        ),
        (
            "Remote - Poland",
            "Fully remote position for candidates in Poland.",
            Eligibility.eligible,
        ),
        (
            "Europe",
            "Our headquarters are located in France.",
            Eligibility.eligible,
        ),
    ],
)
def test_location_restrictions(location, description, expected):
    assert classify_location(location, description) == expected