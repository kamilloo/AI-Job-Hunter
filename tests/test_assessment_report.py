"""Grounded AI details remain inspectable without implying semantic proof."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from job_hunter.cli import run, report
from job_hunter.collectors.normalize_rows import CollectionResult
from job_hunter.collectors.verify_detail import VerificationResult
from job_hunter.evaluate import evaluate
from job_hunter.model.RequirementAssessment import TechnicalAssessment
from job_hunter.technical_eligibility import grounded_technical_eligibility
from test_cli import make_args, make_job


PROFILE = {'skill_experiences': [{'technology': 'Python', 'context': 'Built Python services'}]}
DESCRIPTION = 'Python required. Go required. Docker preferred.'


def assessment():
    return TechnicalAssessment.model_validate({
        'requirements': [
            {'name': 'Python', 'mandatory': True, 'status': 'met',
             'job_evidence': 'Python required.', 'candidate_evidence': 'Built Python services', 'explanation': 'Direct overlap'},
            {'name': 'Go', 'mandatory': True, 'status': 'unknown',
             'job_evidence': 'Invented job quotation', 'candidate_evidence': '', 'explanation': 'Missing direct evidence'},
            {'name': 'Docker', 'mandatory': False, 'status': 'unmet',
             'job_evidence': 'Docker preferred.', 'candidate_evidence': 'Invented candidate quotation', 'explanation': 'Model claims a gap'},
        ], 'summary': 'Review technical gaps', 'confidence': 0.75, 'technical_fit': 'partial',
    })


@pytest.mark.parametrize('backend', ['gemini', 'agent'])
def test_completed_assessment_is_retained_and_rendered(tmp_path, backend):
    args = make_args(tmp_path, ai=True)
    args.ai_backend = backend
    args.profile.write_text(yaml.safe_dump(PROFILE))
    job = make_job('1', 'Backend Engineer')
    job.description = DESCRIPTION
    job.remote = True
    job.verified_live = True
    with (
        patch('job_hunter.cli.collect_with_diagnostics', new=AsyncMock(return_value=CollectionResult(jobs=[job]))),
        patch('job_hunter.cli.verify_detail', new=AsyncMock(return_value=VerificationResult(verified=True))),
        patch('job_hunter.cli.assess_requirements', new=AsyncMock(return_value=assessment())) as gemini,
        patch('job_hunter.cli.assess_requirements_agent', new=AsyncMock(return_value=assessment())) as agent,
    ):
        asyncio.run(run(args))
    assert (gemini.await_count, agent.await_count) == ((1, 0) if backend == 'gemini' else (0, 1))
    content = args.output.read_text()
    assert f'**AI backend:** {backend}' in content
    assert 'Keep this report local' in content
    assert '**Technical fit (model assessment):** Partial' in content
    assert '**Model confidence:** 0.75' in content
    assert '| Python | Mandatory | Met | Yes | Yes |' in content
    assert '| Go | Mandatory | Unknown | No | Not established |' in content
    assert '| Docker | Preferred | Unmet | Yes | No |' in content
    assert '**Candidate evidence (model quotation):** Not established' in content
    assert '**Employer quotation provenance:** No — Evidence not found in job description' in content
    assert '**Model explanation (unverified):** Missing direct evidence' in content
    assert 'source provenance only' in content and 'do not prove semantic suitability' in content
    assert '<summary>Evidence details (3 requirements)</summary>' in content
    assert 'eligible: 0; review: 1; rejected: 0' in content


@pytest.mark.parametrize('backend', ['gemini', 'agent'])
@pytest.mark.parametrize('state', ['failed', 'limited', 'rejected', 'disabled'])
def test_no_assessment_details_are_invented(tmp_path, backend, state):
    args = make_args(tmp_path, ai=state != 'disabled')
    args.ai_backend = backend
    if state == 'limited':
        args.max_ai_jobs = 1
    jobs = [make_job(str(i), 'Frontend Developer' if state == 'rejected' else 'Backend Engineer')
            for i in range(2 if state == 'limited' else 1)]
    assessor = AsyncMock(return_value=assessment(), side_effect=RuntimeError('private') if state == 'failed' else None)
    with (
        patch('job_hunter.cli.collect_with_diagnostics', new=AsyncMock(return_value=CollectionResult(jobs=jobs))),
        patch('job_hunter.cli.verify_detail', new=AsyncMock(return_value=VerificationResult(verified=True))),
        patch('job_hunter.cli.assess_requirements_agent' if backend == 'agent' else 'job_hunter.cli.assess_requirements', new=assessor),
    ):
        asyncio.run(run(args))
    content = args.output.read_text()
    assert content.count('#### Technical requirements') == (1 if state == 'limited' else 0)
    if state == 'limited':
        assert '--max-ai-jobs limit reached' in content
    if state == 'failed':
        assert 'RuntimeError' in content and 'AI analysis failed' in content
        assert 'private' not in content
    if state == 'rejected':
        assert 'rejected: 1' in content
    assert assessor.await_count == (0 if state in ('rejected', 'disabled') else 1)


def test_untrusted_markdown_and_html_are_literal_text(tmp_path):
    job = make_job('1', 'Backend [click](https://bad.test) <script>')
    job.company = '**fake** | company\n## heading'
    job.description = DESCRIPTION
    match = evaluate(job, PROFILE)
    match.ai_analyzed = True
    output = assessment()
    payload = '[click](https://bad.test) | **bold** `code` <script>\n## heading\n</details>'
    output.requirements[0].name = payload
    output.requirements[0].job_evidence = payload
    output.requirements[0].candidate_evidence = payload
    output.requirements[0].explanation = payload
    output.summary = payload
    grounded_technical_eligibility(output, PROFILE, DESCRIPTION)
    original = match.model_dump()
    path = tmp_path / 'report.md'
    report([(job, match)], [], path, ai_assessments={job.key: output}, candidate_contexts=['Built Python services'])
    content = path.read_text()
    assert '<script>' not in content
    assert '[click](https://bad.test)' not in content
    assert '\n## heading' not in content
    assert '&lt;script&gt;' in content
    assert r'\[click\]\(https://bad.test\)' in content
    assert r'\| \*\*bold\*\* \`code\`' in content
    assert content.count('</details>') == 1
    assert match.model_dump() == original  # Reporting never changes eligibility.


def test_missing_fit_empty_requirements_and_unchecked_provenance(tmp_path):
    job = make_job('1', 'Backend Engineer')
    match = evaluate(job, PROFILE)
    match.ai_analyzed = True
    path = tmp_path / 'report.md'
    output = TechnicalAssessment(requirements=[], summary='', confidence=0)
    report([(job, match)], [], path, ai_assessments={job.key: output})
    assert 'No technical requirements returned' in path.read_text()
    assert '**Technical fit' not in path.read_text()
    output = assessment()
    # No validators have run; never promote model-provided text into a pass.
    report([(job, match)], [], path, ai_assessments={job.key: output})
    assert '| Python | Mandatory | Met | Not checked | Not checked |' in path.read_text()


def test_model_supplied_provenance_is_not_reported_as_a_completed_check(tmp_path):
    args = make_args(tmp_path, ai=True)
    output = assessment()
    for requirement in output.requirements:
        requirement.mandatory = False
    # The eligibility validator returns early for an all-preferred assessment.
    # A provider-supplied provenance claim must not masquerade as its result.
    from job_hunter.validation.evidence import EvidenceValidation
    output.requirements[0].evidence_validation = EvidenceValidation(True, 'Model claims verified')
    with (
        patch('job_hunter.cli.collect_with_diagnostics', new=AsyncMock(return_value=CollectionResult(jobs=[make_job('1', 'Backend Engineer')]))),
        patch('job_hunter.cli.verify_detail', new=AsyncMock(return_value=VerificationResult(verified=True))),
        patch('job_hunter.cli.assess_requirements', new=AsyncMock(return_value=output)),
    ):
        asyncio.run(run(args))
    content = args.output.read_text()
    assert '| Python | Preferred | Met | Not checked | No |' in content
    assert 'Model claims verified' not in content
    assert 'eligible: 0; review: 1; rejected: 0' in content
