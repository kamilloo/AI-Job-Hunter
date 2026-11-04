import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Log(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: str
    component: str
    outcome: str

    attempt: int | None = Field(default=None, ge=1)
    status_code: int | None = Field(default=None, ge=100, le=599)

    level: Literal[
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    ] = logging.INFO

    duration_ms: float | None = Field(
        default=None, ge=0,allow_inf_nan=False
    )