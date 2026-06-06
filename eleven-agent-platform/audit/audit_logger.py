import json
from datetime import datetime, timezone
from pathlib import Path

from guards.common import redact_sensitive_text


class AuditLogger:
    def __init__(self, enabled: bool, log_path: str) -> None:
        self.enabled = enabled
        self.log_path = Path(log_path)

    def log(self, payload: dict) -> None:
        if not self.enabled:
            return
        record = dict(payload)
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
        if "query" in record:
            record["query"] = redact_sensitive_text(str(record["query"]))
        if "answer" in record:
            record["answer"] = redact_sensitive_text(str(record["answer"]))
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
