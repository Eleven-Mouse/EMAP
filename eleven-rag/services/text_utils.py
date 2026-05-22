import math
import re
import hashlib
from collections import Counter


EN_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
CJK_CHAR_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def tokenize_text(text: str) -> list[str]:
    normalized = text.lower()
    tokens: list[str] = []

    # English/number word tokens
    tokens.extend(EN_TOKEN_PATTERN.findall(normalized))

    # Chinese single-char tokens + bi-grams for basic phrase matching
    cjk_chars = CJK_CHAR_PATTERN.findall(normalized)
    tokens.extend(cjk_chars)
    if len(cjk_chars) > 1:
        tokens.extend(
            [cjk_chars[i] + cjk_chars[i + 1] for i in range(len(cjk_chars) - 1)]
        )
    return tokens


def _stable_hash_bucket(token: str, dim: int) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return value % dim


def hashed_vector(text: str, dim: int = 256) -> list[float]:
    tokens = tokenize_text(text)
    if not tokens:
        return [0.0] * dim

    counts = Counter(tokens)
    vector = [0.0] * dim
    for token, cnt in counts.items():
        idx = _stable_hash_bucket(token, dim)
        vector[idx] += float(cnt)

    norm = math.sqrt(sum(v * v for v in vector))
    if norm <= 0:
        return vector
    return [v / norm for v in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))
