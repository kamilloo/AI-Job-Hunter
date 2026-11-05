import logging
from decimal import Decimal
from uuid import UUID

from job_hunter.model.Log import Log

def make_log_event(
    event: str,
    *,
    component: str,
    outcome: str,
    attempt: int | None = None,
    status_code: int | None = None,
    duration_ms: float | None = None,
    level: int = logging.INFO,
    prompt_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    model: str | None = None,
    estimated_cost_usd: Decimal | None = None,
    operation_id: UUID | None = None,
) -> Log:
    return Log(
        event=event,
        outcome=outcome,
        component=component,
        attempt=attempt,
        status_code=status_code,
        duration_ms=duration_ms,
        level=level,
        prompt_tokens=prompt_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model=model,
        estimated_cost_usd=estimated_cost_usd,
        operation_id=operation_id,
    )

def emit_log(logger: logging.Logger, event: Log) -> None:
    logger.log(
        event.level,
        event.model_dump_json(exclude_none=True),
    )
