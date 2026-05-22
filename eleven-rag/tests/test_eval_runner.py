from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.dataset import EvalSample
from evaluation.runner import EvaluationRunner
from schemas.common import SourceItem


class FakeRAGSystem:
    def __init__(self):
        self.calls = []

    def ask(self, user_id: str, session_id: str, query: str, top_k: int):
        self.calls.append((user_id, session_id, query, top_k))
        if "检索策略" in query:
            sources = [
                SourceItem(
                    chunk_id="doc-rag-c2",
                    document_id="doc-rag",
                    content="检索采用关键词 + 向量 + 重排的混合策略",
                    score=0.95,
                )
            ]
            return "证据来自 [doc-rag-c2]，系统采用关键词 + 向量 + 重排", sources

        sources = [
            SourceItem(
                chunk_id="doc-rag-c1",
                document_id="doc-rag",
                content="RAG 是检索增强生成，先检索再回答",
                score=0.99,
            )
        ]
        return "结论见 [doc-rag-c1]：RAG 是检索增强生成", sources


def test_evaluation_runner_produces_summary_without_optional_integrations():
    runner = EvaluationRunner(rag_system=FakeRAGSystem())
    samples = [
        EvalSample(
            sample_id="s1",
            query="什么是RAG？",
            reference_answer="RAG 是检索增强生成",
            expected_chunk_ids=["doc-rag-c1"],
        ),
        EvalSample(
            sample_id="s2",
            query="这个系统检索策略是什么？",
            reference_contexts=["关键词 + 向量 + 重排"],
        ),
    ]

    result = runner.run(
        samples=samples,
        top_k=3,
        enable_ragas=False,
        enable_phoenix=False,
    )

    summary = result["summary"]
    assert summary["sample_count"] == 2
    assert summary["retrieval_hit_rate"] == 1.0
    assert summary["average_context_precision"] >= 0.5
    assert summary["average_context_recall"] >= 0.5
    assert summary["citation_coverage_rate"] > 0
    assert summary["ragas_metrics"] == {}
    assert result["phoenix"]["enabled"] is False
    assert len(result["rows"]) == 2
