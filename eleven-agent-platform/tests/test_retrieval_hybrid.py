from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qa.answering import IntelligentQA
from qa.retrieval_stack import BM25Retriever
from repositories.metadata_repository import StoredChunk
from repositories.vector_repository import VectorHit


class FakeMetadataRepository:
    def list_chunks(self):
        return [
            StoredChunk(
                chunk_id="doc-1-chunk-0",
                document_id="doc-1",
                content="苹果手机相机表现很强，适合喜欢拍照的人。",
                source="unit-test",
                chunk_order=0,
            ),
            StoredChunk(
                chunk_id="doc-2-chunk-0",
                document_id="doc-2",
                content="苹果手机续航更稳，适合高频外出使用。",
                source="unit-test",
                chunk_order=0,
            ),
            StoredChunk(
                chunk_id="doc-3-chunk-0",
                document_id="doc-3",
                content="安卓手机更适合长时间游戏场景。",
                source="unit-test",
                chunk_order=0,
            ),
        ]


class FakeVectorRepository:
    def query(self, text: str, top_k: int):
        return [
            VectorHit(chunk_id="doc-2-chunk-0", score=0.92),
            VectorHit(chunk_id="doc-1-chunk-0", score=0.65),
            VectorHit(chunk_id="doc-3-chunk-0", score=0.20),
        ][:top_k]


class FakeReranker:
    def score(self, query: str, chunks: list[StoredChunk]) -> dict[str, float]:
        base_scores = {
            "doc-1-chunk-0": 0.15,
            "doc-2-chunk-0": 0.98,
            "doc-3-chunk-0": 0.05,
        }
        return {chunk.chunk_id: base_scores[chunk.chunk_id] for chunk in chunks}


def test_bm25_retriever_prefers_exact_keyword_match():
    retriever = BM25Retriever()
    chunks = FakeMetadataRepository().list_chunks()

    hits = retriever.query("苹果 手机 相机", chunks=chunks, top_k=2)

    assert hits[0][0] == "doc-1-chunk-0"
    assert hits[0][1] > hits[1][1]


def test_hybrid_retrieval_uses_configured_weights(monkeypatch):
    qa = IntelligentQA()
    qa._get_repositories = lambda: (FakeMetadataRepository(), FakeVectorRepository())
    qa._reranker = FakeReranker()

    monkeypatch.setattr("qa.answering.settings.hybrid_bm25_enabled", True)
    monkeypatch.setattr("qa.answering.settings.hybrid_vector_enabled", True)
    monkeypatch.setattr("qa.answering.settings.hybrid_reranker_enabled", True)
    monkeypatch.setattr("qa.answering.settings.hybrid_bm25_top_k", 3)
    monkeypatch.setattr("qa.answering.settings.hybrid_vector_top_k", 3)
    monkeypatch.setattr("qa.answering.settings.hybrid_candidate_pool_size", 3)

    monkeypatch.setattr("qa.answering.settings.hybrid_bm25_weight", 0.8)
    monkeypatch.setattr("qa.answering.settings.hybrid_vector_weight", 0.1)
    monkeypatch.setattr("qa.answering.settings.hybrid_reranker_weight", 0.1)
    bm25_first = qa.retrieve("苹果手机相机推荐", top_k=2)
    assert bm25_first[0].chunk_id == "doc-1-chunk-0"

    monkeypatch.setattr("qa.answering.settings.hybrid_bm25_weight", 0.1)
    monkeypatch.setattr("qa.answering.settings.hybrid_vector_weight", 0.1)
    monkeypatch.setattr("qa.answering.settings.hybrid_reranker_weight", 0.8)
    reranker_first = qa.retrieve("苹果手机相机推荐", top_k=2)
    assert reranker_first[0].chunk_id == "doc-2-chunk-0"
