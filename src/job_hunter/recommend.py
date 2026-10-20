from job_hunter.models import JobAnalysis, Eligibility


def recommend(analysis: JobAnalysis) -> bool:
    if analysis.location_eligibility != Eligibility.eligible:
        return False

    return analysis.ai_transition_score > 70