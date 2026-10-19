# Daily AI Job Hunter — MVP

A Python 3.11+ project for scheduled ATS job collection, deterministic candidate filters, optional OpenAI Agents SDK analysis, persistence, and a Markdown report. Extracted criteria come from `config/job_search_overview.txt` (user-provided, updated October 19, 2026).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e '.[dev,ai]'
pytest -q
```

1. Add real company board IDs to `config/sources.yaml`; examples are comments, not live company IDs. To find a board ID, inspect the company's official Greenhouse/Ashby/Lever careers URL. One board ID fetches jobs at *that company only*.
2. Run:

```bash
job-hunter --output reports/daily.md
```

3. Open `reports/daily.md`. Without sources configured, the report contains zero jobs and still runs successfully. For AI-assisted evaluation, set `OPENAI_API_KEY` in your shell and run:

```bash
export OPENAI_API_KEY='your-key-here'
job-hunter --ai --model gpt-4.1-mini --output reports/daily.md
```

The model option is illustrative; select a model supported by your API account. No AI calls happen without `--ai`.

## How it works

- `collectors/ats.py` fetches publicly published Greenhouse, Ashby, and Lever postings. It parses HTML into text and validates structured data using Pydantic.
- `evaluate.py` flags role, company, location, culture, skill, and remote evidence. The scoring formula is a transparent *baseline heuristic* and is **not calibrated**.
- `cli.py` checks a canonical Greenhouse/Lever detail endpoint or a live Ashby public board response, then persists deduplicated job IDs in SQLite. It skips records manually tagged `applied`, `skipped`, or `dismissed`.
- `agent.py` optionally uses the OpenAI Agents SDK with typed output to add reasons, risks, and AI transition assessment. The LLM cannot change deterministic eligibility.
- The report separates `eligible`, `review`, and `rejected`. In particular, unclear Poland eligibility never silently passes.

## Mark a job as handled

Get the `provider:board:external_id` key from the SQLite table and run:

```bash
python -c "import sqlite3; c=sqlite3.connect('jobs.sqlite3'); print(c.execute('select key,status from jobs').fetchall())"
python -c "import sqlite3; c=sqlite3.connect('jobs.sqlite3'); c.execute('update jobs set status=? where key=?', ('applied','greenhouse:example:123')); c.commit()"
```

## Limitations / next steps

- This is a working **MVP**, not a fully autonomous broad web search. It requires curated company ATS board slugs; collectors do not crawl the whole internet.
- A live ATS listing API is evidence that the listing was published at check time, **not proof that the external application form accepts submissions**. Human verification of the official apply flow remains mandatory. An Ashby board response is weaker than job-specific endpoint verification.
- Remote-location matching is conservative but regex-based: words such as 'Europe' in unrelated context can be false positives. The `eligible` bucket is provisional, not a legal guarantee. Validate job location and employment eligibility before applying.
- Compensation is captured where provided but **not compared automatically** across currency / contract types. Do not interpret missing salary as passing your floor.
- Old submitted companies remain searchable for materially new jobs. The full historic application list is provided for manual review; matching exact past roles is not yet automated.
- Token / API costs and rate limits apply to `--ai`; no credentials are stored by this project.
- Future additions: seeded boards, career-page cross-checks, browser-based form verification, exact prior-role imports, human feedback dataset, evaluation metrics and production scheduling.

## Official references

- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/quickstart/
- Greenhouse public Job Board API: https://docs.greenhouse.io/job-board
- Ashby public postings API: https://developers.ashbyhq.com/docs/public-job-posting-api
- Lever Postings API: https://github.com/lever/postings-api
