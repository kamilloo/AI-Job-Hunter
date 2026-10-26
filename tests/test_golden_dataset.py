"""Offline golden tests cover deterministic gates, not model judgment."""
import json
from pathlib import Path

import pytest
import yaml

from job_hunter.classify_location import classify_location
from job_hunter.evaluate import evaluate
from job_hunter.models import Eligibility, Job

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evaluations/fixtures"
JOBS = {case["id"]: case for case in json.loads((FIXTURES / "jobs.json").read_text())}
CASES = json.loads((FIXTURES / "deterministic.json").read_text())
PROFILE = yaml.safe_load((ROOT / "config/profile.yaml").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["job_id"])
def test_expected_eligibility(case):
    job = Job(**JOBS[case["job_id"]]["job"])
    match = evaluate(job, PROFILE)
    assert match.eligibility == Eligibility(case["expected_eligibility"]), (
        f"{case['job_id']}: {job.title}\n"
        f"Reasons: {match.reasons}\nConcerns: {match.concerns}"
    )


def test_formal_management_requires_review():
    match = evaluate(Job(**JOBS["E08"]["job"]), PROFILE)
    assert match.eligibility == Eligibility.review
    assert any("people-management" in concern.lower() for concern in match.concerns)


def test_france_only_rejected():
    job = Job(**JOBS["E03"]["job"])
    assert classify_location(job.location, job.description) == Eligibility.rejected
