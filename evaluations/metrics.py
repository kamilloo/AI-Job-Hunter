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
    Flat rows with id/expected/predicted are also accepted.
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
    }

def calculate_requirements_metrics(rows):
    """Summarize focused Gemini requirement regressions."""

    total = len(rows)

    classification_compared = 0
    classification_passed = 0
    grounding_compared = 0
    grounding_passed = 0
    candidate_grounding_compared = 0
    candidate_grounding_passed = 0
    passed = 0

    for row in rows:
        requirements = (row.get("assessment") or {}).get("requirements", [])

        if row.get("classification_passed") is not None:
            classification_compared += 1
            classification_passed += row["classification_passed"] is True

        if row.get("grounding_passed") is not None:
            grounding_compared += 1
            grounding_passed += row["grounding_passed"] is True

        # Only cases containing actual candidate quotations are applicable.
        has_candidate_quotation = any(
            requirement.get("candidate_evidence", "").strip()
            for requirement in requirements
        )

        if has_candidate_quotation and row.get("candidate_grounding_passed") is not None:
            candidate_grounding_compared += 1
            candidate_grounding_passed += row["candidate_grounding_passed"] is True

        passed += row.get("passed") is True

    def rate(numerator, denominator):
        return numerator / denominator if denominator else None

    def calculate_requirements_metrics(rows):
        technical_fit_compared = 0
        technical_fit_correct = 0
        technical_fit_mismatches = []

        for row in rows:
            reference = row.get("reference") or {}
            assessment = row.get("assessment") or {}

            expected = reference.get("expected_technical_fit")
            predicted = assessment.get("technical_fit")

            if expected is None or predicted is None:
                continue

            technical_fit_compared += 1
            expected_predicted = expected == predicted
            technical_fit_correct += expected_predicted

            if not expected_predicted:
                technical_fit_mismatches.append({
                    "id": row.get("id"),
                    "expected": expected,
                    "predicted": predicted
                })

        return {
            "compared": technical_fit_compared,
            "correct": technical_fit_correct,
            "agreement_rate": (
                technical_fit_correct / technical_fit_compared
                if technical_fit_compared
                else None
            ),
            'mismatches': technical_fit_mismatches
        }

    return {
        "total": total,
        "classification": {
            "compared": classification_compared,
            "passed": classification_passed,
            "pass_rate": rate(classification_passed, classification_compared),
        },
        "job_grounding": {
            "compared": grounding_compared,
            "passed": grounding_passed,
            "pass_rate": rate(grounding_passed, grounding_compared),
        },
        "candidate_grounding": {
            "applicable": candidate_grounding_compared,
            "passed": candidate_grounding_passed,
            "pass_rate": rate(
                candidate_grounding_passed, candidate_grounding_compared
            ),
        },
        "overall": {
            "passed": passed,
            "total": total,
            "pass_rate": rate(passed, total),
        },
        'technical_fit': calculate_requirements_metrics(rows)
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
