"""Explicit, paid Gemini evaluation; never invoked by the default test suite."""
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

import httpx
from dotenv import load_dotenv

from evaluations.common import digest, finish, load_inputs, parser, save
from job_hunter.agents.requirements_agent import ASSESSMENT_INSTRUCTIONS, assess_requirements, build_prompt
from job_hunter.evaluate import evaluate
from job_hunter.model.RequirementAssessment import TechnicalAssessment
from job_hunter.models import Eligibility, Job
from job_hunter.technical_eligibility import technical_eligibility


def final_prediction(deterministic, technical):
    if deterministic == Eligibility.rejected:
        return Eligibility.rejected
    if deterministic == Eligibility.review or technical == Eligibility.review:
        return Eligibility.review
    return Eligibility.eligible


async def run(args):
    load_dotenv(ROOT / '.env', override=False)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError('Set GEMINI_API_KEY before running live AI evaluation')
    profile, jobs, cases, output, artifact = load_inputs(args, 'ai')
    model = args.model or os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')
    artifact['assessor'] = {
        'provider': 'gemini', 'model': model,
        'instructions': ASSESSMENT_INSTRUCTIONS,
        'instructions_sha256': digest(ASSESSMENT_INSTRUCTIONS),
        'output_schema': TechnicalAssessment.model_json_schema(),
    }
    save(output, artifact, first=True)
    async with httpx.AsyncClient() as client:
        for case in cases:
            snapshot = jobs[case['job_id']]
            job = Job(**snapshot['job'])
            match = evaluate(job, profile)
            row = {
                'job_id': case['job_id'], 'snapshot': snapshot, 'reference': case,
                'started_at': datetime.now(timezone.utc).isoformat(),
                'request_prompt': build_prompt(profile, job.description),
                'deterministic_match': match.model_dump(mode='json'),
                'deterministic_correct': match.eligibility.value == case['expected_deterministic_eligibility'],
                'assessment': None, 'technical_prediction': None,
                'final_prediction': None, 'error': None,
            }
            try:
                # Deliberately do not send labels, rubrics or reference explanations.
                assessment = await assess_requirements(profile, job.description, model, client=client)
                technical = technical_eligibility(assessment)
                # No extracted requirements is insufficient evidence, not a pass.
                if not assessment.requirements:
                    technical = Eligibility.review
                row['assessment'] = assessment.model_dump(mode='json')
                row['technical_prediction'] = technical.value
                row['final_prediction'] = final_prediction(match.eligibility, technical).value
            except (httpx.HTTPError, ValueError) as exc:
                # Do not serialize exception messages that may contain credential-bearing data.
                row['error'] = {'type': type(exc).__name__}
                if isinstance(exc, httpx.HTTPStatusError):
                    row['error']['status_code'] = exc.response.status_code
            row['finished_at'] = datetime.now(timezone.utc).isoformat()
            artifact['results'].append(row)
            save(output, artifact)
    return finish(output, artifact)


def main():
    arguments = parser('ai')
    arguments.add_argument('--model', help='Gemini model ID; defaults to GEMINI_MODEL')
    return asyncio.run(run(arguments.parse_args()))


if __name__ == '__main__':
    raise SystemExit(main())
