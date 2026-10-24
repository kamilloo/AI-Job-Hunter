import pytest

from job_hunter.models import Eligibility
from job_hunter.models import EligibilityFactors
from job_hunter.evaluate import aggregate_eligibility


@pytest.mark.parametrize(
    "location_result, remote_result, expected",
    [
        (Eligibility.rejected, Eligibility.eligible, Eligibility.rejected),
        (Eligibility.review, Eligibility.eligible, Eligibility.review),
        (Eligibility.eligible, Eligibility.rejected, Eligibility.rejected),
        (Eligibility.eligible, Eligibility.review, Eligibility.review),
        (Eligibility.eligible, Eligibility.eligible, Eligibility.eligible),
    ],
)
def test_eligibility_aggregation(
    location_result, remote_result, expected
):
    assert aggregate_eligibility(
        EligibilityFactors(
            location=location_result,
            remote=remote_result,
            technical=Eligibility.eligible,
            compensation=Eligibility.eligible,
            ats=Eligibility.eligible
        )
    ) == expected

def test_unknown_technical_requirement_requires_review():
    factors = EligibilityFactors(
        location=Eligibility.eligible,
        remote=Eligibility.eligible,
        technical=Eligibility.review,
        compensation=Eligibility.eligible,
        ats=Eligibility.eligible,
    )

    assert aggregate_eligibility(factors) == Eligibility.review