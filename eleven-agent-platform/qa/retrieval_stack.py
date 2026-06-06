import math
from collections import Counter

from repositories.metadata_repository import StoredChunk
from services.text_utils import tokenize_text


class BM25Retriever:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = max(0.0, k1)
        self.b = min(max(0.0, b), 1.0)

    def query(
        self,
        query: str,
        chunks: list[StoredChunk],
        top_k: int,
    ) -> list[tuple[str, float]]:
        if top_k <= 0 or not chunks:
            return []

        query_terms = tokenize_text(query)
        if not query_terms:
            return []

        tokenized_docs = [tokenize_text(chunk.content) for chunk in chunks]
        doc_lens = [len(tokens) for tokens in tokenized_docs]
        avg_doc_len = sum(doc_lens) / max(1, len(doc_lens))

        doc_freqs: Counter[str] = Counter()
        term_freqs: list[Counter[str]] = []
        for tokens in tokenized_docs:
            tf = Counter(tokens)
            term_freqs.append(tf)
            doc_freqs.update(tf.keys())

        query_tf = Counter(query_terms)
        corpus_size = len(chunks)
        scored: list[tuple[str, float]] = []
        for chunk, tf, doc_len in zip(chunks, term_freqs, doc_lens, strict=True):
            score = 0.0
            for term, qtf in query_tf.items():
                freq = tf.get(term, 0)
                if freq <= 0:
                    continue
                doc_freq = doc_freqs.get(term, 0)
                idf = math.log(1 + (corpus_size - doc_freq + 0.5) / (doc_freq + 0.5))
                denom = freq + self.k1 * (
                    1 - self.b + self.b * (doc_len / max(avg_doc_len, 1.0))
                )
                score += idf * ((freq * (self.k1 + 1)) / max(denom, 1e-9)) * qtf
            if score > 0:
                scored.append((chunk.chunk_id, float(score)))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str,
        cache_dir: str,
        device: str = "cpu",
        batch_size: int = 8,
        local_files_only: bool = False,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.device = device
        self.batch_size = max(1, batch_size)
        self.local_files_only = local_files_only
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is required for reranker support. Run `uv sync`."
                ) from exc
            self._model = CrossEncoder(
                self.model_name,
                device=self.device,
                cache_folder=self.cache_dir,
                local_files_only=self.local_files_only,
                trust_remote_code=False,
            )
        return self._model

    def score(self, query: str, chunks: list[StoredChunk]) -> dict[str, float]:
        if not chunks:
            return {}
        pairs = [(query, chunk.content) for chunk in chunks]
        try:
            scores = self._get_model().predict(
                pairs,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        except Exception as exc:
            raise RuntimeError(
                "Reranker inference failed. Check model availability and runtime dependencies."
            ) from exc
        return {
            chunk.chunk_id: float(score)
            for chunk, score in zip(chunks, scores, strict=True)
        }
