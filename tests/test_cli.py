import argparse
import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import yaml

from job_hunter.cli import run, report
from job_hunter.models import Job


def test_discovery_preserves_jobs_when_one_source_fails(tmp_path):
    profile = tmp_path / "profile.yaml"
    sources = tmp_path / "sources.yaml"
    database = tmp_path / "jobs.sqlite3"
    output = tmp_path / "daily.md"

    profile.write_text(
        yaml.safe_dump({
            "primary_titles": ["backend engineer"],
            "core_skills": ["python"],
        }),
        encoding="utf-8",
    )

    sources.write_text(
        yaml.safe_dump({
            "boards": [
                {
                    "provider": "greenhouse",
                    "slug": "broken",
                    "company": "Broken",
                },
                {
                    "provider": "greenhouse",
                    "slug": "working",
                    "company": "Working",
                },
            ],
        }),
        encoding="utf-8",
    )

    job = Job(
        provider="greenhouse",
        board="working",
        external_id="123",
        company="Working",
        title="Backend Engineer",
        location="Remote - Poland",
        description="Python backend engineering.",
        url="https://example.com/jobs/123",
    )

    async def fake_collect(client, provider, slug, company):
        if slug == "broken":
            request = httpx.Request("GET", "https://example.com/jobs")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError(
                "Service unavailable",
                request=request,
                response=response,
            )
        return [job]

    args = argparse.Namespace(
        profile=profile,
        sources=sources,
        database=database,
        output=output,
        ai=False,
        model=None,
    )

    with (
        patch(
            "job_hunter.cli.collect",
            side_effect=fake_collect,
        ) as mock_collect,
        patch(
            "job_hunter.cli.verify_detail",
            new_callable=AsyncMock,
        ),
    ):
        asyncio.run(run(args))

    report = output.read_text(encoding="utf-8")

    assert mock_collect.await_count == 2
    assert "Backend Engineer" in report
    assert "Collection / verification errors" in report
    assert "Collection failure: greenhouse/broken" in report
    assert "transient (HTTP 503)" in report
    assert "Service unavailable" not in report

def test_report_handles_ai_errors(tmp_path):
    output = tmp_path / "report.md"

    report(
        items=[],
        errors=[],
        path=output,
        ai_errors=[
            {
                "job_key": "greenhouse:test:123",
                "error_type": "ReadTimeout",
            }
        ],
    )

    content = output.read_text(encoding="utf-8")

    assert "## AI analysis errors" in content
    assert "greenhouse:test:123" in content
    assert "ReadTimeout" in content

def test_report_handles_mixed_failure_stages(tmp_path):
    output = tmp_path / "report.md"

    report(
        items=[],
        errors=[
            {
                "provider": "greenhouse",
                "board": "broken",
                "error_type": "HTTPStatusError",
                "category": "transient",
                "status_code": 503,
            }
        ],
        path=output,
        ai_errors=[
            {
                "job_key": "greenhouse:test:123",
                "error_type": "ReadTimeout",
            }
        ],
    )

    content = output.read_text(encoding="utf-8")

    assert "Collection failure: greenhouse/broken" in content
    assert "transient (HTTP 503)" in content
    assert "AI analysis failure:" in content