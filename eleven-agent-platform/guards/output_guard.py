from dataclasses import dataclass, field

from guards.common import contains_sensitive_leak, extract_citations, is_refusal_answer
from schemas.common import SourceItem


@dataclass
class OutputGuardResult:
    passed: bool
    final_answer: str
    reason: str | None = None
    labels: list[str] = field(default_factory=list)


def build_grounded_safe_answer(
    query: str,
    hits: list[SourceItem],
    reason: str | None = None,
) -> str:
    prefix = "先给保守结论：我只能基于当前证据回答。"
    if reason == "high_risk_degraded":
        prefix = "这个问题风险较高，奶龙改用保守模式，只整理可引用证据。"
    elif reason == "citation_mismatch":
        prefix = "刚才那版回答的引用不可信，奶龙改成只给可核对证据。"
    elif reason == "missing_citation":
        prefix = "当前回答缺少有效引用，奶龙改成证据式答复。"

    evidence_lines = [
        f"- [{hit.chunk_id}] {hit.content[:120]}"
        for hit in hits[: min(3, len(hits))]
    ]
    evidence_block = "\n".join(evidence_lines) if evidence_lines else "- 暂无可引用证据"
    return f"{prefix}\n问题：{query}\n证据：\n{evidence_block}"


class OutputGuard:
    def validate(
        self,
        query: str,
        answer: str,
        hits: list[SourceItem],
        risk_level: str,
    ) -> OutputGuardResult:
        safe_answer = str(answer or "").strip()
        if not safe_answer:
            return OutputGuardResult(
                passed=False,
                final_answer=build_grounded_safe_answer(
                    query=query,
                    hits=hits,
                    reason="missing_citation",
                ),
                reason="empty_answer",
                labels=["empty_answer"],
            )

        if contains_sensitive_leak(safe_answer):
            return OutputGuardResult(
                passed=False,
                final_answer="回答中检测到潜在敏感信息，奶龙先不直接输出。请改成合规的脱敏、治理或排查问题。",
                reason="sensitive_leak",
                labels=["sensitive_leak"],
            )

        if is_refusal_answer(safe_answer):
            return OutputGuardResult(
                passed=True,
                final_answer=safe_answer,
                reason="refusal",
                labels=["refusal"],
            )

        cited_ids = extract_citations(safe_answer)
        allowed_ids = {item.chunk_id for item in hits}
        if cited_ids:
            invalid_ids = [item for item in cited_ids if item not in allowed_ids]
            if invalid_ids:
                return OutputGuardResult(
                    passed=False,
                    final_answer=build_grounded_safe_answer(
                        query=query,
                        hits=hits,
                        reason="citation_mismatch",
                    ),
                    reason="citation_mismatch",
                    labels=["citation_mismatch"],
                )
        elif hits:
            return OutputGuardResult(
                passed=False,
                final_answer=build_grounded_safe_answer(
                    query=query,
                    hits=hits,
                    reason="high_risk_degraded" if risk_level == "high" else "missing_citation",
                ),
                reason="missing_citation",
                labels=["missing_citation"],
            )

        return OutputGuardResult(
            passed=True,
            final_answer=safe_answer,
        )
