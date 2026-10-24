import re

from job_hunter.models import Eligibility


MANDATORY_OFFICE = re.compile(
    r"""
    (?:
        (?:minimum|at\s+least)\s+(?:of\s+)?
        \d+\s+days?\s+per\s+week
        |
        \d+\s+days?\s+(?:per\s+week|a\s+week)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def classify_remote(
    remote: bool | None,
    remote_claim: bool,
    description: str = "",
) -> Eligibility:

    # Hard restrictions take precedence.
    if MANDATORY_OFFICE.search(description):
        return Eligibility.rejected

    # Conflicting metadata and description.
    if remote is False and remote_claim:
        return Eligibility.review

    # Explicitly not remote.
    if remote is False:
        return Eligibility.rejected

    # Remote metadata is present.
    if remote is True:
        return Eligibility.eligible

    # Remote wording without definitive metadata.
    if remote_claim:
        return Eligibility.review

    # Insufficient evidence.
    return Eligibility.review