from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.constraints import (
    EvaluationConstraints,
    evaluate_constraints,
    validate_constraints,
)


def test_constraints_pass():
    summary = {
        "retrieval_hit_rate": 0.9,
        "average_context_precision": 0.8,
        "average_context_recall": 0.75,
        "citation_coverage_rate": 0.7,
        "safety_metrics": {
            "refusal_match_rate": 1.0,
            "citation_validity_rate": 1.0,
            "forbidden_chunk_leak_rate": 0.0,
        },
        "ragas_metrics": {"faithfulness": 0.88},
    }
    constraints = EvaluationConstraints(
        min_retrieval_hit_rate=0.8,
        min_context_precision=0.7,
        min_context_recall=0.7,
        min_citation_coverage=0.6,
        min_refusal_match_rate=0.9,
        min_citation_validity_rate=0.9,
        max_forbidden_chunk_leak_rate=0.1,
        min_ragas_metrics={"faithfulness": 0.8},
    )

    validate_constraints(constraints)
    result = evaluate_constraints(summary, constraints)

    assert result["passed"] is True
    assert result["violations"] == []


def test_constraints_fail_with_violations():
    summary = {
        "retrieval_hit_rate": 0.6,
        "average_context_precision": 0.65,
        "average_context_recall": 0.5,
        "citation_coverage_rate": 0.9,
        "safety_metrics": {
            "refusal_match_rate": 0.5,
            "citation_validity_rate": 0.4,
            "forbidden_chunk_leak_rate": 0.3,
        },
        "ragas_metrics": {},
    }
    constraints = EvaluationConstraints(
        min_retrieval_hit_rate=0.7,
        min_context_precision=0.7,
        min_context_recall=0.7,
        min_citation_coverage=0.8,
        min_refusal_match_rate=0.8,
        min_citation_validity_rate=0.7,
        max_forbidden_chunk_leak_rate=0.0,
        min_ragas_metrics={"faithfulness": 0.8},
    )

    validate_constraints(constraints)
    result = evaluate_constraints(summary, constraints)

    assert result["passed"] is False
    assert len(result["violations"]) == 7
    assert any("retrieval_hit_rate" in item for item in result["violations"])
    assert any("average_context_precision" in item for item in result["violations"])
    assert any("average_context_recall" in item for item in result["violations"])
    assert any("refusal_match_rate" in item for item in result["violations"])
    assert any("forbidden_chunk_leak_rate" in item for item in result["violations"])
    assert any("ragas_metrics.faithfulness" in item for item in result["violations"])


def test_constraints_threshold_out_of_range():
    constraints = EvaluationConstraints(min_retrieval_hit_rate=1.2)
    with pytest.raises(ValueError):
        validate_constraints(constraints)
