"""Offline checks of regression scoring; model behavior requires the live runner."""
import json

import pytest

from evaluations.common import ROOT
from evaluations.run_requirements_evaluation import matches_reference
from job_hunter.model.RequirementAssessment import TechnicalAssessment


CASE = json.loads((ROOT / 'evaluations/fixtures/requirements_ai.json').read_text())[0]


@pytest.mark.parametrize(('overrides', 'passed'), [
    ({}, True),
    ({'status': 'met'}, False),
    ({'status': 'unmet'}, False),
    ({'mandatory': False}, False),
    ({'candidate_evidence': 'senior full-stack engineer'}, False),
])
def test_scores_missing_experience_regression(overrides, passed):
    requirement = {
        **CASE['expected_requirements'][0],
        'job_evidence': CASE['job_description'],
        **overrides,
    }
    assessment = TechnicalAssessment(
        requirements=[requirement], summary='No documented experience.', confidence=0.9,
    )
    assert matches_reference(assessment, CASE['expected_requirements']) is passed


def test_missing_requirements_fail_regression():
    assessment = TechnicalAssessment(requirements=[], summary='', confidence=0.9)
    assert not matches_reference(assessment, CASE['expected_requirements'])
