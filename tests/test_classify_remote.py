import pytest
from job_hunter.evaluate import classify_remote
from job_hunter.models import Eligibility


@pytest.mark.parametrize(
    "remote, remote_claim, expected",
    [
        (True, True, "eligible"),
        (False, False, "rejected"),
        (None, False, "review"),
        (False, True, "review"),
    ],
)
def test_remote_classification(remote, remote_claim, expected):
    assert classify_remote(remote, remote_claim) == expected

def test_box_mandatory_office_rejected():
    description = (
        "Boxers are expected to work from their "
        "assigned office a minimum of 3 days per week."
    )

    result = classify_remote(
        remote=None,
        remote_claim=False,
        description=description,
    )

    assert result == Eligibility.rejected

def test_office_requirement_overrides_remote_flag():
    description = (
        "Employees must work from their assigned "
        "office at least 3 days per week."
    )

    result = classify_remote(
        remote=True,
        remote_claim=True,
        description=description,
    )

    assert result == Eligibility.rejected