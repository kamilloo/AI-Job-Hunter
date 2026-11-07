"""Candidate quotation policy shared by CLI and AI evaluation."""
import pytest

from evaluations.run_requirements_evaluation import candidate_grounding_passes
from job_hunter.model.RequirementAssessment import (
    RequirementStatus, TechnicalAssessment, TechnicalRequirement,
)
from job_hunter.models import Eligibility
from job_hunter.technical_eligibility import grounded_technical_eligibility


@pytest.mark.parametrize('status', list(RequirementStatus))
@pytest.mark.parametrize('evidence,quotation_valid', [
    pytest.param('', None, id='empty'),
    pytest.param(' \n\t ', None, id='whitespace'),
    pytest.param('Built Python services', True, id='grounded'),
    pytest.param('Invented production experience', False, id='ungrounded'),
])
@pytest.mark.parametrize('mandatory', [True, False], ids=['mandatory', 'preferred'])
def test_candidate_quotation_policy_matches_focused_evaluator(
    status, evidence, quotation_valid, mandatory,
):
    candidate = {'skill_experiences': [
        {'technology': 'Python', 'context': 'Built Python services'},
    ]}
    job_description = 'Python experience is required. Docker experience is preferred.'
    # A grounded mandatory control prevents empty/no-mandatory rules from
    # masking the quotation policy, especially for unknown preferred skills.
    control = TechnicalRequirement(
        name='Python', mandatory=True, status=RequirementStatus.met,
        job_evidence='Python experience is required.',
        candidate_evidence='Built Python services', explanation='',
    )
    subject = TechnicalRequirement(
        name='Docker', mandatory=mandatory, status=status,
        job_evidence='Docker experience is preferred.',
        candidate_evidence=evidence, explanation='',
    )
    assessment = TechnicalAssessment(
        requirements=[control, subject], summary='', confidence=0.9,
    )
    candidate_grounded = (
        quotation_valid if quotation_valid is not None
        else status == RequirementStatus.unknown
    )
    assert candidate_grounding_passes(candidate, assessment.requirements) == candidate_grounded
    expected = (
        Eligibility.eligible
        if candidate_grounded and (not mandatory or status == RequirementStatus.met)
        else Eligibility.review
    )
    assert grounded_technical_eligibility(assessment, candidate, job_description) == expected
