import asyncio
from unittest.mock import AsyncMock, patch, call
import httpx
import pytest
import json
import logging

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

def test_ats_retry_emits_structured_warning(caplog):
    requests = []

    def handler(request):
        requests.append(request)

        if len(requests) == 1:
            return httpx.Response(503)

        return httpx.Response(200, json={"jobs": []})

    async def scenario():
        with patch(
            "job_hunter.collectors.ats.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                await collect(
                    client,
                    provider="greenhouse",
                    slug="example",
                    company="Example",
                )

    with caplog.at_level(
        logging.WARNING,
        logger="job_hunter.collectors.ats",
    ):
        asyncio.run(scenario())

    retry_events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.collectors.ats"
        and record.message.startswith("{")
        and json.loads(record.message)["event"] == "http_retry_scheduled"
    ]

    assert len(requests) == 2
    assert len(retry_events) == 1

    assert retry_events[0]["event"] == "http_retry_scheduled"
    assert retry_events[0]["component"] == "ats"
    assert retry_events[0]["outcome"] == "retry"
    assert retry_events[0]["attempt"] == 1
    assert retry_events[0]["status_code"] == 503
    assert retry_events[0]["level"] == logging.WARNING

def test_ats_retry_exhaustion_emits_terminal_failure(caplog):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(503)

    async def scenario():
        with patch(
            "job_hunter.collectors.ats.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await collect(
                        client,
                        provider="greenhouse",
                        slug="example",
                        company="Example",
                    )
                    mock_sleep.assert_not_awaited()

    with caplog.at_level(
        logging.WARNING,
        logger="job_hunter.collectors.ats",
    ):
        asyncio.run(scenario())

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.collectors.ats"
        and record.message.startswith("{")
    ]

    retries = [
        event for event in events
        if event["event"] == "http_retry_scheduled"
    ]
    failures = [
        event for event in events
        if event["event"] == "http_request_failed"
    ]

    assert len(requests) == 3
    assert len(retries) == 2
    assert len(failures) == 1

    assert failures[0]["component"] == "ats"
    assert failures[0]["outcome"] == "failure"
    assert failures[0]["attempt"] == 3
    assert failures[0]["status_code"] == 503
    assert failures[0]["level"] == logging.ERROR

def test_ats_permanent_failure_emits_terminal_failure(caplog):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            400,
            json={"error": "secret-response-content"},
        )

    async def scenario():
        with patch(
            "job_hunter.collectors.ats.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                with pytest.raises(httpx.HTTPStatusError):
                    await collect(
                        client,
                        provider="greenhouse",
                        slug="example",
                        company="Example",
                    )

    with caplog.at_level(
        logging.WARNING,
        logger="job_hunter.collectors.ats",
    ):
        asyncio.run(scenario())

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.collectors.ats"
        and record.message.startswith("{")
    ]

    retries = [
        event for event in events
        if event["event"] == "http_retry_scheduled"
    ]

    failures = [
        event for event in events
        if event["event"] == "http_request_failed"
    ]

    assert len(requests) == 1
    assert len(failures) == 1
    assert len(retries) == 0

    assert failures[0]["component"] == "ats"
    assert failures[0]["outcome"] == "failure"
    assert failures[0]["attempt"] == 1
    assert failures[0]["status_code"] == 400
    assert failures[0]["level"] == logging.ERROR

    #avoid logging sensitive-data
    assert "secret" not in caplog.text
    assert "secret-response-content" not in caplog.text
    assert "https://example.com" not in caplog.text
    assert str(requests[0].url) not in caplog.text

def test_ats_success_emits_attempt_latency(caplog):
    def handler(request):
        return httpx.Response(200, json={"jobs": []})

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            await collect(
                client,
                provider="greenhouse",
                slug="example",
                company="Example",
            )

    with (
        patch(
            "job_hunter.collectors.ats.perf_counter",
        ) as mock_time,
        caplog.at_level(
            logging.INFO,
            logger="job_hunter.collectors.ats",
        ),
    ):
        mock_time.side_effect = [10.0, 10.125]
        asyncio.run(scenario())

    assert mock_time.call_count == 2

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.collectors.ats"
        and record.message.startswith("{")
    ]

    latency_events = [
        event for event in events
        if event["event"] == "http_attempt_completed"
    ]

    assert len(latency_events) == 1
    assert latency_events[0]["component"] == "ats"
    assert latency_events[0]["outcome"] == "success"
    assert latency_events[0]["attempt"] == 1
    assert latency_events[0]["status_code"] == 200
    assert latency_events[0]["duration_ms"] == pytest.approx(125.0)

def test_ats_failure_emits_attempt_latency(caplog):
    requests = []

    def handler(request):
        requests.append(request)
        status_code = 503 if len(requests) == 1 else 200

        return httpx.Response(
            status_code,
            json={"jobs": []} if status_code == 200 else {},
        )

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            await collect(
                client,
                provider="greenhouse",
                slug="example",
                company="Example",
            )

    with (
        patch(
            "job_hunter.collectors.ats.perf_counter",
            side_effect=[10.0, 10.125, 20.0, 20.125],
        ) as mock_clock,
        patch(
            "job_hunter.collectors.ats.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        caplog.at_level(
            logging.INFO,
            logger="job_hunter.collectors.ats",
        ),
    ):
        asyncio.run(scenario())

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.collectors.ats"
        and record.message.startswith("{")
    ]

    latency_events = [
        event for event in events
        if event["event"] == "http_attempt_completed"
    ]

    retry_events = [
        event for event in events
        if event["event"] == "http_retry_scheduled"
    ]

    terminal_failures = [
        event for event in events
        if event["event"] == "http_request_failed"
    ]

    assert len(requests) == 2
    assert mock_clock.call_count == 4
    mock_sleep.assert_awaited_once_with(1.0)

    assert len(latency_events) == 2
    assert len(retry_events) == 1
    assert terminal_failures == []

    first, second = latency_events

    assert first["component"] == "ats"
    assert first["outcome"] == "failure"
    assert first["attempt"] == 1
    assert first["status_code"] == 503
    assert first["duration_ms"] == pytest.approx(125.0)

    assert second["component"] == "ats"
    assert second["outcome"] == "success"
    assert second["attempt"] == 2
    assert second["status_code"] == 200
    assert second["duration_ms"] == pytest.approx(125.0)

def test_ats_transport_error_emits_latency(caplog):
    requests = []

    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout(
            "response timed out",
            request=request,
        )

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with pytest.raises(httpx.ReadTimeout) as exc_info:
                await collect(
                    client,
                    provider="greenhouse",
                    slug="example",
                    company="Example",
                )

            assert exc_info.value.request is requests[-1]

    with (
        patch(
            "job_hunter.collectors.ats.perf_counter",
            side_effect=[
                10.0, 10.100,  # Attempt 1: 100 ms
                20.0, 20.200,  # Attempt 2: 200 ms
                30.0, 30.300,  # Attempt 3: 300 ms
            ],
        ) as mock_clock,
        patch(
            "job_hunter.collectors.ats.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        caplog.at_level(
            logging.INFO,
            logger="job_hunter.collectors.ats",
        ),
    ):
        asyncio.run(scenario())

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "job_hunter.collectors.ats"
        and record.message.startswith("{")
    ]

    latency_events = [
        event
        for event in events
        if event["event"] == "http_attempt_completed"
    ]

    retry_events = [
        event
        for event in events
        if event["event"] == "http_retry_scheduled"
    ]

    terminal_failures = [
        event
        for event in events
        if event["event"] == "http_request_failed"
    ]

    # Three failed requests exhaust the ATS retry policy.
    assert len(requests) == 3
    assert mock_clock.call_count == 6

    # Backoff occurs only between attempts.
    assert mock_sleep.await_count == 2
    assert mock_sleep.await_args_list == [
        call(1.0),
        call(2.0),
    ]

    # Every HTTP attempt has its own latency measurement.
    assert len(latency_events) == 3
    assert len(retry_events) == 2
    assert len(terminal_failures) == 1

    expected_durations = [100.0, 200.0, 300.0]

    for attempt, (event, duration) in enumerate(
        zip(latency_events, expected_durations),
        start=1,
    ):
        assert event["event"] == "http_attempt_completed"
        assert event["component"] == "ats"
        assert event["outcome"] == "failure"
        assert event["attempt"] == attempt
        assert event["duration_ms"] == pytest.approx(duration)
        assert event["level"] == logging.WARNING

        # A transport timeout has no HTTP response status.
        assert "status_code" not in event

    # Only attempts 1 and 2 schedule another request.
    assert [event["attempt"] for event in retry_events] == [1, 2]

    for event in retry_events:
        assert event["component"] == "ats"
        assert event["outcome"] == "retry"
        assert event["level"] == logging.WARNING
        assert "status_code" not in event

    # Attempt 3 fails permanently due to retry exhaustion.
    assert terminal_failures == [
        {
            "event": "http_request_failed",
            "component": "ats",
            "outcome": "failure",
            "attempt": 3,
            "level": logging.ERROR,
        }
    ]

    # Sensitive exception messages must not enter structured logs.
    assert "response timed out" not in caplog.text
