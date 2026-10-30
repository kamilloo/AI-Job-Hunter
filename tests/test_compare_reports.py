import json
import subprocess
import sys

from evaluations.compare_reports import compare_reports


def test_compare_reports_detects_technical_fit_changes():
    baseline = {
        "dataset_sha256": "same-hash",
        "model": "gemini-test",
        "instructions": "same-instructions",
        "results": [
            {
                "id": "case-a",
                "assessment": {"technical_fit": "partial"},
            },
            {
                "id": "case-b",
                "assessment": {"technical_fit": "strong"},
            },
        ],
    }

    current = {
        "dataset_sha256": "same-hash",
        "model": "gemini-test",
        "instructions": "same-instructions",
        "results": [
            {
                "id": "case-b",
                "assessment": {"technical_fit": "strong"},
            },
            {
                "id": "case-a",
                "assessment": {"technical_fit": "weak"},
            },
        ],
    }

    comparison = compare_reports(baseline, current)


    assert comparison["cases"]["common"] == 2
    assert comparison["cases"]["added"] == []
    assert comparison["cases"]["removed"] == []

    assert comparison["technical_fit_changes"] == [
        {
            "id": "case-a",
            "before": "partial",
            "after": "weak",
        }
    ]

def test_compare_reports_tracks_added_and_removed_cases():
    baseline = {
        "results": [
            {"id": "case-a"},
            {"id": "case-b"},
        ]
    }

    current = {
        "results": [
            {"id": "case-b"},
            {"id": "case-c"},
        ]
    }

    comparison = compare_reports(baseline, current)

    assert comparison["cases"] == {
        "common": 1,
        "added": ["case-c"],
        "removed": ["case-a"],
    }

    assert comparison["technical_fit_changes"] == []

def test_compare_reports_when_no_assessment_was_returned():
    baseline = {
        "results": [
            {
                "id": "case-a",
                "assessment": {"technical_fit": "strong"},
            }
        ]
    }

    current = {
        "results": [
            {
                "id": "case-a",
                "assessment": None,
            }
        ]
    }

    comparison = compare_reports(baseline, current)


    assert comparison["cases"]["common"] == 1
    assert comparison["cases"]["added"] == []
    assert comparison["cases"]["removed"] == []

    assert comparison["technical_fit_changes"] == [
        {
            "id": "case-a",
            "before": "strong",
            "after": None,
        }
    ]

import pytest


@pytest.mark.parametrize(
    ("field", "before", "after", "warning"),
    [
        ("dataset_sha256", "hash-a", "hash-b", "Dataset hashes differ"),
        ("model", "gemini-a", "gemini-b", "Models differ"),
        ("instructions", "prompt-a", "prompt-b", "Instructions differ"),
        (
            "output_schema",
            {"version": 1},
            {"version": 2},
            "Output schemas differ",
        ),
    ],
)
def test_compare_reports_detects_metadata_changes(
    field, before, after, warning
):
    baseline = {
        "dataset_sha256": "same-hash",
        "model": "gemini-test",
        "instructions": "same-instructions",
        "output_schema": {"version": 1},
        "results": [],
    }
    current = {
        **baseline,
        field: after,
    }
    baseline = {
        **baseline,
        field: before,
    }

    comparison = compare_reports(baseline, current)

    assert comparison["comparable"] is False
    assert warning in comparison["warnings"]


def test_compare_reports_cli(tmp_path):
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"

    metadata = {
        "dataset_sha256": "hash",
        "model": "gemini-test",
        "instructions": "instructions",
        "output_schema": {"version": 1},
    }

    baseline.write_text(json.dumps({
        **metadata,
        "results": [
            {"id": "case-a", "assessment": {"technical_fit": "partial"}}
        ],
    }), encoding="utf-8")

    current.write_text(json.dumps({
        **metadata,
        "results": [
            {"id": "case-a", "assessment": {"technical_fit": "weak"}}
        ],
    }), encoding="utf-8")

    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluations.compare_reports",
            str(baseline),
            str(current),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    comparison = json.loads(process.stdout)

    assert comparison["comparable"] is True
    assert comparison["technical_fit_changes"] == [
        {"id": "case-a", "before": "partial", "after": "weak"}
    ]