"""Run deterministic golden evaluation without any model requests."""
import sys
from pathlib import Path

# Support both `python evaluations/run_evaluation.py` and `python -m ...`.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from evaluations.common import finish, load_inputs, parser, save
from job_hunter.evaluate import evaluate
from job_hunter.models import Job


def run(args):
    profile, jobs, cases, output, artifact = load_inputs(args, 'deterministic')
    save(output, artifact, first=True)
    for case in cases:
        snapshot = jobs[case['job_id']]
        job = Job(**snapshot['job'])
        match = evaluate(job, profile)
        prediction = match.eligibility.value
        artifact['results'].append({
            'job_id': case['job_id'], 'snapshot': snapshot, 'reference': case,
            'deterministic_match': match.model_dump(mode='json'),
            'final_prediction': prediction,
            'deterministic_correct': prediction == case['expected_eligibility'],
            'error': None,
        })
        save(output, artifact)
    return finish(output, artifact)


def main():
    return run(parser('deterministic').parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
