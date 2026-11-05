from job_hunter.model.OperationalSummary import OperationalSummary


def render_operational_report(
    summary: OperationalSummary,
) -> str:
    return summary.model_dump_json()