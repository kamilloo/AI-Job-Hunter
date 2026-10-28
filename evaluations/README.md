# Golden evaluation datasets

`fixtures/jobs.json` stores shared job snapshots and their provenance. IDs remain stable; both evaluation datasets reference a snapshot with `job_id`.

`fixtures/deterministic.json` labels the result of `evaluate(job, profile)` using `config/profile.yaml`, the Poland-based candidate profile. These cases test role exclusions, location, remote restrictions, live verification and the existing management gate. They do not require a model or credentials. E05 passes those gates; its specialist stack gap belongs to a separate assessment. E07 remains in review because its location field records only Warsaw, which the current location classifier does not resolve to Poland; its technical gaps and compensation concerns are assessed separately. An `eligible` result is not a complete recommendation or confirmation of salary suitability.

`fixtures/ai.json` is a separate rubric for AI or human assessment of technical fit and career transition opportunities. Each case includes the expected technical fit, evidence to assess, the original reference rationale, and the deterministic eligibility that an assessment must respect. Evaluate transferable skills, explicit production requirements, missing evidence, and direct AI duties separately. A transition to Go or data infrastructure is not automatically a transition into AI engineering. Do not infer production AI experience from company marketing or a job title. E01 intentionally has insufficient evidence.

To assess a model, supply only the referenced job and candidate profile as input; keep labels, reference explanations and assessment criteria out of the prompt. Compare its reasons, concerns and transition assessment with the rubric. Model output must not promote a deterministically rejected role. These are qualitative rubrics, not calibrated numerical score targets.

Run the offline golden checks with:

```bash
python -m pytest -q tests/test_golden_dataset.py tests/test_ai_dataset.py
```

`test_ai_dataset.py` checks dataset integrity only. Passing it does not demonstrate model quality. Live model assessment is separate and is not run by the default test suite. Use the explicit scripts below for saved evaluation runs.

## Explicit evaluation runs

Run from the repository root with the project virtual environment:

```bash
.venv/bin/python -m evaluations.run_evaluation
GEMINI_API_KEY='your-key' .venv/bin/python -m evaluations.run_ai_evaluation --model gemini-3.5-flash-lite
```

The AI script makes real, billable requests using the production `assess_requirements` implementation. It loads `GEMINI_API_KEY` and `GEMINI_MODEL` from the repository root `.env` file; existing environment variables take priority. You can also export credentials in your environment. `--model` overrides `GEMINI_MODEL`. Both scripts use `config/profile.yaml` by default; `--profile` can select a richer verified candidate profile. Only recorded profile evidence is sent; the profile is not enriched from other documents.

Both commands also work as direct scripts, for example `.venv/bin/python evaluations/run_evaluation.py`. Optional arguments:

```bash
.venv/bin/python -m evaluations.run_evaluation --job-id E02 --job-id E03 --output evaluations/results/baseline.json
.venv/bin/python -m evaluations.run_ai_evaluation --job-id E05 --profile config/profile.yaml --output evaluations/results/gemini-trial.json
```

Use `--jobs` and `--dataset` to select alternate snapshots and labels. Unknown IDs and duplicate IDs are rejected. Existing output files are never overwritten. Without `--output`, each run gets a timestamped JSON file under `evaluations/results/`.

Artifacts include the complete candidate profile, job snapshots, reference labels/rubrics, full deterministic matches, final predictions, UTC timestamps, input hashes, and Git revision/dirty status. AI artifacts additionally include the configured model, exact system instructions, request prompt, output schema, and complete validated technical assessments (requirements, evidence, explanations, summary and confidence). These are the model's returned evidence and explanations, not hidden chain-of-thought. No credentials are saved. Keep artifacts private if the candidate profile contains personal information.

AI calls receive only the candidate profile and employer description. Reference rubrics are saved for later inspection but never sent to the assessor. Every selected AI case is assessed, including deterministic rejections, so reasoning can be inspected while final predictions still respect hard restrictions. Mandatory unmet/unknown technical requirements result in review. An empty requirements list is conservatively treated as review in this evaluator. Deterministic rejection always wins; deterministic review cannot be promoted by AI.

This assessor evaluates technical requirements, not the full transition-opportunity or compensation rubric. Those rubric items remain available for human review; the scripts do not claim an automatic technical-fit/transition accuracy score. `expected_technical_fit` is not directly comparable to eligibility. `deterministic_correct` compares only deterministic predictions with deterministic labels.

Results are checkpointed after each case. Expected API/validation failures are recorded by error type (and HTTP status where applicable), with null AI/final predictions, and subsequent cases continue. A running artifact after interruption contains completed cases. Exit status is 1 for recorded errors or deterministic label mismatches and 0 otherwise; argument/setup errors also fail the command.

## Focused AI requirements regressions

`fixtures/requirements_ai.json` contains isolated candidate profiles and job
descriptions. The preferred-full-stack-title case requires `unknown`, mandatory
`true`, and empty candidate evidence when a preferred title has no documented
experience. Reference explanations are illustrative; exact model wording is not
scored. Only candidate data and the job description are sent to Gemini.

Run the live regression explicitly (uses the same `.env` configuration):

```bash
.venv/bin/python -m evaluations.run_requirements_evaluation
```

The runner saves prompts, references, validated assessments, and pass/fail results
under `evaluations/results/`. It exits with status 1 for classification mismatches
or API errors. `--model`, `--dataset`, and `--output` can override defaults.
Offline scoring checks are in `tests/test_requirements_ai_regression.py`; they do
not demonstrate Gemini behavior.

## Deterministic metrics

Completed reports include a `metrics` object matching `results/metrics.json`.
Metric counts use `total`, `false_eligible`, and `false_rejected`. `calculate(rows)` accepts saved-report rows or flat `{id, expected, predicted}` rows.
Calculate the same metrics for an existing deterministic or AI report without API calls:

```bash
.venv/bin/python -m evaluations.metrics evaluations/results/gemini-e12.json
.venv/bin/python -m evaluations.metrics evaluations/results/gemini-e12.json --output evaluations/results/gemini-e12-metrics.json
```

The confusion matrix uses expected labels as rows and deterministic predictions as columns. `false_eligible` counts eligible predictions whose expected label is review or rejected; `false_rejected` counts rejected predictions whose expected label is eligible or review. Mismatches list job ID, expected label and predicted label. Missing labels or predictions count toward `total` but not `compared`; accuracy is null when no rows can be compared. Invalid labels raise an error. AI reports use `expected_deterministic_eligibility` and `deterministic_match.eligibility`, regardless of technical/final predictions or API errors. Output files cannot be overwritten.
