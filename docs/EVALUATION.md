# AI Job Hunter — Evaluation Methodology

**Project:** AI Job Hunter  
**Document status:** Baseline documentation  
**Baseline date:** 2026-10-26  
**Purpose:** Explain how job-eligibility decisions and Gemini technical assessments are tested, measured, and reproduced.

## 1. Why evaluation exists

AI Job Hunter discovers job opportunities and evaluates them against a configurable candidate profile. A plausible recommendation is not sufficient: the system must avoid recommending jobs with confirmed hard restrictions, expose missing evidence, and make mistakes observable.

The evaluation framework is intended to:

- Detect regressions in deterministic eligibility rules.
- Measure false-positive recommendations, especially **false eligible** decisions.
- Examine whether Gemini extracts job requirements and grounds assessments in job descriptions and verified candidate evidence.
- Preserve reproducible run metadata and individual decisions for diagnosis.
- Separate offline, deterministic tests from deliberate, potentially paid live-model experiments.

**Out of scope:** The benchmark does not establish hiring eligibility, predict recruitment outcomes, or demonstrate generalization to all job postings.

## 2. Evaluation architecture

```text
Tracked fixtures and candidate profile
                |
                v
      Evaluation runner
         /          \
        v            v
 Deterministic     Live Gemini
  evaluator        assessor
        |            |
        v            v
 Deterministic    Technical
  eligibility      assessment
        |            |
        +------ + ---+
                v
     Final eligibility policy
                |
                v
        JSON run artifact
                |
                v
      Metrics and review
```

**Production code determines predictions.** Evaluation code loads fixtures, invokes production logic, compares predictions against references, and records results. Evaluation metrics must not reimplement location, remote, technical, or compensation rules.

### Distinct labels and decisions

| Concept | Meaning | Values |
|---|---|---|
| Deterministic eligibility | Result of non-LLM eligibility checks | `eligible`, `review`, `rejected` |
| Reference technical fit | Human-curated qualitative assessment | `strong`, `partial`, etc. as defined in the AI fixture |
| Gemini technical prediction | Whether mandatory technical requirements are supported | `eligible`, `review`, `rejected` as supported by the technical policy |
| Final prediction | Deterministic result combined with technical prediction | `eligible`, `review`, `rejected` |

**Important:** A deterministic `eligible` means the deterministic checks pass; it does **not** prove that the candidate meets every technical requirement. For example, E05 passes the deterministic checks but is sent to `review` after Gemini identifies unverified specialist skills.

Current final-combination policy in `evaluations/run_ai_evaluation.py`:

1. A deterministic `rejected` decision remains `rejected`.
2. Otherwise, if deterministic or technical eligibility is `review`, the final result is `review`.
3. Otherwise the final result is `eligible`.

The AI runner also treats an empty extracted requirements list as insufficient evidence (`review`).

## 3. Version-controlled datasets

| Path | Role |
|---|---|
| `evaluations/fixtures/jobs.json` | Job snapshots and associated source information |
| `evaluations/fixtures/deterministic.json` | Deterministic reference cases and expected eligibility |
| `evaluations/fixtures/ai.json` | AI reference cases, technical-fit labels, and assessment criteria |
| `config/profile.yaml` | Candidate preferences and documented skill evidence |

Fixtures include synthetic jobs, real posting snapshots, and reconstructed historical applications. These provenance types should be preserved in analyses: synthetic cases test specific boundaries, while actual or reconstructed postings exercise realistic language. A reconstructed summary is not identical to a verbatim employer posting.

### Dataset validation

The shared input loader (`evaluations/common.py`) currently checks:

- The candidate profile is a mapping.
- Job snapshot IDs are unique.
- Evaluation case IDs are unique.
- Each evaluation case refers to an existing job snapshot.
- Selected `--job-id` values exist in the chosen evaluation dataset.
- An explicitly chosen report output path does not already exist.

The deterministic runner constructs `Job` models from the snapshots, providing Pydantic validation of evaluated job fields. The tests additionally verify metrics input validation and script behavior.

## 4. How to run evaluations

Run commands from the repository root using the project's configured Python environment.

### Offline deterministic evaluation

```bash
python -m evaluations.run_evaluation
```

To evaluate selected examples:

```bash
python -m evaluations.run_evaluation --job-id E02 --job-id E05
```

This runner does not call Gemini. It writes a timestamped report under `evaluations/results/` unless `--output` is provided.

### Explicit live Gemini evaluation

Ensure the required Gemini credentials are configured in the environment or the repository-root `.env` file; do not commit credentials.

```bash
python -m evaluations.run_ai_evaluation --job-id E02 --job-id E05
```

Other useful examples: `E07` tests specialization uncertainty; `E12` tests transferable backend experience versus unverified specialist requirements. The live runner can incur model API charges. It is **not** invoked by the default pytest suite.

### Automated tests

```bash
pytest tests/test_evaluation_metrics.py \
       tests/test_evaluation_reports.py \
       tests/test_evaluation_scripts.py
```

The integration tests mock Gemini and verify saved artifacts, failure handling, secret redaction, `.env` resolution, reference-label isolation, and overwrite protection. Run the full project suite separately with `pytest`.

### Report retention

Generated reports are deliberately ignored by Git via `evaluations/results/.gitignore`. Commit evaluation **code, tests, fixtures, and documentation**, not every generated report. Selected summary metrics may be documented in this file or the README. Full reports can be retained locally for investigation.

## 5. Deterministic metrics

The metrics implementation is `evaluations/metrics.py`, with `calculate(rows)` operating on existing result records or flat `id`/`expected`/`predicted` rows.

| Field | Interpretation |
|---|---|
| `total` | Number of input result rows |
| `compared` | Rows with both valid expected and predicted labels |
| `correct` | Matching labels among compared rows |
| `accuracy` | `correct / compared`; `null` when no rows can be compared |
| `false_eligible` | Expected `review` or `rejected`, predicted `eligible` |
| `false_rejected` | Expected `eligible` or `review`, predicted `rejected` |
| `mismatches` | IDs and labels for compared disagreements |
| `confusion_matrix` | Three-by-three matrix, **rows = expected**, columns = predicted |

Some generated reports also include compatibility aliases such as `count`, `false_eligible_count`, and `false_rejected_count`.

Execution failures are separately counted in the artifact `summary.errors`; missing references or predictions are excluded from `compared`, rather than being treated as incorrect classifications. Consequently, interpret `accuracy` alongside `total`, `compared`, and `errors`.

### Recorded deterministic baseline — October 26, 2026

From the saved 12-case report (`run_id: 20261026T161130.659963Z`):

| Measure | Value |
|---|---:|
| Total cases | 12 |
| Compared cases | 12 |
| Correct predictions | 12 |
| Accuracy | 100% |
| False eligible | 0 |
| False rejected | 0 |
| Execution errors | 0 |

Confusion matrix:

| Expected \\ Predicted | Eligible | Review | Rejected |
|---|---:|---:|---:|
| Eligible | 3 | 0 | 0 |
| Review | 0 | 6 | 0 |
| Rejected | 0 | 0 | 3 |

**Interpretation:** All 12 outputs agree with their current deterministic reference labels. The reference dataset is small and curated. This figure is **not** an estimate of accuracy on unseen job listings. The saved report records `git_dirty: true`, so a Git revision alone cannot reproduce the exact code state; fixture/profile hashes and a clean committed code baseline improve traceability.

## 6. AI evaluation and evidence quality

The AI fixtures store an `expected_technical_fit` reference (`strong` or `partial` in the reviewed four examples) and an `expected_deterministic_eligibility`. Gemini produces structured individual requirements and a technical eligibility decision.

**Do not calculate AI accuracy by silently equating `strong` with `eligible` and `partial` with `review`.** That is an optional interpretation requiring an explicitly documented mapping. Technical fit and mandatory-skill verification are different evaluation questions.

A useful AI assessment should:

- Extract relevant requirements from the employer-provided description.
- Distinguish mandatory skills from preferred or bonus experience.
- Clearly identify requirements as `met`, `unmet`, or `unknown` based on documented candidate evidence.
- Avoid treating a transferable language as verified professional specialization.
- Keep location/remote restrictions and compensation in their appropriate deterministic stages.
- Cite supporting job evidence and grounded candidate evidence.
- Use `review` when mandatory requirements cannot be verified.

### Initial live experiment — four jobs

The four reports saved on October 26, 2026 completed without execution errors:

| Case | Curated technical fit | Gemini technical prediction | Final prediction | Main observation |
|---|---|---|---|---|
| E02 — Example Backend SaaS | `strong` | `eligible` | `eligible` | Clearly documented PHP/backend overlap |
| E05 — Kimchi Studio | `partial` | `review` | `review` | TypeScript and Go specialization not verified |
| E07 — Flix | `partial` | `review` | `review` | Python/FastAPI and infrastructure-as-code evidence gaps |
| E12 — Modash | `strong` | `review` | `review` | Strong transferable backend fit, but Node.js/TypeScript and proxy experience unverified |

### Case study: E12 — strong fit versus verification

E12 is a historical Modash Data Core opportunity whose fixture describes high-volume data systems, external integrations, operational reliability, and a TypeScript/Node.js stack.

Gemini marked large-scale backend/data systems, distributed-system operation, resilient API integrations, production ownership, PostgreSQL, and AWS as met. It marked proxy management/routing and TypeScript/Node.js experience as unknown. Therefore its conservative technical policy returned `review`, while the human reference described overall technical fit as `strong`.

This is **not necessarily a model hallucination or a bad label**. It identifies two distinct targets:

- **Technical-fit strength:** How much of the role aligns with the candidate's demonstrated and transferable skills?
- **Mandatory-requirement verification:** Is sufficient evidence available to affirm all essential requirements?

A future schema may represent these separately (for example, `fit: strong` alongside `verification: review`). Do not change the reference label simply to improve apparent agreement.

### Known extraction/grounding limitations

- **E02:** The assessor included fully remote work from Poland among technical requirements; this belongs to the location/remote evaluator.
- **E05:** Electron/React was treated as nonmandatory, although the posting describes those technologies as part of the core product stack; experience *shipping Electron applications at scale* is the separate bonus.
- **E07:** Years of production engineering were marked unknown because the machine-readable profile lacks explicit evidence of years of experience; the profile can be strengthened with verified experience facts. The advertised 90–120 PLN/hour is below the profile's 140 PLN/hour minimum, but compensation is outside the current technical assessor's scope.
- **E12:** The source description is explicitly a normalized summary rather than a complete verbatim posting, constraining exact-quote verification.
- **Source evidence:** LLM-produced `job_evidence` can be paraphrased or contain ellipses rather than literal source substrings. A strict quote validator should distinguish verbatim evidence from paraphrases before treating any match rate as groundedness accuracy.

These are improvement opportunities for a later AI-quality milestone, not reasons to rewrite the deterministic evaluator during Task 4.2.

## 7. Test strategy and safeguards

| Test layer | Purpose | Typical execution |
|---|---|---|
| Unit tests | Exercise accuracy, confusion matrix, false positives, empty inputs and invalid labels | Offline, normal pytest |
| Runner integration tests | Verify output files, reference isolation, secrets, retries/errors and deterministic overrides | Offline, mocked Gemini |
| Deterministic golden run | Detect eligibility-rule regressions across labeled jobs | Offline, explicit command |
| Live Gemini run | Inspect actual model extraction and candidate evidence quality | Explicit command, API credentials and possible cost |

Implemented script-test safeguards include:

- No expected technical-fit/reference labels passed to the Gemini assessor prompt.
- API credential values not written into reports.
- API exception text not exposed in artifacts; error type is retained.
- A failed AI job does not prevent all subsequent cases from being assessed.
- A deterministic rejection cannot be overridden by a favorable AI assessment.
- Existing report files are not silently overwritten.

## 8. Reproducibility and privacy

Reports record the run ID, UTC timestamps, schema version, evaluator kind, Git revision and dirty state, candidate profile, relevant input hashes, and individual result records. Live AI artifacts additionally record model metadata, instructions, schema, and prompts.

Because full reports may contain candidate information, original job descriptions and prompts, keeping them outside source control is intentional. Do not put provider API secrets, tokens or confidential profile details in tracked documentation.

To reproduce an experiment, record the same fixture files, profile, implementation version, model ID and prompt version. For live Gemini runs, model variability means identical inputs need not yield identical assessments.

## 9. Remaining Task 4.2 checks

The core framework, metrics, golden-data execution and mocked runner tests are implemented. Before marking Task 4.2 closed:

1. Run the full pytest suite and verify a clean result.
2. Add or strengthen a test asserting consistency between report totals, error counts, compared cases, mismatches and confusion-matrix cell counts.
3. Decide explicitly how the runner handles **zero comparable cases**. An empty comparison set should not be mistaken for a successful accuracy measurement.
4. Optionally add a focused duplicate-ID rejection test; validation logic already exists in `load_inputs()`.
5. Record one reproducible baseline against a clean committed code revision, without committing generated reports.

## 10. Next milestone

Improve the **quality of Gemini technical assessments**, not just the number of classifications matching reference labels. Focus on requirement completeness, mandatory-versus-optional distinctions, source-evidence verification, richer candidate evidence, and separate measures for transferable fit and strict requirement verification. Expand the AI reference set and assess regressions using the existing framework.

---

**Core principle:** *An evaluation framework must measure production behavior, not redefine production behavior to make the benchmark pass.*
