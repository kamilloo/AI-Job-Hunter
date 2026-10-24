import re

from job_hunter.models import Eligibility


FRANCE_ONLY = re.compile(
    r"""
    \b(?:
        remote\s+(?:within|in)\s+france\s+only
        |
        (?:must|required\s+to)\s+
        (?:reside|live|be\s+based)\s+in\s+france
        |
        france\s+only
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

SUPPORTED_LOCATION = re.compile(
    r"""
    \b(?:
        poland
        |
        polska
        |
        europe
        |
        european\s+union
        |
        eu
        |
        eea
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def classify_location(
    location: str,
    description: str,
) -> Eligibility:
    text = f"{location}\n{description}"

    # Explicit restrictions override general location mentions.
    if FRANCE_ONLY.search(text):
        return Eligibility.rejected

    if SUPPORTED_LOCATION.search(location):
        return Eligibility.eligible

    return Eligibility.review