from pydantic import BaseModel, ConfigDict, Field

class GeminiUsage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True
    )

    prompt_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    thinking_tokens: int | None = Field(
        default=None, ge=0, strict=True
    )

    cached_input_tokens: int | None = Field(
        default=None, ge=0, strict=True
    )