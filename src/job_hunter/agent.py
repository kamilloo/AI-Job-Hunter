"""Optional Agents SDK transport for CLI technical assessments via Gemini."""
import asyncio

from job_hunter.agents.requirements_agent import (
    ASSESSMENT_INSTRUCTIONS, build_prompt, gemini_config,
)
from job_hunter.model.RequirementAssessment import TechnicalAssessment


async def assess_requirements_agent(
    candidate_profile: dict, job_description: str, model: str | None = None,
) -> TechnicalAssessment:
    """Use one bounded agent turn; callers own grounding and final eligibility."""
    key, selected_model = gemini_config(model)
    if not job_description.strip():
        raise ValueError("An employer job description is required")
    # Optional imports keep the default CLI and evaluation runners SDK-free.
    from agents import Agent, Runner, RunConfig, OpenAIChatCompletionsModel
    from openai import AsyncOpenAI

    async with AsyncOpenAI(
        api_key=key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout=60,
        max_retries=0,
    ) as client:
        agent = Agent(
            name="Technical Requirements Assessor",
            model=OpenAIChatCompletionsModel(model=selected_model, openai_client=client),
            instructions=ASSESSMENT_INSTRUCTIONS,
            output_type=TechnicalAssessment,
        )
        async with asyncio.timeout(75):
            result = await Runner.run(
                agent,
                build_prompt(candidate_profile, job_description),
                max_turns=1,
                run_config=RunConfig(tracing_disabled=True, trace_include_sensitive_data=False),
            )
    # Do not trust the result object's annotation or an already-created model.
    output = result.final_output
    if isinstance(output, TechnicalAssessment):
        output = output.model_dump(mode="json")
    return TechnicalAssessment.model_validate(output)
