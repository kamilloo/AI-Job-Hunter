"""Validate AI rubric references; these checks do not evaluate model quality."""
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "evaluations/fixtures"
JOBS = {case["id"] for case in json.loads((FIXTURES / "jobs.json").read_text())}
DETERMINISTIC = {
    case["job_id"]: case["expected_eligibility"]
    for case in json.loads((FIXTURES / "deterministic.json").read_text())
}
CASES = json.loads((FIXTURES / "ai.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["job_id"])
def test_ai_rubric_has_grounded_reference(case):
    assert case["job_id"] in JOBS
    assert case["expected_technical_fit"] in {"strong", "partial", "unknown"}
    assert case["assessment_criteria"]
    assert case["expected_deterministic_eligibility"] == DETERMINISTIC[case["job_id"]]


def test_deterministic_dataset_covers_every_snapshot_once():
    cases = json.loads((FIXTURES / "deterministic.json").read_text())
    assert len(cases) == len(DETERMINISTIC)
    assert set(DETERMINISTIC) == JOBS
