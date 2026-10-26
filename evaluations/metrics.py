"""Deterministic eligibility metrics for saved evaluation report rows."""
import argparse
import json
from pathlib import Path


LABELS = ('eligible', 'review', 'rejected')


def calculate(rows):
    """Compare deterministic predictions; matrix rows are expected labels.

    Rows without a reference or prediction count toward total but not compared.
    AI errors do not exclude an available deterministic prediction. Undefined
    accuracy (no comparable rows) is represented by null in JSON.
    Flat rows with id/expected/predicted are also accepted. Count fields with
    a _count suffix are aliases for the original report metric fields.
    """
    matrix = {expected: dict.fromkeys(LABELS, 0) for expected in LABELS}
    total = compared = correct = false_eligible = false_rejected = 0
    mismatches = []
    for row in rows:
        total += 1
        reference = row.get('reference') or {}
        expected = reference.get('expected_eligibility')
        if expected is None:
            expected = reference.get('expected_deterministic_eligibility')
        predicted = (row.get('deterministic_match') or {}).get('eligibility')
        expected = row.get('expected', expected)
        predicted = row.get('predicted', predicted)
        job_id = row.get('job_id', row.get('id'))
        for value in (expected, predicted):
            if value is not None and value not in LABELS:
                raise ValueError(f'Invalid eligibility label for {job_id}: {value!r}')
        if expected is None or predicted is None:
            continue
        compared += 1
        matrix[expected][predicted] += 1
        if expected == predicted:
            correct += 1
        else:
            false_eligible += predicted == 'eligible'
            false_rejected += predicted == 'rejected'
            mismatches.append({'job_id': job_id, 'expected': expected,
                               'predicted': predicted})
    return {
        'total': total, 'compared': compared, 'correct': correct,
        'accuracy': correct / compared if compared else None,
        'false_eligible': false_eligible, 'false_rejected': false_rejected,
        'mismatches': mismatches, 'confusion_matrix': matrix,
        'count': total, 'false_eligible_count': false_eligible,
        'false_rejected_count': false_rejected,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path, help='Saved deterministic or AI evaluation JSON')
    parser.add_argument('--output', type=Path, help='New metrics JSON file; defaults to stdout')
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8'))
    result = json.dumps(calculate(report['results']), indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(result)
    else:
        print(result, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
