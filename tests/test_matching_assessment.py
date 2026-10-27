import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from job_hunter.model.RequirementAssessment import MatchingAssessment, TechnicalFit
from job_hunter.models import Eligibility


class TestMatchingAssessment(unittest.TestCase):

    def test_invalid_technical_fit_label_raise_validation_error(self):
        with self.assertRaises(ValidationError) as context:
            MatchingAssessment(
                technical_fit="invalid_label",
                requirement_verification=Eligibility.review,
                final_eligibility=Eligibility.review
            )
        errors = context.exception.errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["loc"], ("technical_fit",))
        self.assertEqual(errors[0]["type"], "enum")
        self.assertEqual(errors[0]["input"], "invalid_label")

    def test_matching_assessment_accepts_golden_cases(self):
        fixture = (
                Path(__file__).resolve().parents[1]
                / "evaluations"
                / "fixtures"
                / "matching_assessment.json"
        )

        cases = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertTrue(cases)

        for case in cases:
            with self.subTest(job_id=case["job_id"]):
                match = MatchingAssessment.model_validate(case)

                self.assertEqual(
                    match.technical_fit.value,
                    case["technical_fit"],
                )
                self.assertEqual(
                    match.requirement_verification.value,
                    case["requirement_verification"],
                )
                self.assertEqual(
                    match.final_eligibility.value,
                    case["final_eligibility"],
                )

    def test_strong_fit_can_require_manual_review(self):
        match = MatchingAssessment(
            technical_fit=TechnicalFit.strong,
            requirement_verification=Eligibility.review,
            final_eligibility=Eligibility.review,
        )

        self.assertEqual(match.technical_fit, TechnicalFit.strong)
        self.assertEqual(
            match.requirement_verification,
            Eligibility.review,
        )
        self.assertEqual(
            match.final_eligibility,
            Eligibility.review,
        )
