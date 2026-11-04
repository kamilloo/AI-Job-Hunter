from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class TokenPricing(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    input_per_million: Decimal = Field(ge=0, allow_inf_nan=False)
    output_per_million: Decimal = Field(ge=0, allow_inf_nan=False)
    cached_input_per_million: Decimal = Field(ge=0, allow_inf_nan=False)


