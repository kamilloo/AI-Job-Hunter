from collections.abc import Mapping

from job_hunter.model.TokenPricing import TokenPricing


def resolve_model_pricing(
    model: str,
    pricing_table: Mapping[str, TokenPricing],
) -> TokenPricing | None:
    if not model.strip():
        raise ValueError("Model ID must not be blank")

    return pricing_table.get(model)