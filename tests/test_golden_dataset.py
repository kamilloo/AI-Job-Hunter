import unittest
import json
import pytest
from pathlib import Path
from job_hunter.models import Job, Eligibility
from job_hunter.evaluate import evaluate, ROLE

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
                if case["id"] == "E08":
                    print("TITLE:", job.title)
                    print("ROLE MATCH:", bool(ROLE.search(job.title)))
                    print("REMOTE:", job.remote)
                    print("VERIFIED:", job.verified_live)
                    print("RESULT:", match.eligibility.value)
                    print("CONCERNS:", match.concerns)

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

if __name__ == '__main__':
    unittest.main()
