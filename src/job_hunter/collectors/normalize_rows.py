from dataclasses import dataclass, field

from job_hunter.collectors.normalize import normalize
from job_hunter.models import Job


@dataclass
class CollectionResult:
    jobs: list[Job] = field(default_factory=list)
    skipped_invalid: int = 0


def normalize_rows(
    provider: str,
    slug: str,
    company: str,
    rows: list[dict],
) -> CollectionResult:
    result = CollectionResult()

    for row in rows:
        if provider == "ashby" and row.get("isListed") is False:
            continue

        try:
            result.jobs.append(normalize(provider, slug, company, row))
        except (KeyError, ValueError):
            result.skipped_invalid += 1

    return result
