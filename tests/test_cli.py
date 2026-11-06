import argparse
import asyncio
import json
import logging
from unittest.mock import AsyncMock, patch

import httpx
import yaml

from job_hunter.cli import run, report
from job_hunter.collectors.normalize_rows import CollectionResult, normalize_rows
from job_hunter.models import Job
from job_hunter.collectors.verify_detail import VerificationResult

import argparse
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from job_hunter.cli import run, report
from job_hunter.collectors.normalize_rows import CollectionResult
from job_hunter.collectors.verify_detail import VerificationResult
from job_hunter.models import Job, Eligibility


def make_job(external_id: str, title: str) -> Job:
    return Job(
        provider="greenhouse",
        board="example",
        external_id=external_id,
        company="Example",
        title=title,
        location="Remote - Poland",
        description="Python backend engineering.",
        url=f"https://example.com/jobs/{external_id}",
    )


def make_args(tmp_path, *, ai=False):
    profile = tmp_path / "profile.yaml"
    sources = tmp_path / "sources.yaml"

    profile.write_text(
        yaml.safe_dump({
            "primary_titles": ["backend engineer"],
            "core_skills": ["python"],
        }),
        encoding="utf-8",
    )

    sources.write_text(
        yaml.safe_dump({
            "boards": [{
                "provider": "greenhouse",
                "slug": "example",
                "company": "Example",
            }],
        }),
        encoding="utf-8",
    )

    return argparse.Namespace(
        profile=profile,
        sources=sources,
        database=tmp_path / "jobs.sqlite3",
        output=tmp_path / "daily.md",
        ai=ai,
        model="test-model",
    )


def fake_evaluate(job, profile):
    return SimpleNamespace(
        eligibility=Eligibility.review,
        score=50,
        ai_transition_score=30,
        ai_analyzed=False,
        reasons=[],
        concerns=[],
    )

def make_discovery_args(tmp_path, board_slugs):
    profile_path = tmp_path / "profile.yaml"
    sources_path = tmp_path / "sources.yaml"

    profile_path.write_text(
        yaml.safe_dump({
            "primary_titles": ["backend engineer"],
            "core_skills": ["python"],
        }),
        encoding="utf-8",
    )

    sources_path.write_text(
        yaml.safe_dump({
            "boards": [
                {
                    "provider": "greenhouse",
                    "slug": slug,
                    "company": slug.title(),
                }
                for slug in board_slugs
            ]
        }),
        encoding="utf-8",
    )

    return argparse.Namespace(
        profile=profile_path,
        sources=sources_path,
        database=tmp_path / "jobs.sqlite3",
        output=tmp_path / "daily.md",
        ai=False,
        model=None,
    )


def make_discovery_job():
    return Job(
        provider="greenhouse",
        board="working",
        external_id="123",
        company="Working",
        title="Backend Engineer",
        location="Remote - Poland",
        description="Python backend engineering.",
        url="https://example.com/jobs/123",
    )


def raise_http_503():
    request = httpx.Request(
        "GET",
        "https://example.com/jobs",
    )
    response = httpx.Response(
        503,
        request=request,
    )

    raise httpx.HTTPStatusError(
        "Service unavailable",
        request=request,
        response=response,
    )

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
        return CollectionResult(jobs=[job])


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
            "job_hunter.cli.collect_with_diagnostics",
            side_effect=fake_collect,
        ) as mock_collect,
        patch(
            "job_hunter.cli.verify_detail",
            new_callable=AsyncMock,
            return_value=VerificationResult(verified=True),
        ) as mock_verify,
    ):
        asyncio.run(run(args))

    report = output.read_text(encoding="utf-8")

    assert mock_collect.await_count == 2
    mock_verify.assert_awaited_once()
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

def test_discovery_preserves_jobs_when_two_invalid_jobs(tmp_path):
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
                    "slug": "working",
                    "company": "Working",
                },
            ],
        }),
        encoding="utf-8",
    )

    async def fake_collect(client, provider, slug, company):
        return normalize_rows(
            provider=provider,
            slug=slug,
            company=company,
            rows=[
                {
                    "id": 123,
                    "title": "Backend Engineer",
                    "absolute_url": "https://example.com/jobs/123",
                    "location": {"name": "Remote - Poland"},
                    "content": "Python backend engineering.",
                },
                {"id": 456},  # Missing title and absolute_url.
                {"id": 789, "title": "Backend Engineer"},  # Missing absolute_url.
            ],
        )

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
            "job_hunter.cli.collect_with_diagnostics",
            side_effect=fake_collect,
        ) as mock_collect,
        patch(
            "job_hunter.cli.verify_detail",
            new_callable=AsyncMock,
            return_value=VerificationResult(verified=True),
        ) as mock_verify,
    ):
        asyncio.run(run(args))

    report_text = output.read_text(encoding="utf-8")

    assert "Backend Engineer" in report_text
    assert "## Malformed ATS records" in report_text
    assert "2 invalid records skipped" in report_text
    assert "Collection failure:" not in report_text
    assert "greenhouse/working: 2 invalid records skipped" in report_text
    assert mock_collect.await_count == 1
    mock_verify.assert_awaited_once()

def test_partial_verification_failure_preserves_jobs(tmp_path):
    args = make_args(tmp_path)

    jobs = [
        make_job("123", "Backend Engineer"),
        make_job("456", "Platform Engineer"),
    ]

    async def fake_collect(client, provider, slug, company):
        return CollectionResult(
            jobs=jobs,
            skipped_invalid=0,
        )

    async def fake_verify(client, job):
        if job.external_id == "123":
            job.verified_live = False
            job.verified_at = None

            return VerificationResult(
                verified=False,
                error_type="HTTPStatusError",
                category="transient",
                status_code=503,
            )

        job.verified_live = True
        job.verified_at = "2026-11-03T10:00:00+00:00"

        return VerificationResult(verified=True)

    with (
        patch(
            "job_hunter.cli.collect_with_diagnostics",
            side_effect=fake_collect,
        ) as mock_collect,
        patch(
            "job_hunter.cli.verify_detail",
            side_effect=fake_verify,
        ) as mock_verify,
        patch(
            "job_hunter.cli.evaluate",
            side_effect=fake_evaluate,
        ),
    ):
        asyncio.run(run(args))

    report_text = args.output.read_text(encoding="utf-8")

    assert mock_collect.await_count == 1
    assert mock_verify.await_count == 2

    # Both jobs survive verification.
    assert "Backend Engineer" in report_text
    assert "Platform Engineer" in report_text

    # Exactly one verification failure is reported.
    assert "## Job verification failures" in report_text
    assert (
        "Verification failure: greenhouse/example"
        in report_text
    )
    assert "transient (HTTP 503)" in report_text
    assert report_text.count("- Verification failure:") == 1

    # The failed job is not incorrectly marked as verified.
    assert jobs[0].verified_live is False
    assert jobs[0].verified_at is None

    assert jobs[1].verified_live is True
    assert jobs[1].verified_at is not None

def test_successful_verification_has_no_failure_section(tmp_path):
    args = make_args(tmp_path)
    job = make_job("123", "Backend Engineer")

    async def fake_collect(client, provider, slug, company):
        return CollectionResult(
            jobs=[job],
            skipped_invalid=0,
        )

    async def fake_verify(client, job):
        job.verified_live = True
        job.verified_at = "2026-11-03T10:00:00+00:00"

        return VerificationResult(verified=True)

    with (
        patch(
            "job_hunter.cli.collect_with_diagnostics",
            side_effect=fake_collect,
        ),
        patch(
            "job_hunter.cli.verify_detail",
            side_effect=fake_verify,
        ) as mock_verify,
        patch(
            "job_hunter.cli.evaluate",
            side_effect=fake_evaluate,
        ),
    ):
        asyncio.run(run(args))

    report_text = args.output.read_text(encoding="utf-8")

    assert mock_verify.await_count == 1
    assert "Backend Engineer" in report_text
    assert "## Job verification failures" not in report_text
    assert "Verification failure:" not in report_text
    assert job.verified_live is True

def test_report_handles_ai_and_verification_errors(tmp_path):
    output = tmp_path / "report.md"

    report(
        items=[],
        errors=[],
        path=output,
        ai_errors=[
            {
                "job_key": "greenhouse:example:123",
                "error_type": "ReadTimeout",
            }
        ],
        verification_errors=[
            {
                "job_key": "greenhouse:example:456",
                "provider": "greenhouse",
                "board": "example",
                "error_type": "HTTPStatusError",
                "category": "permanent",
                "status_code": 404,
            }
        ],
    )

    content = output.read_text(encoding="utf-8")

    assert "## AI analysis errors" in content
    assert "ReadTimeout" in content

    assert "## Job verification failures" in content
    assert "permanent (HTTP 404)" in content

    assert "greenhouse:example:123" in content
    assert "greenhouse:example:456" in content

def test_report_does_not_allow_markdown_injection(tmp_path):
    output = tmp_path / "report.md"

    report(
        items=[],
        errors=[
            {
                "provider": "greenhouse",
                "board": "broken\n## Injected heading",
                "error_type": "HTTPStatusError",
                "category": "transient",
                "status_code": 503,
            }
        ],
        path=output,
    )

    content = output.read_text(encoding="utf-8")

    assert "## Injected heading" not in content
    assert "HTTP 503" in content
    assert "Collection failure: greenhouse/invalid" in content

def test_discovery_summary_partial(tmp_path):
    args = make_discovery_args(
        tmp_path,
        board_slugs=["broken", "working"],
    )

    async def fake_collect(client, provider, slug, company):
        if slug == "broken":
            raise_http_503()

        return CollectionResult(
            jobs=[make_discovery_job()],
            skipped_invalid=0,
        )

    with (
        patch(
            "job_hunter.cli.collect_with_diagnostics",
            side_effect=fake_collect,
        ) as mock_collect,
        patch(
            "job_hunter.cli.verify_detail",
            new_callable=AsyncMock,
        ),
    ):
        asyncio.run(run(args))

    report_text = args.output.read_text(encoding="utf-8")

    assert mock_collect.await_count == 2

    assert "## Discovery summary" in report_text
    assert "Status: partial" in report_text
    assert "Sources: 1 succeeded, 1 failed, 2 total" in report_text
    assert "Jobs collected: 1" in report_text

    assert "Backend Engineer" in report_text
    assert "Collection failure: greenhouse/broken" in report_text

def test_discovery_summary_failed(tmp_path):
    args = make_discovery_args(
        tmp_path,
        board_slugs=["broken-one", "broken-two"],
    )

    async def fake_collect(client, provider, slug, company):
        raise_http_503()

    with (
        patch(
            "job_hunter.cli.collect_with_diagnostics",
            side_effect=fake_collect,
        ) as mock_collect,
        patch(
            "job_hunter.cli.verify_detail",
            new_callable=AsyncMock,
        ) as mock_verify,
    ):
        asyncio.run(run(args))

    report_text = args.output.read_text(encoding="utf-8")

    assert mock_collect.await_count == 2
    mock_verify.assert_not_awaited()

    assert "## Discovery summary" in report_text
    assert "Status: failed" in report_text
    assert "Sources: 0 succeeded, 2 failed, 2 total" in report_text
    assert "Jobs collected: 0" in report_text

    assert report_text.count("- Collection failure:") == 2

def test_discovery_summary_complete_with_zero_jobs(tmp_path):
    args = make_discovery_args(
        tmp_path,
        board_slugs=["empty-board"],
    )

    async def fake_collect(client, provider, slug, company):
        return CollectionResult(
            jobs=[],
            skipped_invalid=0,
        )

    with (
        patch(
            "job_hunter.cli.collect_with_diagnostics",
            side_effect=fake_collect,
        ) as mock_collect,
        patch(
            "job_hunter.cli.verify_detail",
            new_callable=AsyncMock,
        ) as mock_verify,
    ):
        asyncio.run(run(args))

    report_text = args.output.read_text(encoding="utf-8")

    assert mock_collect.await_count == 1
    mock_verify.assert_not_awaited()

    assert "## Discovery summary" in report_text
    assert "Status: complete" in report_text
    assert "Sources: 1 succeeded, 0 failed, 1 total" in report_text
    assert "Jobs collected: 0" in report_text

    assert "Collection failure:" not in report_text
    assert "## Job verification failures" not in report_text

def test_partial_discovery_emits_warning(caplog, tmp_path):
    args = make_discovery_args(
        tmp_path,
        board_slugs=["broken", "working"],
    )

    async def fake_collect(client, provider, slug, company):
        if slug == "broken":
            raise_http_503()

        return CollectionResult(jobs=[], skipped_invalid=0)

    with (
        patch(
            "job_hunter.cli.collect_with_diagnostics",
            side_effect=fake_collect,
        ),
        caplog.at_level(
            logging.INFO,
            logger="job_hunter.cli",
        ),
    ):
        asyncio.run(run(args))

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.cli"
        and record.message.startswith("{")
    ]

    discovery_events = [
        event
        for event in events
        if event["event"] == "discovery_completed"
    ]

    assert len(discovery_events) == 1
    assert discovery_events[0]["component"] == "discovery"
    assert discovery_events[0]["outcome"] == "partial"
    assert discovery_events[0]["level"] == logging.WARNING

def test_complete_discovery_emits_info(caplog, tmp_path):
    args = make_discovery_args(
        tmp_path,
        board_slugs=["working"],
    )

    async def fake_collect(client, provider, slug, company):
        return CollectionResult(jobs=[], skipped_invalid=0)

    with (
        patch(
            "job_hunter.cli.collect_with_diagnostics",
            side_effect=fake_collect,
        ),
        caplog.at_level(
            logging.INFO,
            logger="job_hunter.cli",
        ),
    ):
        asyncio.run(run(args))

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.cli"
        and record.message.startswith("{")
    ]

    discovery_events = [
        event
        for event in events
        if event["event"] == "discovery_completed"
    ]

    assert len(discovery_events) == 1
    assert discovery_events[0]["component"] == "discovery"
    assert discovery_events[0]["outcome"] == "complete"
    assert discovery_events[0]["level"] == logging.INFO

def test_failed_discovery_emits_error(caplog, tmp_path):
    args = make_discovery_args(
        tmp_path,
        board_slugs=["broken"],
    )

    async def fake_collect(client, provider, slug, company):
        if slug == "broken":
            raise_http_503()

        return CollectionResult(jobs=[], skipped_invalid=0)

    with (
        patch(
            "job_hunter.cli.collect_with_diagnostics",
            side_effect=fake_collect,
        ),
        caplog.at_level(
            logging.INFO,
            logger="job_hunter.cli",
        ),
    ):
        asyncio.run(run(args))

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.cli"
        and record.message.startswith("{")
    ]

    discovery_events = [
        event
        for event in events
        if event["event"] == "discovery_completed"
    ]

    assert len(discovery_events) == 1
    assert discovery_events[0]["component"] == "discovery"
    assert discovery_events[0]["outcome"] == "failed"
    assert discovery_events[0]["level"] == logging.ERROR


def test_no_source_discovery_emits_warnings(caplog, tmp_path):
    args = make_discovery_args(
        tmp_path,
        board_slugs=[],
    )

    async def fake_collect(client, provider, slug, company):
        if slug == "broken":
            raise_http_503()

        return CollectionResult(jobs=[], skipped_invalid=0)

    with (
        patch(
            "job_hunter.cli.collect_with_diagnostics",
            side_effect=fake_collect,
        ),
        caplog.at_level(
            logging.INFO,
            logger="job_hunter.cli",
        ),
    ):
        asyncio.run(run(args))

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.cli"
        and record.message.startswith("{")
    ]

    discovery_events = [
        event
        for event in events
        if event["event"] == "discovery_completed"
    ]

    assert len(discovery_events) == 1
    assert discovery_events[0]["outcome"] == "no_sources"
    assert discovery_events[0]["level"] == logging.WARNING
