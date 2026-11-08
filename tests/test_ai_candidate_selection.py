"""AI capacity follows deterministic fit, independent of ATS ordering."""
import itertools
import sqlite3
import sys
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from job_hunter import cli
from job_hunter.collectors.normalize_rows import CollectionResult
from job_hunter.collectors.verify_detail import VerificationResult
from job_hunter.evaluate import evaluate
from job_hunter.model.RequirementAssessment import TechnicalAssessment
from job_hunter.models import Eligibility, Match
from job_hunter.select_ai_candidates import select_ai_candidates
from test_cli import make_args, make_job


def test_selection_is_ranked_stable_and_pure():
    items = []
    for key, score, eligibility in [
        ('low', 47, Eligibility.eligible),
        ('b-high', 65, Eligibility.review),
        ('a-high', 65, Eligibility.review),
        ('rejected', 100, Eligibility.rejected),
    ]:
        job = make_job(key, 'Backend Engineer')
        items.append((job, Match(key=job.key, eligibility=eligibility, score=score, ai_transition_score=100 - score)))
    original = [(job.model_dump(), match.model_dump()) for job, match in items]
    for permutation in itertools.permutations(items):
        for limit, expected in [(1, ['a-high']), (2, ['a-high', 'b-high']), (None, ['a-high', 'b-high', 'low'])]:
            result = select_ai_candidates(list(permutation), limit)
            assert [job.external_id for job, _ in result] == expected
    assert [(job.model_dump(), match.model_dump()) for job, match in items] == original
    assert select_ai_candidates([]) == []
    assert select_ai_candidates([items[-1]], 1) == []


@pytest.mark.parametrize('backend', ['gemini', 'agent'])
@pytest.mark.parametrize('reverse', [False, True], ids=['discovery-order', 'reversed-order'])
@pytest.mark.parametrize('fails', [False, True], ids=['success', 'failure'])
@pytest.mark.parametrize('limit', [1, None], ids=['one', 'unlimited'])
def test_main_prioritizes_unhandled_matches_and_preserves_persistence(
    tmp_path, monkeypatch, backend, reverse, fails, limit,
):
    args = make_args(tmp_path, ai=True)
    profile = {'core_skills': ['Python', 'Docker', 'PostgreSQL', 'Redis']}
    args.profile.write_text(yaml.safe_dump(profile))
    jobs = [
        make_job('low', 'Backend Engineer'),
        make_job('b-high', 'Senior Backend Engineer'),
        make_job('handled', 'Senior Backend Engineer'),
        make_job('rejected', 'Senior Frontend Developer'),
        make_job('a-high', 'Senior Backend Engineer'),
    ]
    for job in jobs:
        job.remote = True
        job.verified_live = True
        skills = 'Python' if job.external_id == 'low' else 'Python Docker PostgreSQL'
        if job.external_id in ('handled', 'rejected'):
            skills += ' Redis'
        job.description = f'{skills}. Posting {job.external_id}.'
    scores = {job.external_id: evaluate(job, profile).score for job in jobs}
    assert scores['handled'] > scores['a-high'] == scores['b-high'] > scores['low']
    with sqlite3.connect(args.database) as conn:
        cli.db_init(conn)
        cli.save_job(conn, jobs[2])
        conn.execute('UPDATE jobs SET status=? WHERE key=?', ('dismissed', jobs[2].key))
    if reverse:
        jobs.reverse()
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    monkeypatch.setattr(sys, 'argv', [
        'job-hunter', '--ai', '--ai-backend', backend, '--model', 'test-model',
        '--profile', str(args.profile), '--sources', str(args.sources),
        '--database', str(args.database), '--output', str(args.output),
        *([] if limit is None else ['--max-ai-jobs', str(limit)]),
    ])
    assessment = TechnicalAssessment(requirements=[], summary='Insufficient evidence', confidence=0.2)
    selected = AsyncMock(return_value=assessment, side_effect=RuntimeError('private provider error') if fails else None)
    other = AsyncMock()
    with (
        patch('job_hunter.cli.collect_with_diagnostics', new=AsyncMock(return_value=CollectionResult(jobs=jobs))),
        patch('job_hunter.cli.verify_detail', new=AsyncMock(return_value=VerificationResult(verified=True))),
        patch('job_hunter.cli.assess_requirements', new=selected if backend == 'gemini' else other),
        patch('job_hunter.cli.assess_requirements_agent', new=selected if backend == 'agent' else other),
        patch('job_hunter.cli.report', wraps=cli.report) as report_call,
    ):
        cli.main()
    expected = ['a-high'] if limit == 1 else [
        job.external_id for job in jobs if job.external_id not in ('handled', 'rejected')
    ]
    assert [call.args[1].split('Posting ')[1].rstrip('.') for call in selected.call_args_list] == expected
    other.assert_not_called()
    items = report_call.call_args.args[0]
    assert len(items) == 4
    for job, match in items:
        assert job.external_id != 'handled'
        assert match.score == scores[job.external_id]
        if job.external_id == 'rejected':
            assert match.eligibility == Eligibility.rejected and not match.ai_analyzed
        else:
            assert match.ai_analyzed == (job.external_id in expected and not fails)
            assert any('--max-ai-jobs limit reached' in concern for concern in match.concerns) == (job.external_id not in expected)
    with sqlite3.connect(args.database) as conn:
        persisted = dict(conn.execute('SELECT key,status FROM jobs'))
    assert len(persisted) == 5
    assert persisted['greenhouse:example:handled'] == 'dismissed'
    assert all(status == 'new' for key, status in persisted.items() if not key.endswith(':handled'))
    assert 'Jobs analyzed: 4;' in args.output.read_text()
    assert args.output.read_text().count('--max-ai-jobs limit reached') == 3 - len(expected)
    assert len(report_call.call_args.kwargs['ai_errors']) == (len(expected) if fails else 0)
