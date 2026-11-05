# AI Job Hunter

**Evidence-aware job discovery, eligibility screening, and LLM-assisted technical assessment.**

AI Job Hunter is a Python 3.11+ portfolio project that collects job postings from selected applicant tracking systems (ATS), compares them with a configurable candidate profile, and produces explainable job recommendations. It combines **deterministic eligibility checks** with optional AI analysis, plus an evaluation framework for measuring and investigating mistakes.

The primary use case is finding backend, platform, and AI-transition roles that can be performed remotely from Poland. The profile is configurable; the project is not a general web crawler or an automated job-application service.

## Project goals

- Discover real jobs from official public ATS endpoints rather than inventing openings.
- Normalize job data into validated Pydantic models.
- Respect hard constraints, including location, remote-work eligibility, and application verification.
- Keep eligibility (`eligible`, `review`, `rejected`) separate from relevance and AI-transition scores.
- Use an LLM to assess natural-language technical requirements while explicitly preserving uncertainty and evidence.
- Measure classification behavior using labeled fixtures, offline tests, optional live Gemini experiments, and JSON reports.
- Handle provider failures with bounded retries, partial-discovery recovery, and structured diagnostics.
- Track request and operation latency, Gemini token usage, and conservatively estimated cost; aggregate validated events into JSON operational reports.

**Design principle:** An appealing job or high similarity score must not override a confirmed hard restriction. Missing evidence calls for review, not an unsupported positive recommendation.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e '.[dev,ai]'
pytest -q
```

Configure your candidate preferences in `config/profile.yaml`, and add actual company board IDs to `config/sources.yaml`. Board identifiers must come from official Greenhouse, Lever, or Ashby careers pages. Each configured board retrieves openings for **that company**, not jobs across the entire internet.

Run the daily discovery CLI:

```bash
job-hunter --output reports/daily.md
```

Open `reports/daily.md` to inspect ranked results and evidence. If no company boards are configured, the command can produce a valid report with zero jobs.

> **CLI AI path:** `job-hunter --ai` uses the older `job_hunter.agent` implementation, **not** the separate Gemini technical-requirements evaluation described below. The current `agent.py` has an unresolved import/client setup issue, so its live OpenAI/Gemini execution should be verified and fixed before relying on the command. The deterministic CLI does not require an LLM key.

## How the application works

1. **Collect:** `src/job_hunter/collectors/ats.py` retrieves public Greenhouse, Lever, and Ashby postings.
2. **Normalize:** Structured `Job` objects are validated with Pydantic and deduplicated by `provider:board:external_id`.
3. **Verify:** The CLI checks Greenhouse/Lever job-detail endpoints or uses the current Ashby public board response to record listing availability. This does **not** verify that an application form accepts submissions.
4. **Evaluate:** `src/job_hunter/evaluate.py` applies deterministic checks for role, location, remote-work conditions, company history and other evidence; it produces eligibility, scores, reasons and concerns.
5. **Review technical requirements:** The separate Gemini assessor extracts job requirements and compares them with the candidate profile, recording `met`, `unknown`, or other supported requirement statuses and their evidence. The AI evaluation runner combines its technical verdict with deterministic eligibility; a deterministic rejection cannot be overridden.
6. **Report:** The CLI generates a Markdown job report and stores seen jobs in SQLite. Evaluation scripts generate detailed JSON artifacts with reference comparisons and reproducibility metadata.

**Interpretation of labels:** In a *deterministic-only* evaluation, `eligible` means that the deterministic gates pass; it does **not** prove every specialist technical requirement is met. The AI-assisted final classification may downgrade such a case to `review` when mandatory skills are not established.

### Job tracking

The SQLite database tracks seen jobs and lets the CLI skip jobs marked `applied`, `skipped`, or `dismissed`. To inspect or manually mark a job:

```bash
python -c "import sqlite3; c=sqlite3.connect('jobs.sqlite3'); print(c.execute('select key,status from jobs').fetchall())"
python -c "import sqlite3; c=sqlite3.connect('jobs.sqlite3'); c.execute('update jobs set status=? where key=?', ('applied','greenhouse:example:123')); c.commit()"
```

These examples manipulate the local database directly; a dedicated job-status CLI is not yet provided.

## Operational reliability and metrics

**Milestone 6 is implemented for its documented scope.** ATS and Gemini HTTP operations classify failures and use bounded retry policies. ATS GET requests allow up to three total attempts; Gemini generation allows up to two for eligible failures, while ambiguous timeout failures are not retried automatically. Discovery isolates failing boards, preserves successful sources, and reports `complete`, `partial`, `failed`, or `no_sources` rather than silently dropping failures.

### Structured logging and latency

Validated JSON log events record scheduled retries, terminal HTTP failures, individual HTTP attempt durations (`http_attempt_completed`), and end-to-end operation durations (`operation_completed`). Operation timing includes retries and backoff; Gemini operation timing also includes assessment response parsing and validation. The metrics aggregator counts operation durations **without adding HTTP attempt durations again**. Diagnostics avoid logging raw job descriptions, candidate details, API keys, URLs, and raw provider exceptions.

### Gemini usage and estimated costs

When Gemini provides valid usage metadata, the assessor emits `gemini_usage_reported` with observed token counts. Cost estimates use strict token accounting, model-specific pricing lookup, and `Decimal` arithmetic for uncached input, cached input, and billable output (including thinking tokens where reported). A `gemini_cost_estimated` event is emitted **only** if usage is complete and consistent and a pricing configuration exists for the exact model.

**Production pricing is intentionally not configured.** Without verified model rates, usage can be observed but no monetary estimate is emitted. Missing thinking or cached-token categories can also prevent an estimate. Known estimated USD is therefore a **subtotal of available estimates, not an invoice**; missing cost data does not imply a free request. Failed technical assessment validation can still produce billable usage and an estimate.

### Operational JSON reports

The tested reporting pipeline accepts validated structured events, aggregates operation outcomes, latency, Gemini usage, and known estimated USD, then serializes the result as JSON:

```text
JSONL log lines → parse_log_lines() → build_operational_report() → JSON report
```

For example, to report on an existing file containing **only structured JSONL log events**:

```python
from pathlib import Path

from job_hunter.metrics.build_operational_report import build_operational_report
from job_hunter.metrics.parse_log_lines import parse_log_lines

with Path("logs.jsonl").open(encoding="utf-8") as lines:
    report_json = build_operational_report(parse_log_lines(lines))

print(report_json)
```

This is a Python API example, **not** a `job-hunter metrics` CLI command. The parser rejects malformed nonblank records with line-numbered errors. Monetary amounts are represented as decimal strings in JSON to preserve precision. The report distinguishes the number of observed cost estimates from their subtotal.

An optional `operation_id` exists in the log schema, but IDs are not yet propagated through requests. Per-operation cost attribution and exact missing-estimate coverage remain deferred, as does a public metrics-reporting CLI.

### CI and offline verification

The existing GitHub Actions workflow has run checks on both pushes and pull requests. The full local test suite has also passed with the Gemini key absent:

```bash
env -u GEMINI_API_KEY pytest -q
```

Explicit live Gemini evaluation commands remain separate from the default test suite. Full network-isolation auditing and additional CI failure-path verification remain potential hardening tasks.

## Evaluation framework

Evaluation is a first-class part of the project, not a future feature. It uses checked-in job snapshots and reference datasets, but generated evaluation reports remain local.

### Offline deterministic evaluation

```bash
python -m evaluations.run_evaluation
```

This evaluates the labeled deterministic fixtures **without LLM calls** and writes a new timestamped artifact under `evaluations/results/`.

To evaluate selected cases:

```bash
python -m evaluations.run_evaluation --job-id E02 --job-id E05
```

The runner records predictions, expected labels, scores, reasons, concerns, a confusion matrix, accuracy, false-eligible/false-rejected counts, execution errors, and input hashes. It will not overwrite an existing output artifact.

**Documented baseline (October 26, 2026):** 12/12 deterministic predictions matched the current curated reference labels (100% agreement, zero false-eligible classifications in that dataset). This is a **small in-sample benchmark**, not an estimate of real-world accuracy on unseen jobs.

### Optional live Gemini technical evaluation

The separate AI evaluation runner uses **real paid Gemini API calls**. It is not invoked by `pytest`.

```bash
export GEMINI_API_KEY='your-key-here'
# Optional: export GEMINI_MODEL='a-model-supported-by-your-account'
python -m evaluations.run_ai_evaluation --job-id E05
```

The runner loads `.env` when present (without overriding an existing environment variable). It records the job description, model/prompt metadata, structured technical assessment, predicted technical eligibility, and combined final eligibility. Golden labels and reference explanations are **not** sent to the assessor.

Four exploratory live Gemini evaluations were recorded for E02, E05, E07 and E12. E05 demonstrated a useful `review` decision for unverified TypeScript/Go skills. E12 exposed a meaningful distinction between **strong transferable fit** and **verification of every mandatory requirement**. Do not interpret the existing deterministic classification metrics in these AI reports as a separately validated metric of technical-assessment quality.

### Focused Gemini requirement regressions

The focused regression suite tests known technical-assessment failure modes: preferred titles without verified experience, Redis queues incorrectly treated as AWS SQS experience, missing TypeScript/Node.js production evidence, and a positive control with verified AWS SQS production work. It validates requirement classification, exact quotations from the job posting, and candidate quotations against structured experience records.

```bash
# Explicit live Gemini calls; requires GEMINI_API_KEY
python -m evaluations.run_requirements_evaluation

# Offline comparison of two saved focused evaluation reports
python -m evaluations.compare_reports \
    evaluations/results/baseline.json \
    evaluations/results/current.json
```

The focused runner writes individual validation outcomes and aggregate metrics to a timestamped JSON report. Technical-fit agreement compares Gemini's `strong` / `partial` / `weak` prediction with curated reference labels and records mismatches separately from the classification-and-grounding regression result. The offline comparator matches cases by ID and warns about changes to the dataset, model, instructions, or output schema; a changed prediction is not automatically an improvement.

**Focused live baseline (October 30, 2026; Gemini 3.5 Flash Lite):**

| Measure | Recorded result |
| --- | ---: |
| Requirement classification (case-level regression pass) | 4/4 |
| Job-description quotation grounding | 4/4 |
| Candidate quotation grounding (cases with nonempty quotations) | 1/1 |
| Technical-fit agreement against curated labels | 4/4 |
| Overall focused regression pass | 4/4 |

These are four small, curated regression controls, **not** estimates of accuracy on new job postings. The three cases without candidate quotations correctly leave that evidence blank; they do not count as independently grounded candidate quotations. Exact-substring validation establishes quotation provenance, not whether the evidence logically proves a technical skill. Live results may vary between identical runs.

Run metrics against a saved evaluation report:

```bash
python -m evaluations.metrics evaluations/results/<your-report>.json
```

Details on datasets, interpretation, known limitations, and reproducibility are in [Evaluation Methodology](docs/EVALUATION.md).

### Tests

```bash
pytest -q
pytest -q tests/test_evaluation_metrics.py tests/test_evaluation_reports.py tests/test_evaluation_scripts.py
```

The test suite includes classification metrics, malformed labels, empty inputs, offline runner artifacts, overwrite protection, mocked Gemini calls, reference-label isolation, error continuation, and key-redaction checks. It also covers retry behavior, latency boundaries, usage and cost estimates, structured event aggregation, JSONL parsing, and reporting. The normal test suite does not require paid Gemini calls.

## Roadmap

| Milestone | Focus | Status |
| --- | --- | --- |
| 1. MVP | Python CLI, structured models, collection, basic matching | Completed |
| 2. Real discovery and AI integration | ATS sources and optional LLM analysis | Implemented; legacy CLI AI path needs verification |
| 3. Eligibility vs. scoring | Explicit hard constraints, uncertainty, separate ranking | Completed |
| 4. Evaluation framework | Golden fixtures, offline and live runners, metrics, tests | Functionally complete; minor validation/documentation refinements |
| 5. AI quality | Structured candidate evidence, deterministic grounding, focused Gemini regressions, metrics and saved-report comparison | Completed |
| 6. Operational reliability | Rate limits, retries, partial recovery, structured diagnostics, latency, usage/cost estimation, JSONL reporting, CI | Completed for implemented scope; correlation and live pricing deferred |
| 7. Portfolio readiness | Architecture and trade-offs, reproducible demo, documentation | Planned |

See [Project Roadmap](docs/PROJECT_ROADMAP.md) for completed milestones, engineering decisions, known limitations and upcoming priorities.

## Key engineering decisions

- **Deterministic gates remain authoritative:** Confirmed location or remote-work restrictions cannot be overridden by an attractive score or favorable LLM assessment.
- **Fit differs from verification:** `TechnicalFit` communicates overall alignment and transferable experience; mandatory-requirement verification determines whether evidence is sufficient to proceed without review.
- **LLM outputs are untrusted until checked:** Requirements cite employer text; deterministic validators check job quotations and candidate quotations against documented experience contexts. Unsupported or missing direct experience remains visible as uncertainty.
- **Quality measures stay separate:** Deterministic eligibility accuracy, focused requirement-classification pass rates, evidence-grounding rates and technical-fit agreement answer different questions. Small curated datasets are regression tools, not calibrated real-world performance.
- **Evaluation is reproducible and deliberately opt-in:** Offline tests and report comparisons need no API key. Live Gemini runs are explicit and may incur provider charges; reports preserve useful experiment metadata and remain local.
- **Operational costs are conservative estimates:** Report only supported token accounting and configured model prices. Missing costs remain unknown, and aggregated known estimates are not treated as a complete bill.
- **Retry and latency semantics are explicit:** Retry budgets are bounded, ambiguous Gemini transport failures are handled conservatively, and operation latency is not double-counted with individual HTTP attempts.

## Limitations and safety boundaries

- **Curated discovery:** Only configured ATS company boards are searched; there is no broad autonomous web crawl or automated application submission.
- **ATS verification is limited:** Seeing a listing via a public API does not guarantee the external apply form is operational or that employment from Poland is permitted.
- **Remote and location heuristics:** Regex-based and text-based checks can misinterpret context; manually verify legal eligibility and office requirements before applying.
- **Compensation:** Rates may be extracted but are not consistently compared across currencies, hourly/monthly periods, tax arrangements, and contract types. Missing compensation is not evidence of suitability.
- **Technical uncertainty:** An LLM's assessment is not proof of candidate experience; unverified mandatory skills should remain visible. Exact-quotation grounding does not establish semantic correctness, and technical-fit labels can involve judgment.
- **Scoring:** Relevance and AI-transition scores are baseline heuristics, not calibrated hiring probabilities.
- **Privacy and artifacts:** Evaluation reports can include candidate-profile content, job descriptions, prompts, and model outputs. Files in `evaluations/results/` are intentionally Git-ignored. Review any artifact before sharing it.
- **API use:** Live AI runs incur provider costs and may encounter model variability, API errors, and rate limits. Use a supported model and keep API keys out of source control. Retries cannot guarantee exactly-once Gemini execution or billing; capped `Retry-After` delays may be shorter than provider guidance.
- **Operational cost coverage:** No verified production Gemini pricing is configured; strict usage accounting may omit valid provider responses. Structured reports contain known estimated subtotals, not actual bills or per-operation attribution. Operation correlation and a public metrics CLI are deferred.
- **Scheduling:** Despite the project name, unattended production scheduling has not been established as a completed feature.

## References

- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/quickstart/)
- [Greenhouse public Job Board API](https://docs.greenhouse.io/job-board)
- [Ashby public postings API](https://developers.ashbyhq.com/docs/public-job-posting-api)
- [Lever Postings API](https://github.com/lever/postings-api)