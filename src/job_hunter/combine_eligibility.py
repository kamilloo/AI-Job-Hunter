from job_hunter.models import Eligibility

def combine_eligibility(
    deterministic: Eligibility,
    requirement_verification: Eligibility,
) -> Eligibility:
    """Combine deterministic eligibility with a verified requirement decision.

    Callers must use requirement_verification=rejected only for a confirmed
    failure of a mandatory requirement. Missing candidate evidence, unsupported
    claims, or quotations that fail grounding validation require review.
    An independent deterministic rejection still takes precedence over review.
    """
    if deterministic == Eligibility.rejected or requirement_verification == Eligibility.rejected:
        return Eligibility.rejected
    if deterministic == Eligibility.review or requirement_verification == Eligibility.review:
        return Eligibility.review
    return Eligibility.eligible


