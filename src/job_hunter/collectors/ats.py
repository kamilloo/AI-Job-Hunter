import asyncio
import re
import httpx
import logging

from job_hunter.calculate_retry_delay import calculate_retry_delay
from job_hunter.collectors.normalize_rows import normalize_rows
from job_hunter.collectors.normalize_rows import CollectionResult
from job_hunter.observability import make_log_event, emit_log
from job_hunter.should_retry import should_retry
from job_hunter.classify_http_error import classify_http_error, FailureCategory
from job_hunter.classify_transport_error import classify_transport_error

from job_hunter.models import Job
logger = logging.getLogger(__name__)

SLUG = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


async def collect(client: httpx.AsyncClient, provider: str, slug: str, company: str) -> list[Job]:
    result = await collect_with_diagnostics(
        client, provider, slug, company
    )
    return result.jobs

async def collect_with_diagnostics(
    client: httpx.AsyncClient,
    provider: str,
    slug: str,
    company: str,
) -> CollectionResult:
    if not SLUG.fullmatch(slug):
        raise ValueError("Invalid board slug")
    urls = {
        "greenhouse": (f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", {"content": "true"}),
        "ashby": (f"https://api.ashbyhq.com/posting-api/job-board/{slug}", {"includeCompensation": "true"}),
        "lever": (f"https://api.lever.co/v0/postings/{slug}", {"mode": "json"}),
    }
    if provider not in urls:
        raise ValueError(f"Unsupported provider: {provider}")
    endpoint, params = urls[provider]

    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            break
        except httpx.HTTPError as exc:
            if isinstance(exc, httpx.HTTPStatusError):
                category = classify_http_error(exc.response.status_code)
            else:
                category = classify_transport_error(exc)

            if not should_retry(
                category,
                attempt=attempt,
                max_attempts=max_attempts,
                retry_safe=True,
            ):
                emit_log(
                    logger,
                    make_log_event(
                        "http_request_failed",
                        component="ats",
                        outcome="failure",
                        attempt=attempt,
                        status_code=(
                            exc.response.status_code
                            if isinstance(exc, httpx.HTTPStatusError)
                            else None
                        ),
                        level=logging.ERROR,
                    ),
                )
                raise

            retry_after = (
                exc.response.headers.get("Retry-After")
                if isinstance(exc, httpx.HTTPStatusError)
                   and category == FailureCategory.RATE_LIMITED
                else None
            )

            delay = calculate_retry_delay(
                attempt=attempt,
                retry_after=retry_after,
            )
            emit_log(logger,
                     make_log_event(
                         event="http_retry_scheduled",
                         component='ats',
                         outcome="retry",
                         attempt=attempt,
                         status_code=
                         (exc.response.status_code
                         if isinstance(exc, httpx.HTTPStatusError)
                         else None),
                         level=logging.WARNING,
                         ),
                     )

            await asyncio.sleep(delay)

    data = response.json()
    rows = data if provider == "lever" else data["jobs"]

    return normalize_rows(provider, slug, company, rows)
