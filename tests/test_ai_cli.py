"""Offline regression coverage for the actual CLI analysis adapter."""
import asyncio
import sys
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from job_hunter.agents.requirements_agent import gemini_config
from job_hunter.technical_eligibility import grounded_technical_eligibility
from job_hunter.combine_eligibility import combine_eligibility
from job_hunter.cli import main, run
from job_hunter.evaluate import evaluate
from job_hunter.model.RequirementAssessment import TechnicalAssessment, RequirementStatus
from job_hunter.models import Eligibility
from test_cli import make_args, make_job
from job_hunter.collectors.normalize_rows import CollectionResult
from job_hunter.collectors.verify_detail import VerificationResult

PROFILE = {"skill_experiences": [{"technology": "Python", "context": "Built Python services", "production": True}], "core_skills": ["Python"]}


def assessment(**changes):
    value = {"requirements": [{"name": "Python", "mandatory": True, "status": "met", "job_evidence": "Python backend engineering.", "candidate_evidence": "Built Python services", "explanation": "Evidence matches"}], "summary": "Fit", "confidence": 0.9}
    value.update(changes)
    return TechnicalAssessment.model_validate(value)


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)


def test_successful_grounded_assessment():
    assert grounded_technical_eligibility(assessment(), PROFILE, "Python backend engineering.") == Eligibility.eligible


@pytest.mark.parametrize("kind", ["unknown", "unmet", "candidate", "job", "empty", "preferred"])
def test_uncertain_or_ungrounded_requires_review(kind):
    output = assessment()
    if kind in ("unknown", "unmet"):
        output.requirements[0].status = RequirementStatus(kind)
    elif kind == "candidate":
        output.requirements[0].candidate_evidence = "Invented experience"
    elif kind == "job":
        output.requirements[0].job_evidence = "Invented requirement"
    elif kind == "preferred":
        output.requirements[0].mandatory = False
    else:
        output.requirements = []
    assert grounded_technical_eligibility(output, PROFILE, "Python backend engineering.") == Eligibility.review


def test_review_cannot_be_upgraded():
    technical = grounded_technical_eligibility(assessment(), PROFILE, "Python backend engineering.")
    assert combine_eligibility(Eligibility.review, technical) == Eligibility.review
    assert combine_eligibility(Eligibility.rejected, technical) == Eligibility.rejected


def test_gemini_configuration(monkeypatch):
    assert gemini_config() == ("test-secret", "gemini-3.5-flash-lite")
    monkeypatch.setenv("GEMINI_MODEL", "configured-model")
    assert gemini_config() == ("test-secret", "configured-model")
    assert gemini_config("explicit-model") == ("test-secret", "explicit-model")
    with pytest.raises(ValueError):
        gemini_config("https://invalid/model")
    monkeypatch.setenv("GEMINI_MODEL", "")
    with pytest.raises(ValueError):
        gemini_config()
    monkeypatch.setenv("OPENAI_API_KEY", "ignored-secret")
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(ValueError, match="requires GEMINI_API_KEY"):
        gemini_config()
    monkeypatch.setenv("GEMINI_API_KEY", " ")
    with pytest.raises(ValueError, match="requires GEMINI_API_KEY"):
        gemini_config()


@pytest.mark.parametrize("backend", ["gemini", "agent"])
@pytest.mark.parametrize("failure", [None, ValueError("secret provider content"), RuntimeError("private candidate data")])
def test_cli_end_to_end(tmp_path, failure, capsys, backend):
    args = make_args(tmp_path, ai=True)
    args.ai_backend = backend
    job = make_job("1", "Backend Engineer")
    job.verified_live = True
    job.remote = True
    # The fixture profile has no concrete experience, so use unknown evidence.
    output = assessment()
    output.requirements[0].status = RequirementStatus.unknown
    output.requirements[0].candidate_evidence = ""
    with (
        patch("job_hunter.cli.collect_with_diagnostics", new=AsyncMock(return_value=CollectionResult(jobs=[job]))),
        patch("job_hunter.cli.verify_detail", new=AsyncMock(return_value=VerificationResult(verified=True))),
        patch("job_hunter.cli.assess_requirements_agent" if backend == "agent" else "job_hunter.cli.assess_requirements", new=AsyncMock(return_value=output, side_effect=failure)),
    ):
        asyncio.run(run(args))
    report = args.output.read_text()
    assert "eligible: 0; review: 1; rejected: 0" in report
    assert f"**AI analyzed:** {failure is None}" in report
    assert f"**AI backend:** {backend}" in report
    if failure:
        assert "AI analysis errors" in report
        assert type(failure).__name__ in report
        assert str(failure) not in report + capsys.readouterr().out


@pytest.mark.parametrize("backend", ["gemini", "agent"])
@pytest.mark.parametrize("ai", [False, True])
def test_cli_eligible_with_grounded_experience(tmp_path, ai, backend):
    args = make_args(tmp_path, ai=ai)
    args.ai_backend = backend
    args.profile.write_text(yaml.safe_dump(PROFILE))
    job = make_job("1", "Backend Engineer")
    job.verified_live = True
    job.remote = True
    with (
        patch("job_hunter.cli.collect_with_diagnostics", new=AsyncMock(return_value=CollectionResult(jobs=[job]))),
        patch("job_hunter.cli.verify_detail", new=AsyncMock(return_value=VerificationResult(verified=True))),
        patch("job_hunter.cli.assess_requirements_agent" if backend == "agent" else "job_hunter.cli.assess_requirements", new=AsyncMock(return_value=assessment())) as call,
    ):
        asyncio.run(run(args))
    assert "eligible: 1; review: 0; rejected: 0" in args.output.read_text()
    assert call.await_count == int(ai)
    if ai:
        assert call.call_args.args == (PROFILE, job.description, "test-model")


def test_entrypoint_and_arguments(monkeypatch, capsys):
    from importlib.metadata import entry_points
    assert any(ep.name == "job-hunter" and ep.value == "job_hunter.cli:main" for ep in entry_points(group="console_scripts"))
    monkeypatch.setattr(sys, "argv", ["job-hunter", "--help"])
    with pytest.raises(SystemExit) as exit:
        main()
    assert exit.value.code == 0 and "--ai" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["job-hunter", "--ai", "--model", "bad/model"])
    with pytest.raises(SystemExit) as exit:
        main()
    assert exit.value.code == 2


@pytest.mark.parametrize("backend", ["gemini", "agent"])
def test_cli_rejection_skips_assessment(tmp_path, backend):
    args = make_args(tmp_path, ai=True)
    args.ai_backend = backend
    job = make_job("1", "Frontend Developer")
    with (
        patch("job_hunter.cli.collect_with_diagnostics", new=AsyncMock(return_value=CollectionResult(jobs=[job]))),
        patch("job_hunter.cli.verify_detail", new=AsyncMock(return_value=VerificationResult(verified=True))),
        patch("job_hunter.cli.assess_requirements_agent" if backend == "agent" else "job_hunter.cli.assess_requirements", new=AsyncMock()) as call,
    ):
        asyncio.run(run(args))
    call.assert_not_awaited()
    assert "eligible: 0; review: 0; rejected: 1" in args.output.read_text()


@pytest.mark.parametrize('arguments', [
    ['--ai-backend', 'agent'],
    ['--ai', '--ai-backend', 'unsupported'],
])
def test_invalid_backend_arguments(monkeypatch, arguments):
    monkeypatch.setattr(sys, 'argv', ['job-hunter', *arguments])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


@pytest.mark.parametrize('backend', ['gemini', 'agent'])
@pytest.mark.parametrize('limit', [None, 1, 2])
@pytest.mark.parametrize('fails', [False, True], ids=['success', 'failure'])
def test_max_ai_jobs_caps_attempts_and_preserves_all_results(tmp_path, backend, limit, fails):
    import sqlite3
    import job_hunter.cli as cli

    args = make_args(tmp_path, ai=True)
    args.ai_backend = backend
    args.max_ai_jobs = limit
    args.profile.write_text(yaml.safe_dump(PROFILE))
    jobs = [make_job(str(i), 'Frontend Developer' if i == 0 else 'Backend Engineer') for i in range(5)]
    for job in jobs:
        job.remote = True
        job.verified_live = True
    # Neither deterministic rejection nor an already-dismissed job uses budget.
    with sqlite3.connect(args.database) as conn:
        cli.db_init(conn)
        cli.save_job(conn, jobs[1])
        conn.execute('UPDATE jobs SET status=? WHERE key=?', ('dismissed', jobs[1].key))
    assessor = AsyncMock(return_value=assessment(), side_effect=ValueError('private error') if fails else None)
    with (
        patch('job_hunter.cli.collect_with_diagnostics', new=AsyncMock(return_value=CollectionResult(jobs=jobs))),
        patch('job_hunter.cli.verify_detail', new=AsyncMock(return_value=VerificationResult(verified=True))),
        patch('job_hunter.cli.assess_requirements_agent' if backend == 'agent' else 'job_hunter.cli.assess_requirements', new=assessor),
        patch('job_hunter.cli.report', wraps=cli.report) as report_call,
    ):
        asyncio.run(run(args))
    expected_attempts = 3 if limit is None else min(3, limit)
    assert assessor.await_count == expected_attempts
    items = report_call.call_args.args[0]
    assert [job.key for job, match in items] == [jobs[i].key for i in (0, 2, 3, 4)]
    assert items[0][1].eligibility == Eligibility.rejected
    for index, (job, match) in enumerate(items[1:]):
        attempted = index < expected_attempts
        assert match.ai_analyzed == (attempted and not fails)
        assert match.eligibility == (Eligibility.eligible if attempted and not fails else Eligibility.review)
        assert any('--max-ai-jobs limit reached' in concern for concern in match.concerns) == (not attempted)
    assert len(report_call.call_args.kwargs['ai_errors']) == (expected_attempts if fails else 0)
    content = args.output.read_text()
    assert 'private error' not in content
    assert content.count('--max-ai-jobs limit reached') == 3 - expected_attempts


@pytest.mark.parametrize('value', ['1', '10'])
def test_max_ai_jobs_argument_parsing(monkeypatch, value):
    monkeypatch.setattr(sys, 'argv', ['job-hunter', '--ai', '--max-ai-jobs', value])
    with patch('job_hunter.cli.run', new=AsyncMock()) as run_call:
        main()
    assert run_call.call_args.args[0].max_ai_jobs == int(value)


@pytest.mark.parametrize('arguments', [
    ['--ai', '--max-ai-jobs', '0'],
    ['--ai', '--max-ai-jobs', '-1'],
    ['--ai', '--max-ai-jobs', '1.5'],
    ['--ai', '--max-ai-jobs', 'invalid'],
    ['--max-ai-jobs', '1'],
])
def test_invalid_max_ai_jobs_arguments(monkeypatch, arguments):
    monkeypatch.setattr(sys, 'argv', ['job-hunter', *arguments])
    with patch('job_hunter.cli.run', new=AsyncMock()) as run_call:
        with pytest.raises(SystemExit) as error:
            main()
    assert error.value.code == 2
    run_call.assert_not_called()
