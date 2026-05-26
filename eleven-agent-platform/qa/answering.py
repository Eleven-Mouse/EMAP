import json

from core.config import settings
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
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


class AnswerOutput(BaseModel):
    final_output: str = Field(
        description="最终给用户展示的中文回答正文（仅此字段用于展示）"
    )


class IntelligentQA:
    def __init__(self) -> None:
        self._memory_service = None
        self._llm_client = None
        self._answer_parser = PydanticOutputParser(pydantic_object=AnswerOutput)

    def _get_memory_service(self):
        if self._memory_service is None:
            from services.memory_service import MemoryService

            self._memory_service = MemoryService()
        return self._memory_service

    def _get_llm_client(self):
        if self._llm_client is None:
            from services.llm_client import LLMClient

            self._llm_client = LLMClient(
                api_base=settings.llm_api_base,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        return self._llm_client

    def _get_repositories(self):
        from services.container import metadata_repository, vector_repository

        return metadata_repository, vector_repository

    def _fallback_answer(
        self,
        query: str,
        hits: list[SourceItem],
        prefs: list,
    ) -> str:
        pref_text = ""
        if prefs:
            pref_pairs = ", ".join([f"{p.key}={p.value}" for p in prefs])
            pref_text = f"（已应用偏好: {pref_pairs}）"
        evidence = "\n".join([f"- [{h.chunk_id}] {h.content[:120]}" for h in hits])
        return (
            f"我是奶龙{pref_text}。\n"
            f"你问的是：{query}\n"
            f"我先给结论：请优先参考下面这些可追溯证据。\n"
            f"证据：\n{evidence}"
        )

    @staticmethod
    def _llm_parse_failure_answer() -> str:
        return "奶龙这次输出格式跑偏了，请重试一次。"

    def _build_prompt_messages(
        self,
        query: str,
        hits: list[SourceItem],
        prefs: list,
    ) -> list[dict[str, str]]:
        pref_text = "无"
        if prefs:
            pref_text = "; ".join([f"{p.key}={p.value}" for p in prefs])

        evidence_lines = []
        for hit in hits:
            evidence_lines.append(
                f"[{hit.chunk_id}] doc={hit.document_id} score={hit.score}\n{hit.content}"
            )
        evidence_block = "\n\n".join(evidence_lines)
        format_instructions = self._answer_parser.get_format_instructions()

        user_prompt = (
            f"用户问题：{query}\n\n"
            f"用户偏好：{pref_text}\n\n"
            f"检索证据（仅可基于这些证据回答）：\n{evidence_block}\n\n"
            "请输出中文答案，并遵守：\n"
            "1. 仅基于证据作答，不得编造来源与事实；\n"
            "2. 关键结论后加引用，如 [doc-1-chunk-0]；\n"
            "3. 若证据不足，明确说明不足点，并给出下一步建议；\n"
            "4. 禁止输出思考过程、推理步骤、草稿或中间分析，只输出最终结果。\n\n"
            "你必须严格按下面的结构化格式返回：\n"
            f"{format_instructions}"
        )
        return [
            {
                "role": "system",
                "content": (
                    "你是“奶龙”风格的RAG问答助手：语气亲切、轻松、带一点幽默，"
                    "但事实判断必须严谨克制。"
                    "你必须遵守以下规则："
                    "1) 只能基于给定检索证据回答，不得编造；"
                    "2) 关键结论必须带引用chunk_id，例如 [doc-1-chunk-0]；"
                    "3) 证据不足时要明确说不知道，并说明缺少什么信息；"
                    "4) 回答优先清晰和可追溯，不要为了幽默牺牲准确性；"
                    "5) 可以使用简短的奶龙口吻开场或收尾，但避免冗长表演；"
                    "6) 严禁输出思考过程（chain-of-thought）或任何中间推理内容。"
                ),
            },
            {"role": "user", "content": user_prompt},
        ]

    def _parse_llm_answer(self, raw_text: str) -> str:
        try:
            parsed = self._answer_parser.parse(raw_text)
        except Exception:
            # Compatibility: some models wrap JSON in markdown fences or add extra text.
            cleaned = raw_text.strip()
            if "```" in cleaned:
                start = cleaned.find("```")
                end = cleaned.find("```", start + 3)
                if end > start:
                    block = cleaned[start + 3 : end].strip()
                    if block.startswith("json"):
                        block = block[4:].strip()
                    cleaned = block
            start_obj = cleaned.find("{")
            end_obj = cleaned.rfind("}")
            if start_obj >= 0 and end_obj > start_obj:
                cleaned = cleaned[start_obj : end_obj + 1]
            parsed = self._answer_parser.parse(cleaned)
        answer_text = parsed.final_output.strip()
        if not answer_text:
            raise ValueError("Parsed final_output is empty")
        return answer_text

    def retrieve(self, query: str, top_k: int) -> list[SourceItem]:
        return self._retrieve(query=query, top_k=top_k, doc_id_prefixes=None)

    def _retrieve(
        self,
        query: str,
        top_k: int,
        doc_id_prefixes: list[str] | None,
    ) -> list[SourceItem]:
        metadata_repository, vector_repository = self._get_repositories()
        chunks = metadata_repository.list_chunks()
        if doc_id_prefixes:
            prefixes = [p.strip() for p in doc_id_prefixes if p and p.strip()]
            if prefixes:
                chunks = [
                    chunk
                    for chunk in chunks
                    if any(chunk.document_id.startswith(prefix) for prefix in prefixes)
                ]
        if not chunks:
            return []

        chunk_map = {chunk.chunk_id: chunk for chunk in chunks}
        vector_hits = vector_repository.query(text=query, top_k=max(top_k * 4, 20))
        if doc_id_prefixes:
            prefixes = [p.strip() for p in doc_id_prefixes if p and p.strip()]
            if prefixes:
                vector_hits = [
                    hit
                    for hit in vector_hits
                    if any(
                        (chunk_map.get(hit.chunk_id) and chunk_map[hit.chunk_id].document_id.startswith(prefix))
                        for prefix in prefixes
                    )
                ]
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
        self,
        user_id: str,
        session_id: str,
        query: str,
        top_k: int | None,
        doc_id_prefixes: list[str] | None = None,
    ) -> tuple[str, list[SourceItem]]:
        k = top_k or settings.top_k
        hits = self._retrieve(query=query, top_k=k, doc_id_prefixes=doc_id_prefixes)
        memory_service = self._get_memory_service()
        prefs = memory_service.list_preferences(user_id)

        memory_service.append_session(session_id, f"user: {query}")

        if not hits:
            answer = "奶龙在呢，但我还没找到可引用证据。先导入文档，我们再一起看。"
            memory_service.append_session(session_id, f"assistant: {answer}")
            return answer, []

        answer = None
        llm_requested = (
            settings.llm_enabled
            and bool(settings.llm_api_base)
            and bool(settings.llm_api_key)
        )
        if llm_requested:
            try:
                messages = self._build_prompt_messages(query=query, hits=hits, prefs=prefs)
                answer = self._get_llm_client().generate(
                    messages=messages,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                )
                answer = self._parse_llm_answer(answer)
            except Exception as exc:  # noqa: BLE001
                print(f"[llm-warning] {exc}")

        if not answer:
            if llm_requested:
                answer = self._llm_parse_failure_answer()
            else:
                answer = self._fallback_answer(query=query, hits=hits, prefs=prefs)

        memory_service.append_session(session_id, f"assistant: {answer}")
        return answer, hits
