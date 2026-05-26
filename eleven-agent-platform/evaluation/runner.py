import importlib.util
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from evaluation.dataset import EvalSample
from agent_system import AgentSystem
from services.text_utils import tokenize_text


@dataclass
class EvaluationSummary:
    sample_count: int
    retrieval_hit_rate: float
    average_context_precision: float
    average_context_recall: float
    citation_coverage_rate: float
    ragas_metrics: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "sample_count": self.sample_count,
            "retrieval_hit_rate": round(self.retrieval_hit_rate, 4),
            "average_context_precision": round(self.average_context_precision, 4),
            "average_context_recall": round(self.average_context_recall, 4),
            "citation_coverage_rate": round(self.citation_coverage_rate, 4),
            "ragas_metrics": {
                name: round(value, 4) for name, value in self.ragas_metrics.items()
            },
        }


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _token_set(text: str) -> set[str]:
    return set(tokenize_text(_normalize_text(text)))


def _jaccard(a: str, b: str) -> float:
    left = _token_set(a)
    right = _token_set(b)
    if not left or not right:
        return 0.0
    return len(left.intersection(right)) / len(left.union(right))


def _coverage(answer: str, contexts: list[str]) -> float:
    answer_tokens = _token_set(answer)
    if not answer_tokens:
        return 0.0

    contexts_tokens: set[str] = set()
    for context in contexts:
        contexts_tokens.update(_token_set(context))

    if not contexts_tokens:
        return 0.0

    overlap = answer_tokens.intersection(contexts_tokens)
    return len(overlap) / len(answer_tokens)


def _build_ragas_rows(rows: list[dict]) -> list[dict]:
    ragas_rows = []
    for row in rows:
        ragas_row = {
            "user_input": row["query"],
            "response": row["answer"],
            "retrieved_contexts": row["retrieved_contexts"],
        }
        reference = row.get("reference_answer")
        if reference:
            ragas_row["reference"] = reference
        reference_contexts = row.get("reference_contexts") or []
        if reference_contexts:
            ragas_row["reference_contexts"] = reference_contexts
        ragas_rows.append(ragas_row)
    return ragas_rows


def _safe_import_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _run_ragas(rows: list[dict]) -> dict[str, float]:
    if not rows:
        return {}
    if not _safe_import_available("ragas"):
        return {}

    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas import metrics as ragas_metrics
    except Exception:
        return {}

    dataset = Dataset.from_list(_build_ragas_rows(rows))
    metric_names = [
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "faithfulness",
    ]
    metrics = [
        getattr(ragas_metrics, name)
        for name in metric_names
        if hasattr(ragas_metrics, name)
    ]

    try:
        result = evaluate(dataset=dataset, metrics=metrics)
        score = result.to_pandas().mean(numeric_only=True).to_dict()
        return {str(k): float(v) for k, v in score.items()}
    except Exception:
        return {}


def _export_to_phoenix(rows: list[dict], phoenix_url: str | None = None) -> dict:
    if not rows:
        return {"enabled": False, "reason": "no rows"}

    phoenix_endpoint = phoenix_url or os.getenv("PHOENIX_ENDPOINT")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_file = f".rag_store/evals/phoenix_export_{timestamp}.jsonl"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as handle:
        for row in rows:
            payload = {
                "id": row["sample_id"],
                "input": row["query"],
                "output": row["answer"],
                "metadata": {
                    "expected_chunk_ids": row["expected_chunk_ids"],
                    "retrieved_chunk_ids": row["retrieved_chunk_ids"],
                    "retrieved_contexts": row["retrieved_contexts"],
                    "reference_answer": row.get("reference_answer"),
                },
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return {
        "enabled": True,
        "endpoint": phoenix_endpoint or "local-file",
        "export_file": output_file,
        "rows": len(rows),
    }


class EvaluationRunner:
    def __init__(self, agent_system: AgentSystem | None = None) -> None:
        self._rag = agent_system or AgentSystem()

    def run(
        self,
        samples: list[EvalSample],
        user_id: str = "eval-user",
        session_prefix: str = "eval-session",
        top_k: int = 5,
        doc_id_prefixes: list[str] | None = None,
        enable_ragas: bool = False,
        enable_phoenix: bool = False,
        phoenix_url: str | None = None,
    ) -> dict:
        rows = []
        retrieval_hits = 0
        precision_values = []
        recall_values = []
        citation_coverages = []

        for index, sample in enumerate(samples):
            session_id = f"{session_prefix}-{index + 1}"
            answer, sources = self._rag.ask(
                user_id=user_id,
                session_id=session_id,
                query=sample.query,
                top_k=top_k,
                doc_id_prefixes=doc_id_prefixes,
            )
            retrieved_chunk_ids = [source.chunk_id for source in sources]
            retrieved_contexts = [source.content for source in sources]

            expected_ids = set(sample.expected_chunk_ids or [])
            hit = bool(expected_ids.intersection(retrieved_chunk_ids)) if expected_ids else bool(sources)
            if hit:
                retrieval_hits += 1

            if expected_ids:
                hit_count = len(expected_ids.intersection(retrieved_chunk_ids))
                precision_values.append(hit_count / max(1, len(retrieved_chunk_ids)))
                recall_values.append(hit_count / len(expected_ids))
            elif sample.reference_contexts:
                # fallback textual alignment if no explicit chunk ids
                best = 0.0
                for context in sample.reference_contexts:
                    for retrieved in retrieved_contexts:
                        best = max(best, _jaccard(context, retrieved))
                precision_values.append(best)
                recall_values.append(best)
            else:
                precision_values.append(1.0 if sources else 0.0)
                recall_values.append(1.0 if sources else 0.0)

            citation_coverages.append(
                _coverage(answer=answer, contexts=retrieved_contexts)
            )

            rows.append(
                {
                    "sample_id": sample.sample_id,
                    "query": sample.query,
                    "answer": answer,
                    "reference_answer": sample.reference_answer,
                    "reference_contexts": sample.reference_contexts or [],
                    "expected_chunk_ids": sample.expected_chunk_ids or [],
                    "retrieved_chunk_ids": retrieved_chunk_ids,
                    "retrieved_contexts": retrieved_contexts,
                }
            )

        summary = EvaluationSummary(
            sample_count=len(samples),
            retrieval_hit_rate=retrieval_hits / len(samples),
            average_context_precision=sum(precision_values) / len(precision_values),
            average_context_recall=sum(recall_values) / len(recall_values),
            citation_coverage_rate=sum(citation_coverages) / len(citation_coverages),
            ragas_metrics=_run_ragas(rows) if enable_ragas else {},
        )

        phoenix_info = (
            _export_to_phoenix(rows=rows, phoenix_url=phoenix_url)
            if enable_phoenix
            else {"enabled": False, "reason": "disabled"}
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary.to_dict(),
            "rows": rows,
            "phoenix": phoenix_info,
        }

