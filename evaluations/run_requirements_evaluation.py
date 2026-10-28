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
from job_hunter.model.RequirementAssessment import TechnicalAssessment


def matches_reference(assessment, expected):
    # Wording can vary. This focused fixture has one requirement, so compare
    # its evidence classification rather than model-generated names or prose.
    actual = assessment.model_dump(mode='json')['requirements']
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
                row['assessment'] = assessment.model_dump(mode='json')
                row['passed'] = matches_reference(assessment, case['expected_requirements'])
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'evaluations/fixtures/requirements_ai.json')
    parser.add_argument('--model')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    parser.add_argument('--output', type=Path, default=ROOT / f'evaluations/results/requirements-ai-{stamp}.json')
    return asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    raise SystemExit(main())
