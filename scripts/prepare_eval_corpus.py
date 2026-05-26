from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "eleven-agent-platform"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from agent_system import AgentSystem  # noqa: E402


E2E_DOC_ID = "doc-e2e-001"
E2E_SOURCE = "eval-seed"
E2E_CONTENT = (
    "RAG（Retrieval-Augmented Generation）是检索增强生成。\n"
    "系统检索策略采用关键词 + 向量 + 重排。\n"
    "重排会结合元数据信号，例如标题、层级、文件名匹配。\n"
    "长期记忆存储在 MySQL，短期会话记忆存储在 Redis。"
)


def main() -> int:
    rag = AgentSystem()
    chunk_count = rag.ingest(
        document_id=E2E_DOC_ID,
        content=E2E_CONTENT,
        source=E2E_SOURCE,
    )
    print("[prepare-eval] completed")
    print(f"[prepare-eval] document_id={E2E_DOC_ID}")
    print(f"[prepare-eval] chunk_count={chunk_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


