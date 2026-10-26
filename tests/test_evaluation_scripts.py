import asyncio
import json
from argparse import Namespace
from unittest.mock import AsyncMock

import httpx
import pytest

from evaluations.common import ROOT
from evaluations.run_evaluation import run as run_deterministic
from evaluations.run_ai_evaluation import run as run_ai
from job_hunter.model.RequirementAssessment import TechnicalAssessment


def args(tmp_path, kind, ids):
    return Namespace(profile=ROOT / 'config/profile.yaml',
                     jobs=ROOT / 'evaluations/fixtures/jobs.json',
                     dataset=ROOT / f'evaluations/fixtures/{kind}.json',
                     output=tmp_path / 'result.json', job_id=ids, model='gemini-test')


def test_deterministic_artifact_and_overwrite_protection(tmp_path):
    options = args(tmp_path, 'deterministic', ['E02', 'E03'])
    assert run_deterministic(options) == 0
    result = json.loads(options.output.read_text())
    assert result['status'] == 'completed'
    assert result['candidate_profile']['location'] == 'Poland'
    assert [row['final_prediction'] for row in result['results']] == ['eligible', 'rejected']
    assert result['results'][0]['deterministic_match']['reasons']
    assert result['metrics']['accuracy'] == 1.0
    assert result['metrics']['compared'] == 2
    with pytest.raises(FileExistsError):
        run_deterministic(options)


def test_ai_records_full_assessment_without_reference_leakage(tmp_path, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'not-for-artifacts')
    assessment = TechnicalAssessment(requirements=[], summary='Insufficient evidence', confidence=0.2)
    assessor = AsyncMock(return_value=assessment)
    monkeypatch.setattr('evaluations.run_ai_evaluation.assess_requirements', assessor)
    options = args(tmp_path, 'ai', ['E02', 'E09'])
    assert asyncio.run(run_ai(options)) == 0
    artifact = json.loads(options.output.read_text())
    assert artifact['results'][0]['assessment'] == assessment.model_dump(mode='json')
    assert artifact['results'][0]['final_prediction'] == 'review'
    assert artifact['results'][1]['final_prediction'] == 'rejected'
    assert artifact['assessor']['model'] == 'gemini-test'
    assert 'not-for-artifacts' not in options.output.read_text()
    for call in assessor.call_args_list:
        profile, description, model = call.args
        assert profile == artifact['candidate_profile']
        assert isinstance(description, str)
        assert model == 'gemini-test'
        assert 'expected_technical_fit' not in description


def test_ai_saves_error_and_continues(tmp_path, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    assessor = AsyncMock(side_effect=[httpx.ReadTimeout('secret'), TechnicalAssessment(
        requirements=[], summary='No requirements', confidence=0.1)])
    monkeypatch.setattr('evaluations.run_ai_evaluation.assess_requirements', assessor)
    options = args(tmp_path, 'ai', ['E01', 'E02'])
    assert asyncio.run(run_ai(options)) == 1
    artifact = json.loads(options.output.read_text())
    assert artifact['status'] == 'completed_with_errors'
    assert artifact['results'][0]['final_prediction'] is None
    assert artifact['results'][0]['error'] == {'type': 'ReadTimeout'}
    assert artifact['results'][1]['assessment'] is not None
    assert 'secret' not in options.output.read_text()


def test_unknown_id_fails_without_writing(tmp_path):
    options = args(tmp_path, 'deterministic', ['does-not-exist'])
    with pytest.raises(ValueError, match='Unknown evaluation IDs'):
        run_deterministic(options)
    assert not options.output.exists()


@pytest.mark.parametrize('environment_key', [None, 'exported-key'])
def test_ai_loads_root_dotenv_without_overriding_environment(tmp_path, monkeypatch, environment_key):
    monkeypatch.setattr('evaluations.run_ai_evaluation.ROOT', tmp_path)
    (tmp_path / '.env').write_text('GEMINI_API_KEY=file-key\nGEMINI_MODEL=file-model\n')
    # Restore even variables that load_dotenv adds when initially absent.
    for name in ('GEMINI_API_KEY', 'GEMINI_MODEL'):
        monkeypatch.setenv(name, '')
        monkeypatch.delenv(name)
    if environment_key:
        monkeypatch.setenv('GEMINI_API_KEY', environment_key)
    monkeypatch.chdir(tmp_path.parent)

    async def assess(*args, **kwargs):
        import os
        assert os.environ['GEMINI_API_KEY'] == (environment_key or 'file-key')
        assert args[2] == 'file-model'
        return TechnicalAssessment(requirements=[], summary='No requirements', confidence=0.1)

    monkeypatch.setattr('evaluations.run_ai_evaluation.assess_requirements', assess)
    options = args(tmp_path, 'ai', ['E02'])
    options.model = None
    assert asyncio.run(run_ai(options)) == 0
    artifact_text = options.output.read_text()
    assert 'file-key' not in artifact_text
    assert 'exported-key' not in artifact_text


def test_generated_report_counts_are_consistent(tmp_path):
    options = args(tmp_path, "deterministic", ["E02", "E03"])
    assert run_deterministic(options) == 0

    report = json.loads(options.output.read_text())
    results = report["results"]
    summary = report["summary"]
    metrics = report["metrics"]

    assert summary["total"] == len(results)
    assert summary["errors"] == sum(
        row["error"] is not None for row in results
    )
    assert metrics["total"] == len(results)
    assert metrics["correct"] + len(metrics["mismatches"]) == metrics["compared"]
    assert sum(
        count
        for predictions in metrics["confusion_matrix"].values()
        for count in predictions.values()
    ) == metrics["compared"]