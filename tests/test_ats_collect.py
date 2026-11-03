import asyncio
import httpx

from job_hunter.collectors.ats import collect, collect_with_diagnostics


def test_ats_collect():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(
                200,
                json={"jobs": [{
                    "id": 1,
                    "title": "PHP Developer",
                    "content": "<p>PHP</p>",
                    "absolute_url": "https://example.com/jobs/1",
                }]},
            )

        transport = httpx.MockTransport(handler)

        async with httpx.AsyncClient(transport=transport) as client:
            jobs = await collect(client, "greenhouse", "acme", "Acme")

        assert len(jobs) == 1
        assert jobs[0].description == "PHP"

    asyncio.run(scenario())

def test_ats_collect_with_diagnostics():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(
                200,
                json={"jobs": [{
                    "id": 1,
                    "title": "PHP Developer",
                    "content": "<p>PHP</p>",
                    "absolute_url": "https://example.com/jobs/1",
                }]},
            )

        transport = httpx.MockTransport(handler)

        async with httpx.AsyncClient(transport=transport) as client:
            collection_with_diagnostics = await collect_with_diagnostics(client, "greenhouse", "acme", "Acme")

        jobs = collection_with_diagnostics.jobs
        assert len(jobs) == 1
        assert jobs[0].description == "PHP"
        assert collection_with_diagnostics.skipped_invalid == 0

    asyncio.run(scenario())

def test_collect_with_diagnostics_counts_invalid_jobs():
    async def scenario():
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "id": 123,
                            "title": "Backend Engineer",
                            "absolute_url": "https://example.com/jobs/123",
                            "location": {"name": "Remote - Poland"},
                            "content": "Python backend development.",
                        },
                        {
                            "id": 456,
                            # Missing required title and URL
                        },
                    ]
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            result = await collect_with_diagnostics(
                client,
                provider="greenhouse",
                slug="example",
                company="Example",
            )

        assert len(result.jobs) == 1
        assert result.jobs[0].title == "Backend Engineer"
        assert result.skipped_invalid == 1

    asyncio.run(scenario())

def test_collect_still_returns_jobs_list():
    async def scenario():
        def handler(request):
            return httpx.Response(
                200,
                json={"jobs": []},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            result = await collect(
                client,
                provider="greenhouse",
                slug="example",
                company="Example",
            )

        assert isinstance(result, list)
        assert result == []

    asyncio.run(scenario())