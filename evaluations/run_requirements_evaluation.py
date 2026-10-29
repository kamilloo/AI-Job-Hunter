"""Explicit live Gemini regressions for isolated candidate-evidence scenarios."""
import argparse
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
import json
from dotenv import load_dotenv

from evaluations.common import ROOT, digest, save
from job_hunter.agents.requirements_agent import (
    ASSESSMENT_INSTRUCTIONS, assess_requirements, build_prompt,
)
from job_hunter.compare_requirements import compare_requirements
from job_hunter.model.RequirementAssessment import TechnicalAssessment, TechnicalRequirement, RequirementStatus
from job_hunter.validation.evidence import validate_job_evidence
from job_hunter.validation.validate_candidate_evidence import validate_candidate_evidence


def candidate_grounding_passes(candidate, requirements) -> bool:
    contexts = [
        experience["context"]
        for experience in candidate.get("skill_experiences", [])
        if experience.get("context")
    ]

    return all(
        validate_candidate_evidence(
            contexts,
            requirement.candidate_evidence,
        ).valid
        if requirement.candidate_evidence.strip()
        else requirement.status == RequirementStatus.unknown
        for requirement in requirements
    )


def matches_reference(assessment, expected, expected_skills: set[str] | None = None,):
    # Wording can vary. This focused fixture has one requirement, so compare
    # its evidence classification rather than model-generated names or prose.
    actual = assessment.model_dump(mode='json')['requirements']

    if expected_skills is not None:
        return compare_requirements(
            expected,
            actual,
            expected_skills=expected_skills,
        )

    fields = ('mandatory', 'status', 'candidate_evidence')
    return len(actual) == len(expected) and all(
        all(result[field] == reference[field] for field in fields)
        for result, reference in zip(actual, expected)
    )

async def run(args):
    load_dotenv(ROOT / '.env', override=False)
    if not os.getenv('GEMINI_API_KEY'):
        raise ValueError('Set GEMINI_API_KEY before running live AI evaluation')
    cases = json.loads(args.dataset.read_text(encoding='utf-8'))
    model = args.model or os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')
    artifact = {
        'kind': 'requirements_ai', 'model': model,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'dataset_sha256': digest(cases),
        'instructions': ASSESSMENT_INSTRUCTIONS,
        'output_schema': TechnicalAssessment.model_json_schema(),
        'status': 'running', 'results': [],
    }
    save(args.output, artifact, first=True)
    async with httpx.AsyncClient() as client:
        for case in cases:
            row = {
                'id': case['id'], 'reference': case,
                'request_prompt': build_prompt(case['candidate'], case['job_description']),
                'assessment': None, 'passed': False, 'error': None,
            }
            try:
                assessment = await assess_requirements(
                    case['candidate'], case['job_description'], model, client=client,
                )
                for requirement in assessment.requirements:
                    validation = validate_job_evidence(
                        job_description=case["job_description"],
                        evidence=requirement.job_evidence,
                    )
                    requirement.evidence_validation = validation

                row['assessment'] = assessment.model_dump(mode='json')
                result = evaluate_assessment(assessment, case)
                row.update(result)

            except (httpx.HTTPError, ValueError) as exc:
                row['error'] = {'type': type(exc).__name__}
                if isinstance(exc, httpx.HTTPStatusError):
                    row['error']['status_code'] = exc.response.status_code
            artifact['results'].append(row)
            save(args.output, artifact)
    artifact['finished_at'] = datetime.now(timezone.utc).isoformat()
    passed = all(row['passed'] for row in artifact['results']) and bool(cases)
    artifact['status'] = 'passed' if passed else 'failed'
    save(args.output, artifact)
    print(f"{artifact['status']}: {args.output}")
    return 0 if passed else 1


def evaluate_assessment(assessment, case) -> dict:
    classification_passed = matches_reference(
        assessment,
        case["expected_requirements"],
        expected_skills=set(case["expected_skills"])
        if "expected_skills" in case
        else None,
    )

    grounding_passed = all(
        validate_job_evidence(
            case["job_description"],
            requirement.job_evidence,
        ).valid
        for requirement in assessment.requirements
    )

    contexts = [
        experience["context"]
        for experience in case["candidate"].get("skill_experiences", [])
        if experience.get("context")
    ]

    candidate_grounding_passed = all(
        validate_candidate_evidence(
            contexts,
            requirement.candidate_evidence,
        ).valid
        if requirement.candidate_evidence.strip()
        else requirement.status == RequirementStatus.unknown
        for requirement in assessment.requirements
    )

    return {
        "classification_passed": classification_passed,
        "grounding_passed": grounding_passed,
        "candidate_grounding_passed": candidate_grounding_passed,
        "passed": (
            classification_passed
            and grounding_passed
            and candidate_grounding_passed
        ),
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'evaluations/fixtures/requirements_ai.json')
    parser.add_argument('--model')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    parser.add_argument('--output', type=Path, default=ROOT / f'evaluations/results/requirements-ai-{stamp}.json')
    return asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    raise SystemExit(main())
