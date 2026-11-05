import logging
from decimal import Decimal
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

    # LLM Usage Logging
    prompt_tokens: int | None = Field(default=None, ge=0, strict=True)
    output_tokens: int | None = Field(default=None, ge=0, strict=True)
    total_tokens: int | None = Field(default=None, ge=0, strict=True)

    # LLM Cost Logging
    model: str | None = None
    estimated_cost_usd: Decimal | None = Field(default=None,ge=0,allow_inf_nan=False)