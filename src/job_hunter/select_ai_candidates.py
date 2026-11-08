"""Choose AI work using existing deterministic matches only."""
from job_hunter.models import Eligibility, Job, Match


def select_ai_candidates(
    items: list[tuple[Job, Match]], limit: int | None = None,
) -> list[tuple[Job, Match]]:
    """Select highest-fit non-rejected jobs; callers exclude handled jobs."""
    candidates = sorted(
        (item for item in items if item[1].eligibility != Eligibility.rejected),
        key=lambda item: (-item[1].score, item[0].key),
    )
    return candidates if limit is None else candidates[:limit]
