"""Shared evaluation input loading and reproducible JSON artifacts."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def parser(kind):
    result = argparse.ArgumentParser(description=f"Run {kind} golden evaluation")
    result.add_argument('--profile', type=Path, default=ROOT / 'config/profile.yaml')
    result.add_argument('--jobs', type=Path, default=ROOT / 'evaluations/fixtures/jobs.json')
    result.add_argument('--dataset', type=Path, default=ROOT / f'evaluations/fixtures/{kind}.json')
    result.add_argument('--output', type=Path, help='New JSON artifact path; existing files are never overwritten')
    result.add_argument('--job-id', action='append', help='Evaluate only these IDs; repeat to select multiple jobs')
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load_inputs(args, kind):
    profile = yaml.safe_load(args.profile.read_text(encoding='utf-8'))
    if not isinstance(profile, dict):
        raise ValueError('Candidate profile must be a mapping')
    snapshots = json.loads(args.jobs.read_text(encoding='utf-8'))
    jobs = {case['id']: case for case in snapshots}
    if len(jobs) != len(snapshots):
        raise ValueError('Duplicate job snapshot IDs')
    cases = json.loads(args.dataset.read_text(encoding='utf-8'))
    ids = [case['job_id'] for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate evaluation case IDs')
    missing = set(ids) - jobs.keys()
    if missing:
        raise ValueError(f'Dataset references missing snapshots: {sorted(missing)}')
    if args.job_id:
        unknown = set(args.job_id) - set(ids)
        if unknown:
            raise ValueError(f'Unknown evaluation IDs: {sorted(unknown)}')
        cases = [case for case in cases if case['job_id'] in args.job_id]
    now = datetime.now(timezone.utc)
    run_id = now.strftime('%Y%m%dT%H%M%S.%fZ')
    output = args.output or ROOT / f'evaluations/results/{kind}-{run_id}.json'
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    try:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True))
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = None, None
    artifact = {
        'schema_version': 1, 'run_id': run_id, 'kind': kind,
        'started_at': now.isoformat(), 'finished_at': None, 'status': 'running',
        'git_revision': revision, 'git_dirty': dirty,
        'inputs': {'profile_path': str(args.profile.resolve()), 'jobs_path': str(args.jobs.resolve()),
                   'dataset_path': str(args.dataset.resolve()), 'profile_sha256': digest(profile),
                   'jobs_sha256': digest(snapshots), 'dataset_sha256': digest(cases)},
        'candidate_profile': profile, 'results': [],
    }
    return profile, jobs, cases, output, artifact


def save(output, artifact, *, first=False):
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(artifact, indent=2, ensure_ascii=False) + '\n'
    if first:
        with output.open('x', encoding='utf-8') as stream:
            stream.write(text)
    else:
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(text, encoding='utf-8')
        temporary.replace(output)


def finish(output, artifact):
    artifact['finished_at'] = datetime.now(timezone.utc).isoformat()
    errors = sum(row.get('error') is not None for row in artifact['results'])
    comparisons = [row['deterministic_correct'] for row in artifact['results'] if row.get('deterministic_correct') is not None]
    artifact['summary'] = {'total': len(artifact['results']), 'errors': errors,
                           'deterministic_correct': sum(comparisons),
                           'deterministic_compared': len(comparisons)}
    artifact['status'] = 'completed_with_errors' if errors else 'completed'
    save(output, artifact)
    print(f"Saved {output} ({len(artifact['results'])} cases, {errors} errors)")
    return 1 if errors or not all(comparisons) else 0
