import asyncio

import httpx

from job_hunter.collectors.verify_detail import verify_detail
from job_hunter.models import Job


def make_job(provider):
    return Job(
        provider=provider,
        board="example",
        external_id="123",
        company="Example",
        title="Backend Engineer",
        location="Remote - Poland",
        description="Python backend development.",
        url="https://example.com/jobs/123",
    )

def test_verify_detail_success():
    async def scenario():
        job = make_job(provider="greenhouse",)

        def handler(request):
            assert request.method == "GET"
            assert request.url.path.endswith(
                "/boards/example/jobs/123"
            )
            return httpx.Response(200, json={"id": 123})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            result = await verify_detail(client, job)

        assert result.verified is True
        assert result.error_type is None
        assert result.category is None
        assert result.status_code is None

        assert job.verified_live is True
        assert job.verified_at is not None

    asyncio.run(scenario())

def test_verify_detail_http_503_records_failure():
    async def scenario():
        job = make_job(provider="greenhouse",)

        def handler(request):
            return httpx.Response(
                503,
                json={"error": "internal-secret-details"},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            result = await verify_detail(client, job)

        assert result.verified is False
        assert result.error_type == "HTTPStatusError"
        assert result.category == "transient"
        assert result.status_code == 503

        assert job.verified_live is not True
        assert job.verified_at is None

        assert "internal-secret-details" not in str(result)

    asyncio.run(scenario())

def test_verify_detail_unsupported_provider():
    async def scenario():
        job = make_job(provider="unknown")

        async with httpx.AsyncClient() as client:
            result = await verify_detail(client, job)

        assert result.verified is False
        assert result.error_type == "UnsupportedProvider"
        assert result.category == "permanent"
        assert result.status_code is None

        assert job.verified_live is False
        assert job.verified_at is None

    asyncio.run(scenario())


def test_failed_reverification_clears_stale_success():
    async def scenario():
        job = make_job(provider="greenhouse")
        job.verified_live = True
        job.verified_at = "2026-11-02T10:00:00+00:00"

        def handler(request):
            return httpx.Response(503)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            result = await verify_detail(client, job)

        assert result.verified is False
        assert result.status_code == 503

        assert job.verified_live is False
        assert job.verified_at is None

    asyncio.run(scenario())

