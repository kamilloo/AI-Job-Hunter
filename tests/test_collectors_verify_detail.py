import asyncio
import logging

import httpx
import pytest

from job_hunter.collectors.verify_detail import verify_detail
from job_hunter.model.Log import Log
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


@pytest.mark.parametrize("provider", ["greenhouse", "lever"])
@pytest.mark.parametrize("response", [200, 204, 404, 429, 503, "timeout"])
def test_verify_detail_logs_actual_http_outcome(provider, response, caplog):
    async def scenario():
        job = make_job(provider)

        def handler(request):
            if response == "timeout":
                raise httpx.ReadTimeout(
                    "private-provider-error", request=request
                )
            return httpx.Response(
                response, text="private-provider-response"
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await verify_detail(client, job)

    logger_name = "job_hunter.collectors.verify_detail"
    with caplog.at_level(logging.INFO, logger=logger_name):
        result = asyncio.run(scenario())

    records = [r for r in caplog.records if r.name == logger_name]
    assert len(records) == 1
    record = records[0]
    event = Log.model_validate_json(record.getMessage())
    success = response in (200, 204)
    expected_level = logging.INFO if success else logging.WARNING

    assert result.verified is success
    assert event.event == "http_attempt_completed"
    assert event.component == "ats"
    assert event.outcome == ("success" if success else "failure")
    assert event.status_code == (None if response == "timeout" else response)
    assert event.level == record.levelno == expected_level
    assert event.attempt == 1
    assert event.duration_ms is not None and event.duration_ms >= 0
    assert "private-provider" not in record.getMessage()
    assert "https://" not in record.getMessage()

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

