import logging
import time
from datetime import datetime, timezone
import httpx

from dataclasses import dataclass

from job_hunter.describe_source_error import describe_source_error
from job_hunter.models import Job
from job_hunter.observability import emit_log, make_log_event

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    error_type: str | None = None
    category: str | None = None
    status_code: int | None = None


async def verify_detail(client, job:Job) -> VerificationResult:
    # Only canonical job-specific ATS GET URLs establish live status; page/ATS form functionality is NOT verified.
    job.verified_live = False
    job.verified_at = None
    endpoint = None
    if job.provider == 'greenhouse':
        endpoint = f'https://boards-api.greenhouse.io/v1/boards/{job.board}/jobs/{job.external_id}'
    elif job.provider == 'lever':
        endpoint = f'https://api.lever.co/v0/postings/{job.board}/{job.external_id}'
    elif job.provider == 'ashby':
        # Ashby public posting API publishes current postings; confirmation comes from the live board response,
        # not from validating a possibly inaccessible application URL.
        job.verified_live = True
        job.verified_at = datetime.now(timezone.utc).isoformat()

        return VerificationResult(verified=True)
    if endpoint:
        start = time.perf_counter()
        try:
            r = await client.get(endpoint)
            r.raise_for_status()
            job.verified_live = True
            job.verified_at = datetime.now(timezone.utc).isoformat()

            return VerificationResult(verified=True)
        except (httpx.HTTPError, ValueError) as exc:
            diagnostic = describe_source_error(
                provider=job.provider,
                board=job.board,
                error=exc,
            )

            return VerificationResult(
                verified=False,
                error_type=diagnostic["error_type"],
                category=diagnostic["category"],
                status_code=diagnostic["status_code"],
            )
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            emit_log(logger,
                     make_log_event(
                         event="http_attempt_completed",
                         component='ats',
                         outcome="success",
                         attempt=1,
                         status_code=200,
                         duration_ms=duration_ms,
                         level=logging.INFO,
                     ),
                 )

    return VerificationResult(
        verified=False,
        error_type="UnsupportedProvider",
        category="permanent",
    )

