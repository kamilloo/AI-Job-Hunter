"""SQLite lifecycle checks through the CLI using only disposable state."""
import sqlite3
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml

from job_hunter import cli
from job_hunter.collectors.normalize_rows import CollectionResult
from job_hunter.collectors.verify_detail import VerificationResult
from job_hunter.model.RequirementAssessment import TechnicalAssessment
from job_hunter.models import Job


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    profile = tmp_path / 'profile.yaml'
    sources = tmp_path / 'sources.yaml'
    profile.write_text(yaml.safe_dump({
        'core_skills': ['Python'],
        'skill_experiences': [{'technology': 'Python', 'context': 'Built Python services'}],
    }))
    sources.write_text(yaml.safe_dump({'boards': [
        {'provider': 'greenhouse', 'slug': 'example', 'company': 'Example'},
    ]}))
    state = SimpleNamespace(
        database=tmp_path / 'jobs.sqlite3', output=tmp_path / 'daily.md', jobs=[],
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return state.now

    monkeypatch.setattr(cli, 'datetime', Clock)
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    monkeypatch.setattr(cli, 'collect_with_diagnostics', AsyncMock(
        side_effect=lambda *args: CollectionResult(jobs=list(state.jobs)),
    ))

    async def verify(client, job):
        job.verified_live = True
        job.verified_at = state.now.isoformat()
        return VerificationResult(verified=True)

    monkeypatch.setattr(cli, 'verify_detail', verify)
    result = TechnicalAssessment.model_validate({
        'requirements': [{
            'name': 'Python', 'mandatory': True, 'status': 'met',
            'job_evidence': 'Python backend engineering.',
            'candidate_evidence': 'Built Python services', 'explanation': '',
        }], 'summary': '', 'confidence': 0.9,
    })
    state.gemini = AsyncMock(return_value=result)
    state.agent = AsyncMock(return_value=result)
    monkeypatch.setattr(cli, 'assess_requirements', state.gemini)
    monkeypatch.setattr(cli, 'assess_requirements_agent', state.agent)

    def run(*arguments):
        monkeypatch.setattr(sys, 'argv', [
            'job-hunter', '--profile', str(profile), '--sources', str(sources),
            '--database', str(state.database), '--output', str(state.output),
            '--model', 'test-model', *arguments,
        ])
        cli.main()

    state.run = run
    return state


def job(identifier, title='Backend Engineer'):
    return Job(
        provider='greenhouse', board='example', external_id=str(identifier),
        company='Example', title=title, location='Poland', remote=True,
        description=f'Python backend engineering. Posting {identifier}.',
        url=f'https://example.com/jobs/{identifier}',
    )


def rows(database):
    # Open a separate connection after main returns: assertions verify commits,
    # not merely changes visible inside the application's own transaction.
    with sqlite3.connect(database) as connection:
        return connection.execute(
            'SELECT key,company,title,url,last_seen,status FROM jobs ORDER BY key',
        ).fetchall()


@pytest.mark.parametrize('backend', ['gemini', 'agent'])
def test_repeat_discovery_preserves_status_and_refreshes_last_seen(lifecycle, backend):
    state = lifecycle
    state.jobs = [job(i) for i in range(4)]
    # Repeated copies within one discovery also resolve to a single record.
    state.jobs.append(state.jobs[0])
    state.run()
    initial = rows(state.database)
    assert initial == [
        (f'greenhouse:example:{i}', 'Example', 'Backend Engineer',
         f'https://example.com/jobs/{i}', state.now.isoformat(), 'new')
        for i in range(4)
    ]
    statuses = ['applied', 'skipped', 'dismissed', 'new']
    with sqlite3.connect(state.database) as connection:
        for i, status in enumerate(statuses):
            connection.execute('UPDATE jobs SET status=? WHERE key=?', (status, f'greenhouse:example:{i}'))
    assessor = state.gemini if backend == 'gemini' else state.agent
    other = state.agent if backend == 'gemini' else state.gemini
    for day in (2, 3):
        state.now = datetime(2026, 1, day, tzinfo=timezone.utc)
        state.run('--ai', '--ai-backend', backend, '--max-ai-jobs', '1')
        persisted = rows(state.database)
        assert len(persisted) == 4
        assert [row[5] for row in persisted] == statuses
        assert [row[4] for row in persisted] == [state.now.isoformat()] * 4
        assert [row[:4] for row in persisted] == [row[:4] for row in initial]
        assert assessor.await_count == day - 1
        assert all('Posting 3.' in call.args[1] for call in assessor.call_args_list)
        other.assert_not_called()
        assert 'Jobs analyzed: 1;' in state.output.read_text()


@pytest.mark.parametrize('backend', ['gemini', 'agent'])
def test_rejection_ai_failure_and_budget_skips_are_all_persisted(lifecycle, backend):
    state = lifecycle
    state.jobs = [job(0, 'Frontend Developer'), *[job(i) for i in range(1, 4)]]
    assessor = state.gemini if backend == 'gemini' else state.agent
    other = state.agent if backend == 'gemini' else state.gemini
    assessor.side_effect = RuntimeError('private provider error')
    state.run('--ai', '--ai-backend', backend, '--max-ai-jobs', '1')
    persisted = rows(state.database)
    assert len(persisted) == 4
    assert [row[0] for row in persisted] == [posting.key for posting in state.jobs]
    assert [row[5] for row in persisted] == ['new'] * 4
    assert [row[4] for row in persisted] == [state.now.isoformat()] * 4
    assessor.assert_awaited_once()
    assert 'Posting 1.' in assessor.call_args.args[1]
    other.assert_not_called()
    report = state.output.read_text()
    assert 'eligible: 0; review: 3; rejected: 1' in report
    assert report.count('--max-ai-jobs limit reached') == 2
    assert 'RuntimeError' in report
    assert 'private provider error' not in report
