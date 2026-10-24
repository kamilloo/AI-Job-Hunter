# Golden evaluation datasets

`fixtures/jobs.json` stores shared job snapshots and their provenance. IDs remain stable; both evaluation datasets reference a snapshot with `job_id`.

`fixtures/deterministic.json` labels the result of `evaluate(job, profile)` using `config/profile.yaml`, the Poland-based candidate profile. These cases test role exclusions, location, remote restrictions, live verification and the existing management gate. They do not require a model or credentials. E05 passes those gates; its specialist stack gap belongs to a separate assessment. E07 remains in review because its location field records only Warsaw, which the current location classifier does not resolve to Poland; its technical gaps and compensation concerns are assessed separately. An `eligible` result is not a complete recommendation or confirmation of salary suitability.

`fixtures/ai.json` is a separate rubric for AI or human assessment of technical fit and career transition opportunities. Each case includes the expected technical fit, evidence to assess, the original reference rationale, and the deterministic eligibility that an assessment must respect. Evaluate transferable skills, explicit production requirements, missing evidence, and direct AI duties separately. A transition to Go or data infrastructure is not automatically a transition into AI engineering. Do not infer production AI experience from company marketing or a job title. E01 intentionally has insufficient evidence.

To assess a model, supply only the referenced job and candidate profile as input; keep labels, reference explanations and assessment criteria out of the prompt. Compare its reasons, concerns and transition assessment with the rubric. Model output must not promote a deterministically rejected role. These are qualitative rubrics, not calibrated numerical score targets.

Run the offline golden checks with:

```bash
python -m pytest -q tests/test_golden_dataset.py tests/test_ai_dataset.py
```

`test_ai_dataset.py` checks dataset integrity only. Passing it does not demonstrate model quality. Live model assessment is separate and is not run by the default test suite. `run_evaluation.py` and `metrics.py` are currently placeholders.
