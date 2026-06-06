import re
from dataclasses import dataclass, field


@dataclass
class InputGuardResult:
    allowed: bool
    risk_level: str
    sanitized_query: str
    reason: str | None = None
    labels: list[str] = field(default_factory=list)
    response_text: str | None = None


class InputGuard:
    _INJECTION_PATTERNS = [
        re.compile(r"(忽略|ignore).{0,20}(系统|system|提示|prompt|规则|instructions?)", re.IGNORECASE),
        re.compile(r"(输出|显示|reveal|show).{0,20}(系统提示|system prompt|提示词|hidden prompt)", re.IGNORECASE),
        re.compile(r"(绕过|bypass|jailbreak).{0,20}(限制|guard|规则|policy)", re.IGNORECASE),
    ]
    _EXFIL_PATTERNS = [
        re.compile(r"(输出|给我|reveal|show|dump).{0,20}(api[_ -]?key|token|password|secret|数据库密码|连接串)", re.IGNORECASE),
        re.compile(r"(身份证号|手机号|住址|银行卡号).{0,12}(给我|告诉我|列出|导出)", re.IGNORECASE),
    ]
    _DANGEROUS_PATTERNS = [
        re.compile(r"(制作|制造|how to make).{0,12}(炸弹|bomb|毒药|木马|勒索软件)", re.IGNORECASE),
        re.compile(r"(破解|入侵|hack).{0,12}(密码|账号|系统|网站)", re.IGNORECASE),
    ]

    def assess(self, query: str) -> InputGuardResult:
        normalized = " ".join((query or "").strip().split())
        if not normalized:
            return InputGuardResult(
                allowed=False,
                risk_level="medium",
                sanitized_query="",
                reason="empty_query",
                labels=["empty_query"],
                response_text="问题是空的，先给奶龙一个明确问题再继续。",
            )

        for pattern in self._EXFIL_PATTERNS:
            if pattern.search(normalized):
                return InputGuardResult(
                    allowed=False,
                    risk_level="critical",
                    sanitized_query=normalized,
                    reason="data_exfiltration",
                    labels=["data_exfiltration"],
                    response_text="这个请求涉及敏感信息或凭据外泄，奶龙不能协助。请改成合规的排查或治理问题。",
                )

        for pattern in self._DANGEROUS_PATTERNS:
            if pattern.search(normalized):
                return InputGuardResult(
                    allowed=False,
                    risk_level="critical",
                    sanitized_query=normalized,
                    reason="harmful_request",
                    labels=["harmful_request"],
                    response_text="这个请求有明显风险，奶龙不能协助。若你是在做安全治理，请改成防护、检测或修复场景。",
                )

        for pattern in self._INJECTION_PATTERNS:
            if pattern.search(normalized):
                return InputGuardResult(
                    allowed=False,
                    risk_level="high",
                    sanitized_query=normalized,
                    reason="prompt_injection",
                    labels=["prompt_injection"],
                    response_text="这个请求带有提示词绕过或系统信息探测意图，奶龙不能按这个方向回答。请直接描述业务问题。",
                )

        if any(token in normalized.lower() for token in ("合规", "风险", "审计", "权限", "隐私")):
            return InputGuardResult(
                allowed=True,
                risk_level="high",
                sanitized_query=normalized,
                labels=["safety_sensitive"],
            )

        return InputGuardResult(
            allowed=True,
            risk_level="low",
            sanitized_query=normalized,
        )
