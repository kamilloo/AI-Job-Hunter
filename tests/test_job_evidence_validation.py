import unittest

from job_hunter.validation.evidence import validate_job_evidence


class TestJobEvidenceValidation(unittest.TestCase):

    def test_exact_quote_is_valid(self):
        description = (
            "Senior backend role using PHP, Laravel, "
            "PostgreSQL, Redis, REST APIs and Docker."
        )

        result = validate_job_evidence(
            description,
            "PHP, Laravel, PostgreSQL",
        )

        self.assertTrue(result.valid)

    def test_go_quote_is_valid_even_when_candidate_lacks_go(self):
        description = (
            "TypeScript where the product lives "
            "and Go where the backend lives."
        )

        result = validate_job_evidence(
            description,
            "Go where the backend lives",
        )

        self.assertTrue(result.valid)

    def test_fabricated_quote_is_invalid(self):
        description = (
            "TypeScript where the product lives "
            "and Go where the backend lives."
        )

        result = validate_job_evidence(
            description,
            "10 years of production Go experience required",
        )

        self.assertFalse(result.valid)

    def test_paraphrase_is_not_an_exact_quote(self):
        description = (
            "Strong in Python (FastAPI or similar) "
            "and comfortable in TypeScript/JavaScript."
        )

        result = validate_job_evidence(
            description,
            "Python experience",
        )

        self.assertFalse(result.valid)

    def test_whitespace_differences_are_accepted(self):
        description = (
            "Strong in Python (FastAPI or similar)\n"
            "and comfortable in TypeScript/JavaScript."
        )

        result = validate_job_evidence(
            description,
            "Python (FastAPI or similar) and comfortable",
        )

        self.assertTrue(result.valid)

    def test_empty_evidence_is_invalid(self):
        description = "Strong in Python and TypeScript."

        result = validate_job_evidence(description, "")

        self.assertFalse(result.valid)

    def test_proxy_quote_is_valid(self):
        description = (
            "Primary stack TypeScript/Node.js, "
            "PostgreSQL, AWS, SQS, and proxy networks."
        )

        result = validate_job_evidence(
            description,
            "proxy networks",
        )

        self.assertTrue(result.valid)

    def test_rejects_plausible_but_unsupported_requirement(self):
        description = (
            "We are looking for a Senior Backend Engineer. "
            "You will build REST APIs using Python and PostgreSQL. "
            "Experience with Docker and AWS is required."
        )

        evidence = "Experience with Kubernetes is required."

        result = validate_job_evidence(description, evidence)

        self.assertFalse(result.valid)
        self.assertEqual(
            result.reason,
            "Evidence not found in job description",
        )

    def test_rejects_changed_requirement_strength(self):
        description = (
            "Experience with Go is a plus. "
            "Strong backend engineering skills are required."
        )

        result = validate_job_evidence(
            description,
            "Experience with Go is required.",
        )

        self.assertFalse(result.valid)