import unittest
import json
import pytest
from pathlib import Path
from job_hunter.models import Job, Eligibility
from job_hunter.evaluate import evaluate, ROLE
from job_hunter.classify_location import classify_location

FIXTURES = json.loads((Path(__file__).parent.parent / "evaluations/fixtures/jobs.json").read_text())


class TestGoldenDataset(unittest.TestCase):
    def _profile(self):
        return {
            "location": "Toronto",
            "remote": True,
            "experience_level": ["junior", "mid", "senior"],
            "job_type": ["full-time", "contract"],
            "compensation": 70000
        }

    def test_expected_eligibility(self):
        for case in FIXTURES:
            with self.subTest(id=case["id"]):
                job = Job(**case["job"])
                match = evaluate(job,self._profile())
                if case["id"] in ("E02", "E05", "E07", "E12"):
                    print(f"\n{case['id']}: {job.title}")
                    print("Expected:", case["expected_eligibility"])
                    print("Predicted:", match.eligibility.value)
                    print("Reasons:", match.reasons)
                    print("Concerns:", match.concerns)

                self.assertEqual(
                    Eligibility(case["expected_eligibility"]).value,
                    match.eligibility.value,
                    msg=(
                        f"\nFixture: {case['id']}"
                        f"\nCompany: {job.company}"
                        f"\nJob: {job.title}"
                        f"\nExpected: {case['expected_eligibility']}"
                        f"\nPredicted: {match.eligibility.value}"
                        f"\nReasons: {match.reasons}"
                        f"\nConcerns: {match.concerns}"
                    ),
                )

    def test_formal_management_requires_review(self):
        case = next(c for c in FIXTURES if c["id"] == "E08")
        job = Job(**case["job"])

        match = evaluate(job, self._profile())

        assert match.eligibility == Eligibility.review
        assert any(
            "people-management" in concern.lower()
            for concern in match.concerns
        )

    def test_e03_francy_only(self):
        case = next(c for c in FIXTURES if c["id"] == "E03")
        job = Job(**case["job"])
        assert classify_location(
            job.location,
            job.description
        ) == Eligibility.rejected

if __name__ == '__main__':
    unittest.main()
