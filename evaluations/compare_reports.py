import argparse
import json
from pathlib import Path

METADATA_FIELDS = {
    "dataset_sha256": "Dataset hashes",
    "model": "Models",
    "instructions": "Instructions",
    "output_schema": "Output schemas",
}


def comparability_warnings(baseline: dict, current: dict) -> list[str]:
    warnings = []

    for field, label in METADATA_FIELDS.items():
        if baseline.get(field) is None or current.get(field) is None:
            warnings.append(f"{label} missing")
        elif baseline[field] != current[field]:
            warnings.append(f"{label} differ")

    return warnings

def compare_reports(baseline: dict, current: dict) -> dict:
    """Compare technical-fit predictions across saved evaluation reports."""

    baseline_rows = {
        row["id"]: row
        for row in baseline.get("results", [])
    }

    current_rows = {
        row["id"]: row
        for row in current.get("results", [])
    }

    baseline_ids = set(baseline_rows)
    current_ids = set(current_rows)

    common_ids = baseline_ids & current_ids
    added_ids = current_ids - baseline_ids
    removed_ids = baseline_ids - current_ids

    technical_fit_changes = []

    for case_id in sorted(common_ids):
        baseline_assessment = baseline_rows[case_id].get("assessment") or {}
        current_assessment = current_rows[case_id].get("assessment") or {}

        before = baseline_assessment.get("technical_fit")
        after = current_assessment.get("technical_fit")

        if before != after:
            technical_fit_changes.append({
                "id": case_id,
                "before": before,
                "after": after,
            })

    warnings = comparability_warnings(baseline, current)

    return {
        "comparable": not warnings,
        "warnings": warnings,
        "cases": {
            "common": len(common_ids),
            "added": sorted(added_ids),
            "removed": sorted(removed_ids),
        },
        "technical_fit_changes": technical_fit_changes,
    }

def main():
    parser = argparse.ArgumentParser(
        description="Compare two saved AI evaluation reports."
    )
    parser.add_argument("baseline", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("--output", type=Path)

    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    current = json.loads(args.current.read_text(encoding="utf-8"))

    comparison = compare_reports(baseline, current)
    result = json.dumps(comparison, indent=2) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(result)
    else:
        print(result, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())