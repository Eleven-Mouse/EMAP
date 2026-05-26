from dataclasses import dataclass, field


@dataclass
class EvaluationConstraints:
    min_retrieval_hit_rate: float | None = None
    min_context_precision: float | None = None
    min_context_recall: float | None = None
    min_citation_coverage: float | None = None
    min_ragas_metrics: dict[str, float] = field(default_factory=dict)


def _check_bound(value: float | None, name: str) -> None:
    if value is None:
        return
    if value < 0 or value > 1:
        raise ValueError(f"{name} must be in [0, 1]")


def validate_constraints(constraints: EvaluationConstraints) -> None:
    _check_bound(constraints.min_retrieval_hit_rate, "min_retrieval_hit_rate")
    _check_bound(constraints.min_context_precision, "min_context_precision")
    _check_bound(constraints.min_context_recall, "min_context_recall")
    _check_bound(constraints.min_citation_coverage, "min_citation_coverage")
    for metric_name, threshold in constraints.min_ragas_metrics.items():
        _check_bound(threshold, f"min_ragas_metrics.{metric_name}")


def evaluate_constraints(summary: dict, constraints: EvaluationConstraints) -> dict:
    violations: list[str] = []

    metric_specs = [
        ("retrieval_hit_rate", constraints.min_retrieval_hit_rate),
        ("average_context_precision", constraints.min_context_precision),
        ("average_context_recall", constraints.min_context_recall),
        ("citation_coverage_rate", constraints.min_citation_coverage),
    ]
    for metric_name, threshold in metric_specs:
        if threshold is None:
            continue
        actual = summary.get(metric_name)
        if actual is None:
            violations.append(f"{metric_name} missing")
            continue
        if float(actual) < float(threshold):
            violations.append(
                f"{metric_name}={actual:.4f} below threshold {threshold:.4f}"
            )

    ragas_metrics = summary.get("ragas_metrics") or {}
    for metric_name, threshold in constraints.min_ragas_metrics.items():
        actual = ragas_metrics.get(metric_name)
        if actual is None:
            violations.append(
                f"ragas_metrics.{metric_name} missing (threshold {threshold:.4f})"
            )
            continue
        if float(actual) < float(threshold):
            violations.append(
                f"ragas_metrics.{metric_name}={actual:.4f} below threshold {threshold:.4f}"
            )

    return {
        "passed": not violations,
        "violations": violations,
    }
