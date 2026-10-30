import json
import subprocess
import sys
from pathlib import Path

import pytest

from evaluations.metrics import calculate_requirements_metrics


FIXTURES = Path(__file__).parent / 'fixtures'


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def row(expected, predicted, job_id='case'):
    return {'job_id': job_id, 'reference': {'expected_eligibility': expected},
            'deterministic_match': {'eligibility': predicted}}


def test_requirements_report_matches_metrics():
    report = load('report/requirements.json')
    metrics = calculate_requirements_metrics(report['results'])
    template = load('requirements_metrics.json')
    assert metrics == template

def test_fabricated_candidate_quotation():

    results = [
        {
            "id": "fabricated-candidate-evidence",
            "assessment": {
                "requirements": [
                    {
                        "name": "AWS SQS",
                        "candidate_evidence": (
                            "10 years operating AWS SQS at Google."
                        ),
                    }
                ]
            },
            "classification_passed": True,
            "grounding_passed": True,
            "candidate_grounding_passed": False,
            "passed": False,
        }
    ]

    metrics = calculate_requirements_metrics(results)
    assert metrics["classification"]["pass_rate"] == 1.0
    assert metrics["job_grounding"]["pass_rate"] == 1.0

    assert metrics["candidate_grounding"] == {
        "passed": 0,
        "applicable": 1,
        "pass_rate": 0.0,
    }

    assert metrics["overall"]["pass_rate"] == 0.0

def test_empty_report():
    metrics = calculate_requirements_metrics([])
    assert metrics['total'] == 0
    assert metrics.get('overall').get('pass_rate') is None
    assert metrics.get('job_grounding').get('pass_rate') is None
    assert metrics.get('classification').get('pass_rate') is None
    assert metrics.get('candidate_grounding').get('pass_rate') is None

def test_failed_gemini_request():
    results = [
        {
            "id": "api-error",
            "assessment": None,
            "passed": False,
            "error": {"type": "HTTPStatusError"},
        }
    ]

    metrics = calculate_requirements_metrics(results)

    assert metrics["total"] == 1
    assert metrics["classification"]["compared"] == 0
    assert metrics["job_grounding"]["compared"] == 0
    assert metrics["candidate_grounding"]["applicable"] == 0
    assert metrics["overall"]["pass_rate"] == 0.0


def test_technical_fit_agreement():
    rows = [
        {
            "reference": {"expected_technical_fit": "strong"},
            "assessment": {"technical_fit": "strong"},
        },
        {
            "reference": {"expected_technical_fit": "partial"},
            "assessment": {"technical_fit": "weak"},
        },
        {
            "reference": {"expected_technical_fit": "weak"},
            "assessment": {"technical_fit": "weak"},
        },
    ]

    metrics = calculate_requirements_metrics(rows)

    assert metrics["technical_fit"]["compared"] == 3
    assert metrics["technical_fit"]["correct"] == 2
    assert metrics["technical_fit"]["agreement_rate"] == 2 / 3


def test_technical_fit_for_missing_reference():
    rows = [
        {
            "assessment": None,
        },
    ]

    metrics = calculate_requirements_metrics(rows)

    assert metrics["technical_fit"] == {
        "compared": 0,
        "correct": 0,
        "agreement_rate": None,
        "mismatches": [],
    }

def test_technical_fit_metrics_do_not_leak_between_calls():
    calculate_requirements_metrics([
        {
            "reference": {"expected_technical_fit": "strong"},
            "assessment": {"technical_fit": "strong"},
        }
    ])

    metrics = calculate_requirements_metrics([
        {
            "assessment": None,
        }
    ])

    assert metrics["technical_fit"] == {
        "compared": 0,
        "correct": 0,
        "agreement_rate": None,
        "mismatches": [],
    }

def test_technical_fit_mismatches():
    rows = [
        {
            "id": "case-a",
            "reference": {"expected_technical_fit": "strong"},
            "assessment": {"technical_fit": "strong"},
        },
        {
            "id": "case-b",
            "reference": {"expected_technical_fit": "partial"},
            "assessment": {"technical_fit": "weak"},
        },
        {
            "id": "case-c",
            "reference": {"expected_technical_fit": "weak"},
            "assessment": {"technical_fit": "partial"},
        },
    ]

    metrics = calculate_requirements_metrics(rows)

    assert metrics["technical_fit"]["mismatches"] == [
        {"id": "case-b", "expected": "partial", "predicted": "weak"},
        {"id": "case-c", "expected": "weak", "predicted": "partial"},
    ]


