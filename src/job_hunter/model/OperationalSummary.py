
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OperationalSummary(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )

    operations_total: int = Field(ge=0)
    operations_succeeded: int = Field(ge=0)
    operations_failed: int = Field(ge=0)

    total_duration_ms: float = Field(
        ge=0,
        allow_inf_nan=False,
    )

    average_duration_ms: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )

    gemini_usage_reports: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    gemini_cost_estimates: int = Field(ge=0)
    known_estimated_cost_usd: Decimal = Field(
        ge=0,
        allow_inf_nan=False,
    )
