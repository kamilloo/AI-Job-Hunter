"""Optional LLM analysis: the agent never overrides hard eligibility gates."""
import json
from pydantic import BaseModel, Field
from job_hunter.models import Job, Match, JobAnalysis, Eligibility
from job_hunter.recommend import recommend


class Analysis(BaseModel):
    reasons: list[str] = Field(description="Grounded reasons based only on supplied job description")
    concerns: list[str]
    ai_transition_score: int = Field(ge=0, le=100)

async def analyze(job: Job, match: Match, profile: dict, model: str) -> Match:
    import os
    from agents import Agent, Runner, AsyncComputer, OpenAIChatCompletionsModel, set_tracing_disabled
    gemini_key=os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        # Tracing to OpenAI is disabled' no OpenAI is required
        # set_tracing_disabled(True)
        client = AsyncOpenAI(
            api_key=gemini_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        model_backend = OpenAIChatCompletionsModel(model=model, openai_client=client)
    else:
        model_backend = model

    agent = Agent(name="Job Match Analyst", model=model_backend, output_type=JobAnalysis,
        instructions=("Evaluate a job against the candidate profile. Be skeptical and concise. "
                      "Only use supplied evidence. Do not infer missing salary, eligibility, "
                      "production AI experience, or company culture. Output specific reasons and concerns. "
                      "Do not decide final eligibility; deterministic checks own that decision."))
    candidate = {k: profile.get(k) for k in ("core_skills", "transferable_languages", "prefer_domains", "strong_specialism_gaps", "remote_requirement")}
    payload = {"candidate": candidate, "job": job.model_dump(mode="json"), "rules_match": match.model_dump(mode="json")}
    result = await Runner.run(agent, json.dumps(payload, ensure_ascii=False))
    outcome: JobAnalysis = result.final_output
    match.reasons.extend(outcome.reasons[:4]); match.concerns.extend(outcome.concerns[:4])
    match.ai_transition_score = outcome.ai_transition_score
    match.ai_analyzed = True
    recommended = recommend(outcome)
    if not recommended:
        match.eligibility = Eligibility.rejected
        match.concerns.append(outcome.location_evidence)
    return match
