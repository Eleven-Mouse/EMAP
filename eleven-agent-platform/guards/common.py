import re


CITATION_PATTERN = re.compile(r"\[([A-Za-z0-9._:-]+)\]")
REFUSAL_MARKERS = (
    "无法协助",
    "不能协助",
    "不能帮助",
    "不能提供",
    "不能按这个方向回答",
    "拒绝",
    "先不直接输出",
)

_EMAIL_PATTERN = re.compile(r"([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_PHONE_PATTERN = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
_SECRET_PATTERN = re.compile(
    r"\b(sk-[A-Za-z0-9]{10,}|Bearer\s+[A-Za-z0-9._-]{10,}|AKIA[0-9A-Z]{16}|api[_-]?key\s*[:=]\s*[A-Za-z0-9._-]{8,})\b",
    re.IGNORECASE,
)
_ID_PATTERN = re.compile(r"(?<!\d)(\d{6})\d{8}(\d{4}|[\dXx]{4})(?!\d)")


def extract_citations(text: str) -> list[str]:
    return [item.strip() for item in CITATION_PATTERN.findall(text or "") if item.strip()]


def is_refusal_answer(text: str) -> bool:
    normalized = (text or "").strip()
    return any(marker in normalized for marker in REFUSAL_MARKERS)


def redact_sensitive_text(text: str) -> str:
    masked = str(text or "")
    masked = _EMAIL_PATTERN.sub(r"\1***@\2", masked)
    masked = _PHONE_PATTERN.sub(r"\1****\2", masked)
    masked = _ID_PATTERN.sub(r"\1********\2", masked)
    masked = _SECRET_PATTERN.sub("[REDACTED_SECRET]", masked)
    return masked


def contains_sensitive_leak(text: str) -> bool:
    value = str(text or "")
    return bool(
        _SECRET_PATTERN.search(value)
        or _PHONE_PATTERN.search(value)
        or _ID_PATTERN.search(value)
    )
