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

**Status: Completed (Tasks 5.1–5.4, including 5.4.5); implementation and tests pushed to master.**

**Goal:** Ground Gemini technical assessments, separate overall transferable fit from mandatory skill verification, and turn observed model failures into reproducible, measurable regressions.

**Task 5.1 — Job-description evidence grounding (completed)**
- Validate model-supplied quotations by normalized exact-substring matching against the original job description.
- Record per-requirement `evidence_validation` and treat unsupported job quotations conservatively.
- Cover supported, fabricated and whitespace-normalized quotations with offline tests.

**Task 5.2 — Technical fit versus mandatory verification (completed)**
- Represent `TechnicalFit` (`strong`, `partial`, `weak`) independently from requirement verification and final eligibility.
- Preserve deterministic hard restrictions when combining decisions; test all nine eligibility combinations.
- Allow strong transferable fit to coexist with `review` for mandatory requirements that remain unverified.

**Task 5.3 — Structured candidate evidence (completed)**
- Introduce structured candidate experience records (technology, context, production usage, years) in the Pydantic profile and YAML configuration.
- Supply those records to Gemini while prohibiting preferred job titles and transferable technologies from being used as proof of direct production experience.
- Preserve `unknown` status and empty candidate evidence when direct experience is undocumented.

**Task 5.4 — Focused AI regressions and measurable quality (completed)**
- Compare requirement classifications despite variable model wording and combined/split skill requirements.
- Add focused negative regressions for unsupported full-stack experience, Redis queues versus AWS SQS, and undocumented TypeScript/Node.js experience; include a verified production AWS SQS positive control.
- Validate candidate quotations against individual documented experience contexts; reject fabricated quotations through offline negative controls.
- Calculate independent classification, job-grounding, candidate-grounding and overall pass rates. Candidate grounding uses an applicable nonempty-quotation denominator.
- Add curated `expected_technical_fit` labels, technical-fit agreement rates and case-level mismatch diagnostics without changing the classification/grounding pass criterion.
- Implement the offline `evaluations.compare_reports` CLI to compare saved runs by case ID, identify technical-fit changes, report added/removed cases, and warn about differing dataset, model, instructions or output schema.

**Recorded focused baseline (October 30, 2026; Gemini 3.5 Flash Lite)**
- Four focused cases; **4/4** requirement-classification regression passes.
- **4/4** job-description grounding passes.
- **1/1** applicable candidate-quotation grounding pass (three cases appropriately contain no candidate quotation).
- **4/4** overall regression passes and **4/4** agreement with curated technical-fit reference labels.
- An offline comparison of two October 30 runs found two technical-fit prediction changes (full-stack `partial → weak`; TypeScript/Node.js `weak → partial`) and correctly warned that the dataset hashes differ due to updated reference labels. This is an observed change, **not evidence of an improved model**.

**Commands**
```bash
pytest -q
python -m evaluations.run_requirements_evaluation  # explicit, paid Gemini calls
python -m evaluations.compare_reports <baseline-report.json> <current-report.json>
```

**Remaining limitations and follow-up targets**
- Four curated focused cases are regression controls, not a representative estimate of real-world AI accuracy.
- Focused classification pass rate is case-level; requirement-level confusion matrices and broader optional/mandatory coverage remain future refinements.
- Exact-substring grounding verifies quotation provenance, not whether the quoted evidence logically proves the skill or matches production/seniority requirements.
- Technical-fit labels involve human judgment; repeated live predictions can vary even with unchanged prompts.
- E12 is a reconstructed historical job summary rather than a verbatim employer posting; continue treating its source provenance explicitly.
- Resolve contradictory Docker production/context details from verified candidate facts.
- Generated reports may contain candidate and job data and stay outside version control; retain useful summary baselines in documentation.

**Completion criteria met:** The project can detect fabricated evidence, preserve uncertainty, measure focused technical-assessment quality separately from deterministic eligibility, and compare saved experiments reproducibly. Operational hardening continues in Milestone 6.

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

1. Begin Milestone 6 by auditing external ATS and Gemini failure handling, timeouts, rate limits, retries and partial-result behavior.
2. Add safe structured diagnostics, request cost/latency measurement and CI verification without exposing credentials.
3. Resolve verified candidate-profile inconsistencies (including Docker production experience).
4. Keep curated regression fixtures and evaluation methodology current as new failure cases appear; avoid interpreting tiny in-sample pass rates as general accuracy.
5. Prepare Milestone 7 architecture documentation, a reproducible end-to-end demonstration, and a clear explanation of the legacy CLI AI path versus the separate technical assessor.

## 8. Guiding Principle

**AI Job Hunter should not merely produce plausible recommendations. It should produce recommendations whose reasoning, evidence, uncertainties, and limitations can be inspected and evaluated.**