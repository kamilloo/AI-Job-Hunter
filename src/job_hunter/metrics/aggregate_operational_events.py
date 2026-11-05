
from collections.abc import Iterable
from decimal import Decimal

from job_hunter.model.Log import Log
from job_hunter.model.OperationalSummary import OperationalSummary


def aggregate_operational_events(
    events: Iterable[Log],
) -> OperationalSummary:
    operations_total = 0
    operations_success = 0
    operations_failure = 0
    total_duration_ms = 0.0
    gemini_usage_reports = 0
    prompt_tokens = 0
    output_tokens = 0
    total_tokens = 0

    gemini_cost_estimates = 0
    known_estimated_cost_usd = Decimal("0")

    for event in events:
        if event.event == "operation_completed":
            if event.duration_ms is None:
                raise ValueError(
                    "operation_completed event missing duration_ms"
                )

            if event.outcome not in ("success", "failure"):
                raise ValueError(
                    "operation_completed event has invalid outcome"
                )

            operations_total += 1
            total_duration_ms += event.duration_ms

            if event.outcome == "success":
                operations_success += 1
            else:
                operations_failure += 1

        elif event.event == "gemini_usage_reported":
            if event.prompt_tokens is None:
                raise ValueError(
                    "gemini_usage_reported missing prompt_tokens"
                )
            if event.output_tokens is None:
                raise ValueError(
                    "gemini_usage_reported missing output_tokens"
                )
            if event.total_tokens is None:
                raise ValueError(
                    "gemini_usage_reported missing total_tokens"
                )

            gemini_usage_reports += 1
            prompt_tokens += event.prompt_tokens
            output_tokens += event.output_tokens
            total_tokens += event.total_tokens

        elif event.event == "gemini_cost_estimated":
            if event.estimated_cost_usd is None:
                raise ValueError(
                    "gemini_cost_estimated missing estimated_cost_usd"
                )

            gemini_cost_estimates += 1
            known_estimated_cost_usd += event.estimated_cost_usd

    average_duration_ms = (
        total_duration_ms / operations_total
        if operations_total > 0
        else None
    )

    return OperationalSummary(
        operations_total=operations_total,
        operations_succeeded=operations_success,
        operations_failed=operations_failure,
        total_duration_ms=total_duration_ms,
        average_duration_ms=average_duration_ms,
        gemini_usage_reports=gemini_usage_reports,
        prompt_tokens=prompt_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        gemini_cost_estimates=gemini_cost_estimates,
        known_estimated_cost_usd=known_estimated_cost_usd,
    )
