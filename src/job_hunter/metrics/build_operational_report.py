from collections.abc import Iterable

from job_hunter.metrics.aggregate_operational_events import aggregate_operational_events
from job_hunter.metrics.render_operational_report import render_operational_report
from job_hunter.model.Log import Log


def build_operational_report(
    events: Iterable[Log],
) -> str:
    summary = aggregate_operational_events(events)
    return render_operational_report(summary)