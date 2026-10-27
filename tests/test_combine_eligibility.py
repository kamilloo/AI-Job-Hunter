import pytest
from job_hunter.combine_eligibility import combine_eligibility
from job_hunter.models import Eligibility

@pytest.mark.parametrize(
    "deterministic, requirements, final",
    [
        (Eligibility.eligible, Eligibility.eligible, Eligibility.eligible),
        (Eligibility.eligible, Eligibility.review, Eligibility.review),
        (Eligibility.eligible, Eligibility.rejected, Eligibility.rejected),
        (Eligibility.review, Eligibility.eligible, Eligibility.review),
        (Eligibility.review, Eligibility.review, Eligibility.review),
        (Eligibility.review, Eligibility.rejected, Eligibility.rejected),
        (Eligibility.rejected, Eligibility.eligible, Eligibility.rejected),
        (Eligibility.rejected, Eligibility.review, Eligibility.rejected),
        (Eligibility.rejected, Eligibility.rejected, Eligibility.rejected),

    ]
)
def test_combine_eligibility(deterministic, requirements, final):
    """Requirement rejection assumes a confirmed mandatory failure.

    Undocumented Go experience or invented Kubernetes evidence must already
    be classified as review by the caller before reaching this combiner.
    """
    assert combine_eligibility(deterministic, requirements) == final
