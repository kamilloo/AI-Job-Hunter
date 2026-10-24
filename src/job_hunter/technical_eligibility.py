from job_hunter.model.RequirementAssessment import TechnicalAssessment, RequirementStatus
from job_hunter.models import Eligibility

def technical_eligibility(
    assessment: TechnicalAssessment,
) -> Eligibility:

    mandatory = [
        requirement
        for requirement in assessment.requirements
        if requirement.mandatory
    ]

    if any(
        requirement.status == RequirementStatus.unmet
        for requirement in mandatory
    ):
        return Eligibility.review

    if any(
        requirement.status == RequirementStatus.unknown
        for requirement in mandatory
    ):
        return Eligibility.review

    return Eligibility.eligible