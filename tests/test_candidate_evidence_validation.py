import unittest

from job_hunter.validation.validate_candidate_evidence import validate_candidate_evidence


class TestCandidateEvidenceValidation(unittest.TestCase):

    def test_candidate_evidence_matches_experience(self):
        contexts = [
            "Built and operated AWS SQS queues in production."
        ]

        result = validate_candidate_evidence(
            contexts,
            "Built and operated AWS SQS queues in production.",
        )

        assert result.valid is True

    def test_candidate_evidence_rejects_fabrication(self):
        contexts = [
            "Built and operated AWS SQS queues in production."
        ]

        result = validate_candidate_evidence(
            contexts,
            "10 years operating AWS SQS at Google.",
        )

        assert result.valid is False

    def test_candidate_evidence_rejects_cross_record_quotation(self):
        contexts = [
            "Built AWS SQS queues.",
            "Operated PostgreSQL databases.",
        ]

        result = validate_candidate_evidence(
            contexts,
            "AWS SQS queues. Operated PostgreSQL",
        )

        assert result.valid is False
