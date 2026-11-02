import asyncio
from unittest.mock import AsyncMock, patch, call
import httpx
import pytest

from job_hunter.collectors.ats import collect

def test_ats_bounded_retries():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
            status_code = 503 if len(requests) == 1 else 200

            return httpx.Response(
                status_code,
                json={"jobs": [{
                    "id": 1,
                    "title": "PHP Developer",
                    "content": "<p>PHP</p>",
                    "absolute_url": "https://example.com/jobs/1",
                }]},
            )

        transport = httpx.MockTransport(handler)

        with patch(
            "job_hunter.collectors.ats.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(transport=transport) as client:
                jobs = await collect(client, "greenhouse", "acme", "Acme")

            mock_sleep.assert_awaited_once_with(1.0)

        assert len(requests) == 2
        assert len(jobs) == 1
        assert all(request.method == "GET" for request in requests)
        assert jobs[0].description == "PHP"

    asyncio.run(scenario())

def test_ats_retry_exhaustion():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(503)

        transport = httpx.MockTransport(handler)

        with patch(
            "job_hunter.collectors.ats.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(transport=transport) as client:
                with pytest.raises(httpx.HTTPStatusError) as exc_info:
                    await collect(client, "greenhouse", "acme", "Acme")

            assert exc_info.value.response.status_code == 503
            assert len(requests) == 3

            mock_sleep.assert_has_awaits([
                call(1.0),
                call(2.0),
            ])

            assert mock_sleep.await_count == 2

    asyncio.run(scenario())

def test_ats_raise_400_response():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(400)

        transport = httpx.MockTransport(handler)

        with patch(
            "job_hunter.collectors.ats.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(transport=transport) as client:
                with pytest.raises(httpx.HTTPStatusError) as exc_info:
                    await collect(client, "greenhouse", "acme", "Acme")

            assert exc_info.value.response.status_code == 400
            assert len(requests) == 1

            assert mock_sleep.await_count == 0

    asyncio.run(scenario())

def test_ats_respects_retry_after():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)

            if len(requests) == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "5"},
                )

            return httpx.Response(200, json={"jobs": []})

        with patch(
            "job_hunter.collectors.ats.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                jobs = await collect(client, "greenhouse", "acme", "Acme")

            assert jobs == []
            assert len(requests) == 2
            mock_sleep.assert_awaited_once_with(5.0)

    asyncio.run(scenario())

def test_ats_recovers_from_connection_error():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)

            if len(requests) == 1:
                raise httpx.ConnectError("Connection failed")

            return httpx.Response(200, json={"jobs": []})

        transport = httpx.MockTransport(handler)

        with patch(
            "job_hunter.collectors.ats.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(transport=transport) as client:
                jobs = await collect(client, "greenhouse", "acme", "Acme")

            assert jobs == []
            assert len(requests) == 2
            mock_sleep.assert_awaited_once_with(1.0)

    asyncio.run(scenario())

