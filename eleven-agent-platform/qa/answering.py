import math
from dataclasses import dataclass

from audit.audit_logger import AuditLogger
from authz.access_control import AccessController
from core.config import settings
from guards.input_guard import InputGuard
from guards.output_guard import OutputGuard, build_grounded_safe_answer
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from qa.retrieval_stack import BM25Retriever, CrossEncoderReranker
from repositories.metadata_repository import StoredChunk
from schemas.common import SourceItem


def _normalize_weights(weight_map: dict[str, float]) -> dict[str, float]:
    positive_weights = {key: max(0.0, value) for key, value in weight_map.items()}
    total = sum(positive_weights.values())
    if total <= 0:
        even = 1.0 / max(1, len(weight_map))
        return {key: even for key in weight_map}
    return {key: value / total for key, value in positive_weights.items()}


def _normalize_score_map(
    raw_scores: dict[str, float],
    candidate_ids: list[str],
) -> dict[str, float]:
    values = [raw_scores[cid] for cid in candidate_ids if cid in raw_scores]
    if not values:
        return {cid: 0.0 for cid in candidate_ids}

    min_score = min(values)
    max_score = max(values)
    if math.isclose(min_score, max_score):
        fill_value = 1.0 if max_score > 0 else 0.0
        return {cid: fill_value if cid in raw_scores else 0.0 for cid in candidate_ids}

    normalized: dict[str, float] = {}
    for cid in candidate_ids:
        if cid not in raw_scores:
            normalized[cid] = 0.0
            continue
        normalized[cid] = (raw_scores[cid] - min_score) / (max_score - min_score)
    return normalized


class AnswerOutput(BaseModel):
    final_output: str = Field(
        description="最终给用户展示的中文回答正文，仅此字段用于展示。",
    )


@dataclass
class AnswerGenerationResult:
    answer: str
    degraded: bool = False
    mode: str | None = None


@dataclass
class RetrievalCandidate:
    candidate_id: str
    document_id: str
    content: str
    search_text: str
    source_type: str
    source: str
    chunk_order: int = 0
    memory_id: str | None = None
    scope_id: str | None = None

    def as_stored_chunk(self) -> StoredChunk:
        return StoredChunk(
            chunk_id=self.candidate_id,
            document_id=self.document_id,
            content=self.search_text,
            source=self.source,
            chunk_order=self.chunk_order,
        )


class RetrievalOrchestrator:
    def __init__(self, qa: "IntelligentQA") -> None:
        self._qa = qa

    @staticmethod
    def _filter_chunks(chunks, doc_id_prefixes: list[str] | None):
        if not doc_id_prefixes:
            return chunks
        prefixes = [prefix.strip() for prefix in doc_id_prefixes if prefix and prefix.strip()]
        if not prefixes:
            return chunks
        return [
            chunk
            for chunk in chunks
            if any(chunk.document_id.startswith(prefix) for prefix in prefixes)
        ]

    @staticmethod
    def _build_document_candidates(chunks: list[StoredChunk]) -> list[RetrievalCandidate]:
        return [
            RetrievalCandidate(
                candidate_id=chunk.chunk_id,
                document_id=chunk.document_id,
                content=chunk.content,
                search_text=chunk.content,
                source_type="document_chunk",
                source=chunk.source,
                chunk_order=chunk.chunk_order,
            )
            for chunk in chunks
        ]

    @staticmethod
    def _build_knowledge_candidates(memories) -> list[RetrievalCandidate]:
        candidates: list[RetrievalCandidate] = []
        for memory in memories:
            search_text = memory.content.strip()
            if memory.title.strip():
                search_text = f"{memory.title.strip()}\n{search_text}"
            candidates.append(
                RetrievalCandidate(
                    candidate_id=memory.memory_id,
                    document_id=memory.scope_id,
                    content=memory.content,
                    search_text=search_text,
                    source_type="knowledge_memory",
                    source=memory.source,
                    memory_id=memory.memory_id,
                    scope_id=memory.scope_id,
                )
            )
        return candidates

    @staticmethod
    def _compose_scores(
        candidate_ids: list[str],
        bm25_scores: dict[str, float],
        vector_scores: dict[str, float],
        reranker_scores: dict[str, float] | None = None,
    ) -> dict[str, float]:
        normalized_bm25 = _normalize_score_map(bm25_scores, candidate_ids)
        normalized_vector = _normalize_score_map(vector_scores, candidate_ids)
        normalized_reranker = _normalize_score_map(reranker_scores or {}, candidate_ids)
        weights = _normalize_weights(
            {
                "bm25": settings.hybrid_bm25_weight if bm25_scores else 0.0,
                "vector": settings.hybrid_vector_weight if vector_scores else 0.0,
                "reranker": (
                    settings.hybrid_reranker_weight if reranker_scores else 0.0
                ),
            }
        )
        return {
            cid: (
                weights["bm25"] * normalized_bm25[cid]
                + weights["vector"] * normalized_vector[cid]
                + weights["reranker"] * normalized_reranker[cid]
            )
            for cid in candidate_ids
        }

    def retrieve(
        self,
        query: str,
        top_k: int,
        doc_id_prefixes: list[str] | None,
    ) -> list[SourceItem]:
        metadata_repository, vector_repository = self._qa._get_repositories()
        chunks = self._filter_chunks(
            metadata_repository.list_chunks(),
            doc_id_prefixes=doc_id_prefixes,
        )
        knowledge_memories = []
        try:
            knowledge_repository = self._qa._get_knowledge_repository()
            knowledge_memories = knowledge_repository.list_active_memories(
                scope_prefixes=doc_id_prefixes
            )
        except Exception:
            knowledge_memories = []
        knowledge_candidates = self._build_knowledge_candidates(knowledge_memories)
        document_candidates = self._build_document_candidates(chunks)
        all_candidates = document_candidates + knowledge_candidates
        if not all_candidates:
            return []

        candidate_map = {candidate.candidate_id: candidate for candidate in all_candidates}
        rerank_chunks = [candidate.as_stored_chunk() for candidate in all_candidates]
        bm25_hits: list[tuple[str, float]] = []
        if settings.hybrid_bm25_enabled:
            bm25_hits = self._qa._get_bm25_retriever().query(
                query=query,
                chunks=rerank_chunks,
                top_k=max(top_k, settings.hybrid_bm25_top_k),
            )

        vector_hits = []
        if settings.hybrid_vector_enabled:
            vector_hits = [
                hit
                for hit in vector_repository.query(
                    text=query,
                    top_k=max(top_k, settings.hybrid_vector_top_k),
                )
                if hit.chunk_id in candidate_map
            ]

        bm25_score_map = {chunk_id: score for chunk_id, score in bm25_hits}
        vector_score_map = {hit.chunk_id: hit.score for hit in vector_hits}
        ordered_candidate_ids = list(
            dict.fromkeys(
                [chunk_id for chunk_id, _ in bm25_hits]
                + [hit.chunk_id for hit in vector_hits]
            )
        )
        if not ordered_candidate_ids:
            ordered_candidate_ids = [
                candidate.candidate_id for candidate in all_candidates[: max(1, top_k)]
            ]

        pre_rerank_scores = self._compose_scores(
            candidate_ids=ordered_candidate_ids,
            bm25_scores=bm25_score_map,
            vector_scores=vector_score_map,
        )
        candidate_pool_size = max(top_k, settings.hybrid_candidate_pool_size)
        candidate_ids = sorted(
            ordered_candidate_ids,
            key=lambda cid: (
                pre_rerank_scores.get(cid, 0.0),
                bm25_score_map.get(cid, 0.0),
                vector_score_map.get(cid, 0.0),
            ),
            reverse=True,
        )[:candidate_pool_size]

        reranker_score_map: dict[str, float] = {}
        if settings.hybrid_reranker_enabled and candidate_ids:
            reranker_score_map = self._qa._get_reranker().score(
                query=query,
                chunks=[candidate_map[cid].as_stored_chunk() for cid in candidate_ids],
            )

        final_scores = self._compose_scores(
            candidate_ids=candidate_ids,
            bm25_scores=bm25_score_map,
            vector_scores=vector_score_map,
            reranker_scores=reranker_score_map,
        )
        ranked_chunk_ids = sorted(
            candidate_ids,
            key=lambda cid: (
                final_scores.get(cid, 0.0),
                reranker_score_map.get(cid, float("-inf")),
                pre_rerank_scores.get(cid, 0.0),
            ),
            reverse=True,
        )[:top_k]
        return [
            SourceItem(
                chunk_id=candidate_map[chunk_id].candidate_id,
                document_id=candidate_map[chunk_id].document_id,
                content=candidate_map[chunk_id].content,
                score=round(final_scores.get(chunk_id, 0.0), 4),
                source_type=candidate_map[chunk_id].source_type,
                memory_id=candidate_map[chunk_id].memory_id,
                scope_id=candidate_map[chunk_id].scope_id,
            )
            for chunk_id in ranked_chunk_ids
        ]


class AnswerGenerator:
    def __init__(self, qa: "IntelligentQA") -> None:
        self._qa = qa

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
    def llm_parse_failure_answer() -> str:
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
        format_instructions = self._qa._answer_parser.get_format_instructions()

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
                    "2) 关键结论必须带引用chunk_id，例如[doc-1-chunk-0]；"
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
            parsed = self._qa._answer_parser.parse(raw_text)
        except Exception:
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
            parsed = self._qa._answer_parser.parse(cleaned)
        answer_text = parsed.final_output.strip()
        if not answer_text:
            raise ValueError("Parsed final_output is empty")
        return answer_text

    def generate(
        self,
        query: str,
        hits: list[SourceItem],
        prefs: list,
        risk_level: str,
        llm_requested: bool,
    ) -> AnswerGenerationResult:
        if risk_level == "high" and not settings.high_risk_allow_llm:
            return AnswerGenerationResult(
                answer=build_grounded_safe_answer(
                    query=query,
                    hits=hits,
                    reason="high_risk_degraded",
                ),
                degraded=True,
                mode="high_risk_grounded_only",
            )

        answer = None
        if llm_requested:
            try:
                messages = self._build_prompt_messages(
                    query=query,
                    hits=hits,
                    prefs=prefs,
                )
                answer = self._qa._get_llm_client().generate(
                    messages=messages,
                    temperature=min(settings.llm_temperature, 0.1)
                    if risk_level == "medium"
                    else settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                )
                answer = self._parse_llm_answer(answer)
            except Exception as exc:  # noqa: BLE001
                print(f"[llm-warning] {exc}")

        if not answer:
            answer = (
                self.llm_parse_failure_answer()
                if llm_requested
                else self._fallback_answer(query=query, hits=hits, prefs=prefs)
            )
        return AnswerGenerationResult(answer=answer)


class IntelligentQA:
    def __init__(self) -> None:
        self._memory_service = None
        self._llm_client = None
        self._knowledge_repository = None
        self._bm25_retriever = None
        self._reranker = None
        self._input_guard = None
        self._output_guard = None
        self._access_controller = None
        self._audit_logger = None
        self._retrieval_orchestrator = None
        self._answer_generator = None
        self._last_trace = None
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

    def _get_knowledge_repository(self):
        if self._knowledge_repository is None:
            from services.container import knowledge_repository

            self._knowledge_repository = knowledge_repository
        return self._knowledge_repository

    def _get_input_guard(self) -> InputGuard:
        if self._input_guard is None:
            self._input_guard = InputGuard()
        return self._input_guard

    def _get_output_guard(self) -> OutputGuard:
        if self._output_guard is None:
            self._output_guard = OutputGuard()
        return self._output_guard

    def _get_access_controller(self) -> AccessController:
        if self._access_controller is None:
            self._access_controller = AccessController(
                enabled=settings.authz_enabled,
                default_allow=settings.authz_default_allow,
                raw_rules=settings.user_doc_permissions,
            )
        return self._access_controller

    def _get_audit_logger(self) -> AuditLogger:
        if self._audit_logger is None:
            self._audit_logger = AuditLogger(
                enabled=settings.audit_log_enabled,
                log_path=settings.audit_log_path,
            )
        return self._audit_logger

    def _get_bm25_retriever(self) -> BM25Retriever:
        if self._bm25_retriever is None:
            self._bm25_retriever = BM25Retriever(
                k1=settings.bm25_k1,
                b=settings.bm25_b,
            )
        return self._bm25_retriever

    def _get_reranker(self) -> CrossEncoderReranker:
        if self._reranker is None:
            self._reranker = CrossEncoderReranker(
                model_name=settings.reranker_model_name,
                cache_dir=settings.reranker_cache_dir,
                device=settings.reranker_device,
                batch_size=settings.reranker_batch_size,
                local_files_only=settings.reranker_local_files_only,
            )
        return self._reranker

    def _get_retrieval_orchestrator(self) -> RetrievalOrchestrator:
        if self._retrieval_orchestrator is None:
            self._retrieval_orchestrator = RetrievalOrchestrator(self)
        return self._retrieval_orchestrator

    def _get_answer_generator(self) -> AnswerGenerator:
        if self._answer_generator is None:
            self._answer_generator = AnswerGenerator(self)
        return self._answer_generator

    def _record_trace(self, payload: dict) -> None:
        self._last_trace = dict(payload)
        try:
            self._get_audit_logger().log(payload)
        except Exception as exc:  # noqa: BLE001
            print(f"[audit-warning] {exc}")

    def get_last_trace(self) -> dict | None:
        return self._last_trace

    def retrieve(self, query: str, top_k: int) -> list[SourceItem]:
        return self._retrieve(query=query, top_k=top_k, doc_id_prefixes=None)

    def _retrieve(
        self,
        query: str,
        top_k: int,
        doc_id_prefixes: list[str] | None,
    ) -> list[SourceItem]:
        return self._get_retrieval_orchestrator().retrieve(
            query=query,
            top_k=top_k,
            doc_id_prefixes=doc_id_prefixes,
        )

    def ask(
        self,
        user_id: str,
        session_id: str,
        query: str,
        top_k: int | None,
        doc_id_prefixes: list[str] | None = None,
    ) -> tuple[str, list[SourceItem]]:
        k = top_k or settings.top_k
        memory_service = self._get_memory_service()
        input_guard_result = (
            self._get_input_guard().assess(query)
            if settings.input_guard_enabled
            else None
        )
        sanitized_query = (
            input_guard_result.sanitized_query
            if input_guard_result
            else str(query or "").strip()
        )
        access_decision = self._get_access_controller().resolve(
            user_id=user_id,
            requested_prefixes=doc_id_prefixes,
        )
        trace = {
            "user_id": user_id,
            "session_id": session_id,
            "query": sanitized_query,
            "risk_level": input_guard_result.risk_level if input_guard_result else "low",
            "input_guard_labels": input_guard_result.labels if input_guard_result else [],
            "requested_doc_prefixes": doc_id_prefixes or [],
            "effective_doc_prefixes": access_decision.effective_prefixes or [],
            "access_reason": access_decision.reason,
            "blocked": False,
            "degraded": False,
            "mode": "normal",
            "retrieved_chunk_ids": [],
            "retrieved_source_types": [],
            "output_guard_labels": [],
        }

        memory_service.append_session(session_id, f"user: {sanitized_query}")

        if input_guard_result and not input_guard_result.allowed:
            answer = input_guard_result.response_text or "这个请求不符合安全要求，奶龙先拒绝处理。"
            memory_service.append_session(session_id, f"assistant: {answer}")
            trace.update(
                {
                    "blocked": True,
                    "mode": "blocked_by_input_guard",
                    "answer": answer,
                }
            )
            self._record_trace(trace)
            return answer, []

        if not access_decision.allowed:
            answer = "你当前没有访问这批文档的权限，先补充授权范围或切换到有权限的资料。"
            memory_service.append_session(session_id, f"assistant: {answer}")
            trace.update(
                {
                    "blocked": True,
                    "mode": "blocked_by_access_control",
                    "answer": answer,
                }
            )
            self._record_trace(trace)
            return answer, []

        hits = self._retrieve(
            query=sanitized_query,
            top_k=k,
            doc_id_prefixes=access_decision.effective_prefixes,
        )
        trace["retrieved_chunk_ids"] = [item.chunk_id for item in hits]
        trace["retrieved_source_types"] = [item.source_type for item in hits]
        prefs = memory_service.list_preferences(user_id)

        if not hits:
            answer = "奶龙在呢，但我还没找到可引用证据。先导入文档，我们再一起看。"
            memory_service.append_session(session_id, f"assistant: {answer}")
            trace["answer"] = answer
            self._record_trace(trace)
            return answer, []

        llm_requested = (
            settings.llm_enabled
            and bool(settings.llm_api_base)
            and bool(settings.llm_api_key)
        )
        risk_level = input_guard_result.risk_level if input_guard_result else "low"
        generation = self._get_answer_generator().generate(
            query=sanitized_query,
            hits=hits,
            prefs=prefs,
            risk_level=risk_level,
            llm_requested=llm_requested,
        )
        answer = generation.answer
        if generation.degraded:
            trace["degraded"] = True
        if generation.mode:
            trace["mode"] = generation.mode

        if settings.output_guard_enabled:
            output_guard_result = self._get_output_guard().validate(
                query=sanitized_query,
                answer=answer,
                hits=hits,
                risk_level=risk_level,
            )
            answer = output_guard_result.final_answer
            if not output_guard_result.passed:
                trace["degraded"] = True
                trace["mode"] = output_guard_result.reason or "output_guard_degraded"
            trace["output_guard_labels"] = output_guard_result.labels

        memory_service.append_session(session_id, f"assistant: {answer}")
        trace["answer"] = answer
        self._record_trace(trace)
        return answer, hits
