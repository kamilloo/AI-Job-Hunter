import json
import subprocess
import sys
from pathlib import Path

import pytest

from evaluations.metrics import LABELS, calculate


FIXTURES = Path(__file__).parent / 'fixtures'


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def row(expected, predicted, job_id='case'):
    return {'job_id': job_id, 'reference': {'expected_eligibility': expected},
            'deterministic_match': {'eligibility': predicted}}


def test_deterministic_report_matches_metrics_template():
    report = load('report/deterministic.json')
    metrics = calculate(report['results'])
    template = load('metrics.json')
    assert metrics == template


def test_ai_report_uses_deterministic_prediction():
    report = load('report/gemini-e12.json')
    assert report['results'][0]['final_prediction'] == 'review'
    metrics = calculate(report['results'])
    assert metrics['accuracy'] == 1.0
    assert metrics['confusion_matrix']['eligible']['eligible'] == 1
    assert metrics['mismatches'] == []


def test_all_confusion_matrix_cells_and_false_decisions():
    rows = [row(expected, predicted, f'{expected}-{predicted}')
            for expected in LABELS for predicted in LABELS]
    metrics = calculate(rows)
    assert metrics['total'] == metrics['compared'] == 9
    assert metrics['correct'] == 3
    assert metrics['accuracy'] == pytest.approx(1 / 3)
    assert metrics['false_eligible'] == metrics['false_rejected'] == 2
    assert all(count == 1 for cells in metrics['confusion_matrix'].values() for count in cells.values())
    assert len(metrics['mismatches']) == 6
    assert metrics['mismatches'][0] == {
        'job_id': 'eligible-review', 'expected': 'eligible', 'predicted': 'review'}


def test_missing_comparisons_and_ai_errors():
    valid = row('eligible', 'eligible')
    valid['error'] = {'type': 'ReadTimeout'}
    valid['deterministic_correct'] = False
    metrics = calculate([{}, row(None, 'review'), row('review', None), valid])
    assert metrics['total'] == 4
    assert metrics['compared'] == metrics['correct'] == 1
    assert metrics['accuracy'] == 1.0


def test_empty_report():
    metrics = calculate([])
    assert metrics['total'] == metrics['compared'] == metrics['correct'] == 0
    assert metrics['accuracy'] is None
    assert metrics['mismatches'] == []


@pytest.mark.parametrize('expected,predicted', [('invalid', 'eligible'), ('review', 'invalid')])
def test_invalid_labels(expected, predicted):
    with pytest.raises(ValueError, match='Invalid eligibility label'):
        calculate([row(expected, predicted)])


def test_saved_report_command_and_overwrite_protection(tmp_path):
    output = tmp_path / 'metrics.json'
    command = [sys.executable, '-m', 'evaluations.metrics',
               str(FIXTURES / 'report/deterministic.json'), '--output', str(output)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    expected = calculate(load('report/deterministic.json')['results'])
    assert json.loads(output.read_text()) == expected
    repeat = subprocess.run(command, capture_output=True, text=True)
    assert repeat.returncode != 0
    assert json.loads(output.read_text()) == expected
