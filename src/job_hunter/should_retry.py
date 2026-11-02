from job_hunter.classify_http_error import FailureCategory


def should_retry(
    category: FailureCategory,
    attempt: int,
    max_attempts: int,
    retry_safe: bool,
) -> bool:
    if attempt <= 0 or max_attempts <= 0:
        raise ValueError("attempt and max_attempts must be positive")

    if not retry_safe or attempt >= max_attempts:
        return False

    return category in {
        FailureCategory.TRANSIENT,
        FailureCategory.RATE_LIMITED,
    }