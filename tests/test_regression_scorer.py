import unittest

from job_hunter.compare_requirements import compare_requirements


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


if __name__ == '__main__':
    unittest.main()
