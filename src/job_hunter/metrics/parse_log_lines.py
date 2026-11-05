
from collections.abc import Iterable, Iterator

from pydantic import ValidationError

from job_hunter.model.Log import Log


def parse_log_lines(lines: Iterable[str]) -> Iterator[Log]:
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue

        try:
            yield Log.model_validate_json(line)
        except (ValidationError, ValueError) as exc:
            raise ValueError(
                f"Invalid structured log at line {line_number}"
            ) from exc
