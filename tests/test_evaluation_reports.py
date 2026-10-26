import json


def test_report_can_be_serialized():
    report = {
        "schema_version": 1,
        "kind": "deterministic",
        "status": "completed",
        "results": [],
        "summary": {
            "total": 0,
            "errors": 0,
            "metrics": {
                "accuracy": None,
                "false_eligible_count": 0,
            },
        },
    }

    encoded = json.dumps(report)
    decoded = json.loads(encoded)

    assert decoded["schema_version"] == 1
    assert decoded["summary"]["metrics"]["accuracy"] is None

def validate_report_summary(report: dict) -> None:
    results = report["results"]
    summary = report["summary"]

    if summary["total"] != len(results):
        raise ValueError("Report total does not match result count")

    errors = sum(row.get("error") is not None for row in results)

    if summary["errors"] != errors:
        raise ValueError("Report error count is inconsistent")