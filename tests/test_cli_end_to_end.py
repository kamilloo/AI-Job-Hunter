"""Run the actual CLI with temporary state and mocked external boundaries."""
import sqlite3
import sys
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
import yaml

from job_hunter.cli import main
from job_hunter.model.RequirementAssessment import TechnicalAssessment


@pytest.mark.parametrize('backend', ['gemini', 'agent'])
@pytest.mark.parametrize('limit', [None, 1, 2], ids=['unlimited', 'one', 'two'])
@pytest.mark.parametrize('first_call_fails', [False, True], ids=['success', 'partial-failure'])
def test_main_discovery_assessment_database_and_report(
    tmp_path, monkeypatch, capsys, backend, limit, first_call_fails,
):
    profile = tmp_path / 'profile.yaml'
    sources = tmp_path / 'sources.yaml'
    database = tmp_path / 'jobs.sqlite3'
    output = tmp_path / 'reports' / 'daily.md'
    profile.write_text(yaml.safe_dump({
        'core_skills': ['Python'],
        'skill_experiences': [{'technology': 'Python', 'context': 'Built Python services'}],
    }))
    sources.write_text(yaml.safe_dump({'boards': [
        {'provider': 'greenhouse', 'slug': 'excluded', 'company': 'Excluded'},
        {'provider': 'ashby', 'slug': 'example', 'company': 'Example'},
    ]}))
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-test-key')
    monkeypatch.setattr(sys, 'argv', [
        'job-hunter', '--ai', '--ai-backend', backend, '--model', 'test-model',
        '--profile', str(profile), '--sources', str(sources),
        '--database', str(database), '--output', str(output),
        *([] if limit is None else ['--max-ai-jobs', str(limit)]),
    ])
    assessment = TechnicalAssessment.model_validate({
        'requirements': [{
            'name': 'Python', 'mandatory': True, 'status': 'met',
            'job_evidence': 'Python backend engineering.',
            'candidate_evidence': 'Built Python services', 'explanation': '',
        }],
        'summary': '', 'confidence': 0.9,
    })
    outcomes = [RuntimeError('private provider response') if first_call_fails else assessment,
                assessment, assessment]
    selected = AsyncMock(side_effect=outcomes)
    unselected = AsyncMock(side_effect=AssertionError('Wrong backend selected'))
    with (
        respx.mock(assert_all_called=True, assert_all_mocked=True) as router,
        patch('job_hunter.cli.assess_requirements', new=selected if backend == 'gemini' else unselected),
        patch('job_hunter.cli.assess_requirements_agent', new=selected if backend == 'agent' else unselected),
    ):
        collection = router.get('https://boards-api.greenhouse.io/v1/boards/excluded/jobs').mock(
            return_value=httpx.Response(200, json={'jobs': [{
                'id': 0, 'title': 'Frontend Developer', 'location': {'name': 'Remote - Poland'},
                'content': 'Python backend engineering.', 'absolute_url': 'https://example.com/jobs/0',
            }]}),
        )
        detail = router.get('https://boards-api.greenhouse.io/v1/boards/excluded/jobs/0').mock(
            return_value=httpx.Response(200, json={'id': 0}),
        )
        discovery = router.get('https://api.ashbyhq.com/posting-api/job-board/example').mock(
            return_value=httpx.Response(200, json={'jobs': [{
                'id': str(i), 'title': f'Senior Backend Engineer {i}',
                'location': 'Poland', 'isRemote': True,
                'descriptionPlain': 'Python backend engineering.',
                'jobUrl': f'https://example.com/jobs/{i}',
            } for i in range(1, 4)]}),
        )
        main()
        assert collection.call_count == discovery.call_count == detail.call_count == 1
    attempts = 3 if limit is None else limit
    assert selected.await_count == attempts
    unselected.assert_not_called()
    assert all(call.args[2] == 'test-model' for call in selected.call_args_list)
    assert database.is_file() and output.is_file()
    with sqlite3.connect(database) as connection:
        rows = connection.execute('SELECT key,status FROM jobs ORDER BY key').fetchall()
    assert rows == [(f'ashby:example:{i}', 'new') for i in range(1, 4)] + [('greenhouse:excluded:0', 'new')]
    markdown = output.read_text()
    successful = attempts - int(first_call_fails)
    assert f'eligible: {successful}; review: {3 - successful}; rejected: 1' in markdown
    assert markdown.count('**AI analyzed:** True') == successful
    assert markdown.count('--max-ai-jobs limit reached') == 3 - attempts
    assert markdown.count(f'**AI backend:** {backend}') == attempts
    assert markdown.count('**Verified ATS detail:** True') == 4
    assert 'Status: complete' in markdown
    assert 'Frontend Developer' in markdown
    assert all(f'Senior Backend Engineer {i}' in markdown for i in range(1, 4))
    assert ('## AI analysis errors' in markdown) == first_call_fails
    if first_call_fails:
        assert 'RuntimeError' in markdown
        assert 'AI analysis failed; technical eligibility requires review' in markdown
    console = capsys.readouterr().out
    assert f'4 results, {int(first_call_fails)} warnings' in console
    assert 'private provider response' not in markdown + console
    assert 'fake-test-key' not in markdown + console
