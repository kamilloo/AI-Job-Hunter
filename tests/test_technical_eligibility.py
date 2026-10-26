import unittest

from job_hunter.model.RequirementAssessment import (
    RequirementStatus,
    TechnicalAssessment,
    TechnicalRequirement,
)
from job_hunter.models import Eligibility
from job_hunter.technical_eligibility import technical_eligibility


def requirement(name, status, mandatory=True):
    return TechnicalRequirement(
        name=name,
        mandatory=mandatory,
        status=status,
        job_evidence=f"The role requires {name}.",
        candidate_evidence="Recorded candidate evidence.",
        explanation="Assessment based on the supplied evidence.",
    )


def assessment(*requirements):
    return TechnicalAssessment(
        requirements=list(requirements),
        summary="Technical requirements assessment.",
        confidence=0.9,
    )


class TestTechnicalEligibility(unittest.TestCase):
    def test_all_mandatory_requirements_met_are_eligible(self):
        result = technical_eligibility(assessment(
            requirement("PHP", RequirementStatus.met),
            requirement("PostgreSQL", RequirementStatus.met),
        ))
        self.assertEqual(result, Eligibility.eligible)

    def test_unmet_mandatory_requirement_requires_review(self):
        result = technical_eligibility(assessment(
            requirement("Production Go", RequirementStatus.unmet),
        ))
        self.assertEqual(result, Eligibility.review)

    def test_unknown_mandatory_requirement_requires_review(self):
        result = technical_eligibility(assessment(
            requirement("Production Go", RequirementStatus.unknown),
        ))
        self.assertEqual(result, Eligibility.review)

    def test_optional_requirements_do_not_block_eligibility(self):
        for status in RequirementStatus:
            with self.subTest(status=status):
                result = technical_eligibility(assessment(
                    requirement("PHP", RequirementStatus.met),
                    requirement("Kubernetes", status, mandatory=False),
                ))
                self.assertEqual(result, Eligibility.eligible)

    def test_only_optional_gaps_are_eligible(self):
        result = technical_eligibility(assessment(
            requirement("Go", RequirementStatus.unmet, mandatory=False),
            requirement("Kubernetes", RequirementStatus.unknown, mandatory=False),
        ))
        self.assertEqual(result, Eligibility.eligible)

    def test_other_matches_do_not_hide_mandatory_gaps(self):
        for status in (RequirementStatus.unmet, RequirementStatus.unknown):
            with self.subTest(status=status):
                result = technical_eligibility(assessment(
                    requirement("PHP", RequirementStatus.met),
                    requirement("Production Go", status),
                    requirement("Docker", RequirementStatus.met, mandatory=False),
                ))
                self.assertEqual(result, Eligibility.review)

    def test_mixed_mandatory_gaps_require_review(self):
        result = technical_eligibility(assessment(
            requirement("Go", RequirementStatus.unmet),
            requirement("Concurrency", RequirementStatus.unknown),
        ))
        self.assertEqual(result, Eligibility.review)

    def test_empty_assessment_is_eligible(self):
        self.assertEqual(technical_eligibility(assessment()), Eligibility.eligible)


if __name__ == "__main__":
    unittest.main()
