from job_hunter.agent import analyze
from job_hunter.models import JobAnalysis, Eligibility
from job_hunter.recommend import recommend


def test_rejects_france_only_remote_job() -> None:
    analysis = JobAnalysis(
        reasons=["Strong infrastructure fit"],
        concerns=["Remote work restricted to France"],
        ai_transition_score=85,
        location_eligibility=Eligibility.rejected,
        location_evidence="Remote work restricted to France",
        recommendation="Reject",
    )

    assert recommend(analysis) is False
