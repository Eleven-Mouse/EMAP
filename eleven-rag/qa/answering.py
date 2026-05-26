import json

from core.config import settings
from schemas.common import SourceItem
from services.text_utils import tokenize_text


def _keyword_score(query_tokens: set[str], text_tokens: set[str]) -> float:
    if not query_tokens or not text_tokens:
        return 0.0
    overlap = query_tokens.intersection(text_tokens)
    return len(overlap) / len(query_tokens)


def _vector_like_score(query_tokens: set[str], text_tokens: set[str]) -> float:
    if not query_tokens or not text_tokens:
        return 0.0
    overlap = query_tokens.intersection(text_tokens)
    denom = len(query_tokens.union(text_tokens))
    return len(overlap) / max(1, denom)


def _parse_metadata(metadata_json: str) -> dict:
    try:
        parsed = json.loads(metadata_json or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _metadata_boost(metadata: dict, query_tokens: set[str]) -> float:
    boost = 0.0
    category = metadata.get("category")
    if category == "Title":
        boost += 0.08

    depth = metadata.get("category_depth")
    if isinstance(depth, int) and depth <= 1:
        boost += 0.03

    filename = metadata.get("filename")
    if isinstance(filename, str) and query_tokens:
        file_tokens = set(tokenize_text(filename))
        overlap = query_tokens.intersection(file_tokens)
        if overlap:
            boost += min(0.06, 0.02 * len(overlap))

    filetype = metadata.get("filetype")
    if filetype == "text/markdown":
        boost += 0.02
    return boost


def _hybrid_score(
    query: str,
    content: str,
    vector_score: float,
    metadata: dict | None = None,
) -> float:
    query_tokens = set(tokenize_text(query))
    text_tokens = set(tokenize_text(content))
    kw = _keyword_score(query_tokens, text_tokens)
    token_vec = _vector_like_score(query_tokens, text_tokens)
    meta = _metadata_boost(metadata or {}, query_tokens)
    # FAISS recall first, then lexical + metadata rerank.
    return vector_score * 0.60 + kw * 0.20 + token_vec * 0.10 + meta


class IntelligentQA:
    def __init__(self) -> None:
        self._memory_service = None

    def _get_memory_service(self):
        if self._memory_service is None:
            from services.memory_service import MemoryService

            self._memory_service = MemoryService()
        return self._memory_service

    def _get_repositories(self):
        from services.container import metadata_repository, vector_repository

        return metadata_repository, vector_repository

    def retrieve(self, query: str, top_k: int) -> list[SourceItem]:
        metadata_repository, vector_repository = self._get_repositories()
        chunks = metadata_repository.list_chunks()
        if not chunks:
            return []

        chunk_map = {chunk.chunk_id: chunk for chunk in chunks}
        vector_hits = vector_repository.query(text=query, top_k=max(top_k * 4, 20))
        vector_score_map = {hit.chunk_id: hit.score for hit in vector_hits}

        scored = []
        candidate_ids = {hit.chunk_id for hit in vector_hits}
        for chunk in chunks:
            if candidate_ids and chunk.chunk_id not in candidate_ids:
                continue
            base_vector_score = vector_score_map.get(chunk.chunk_id, 0.0)
            metadata = _parse_metadata(chunk.metadata_json)
            score = _hybrid_score(query, chunk.content, base_vector_score, metadata)
            if score > 0:
                scored.append((score, chunk.chunk_id))

        if not scored:
            for hit in vector_hits[:top_k]:
                scored.append((hit.score * 0.5, hit.chunk_id))

        if not scored:
            for chunk in chunks[:top_k]:
                scored.append((0.0001, chunk.chunk_id))

        scored.sort(key=lambda x: x[0], reverse=True)
        hits = []
        used: set[str] = set()
        for score, chunk_id in scored:
            if chunk_id in used:
                continue
            hits.append((score, chunk_id))
            used.add(chunk_id)
            if len(hits) >= top_k:
                break
        return [
            SourceItem(
                chunk_id=chunk_map[chunk_id].chunk_id,
                document_id=chunk_map[chunk_id].document_id,
                content=chunk_map[chunk_id].content,
                score=round(score, 4),
            )
            for score, chunk_id in hits
        ]

    def ask(
        self, user_id: str, session_id: str, query: str, top_k: int | None
    ) -> tuple[str, list[SourceItem]]:
        k = top_k or settings.top_k
        hits = self.retrieve(query=query, top_k=k)
        memory_service = self._get_memory_service()
        prefs = memory_service.list_preferences(user_id)

        memory_service.append_session(session_id, f"user: {query}")

        if not hits:
            answer = "奶龙在呢，但我还没找到可引用证据。先导入文档，我们再一起看。"
            memory_service.append_session(session_id, f"assistant: {answer}")
            return answer, []

        pref_text = ""
        if prefs:
            pref_pairs = ", ".join([f"{p.key}={p.value}" for p in prefs])
            pref_text = f"（已应用偏好: {pref_pairs}）"

        evidence = "\n".join([f"- [{h.chunk_id}] {h.content[:120]}" for h in hits])
        answer = (
            f"我是奶龙{pref_text}。\n"
            f"你问的是：{query}\n"
            f"我先给结论：请优先参考下面这些可追溯证据。\n"
            f"证据：\n{evidence}"
        )

        memory_service.append_session(session_id, f"assistant: {answer}")
        return answer, hits
