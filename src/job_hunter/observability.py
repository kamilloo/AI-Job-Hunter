import logging

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
    )

def emit_log(logger: logging.Logger, event: Log) -> None:
    logger.log(
        event.level,
        event.model_dump_json(exclude_none=True),
    )
