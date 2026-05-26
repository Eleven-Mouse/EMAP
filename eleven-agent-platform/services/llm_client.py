import json
from dataclasses import dataclass
from urllib import error, request


@dataclass
class LLMClient:
    api_base: str
    api_key: str
    model: str
    timeout_seconds: int = 60

    def _chat_url(self) -> str:
        return f"{self.api_base}/chat/completions"

    def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if "xiaomimimo.com" in self.api_base:
            payload["max_completion_tokens"] = max_tokens
            payload["response_format"] = {"type": "json_object"}
        else:
            payload["max_tokens"] = max_tokens
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self._chat_url(),
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"LLM HTTP error {exc.code}: {detail[:400]}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"LLM network error: {exc.reason}") from exc

        try:
            data = json.loads(raw)
            message = data["choices"][0]["message"]
            content = message.get("content")
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Unexpected LLM response schema: {raw[:400]}"
            ) from exc

        text = str(content).strip()
        if not text:
            raise RuntimeError("LLM returned empty content")
        return text
