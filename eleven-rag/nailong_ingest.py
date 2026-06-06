import argparse
import json
import urllib.error
import urllib.request


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="奶龙知识导入：把本地 .md/.txt/.pdf 文件导入 RAG"
    )
    parser.add_argument("file", help="本地文件路径（.md / .txt / .pdf）")
    parser.add_argument(
        "--document-id",
        default=None,
        help="文档ID；不传则默认使用文件名",
    )
    parser.add_argument("--source", default="local-file")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    import pathlib
    file_path = pathlib.Path(args.file).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        print(f"文件不存在：{file_path}")
        return 1

    if file_path.suffix.lower() not in {".md", ".txt", ".pdf"}:
        print("仅支持 .md / .txt / .pdf 文件")
        return 1

    parser_service = DocumentParserService()
    document_id = args.document_id or file_path.stem
    payload = {
        "document_id": document_id,
        "file_path": str(file_path),
        "source": args.source,
    }

    try:
        result = _post_json(f"{args.base_url}/v1/ingest", payload)
    except urllib.error.URLError as exc:
        print(f"请求失败：{exc}")
        return 1

    print("导入成功")
    print(f"- document_id: {result.get('document_id')}")
    print(f"- chunk_count: {result.get('chunk_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
