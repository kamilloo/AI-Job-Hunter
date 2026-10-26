import pytest

from evaluations.metrics import calculate


def test_perfect_classification():
    rows = [
        {"id": "E01", "expected": "eligible", "predicted": "eligible"},
        {"id": "E02", "expected": "review", "predicted": "review"},
        {"id": "E03", "expected": "rejected", "predicted": "rejected"},
    ]

    result = calculate(rows)

    assert result["accuracy"] == 1.0
    assert result["false_eligible_count"] == 0
    assert result["mismatches"] == []
    assert result["confusion_matrix"]["eligible"]["eligible"] == 1


def test_false_eligible_is_counted():
    rows = [
        {"id": "E01", "expected": "review", "predicted": "eligible"},
        {"id": "E02", "expected": "rejected", "predicted": "eligible"},
        {"id": "E03", "expected": "eligible", "predicted": "review"},
    ]

    result = calculate(rows)

    assert result["accuracy"] == 0
    assert result["false_eligible_count"] == 2
    assert result["confusion_matrix"]["review"]["eligible"] == 1
    assert result["confusion_matrix"]["rejected"]["eligible"] == 1
    assert len(result["mismatches"]) == 3


def test_empty_results():
    result = calculate([])

    assert result["count"] == 0
    assert result["accuracy"] is None
    assert result["false_eligible_count"] == 0


def test_invalid_prediction_is_rejected():
    rows = [
        {"id": "E01", "expected": "eligible", "predicted": "unknown"}
    ]

    with pytest.raises(ValueError):
        calculate(rows)


def test_flat_and_report_rows_produce_identical_metrics():
    flat = [{"id": "E01", "expected": "review", "predicted": "eligible"}]
    report = [{"job_id": "E01", "reference": {"expected_eligibility": "review"},
               "deterministic_match": {"eligibility": "eligible"}}]

    assert calculate(flat) == calculate(report)
    assert calculate(flat)["mismatches"] == [
        {"job_id": "E01", "expected": "review", "predicted": "eligible"}]
