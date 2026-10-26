# AI Job Hunter — Goals and Engineering Roadmap

## 1. Project Vision

AI Job Hunter is a Python-based, AI-assisted job discovery and matching application.

The project serves two purposes:

1. **Solve a real problem:** Discover and evaluate job opportunities that match a candidate's experience, preferences, compensation expectations, and career goals.
2. **Develop AI engineering expertise:** Build a practical application involving LLMs, agents, external APIs, structured data, deterministic guardrails, evaluation, and reliability engineering.

The project is also intended to serve as an AI engineering portfolio demonstrating practical engineering decisions rather than simply integrating an LLM API.

## 2. Product Goals

The application should:

- Discover real job vacancies from supported applicant tracking systems (ATS), including Greenhouse, Lever, and Ashby.
- Normalize job data into validated, structured models.
- Evaluate opportunities against a configurable candidate profile.
- Enforce hard constraints such as geographic restrictions, remote-work requirements, and application availability.
- Evaluate technical suitability using both deterministic logic and AI.
- Distinguish eligible, rejected, and uncertain opportunities.
- Rank opportunities according to relevance and AI engineering career-transition potential.
- Produce explainable recommendations supported by job descriptions and candidate evidence.
- Avoid fabricating jobs, candidate skills, or unsupported eligibility conclusions.

### Non-goals

The project is not intended to:

- Automatically apply to vacancies without user approval.
- Treat LLM responses as authoritative without validation.
- Guarantee that a candidate will be hired or satisfy every employer requirement.
- Replace human judgment for ambiguous job requirements.
- Build a general-purpose autonomous recruiting platform.

## 3. Engineering Principles

### Reliability over confidence

Unknown information must remain unknown. When evidence is insufficient, the application should request manual review rather than invent a definitive conclusion.

### Deterministic rules for hard constraints

Geographic restrictions, mandatory office attendance, and other verifiable restrictions should not depend exclusively on an LLM's interpretation.

### AI for semantic assessment

Use LLMs where natural-language interpretation adds value, especially for extracting technical requirements, distinguishing mandatory from preferred skills, and evaluating transferable experience.

### Evidence-based decisions

Assessments should reference the original job description and verified candidate information.

### Separation of responsibilities

Job discovery, eligibility checks, technical assessment, scoring, evaluation, and reporting should remain distinct components.

### Measurable quality

Maintain labeled test cases, run evaluations, track false positives and regressions, and investigate disagreements rather than optimizing solely for high accuracy.

### Reproducibility

Track source code, fixtures, configuration and tests in Git. Generate timestamped evaluation reports locally without requiring every execution artifact to be committed.

---

## 4. Project Milestones

### Milestone 1 — Working MVP

**Status: Completed**

**Goal:** Build an end-to-end Python application capable of discovering, evaluating, and ranking job opportunities.

**Scope:**
- Python project structure and CLI.
- Candidate profile configuration.
- Structured `Job` and `Match` models using Pydantic.
- Basic job ingestion and normalization.
- Initial eligibility rules and relevance scoring.
- Unit tests for essential functionality.

**Learning outcomes:**
- Python application architecture.
- Pydantic data modeling.
- Type-safe interfaces.
- Test-driven, modular development.

**Completion criteria:** The application can process job data and produce structured recommendations.

### Milestone 2 — Real Job Discovery and AI Matching

**Status: Completed**

**Goal:** Replace example-only matching with real job data and integrate LLM-assisted analysis.

**Scope:**
- Integration with ATS job sources.
- Retrieval of job descriptions and application URLs.
- Structured job normalization.
- Integration with Gemini and the OpenAI Agents SDK.
- Evidence-based matching against the candidate profile.
- Handling of incomplete job information.

**Learning outcomes:**
- External API integration.
- LLM and agent workflows.
- Structured model responses.
- Grounding AI analysis in external data.

**Completion criteria:** The application discovers actual vacancies and can perform AI-assisted analysis using their descriptions.

### Milestone 3 — Eligibility and Scoring Separation

**Status: Completed**

**Goal:** Make matching decisions more explainable and prevent ranking scores from overriding hard restrictions.

**Scope:**
- Introduce explicit `eligible`, `review`, and `rejected` states.
- Separate remote and geographic eligibility.
- Introduce explicit eligibility factors and aggregation.
- Handle mandatory office attendance and geographic exclusions.
- Distinguish technical fit from eligibility.
- Preserve reasons, concerns, and evidence in evaluation results.
- Add automated tests for eligibility rules.

**Learning outcomes:**
- Hybrid deterministic/AI architectures.
- Decision modeling.
- Conservative uncertainty handling.
- Rule-based guardrails around AI output.

**Completion criteria:** A high technical score cannot override a confirmed hard restriction, and missing evidence is not automatically treated as eligibility.

### Milestone 4 — Evaluation Framework

**Status: Functionally complete; final refinements and documentation**

**Goal:** Build a repeatable way to measure matching quality and identify regressions.

**Scope:**
- Golden datasets containing real, synthetic, and historical job examples.
- Separately defined deterministic and AI reference assessments.
- Offline deterministic evaluation runner.
- Explicit live Gemini evaluation runner.
- Structured JSON evaluation artifacts.
- Accuracy, false-eligible and false-rejected metrics.
- Confusion matrix and mismatch reporting.
- Input hashes, Git revision, model and prompt metadata for reproducibility.
- Unit tests for metrics and integration tests for evaluation runners.
- Mocked Gemini assessments to avoid API calls in the normal test suite.
- Generated evaluation results excluded from Git.

**Current evaluation baseline (October 26, 2026):**
- 12 deterministic golden cases.
- 12/12 classifications matching the deterministic reference labels.
- Zero false-eligible predictions in that dataset.
- Four live Gemini technical-assessment experiments: E02, E05, E07, and E12.
- A documented disagreement involving transferable technical fit versus mandatory skill verification in E12.

**Important limitation:** Dataset accuracy measures agreement with curated reference labels, not guaranteed accuracy on unseen job listings.

**Remaining completion work:**
- Final report-consistency and empty-comparison behavior checks.
- Run the full automated test suite.
- Document the evaluation methodology and limitations.

**Learning outcomes:**
- Evaluation-driven AI development.
- Golden-dataset design.
- Regression detection.
- Confusion matrices and false-positive analysis.
- Reproducible experiments.
- Separating deterministic tests from live LLM evaluations.

**Completion criteria:** A developer can run the offline evaluation locally, inspect classifications and metrics, reproduce the inputs, and detect behavioral regressions without calling Gemini.

---

## 5. Next Development Phase — AI Reliability

*This phase extends the original four milestones.*

### Milestone 5 — Technical Assessment Quality and Grounding

**Status: Planned**

**Goal:** Improve the quality of LLM-generated technical assessments using measured evidence.

**Planned scope:**
- Separate mandatory, preferred, and optional job requirements.
- Prevent LLMs from treating transferable skills as verified production experience.
- Improve candidate evidence, including concrete engineering experience.
- Validate job evidence against source descriptions.
- Distinguish technical fit from strict verification of mandatory skills.
- Expand the labeled AI evaluation dataset.
- Analyze failure cases and compare assessment changes against the baseline.

**Completion criteria:** The AI assessment pipeline demonstrates measurable improvements in evidence quality and technical-fit judgments without increasing unsafe positive recommendations.

### Milestone 6 — Operational Reliability

**Status: Planned**

**Goal:** Make the application robust under realistic API and model failures.

**Planned scope:**
- Timeouts, retries, and backoff.
- API rate-limit handling.
- Structured logging and diagnostics.
- Safe handling of credentials.
- Explicit error and partial-failure states.
- Repeatable offline regression tests.
- CI checks.
- Cost and latency reporting for LLM requests.

**Completion criteria:** Expected provider failures do not silently corrupt recommendations, leak sensitive data, or prevent useful partial results where appropriate.

### Milestone 7 — Portfolio Readiness

**Status: Planned**

**Goal:** Present AI Job Hunter as a maintainable, demonstrable AI engineering project.

**Planned scope:**
- Clear architecture documentation.
- Setup and execution instructions.
- Explanation of agent and LLM responsibilities.
- Evaluation methodology and baseline results.
- Important engineering trade-offs and limitations.
- A realistic end-to-end demonstration.
- GitHub README improvements.

**Completion criteria:** Another developer or interviewer can understand the architecture, run the core application, reproduce offline evaluations, and discuss the reliability decisions.

---

## 6. Success Criteria

The project will be considered successful when:

1. It discovers real, relevant opportunities and produces useful, explainable recommendations.
2. It consistently respects confirmed hard eligibility restrictions.
3. It identifies uncertain technical requirements without fabricating candidate expertise.
4. It supports repeatable offline testing and intentional live LLM evaluation.
5. Improvements can be measured against stable, documented reference data.
6. Its architecture and engineering trade-offs are clear enough to demonstrate in an AI engineering interview.

## 7. Current Priorities

1. Close the remaining small validation and documentation items in Milestone 4.
2. Establish the current deterministic evaluation as the baseline.
3. Improve Gemini requirement extraction and evidence validation.
4. Expand AI evaluation coverage beyond the initial four examples.
5. Move toward operational reliability and portfolio readiness.

## 8. Guiding Principle

**AI Job Hunter should not merely produce plausible recommendations. It should produce recommendations whose reasoning, evidence, uncertainties, and limitations can be inspected and evaluated.**