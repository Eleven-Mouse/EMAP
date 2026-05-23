import argparse
import json
import pathlib
import re
import urllib.error
import urllib.request


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
TRIGGER_WORD = "奶龙"
LEADING_PUNCTUATION = "，,。.!！?？:：;；\"'“”‘’（）()[]【】 "


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def _extract_query(raw: str, require_trigger: bool) -> str | None:
    text = raw.strip()
    if not text:
        return "你好，先介绍一下你能做什么。"

    if require_trigger:
        if not text.startswith(TRIGGER_WORD):
            return None
        query = text[len(TRIGGER_WORD) :].strip()
        query = query.lstrip(LEADING_PUNCTUATION)
        return query or "你好，先介绍一下你能做什么。"

    # Command mode: allow direct question without trigger word.
    if text.startswith(TRIGGER_WORD):
        text = text[len(TRIGGER_WORD) :].strip()
    text = text.lstrip(LEADING_PUNCTUATION)
    return text or "你好，先介绍一下你能做什么。"


def _try_extract_import_path(query: str) -> str | None:
    text = query.strip()
    lower = text.lower()
    if not (lower.startswith("导入:") or lower.startswith("导入：")):
        return None
    path_text = text.split(":", 1)[1] if ":" in text else text.split("：", 1)[1]
    path_text = path_text.strip().strip("\"").strip("'")
    if not path_text:
        return None
    return path_text


def _ingest_file(base_url: str, file_path_text: str) -> int:
    file_path = pathlib.Path(file_path_text).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        print(f"导入失败：文件不存在：{file_path}")
        return 1
    if file_path.suffix.lower() not in {".md", ".txt", ".pdf"}:
        print("导入失败：仅支持 .md / .txt / .pdf 文件")
        return 1

    document_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", file_path.stem).strip("-")
    document_id = document_id or "local-doc"
    payload = {
        "document_id": document_id,
        "file_path": str(file_path),
        "source": "local-file",
    }
    try:
        result = _post_json(f"{base_url}/v1/ingest", payload)
    except urllib.error.URLError as exc:
        print(f"导入请求失败：{exc}")
        return 1

    print("导入成功")
    print(f"- document_id: {result.get('document_id')}")
    print(f"- chunk_count: {result.get('chunk_count')}")
    return 0


def _ask_once(
    *,
    message: str,
    user_id: str,
    session_id: str,
    base_url: str,
    top_k: int,
    require_trigger: bool,
) -> int:
    query = _extract_query(message, require_trigger=require_trigger)
    if query is None:
        print("未触发：请输入以“奶龙”开头的消息，例如：奶龙 什么是RAG")
        return 0

    import_path = _try_extract_import_path(query)
    if import_path:
        return _ingest_file(base_url=base_url, file_path_text=import_path)

    payload = {
        "user_id": user_id,
        "session_id": session_id,
        "query": query,
        "top_k": top_k,
    }

    try:
        result = _post_json(f"{base_url}/v1/chat", payload)
    except urllib.error.URLError as exc:
        print(f"请求失败：{exc}")
        return 1

    print(result.get("answer", ""))
    sources = result.get("sources", [])
    if sources:
        print("\n引用来源：")
        for item in sources:
            print(
                f"- {item.get('chunk_id')} (doc={item.get('document_id')}, score={item.get('score')})"
            )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="奶龙命令行入口：支持直接提问或触发词模式"
    )
    parser.add_argument(
        "message",
        nargs="*",
        help="示例：什么是RAG 或 奶龙 什么是RAG；不填则进入交互模式",
    )
    parser.add_argument("--user-id", default="local-user")
    parser.add_argument("--session-id", default="local-session")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--require-trigger",
        action="store_true",
        help="启用后，必须以“奶龙”开头才触发",
    )
    args = parser.parse_args()

    if args.message:
        return _ask_once(
            message=" ".join(args.message),
            user_id=args.user_id,
            session_id=args.session_id,
            base_url=args.base_url,
            top_k=args.top_k,
            require_trigger=args.require_trigger,
        )

    print("奶龙已就位。输入问题开始对话，输入 exit 或 quit 结束。")
    while True:
        try:
            raw = input("奶龙> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if raw.lower() in {"exit", "quit"}:
            return 0
        if not raw:
            continue
        code = _ask_once(
            message=raw,
            user_id=args.user_id,
            session_id=args.session_id,
            base_url=args.base_url,
            top_k=args.top_k,
            require_trigger=args.require_trigger,
        )
        if code != 0:
            return code


if __name__ == "__main__":
    raise SystemExit(main())
