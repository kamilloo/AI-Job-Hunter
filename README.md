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

The test suite includes classification metrics, malformed labels, empty inputs, offline runner artifacts, overwrite protection, mocked Gemini calls, reference-label isolation, error continuation, and key-redaction checks. The normal test suite does not require paid Gemini calls.

## Roadmap

| Milestone | Focus | Status |
| --- | --- | --- |
| 1. MVP | Python CLI, structured models, collection, basic matching | Completed |
| 2. Real discovery and AI integration | ATS sources and optional LLM analysis | Implemented; legacy CLI AI path needs verification |
| 3. Eligibility vs. scoring | Explicit hard constraints, uncertainty, separate ranking | Completed |
| 4. Evaluation framework | Golden fixtures, offline and live runners, metrics, tests | Functionally complete; minor validation/documentation refinements |
| 5. AI quality | Better requirement extraction, evidence grounding, transferable-skill policy | Planned / in progress |
| 6. Operational reliability | Rate limits, retries, diagnostics, cost/latency tracking, CI | Planned |
| 7. Portfolio readiness | Architecture and trade-offs, reproducible demo, documentation | Planned |

See [Project Roadmap](docs/PROJECT_ROADMAP.md) for the fuller goals and milestone criteria (add that document to the repository if it is not present yet).

## Limitations and safety boundaries

- **Curated discovery:** Only configured ATS company boards are searched; there is no broad autonomous web crawl or automated application submission.
- **ATS verification is limited:** Seeing a listing via a public API does not guarantee the external apply form is operational or that employment from Poland is permitted.
- **Remote and location heuristics:** Regex-based and text-based checks can misinterpret context; manually verify legal eligibility and office requirements before applying.
- **Compensation:** Rates may be extracted but are not consistently compared across currencies, hourly/monthly periods, tax arrangements, and contract types. Missing compensation is not evidence of suitability.
- **Technical uncertainty:** An LLM's assessment is not proof of candidate experience; unverified mandatory skills should remain visible.
- **Scoring:** Relevance and AI-transition scores are baseline heuristics, not calibrated hiring probabilities.
- **Privacy and artifacts:** Evaluation reports can include candidate-profile content, job descriptions, prompts, and model outputs. Files in `evaluations/results/` are intentionally Git-ignored. Review any artifact before sharing it.
- **API use:** Live AI runs incur provider costs and may encounter model variability, API errors, and rate limits. Use a supported model and keep API keys out of source control.
- **Scheduling:** Despite the project name, unattended production scheduling has not been established as a completed feature.

## References

- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/quickstart/)
- [Greenhouse public Job Board API](https://docs.greenhouse.io/job-board)
- [Ashby public postings API](https://developers.ashbyhq.com/docs/public-job-posting-api)
- [Lever Postings API](https://github.com/lever/postings-api)