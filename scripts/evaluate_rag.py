from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "eleven-rag"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from evaluation.dataset import load_eval_samples
from evaluation.constraints import (
    EvaluationConstraints,
    evaluate_constraints,
    validate_constraints,
)
from evaluation.runner import EvaluationRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EMAP offline evaluation")
    parser.add_argument(
        "--dataset",
        default="eval/sample_dataset.jsonl",
        help="Path to .json/.jsonl evaluation dataset",
    )
    parser.add_argument(
        "--output",
        default=".rag_store/evals/latest_eval.json",
        help="Output file for evaluation result",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Retrieve top_k for each sample")
    parser.add_argument(
        "--doc-prefix",
        action="append",
        default=[],
        help="Only keep retrieved sources whose document_id starts with this prefix. "
        "Repeat flag for multiple prefixes.",
    )
    parser.add_argument(
        "--enable-ragas",
        action="store_true",
        help="Enable ragas metrics (requires additional model/runtime config)",
    )
    parser.add_argument(
        "--enable-phoenix",
        action="store_true",
        help="Export Phoenix-compatible JSONL for external analysis",
    )
    parser.add_argument(
        "--phoenix-url",
        default=None,
        help="Optional Phoenix endpoint, fallback to PHOENIX_ENDPOINT",
    )
    parser.add_argument(
        "--min-retrieval-hit-rate",
        type=float,
        default=None,
        help="Fail if retrieval_hit_rate falls below this threshold",
    )
    parser.add_argument(
        "--min-context-precision",
        type=float,
        default=None,
        help="Fail if average_context_precision falls below this threshold",
    )
    parser.add_argument(
        "--min-context-recall",
        type=float,
        default=None,
        help="Fail if average_context_recall falls below this threshold",
    )
    parser.add_argument(
        "--min-citation-coverage",
        type=float,
        default=None,
        help="Fail if citation_coverage_rate falls below this threshold",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    constraints = EvaluationConstraints(
        min_retrieval_hit_rate=args.min_retrieval_hit_rate,
        min_context_precision=args.min_context_precision,
        min_context_recall=args.min_context_recall,
        min_citation_coverage=args.min_citation_coverage,
    )
    validate_constraints(constraints)

    samples = load_eval_samples(args.dataset)
    runner = EvaluationRunner()
    result = runner.run(
        samples=samples,
        top_k=max(1, args.top_k),
        doc_id_prefixes=args.doc_prefix,
        enable_ragas=args.enable_ragas,
        enable_phoenix=args.enable_phoenix,
        phoenix_url=args.phoenix_url,
    )
    summary = result["summary"]
    constraint_result = evaluate_constraints(summary, constraints)
    result["constraints"] = {
        "thresholds": {
            "min_retrieval_hit_rate": constraints.min_retrieval_hit_rate,
            "min_context_precision": constraints.min_context_precision,
            "min_context_recall": constraints.min_context_recall,
            "min_citation_coverage": constraints.min_citation_coverage,
        },
        **constraint_result,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("[eval] completed")
    print(f"[eval] samples={summary['sample_count']}")
    print(f"[eval] retrieval_hit_rate={summary['retrieval_hit_rate']}")
    print(f"[eval] average_context_precision={summary['average_context_precision']}")
    print(f"[eval] average_context_recall={summary['average_context_recall']}")
    print(f"[eval] citation_coverage_rate={summary['citation_coverage_rate']}")

    ragas_metrics = summary.get("ragas_metrics") or {}
    if ragas_metrics:
        print(f"[eval] ragas_metrics={json.dumps(ragas_metrics, ensure_ascii=False)}")
    else:
        print("[eval] ragas_metrics=disabled-or-unavailable")

    phoenix = result.get("phoenix") or {}
    if phoenix.get("enabled"):
        print(f"[eval] phoenix_export={phoenix.get('export_file')}")
    else:
        print(f"[eval] phoenix={phoenix.get('reason')}")

    if constraint_result["passed"]:
        print("[eval] constraints=passed")
    else:
        print(f"[eval] constraints=failed {json.dumps(constraint_result['violations'], ensure_ascii=False)}")
        print(f"[eval] output={output_path}")
        return 2

    print(f"[eval] output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
