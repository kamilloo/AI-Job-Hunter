import unittest

from evaluations.run_requirements_evaluation import evaluate_assessment
from job_hunter.model.CandidateExperience import CandidateExperience, CandidateProfile
from job_hunter.model.RequirementAssessment import TechnicalAssessment
from job_hunter.compare_requirements import compare_requirements, compare_requirement_fields
from job_hunter.validation.evidence import validate_job_evidence
from job_hunter.validation.validate_candidate_evidence import validate_candidate_evidence


class RegressionScorerTestCase(unittest.TestCase):
    def test_one_expected_requirement_one_matching_actual_requirement(self):
        expected = {
            "name": "AWS SQS",
            "mandatory": True,
            "status": "unknown",
            "candidate_evidence": "",
        }
        actual = {
            "name": "AWS SQS",
            "mandatory": True,
            "status": "unknown",
            "candidate_evidence": "",
        }

        assert compare_requirements([expected], [actual]) is True

    def test_wrong_status_fails(self):
        expected = {
            "name": "AWS SQS",
            "mandatory": True,
            "status": "unknown",
            "candidate_evidence": "",
        }
        actual = {
            "name": "AWS SQS",
            "mandatory": True,
            "status": "met",
            "candidate_evidence": "",
        }

        assert compare_requirements([expected], [actual]) is False

    def test_one_compabined_requirement_vs_two_extracted_requirements(self):
        expected = [
            {
                "name": "Professional TypeScript and Node.js experience",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            }
        ]
        actual = [
            {
                "name": "TypeScript",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            },
            {
                "name": "Node.js",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            },
        ]
        assert compare_requirements(
            expected,
            actual,
            expected_skills={"TypeScript", "Node.js"},
        ) is True

    def test_split_requirements_missing_nodejs_fails(self):
        expected = [
            {
                "name": "Professional TypeScript and Node.js experience",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            }
        ]
        actual = [
            {
                "name": "TypeScript",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            },
            {
                "name": "Node.js",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            },
        ]
        assert compare_requirements(
            expected,
            actual[:1],
            expected_skills={"TypeScript", "Node.js"},
        ) is False

    def test_split_requirements_wrong_nodejs_status_fails(self):
        expected = [
            {
                "name": "Professional TypeScript and Node.js experience",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            }
        ]
        actual = [
            {
                "name": "TypeScript",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            },
            {
                "name": "Node.js",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            },
        ]
        wrong = [dict(req) for req in actual]
        wrong[1]["status"] = "met"

        assert compare_requirements(
            expected,
            wrong,
            expected_skills={"TypeScript", "Node.js"},
        ) is False

    def test_unsupported_candidate_evidence(self):
        expected = [
            {
                "name": "Professional TypeScript and Node.js experience",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            }
        ]
        actual = [
            {
                "name": "TypeScript",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            },
            {
                "name": "Node.js",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            },
        ]
        wrong = [dict(req) for req in actual]
        wrong[1]["candidate_evidence"] = (
            "5 years of production Node.js experience."
        )

        assert compare_requirements(
            expected,
            wrong,
            expected_skills={"TypeScript", "Node.js"},
        ) is False


    def test_optional_requirement_incorrectly_classified_as_mandatory(self):
        expected = [
            {
                "name": "Professional TypeScript and Node.js experience",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            }
        ]
        actual = [
            {
                "name": "TypeScript",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            },
            {
                "name": "Node.js",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            },
        ]
        wrong = [dict(req) for req in actual]
        wrong[1]["mandatory"] = False

        assert compare_requirements(
            expected,
            wrong,
            expected_skills={"TypeScript", "Node.js"},
        ) is False

    def test_full_stack_name_variant_passes(self):
        expected = [{
            "name": "Professional full-stack engineering experience",
            "mandatory": True,
            "status": "unknown",
            "candidate_evidence": "",
        }]

        actual = [{
            "name": "Professional full-stack engineering experience",
            "mandatory": True,
            "status": "unknown",
            "candidate_evidence": "",
        }]

        assert compare_requirements(
            expected,
            actual,
            expected_skills={"full-stack"},
        )

    def test_combined_actual_requirement_passes(self):
        expected = [
            {
                "name": "TypeScript",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            },
            {
                "name": "Node.js",
                "mandatory": True,
                "status": "unknown",
                "candidate_evidence": "",
            },
        ]

        actual = [{
            "name": "TypeScript and Node.js",
            "mandatory": True,
            "status": "unknown",
            "candidate_evidence": "",
        }]

        assert compare_requirements(
            expected,
            actual,
            expected_skills={"TypeScript", "Node.js"},
        )

    def test_verified_experience_with_evidence_passes(self):
        expected = {
            "mandatory": True,
            "status": "met",
            "candidate_evidence": "__nonempty__",
        }
        actual = {
            "mandatory": True,
            "status": "met",
            "candidate_evidence": "Built and operated production AWS SQS queues.",
        }

        assert compare_requirement_fields(expected, actual)

    def test_verified_experience_without_evidence_fails(self):
        expected = {
            "mandatory": True,
            "status": "met",
            "candidate_evidence": "__nonempty__",
        }
        actual = {
            "mandatory": True,
            "status": "met",
            "candidate_evidence": "",
        }

        assert not compare_requirement_fields(expected, actual)

    def test_validate_exact_job_evidence(self):
        job_description = (
            "Professional production experience with AWS SQS is required "
            "for building and operating asynchronous processing pipelines."
        )

        evidence = (
            "Professional production experience with AWS SQS is required "
            "for building and operating asynchronous processing pipelines."
        )

        result = validate_job_evidence(job_description, evidence)

        assert result.valid is True

    def test_reject_invented_job_evidence(self):
        job_description = (
            "Professional production experience with AWS SQS is required "
            "for building and operating asynchronous processing pipelines."
        )

        evidence = "At least 10 years of AWS SQS experience is required."

        result = validate_job_evidence(job_description, evidence)

        assert result.valid is False
        assert result.reason == "Evidence not found in job description"

    def test_fabricated_candidate_evidence_fails_overall_evaluation(self):

        job_description = (
            "Professional production experience with AWS SQS is required."
        )

        actual = {
            "name": "AWS SQS",
            "mandatory": True,
            "status": "met",
            "job_evidence": job_description,
            "candidate_evidence": "10 years operating AWS SQS at Google.",
        }

        expected = {
            "name": "AWS SQS",
            "mandatory": True,
            "status": "met",
            "candidate_evidence": "__nonempty__",
        }

        candidate = CandidateProfile(skill_experiences=[
                CandidateExperience(
                    technology="AWS SQS",
                    context="Built and operated AWS SQS queues in production.",
                    production=True,
                    years=3,
                ),
        ])
        case = {
            "expected_requirements": [expected],
            "expected_skills": ["AWS SQS"],
            "job_description": job_description,
            "candidate": candidate.model_dump(mode="json"),
        }

        fabricated_assessment = TechnicalAssessment(
            requirements=[{**actual, "explanation": "Claims production experience."}],
            summary="Claims production experience.",
            confidence=0.9,
        )

        result = evaluate_assessment(
            fabricated_assessment, case,
        )

        assert result["classification_passed"] is True
        assert result["grounding_passed"] is True
        assert result["candidate_grounding_passed"] is False
        assert result["passed"] is False

        valid_assessment = fabricated_assessment.model_copy(deep=True)

        valid_assessment.requirements[0].candidate_evidence = (
            "Built and operated AWS SQS queues in production."
        )

        valid_result = evaluate_assessment(valid_assessment, case)

        assert valid_result["classification_passed"] is True
        assert valid_result["grounding_passed"] is True
        assert valid_result["candidate_grounding_passed"] is True
        assert valid_result["passed"] is True

if __name__ == '__main__':
    unittest.main()
