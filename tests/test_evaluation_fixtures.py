import json
from pathlib import Path

from job_hunter.models import Job

FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "evaluations/fixtures/jobs.json"
)


def test_job_fixtures_are_valid():
    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))

    assert len(cases) >= 10

    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert all(ids)

    for case in cases:
        Job.model_validate(case["job"])


def test_fixture_ids_are_unique():
    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))

    ids = [case["id"] for case in cases]

    assert len(ids) == len(set(ids))


def test_deterministic_references_are_valid():
    reference_path = (
        FIXTURES.parent / "deterministic.json"
    )
    references = json.loads(
        reference_path.read_text(encoding="utf-8")
    )

    # Adapt this extraction to your actual reference-file schema.
    assert references