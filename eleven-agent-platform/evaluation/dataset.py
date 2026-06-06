import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvalSample:
    sample_id: str
    query: str
    reference_answer: str | None = None
    reference_contexts: list[str] | None = None
    expected_chunk_ids: list[str] | None = None
    expected_refusal: bool | None = None
    required_citations: bool | None = None
    forbidden_chunk_ids: list[str] | None = None
    allowed_doc_prefixes: list[str] | None = None


def _to_list_of_str(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _parse_row(row: dict, row_index: int) -> EvalSample:
    sample_id = str(row.get("id") or row.get("sample_id") or f"sample-{row_index + 1}").strip()
    query = str(row.get("query") or row.get("question") or row.get("user_input") or "").strip()
    if not query:
        raise ValueError(f"row[{row_index}] missing query/question/user_input")

    reference_answer = row.get("reference_answer")
    if reference_answer is None:
        reference_answer = row.get("answer")
    if reference_answer is None:
        reference_answer = row.get("ground_truth")
    if reference_answer is not None:
        reference_answer = str(reference_answer).strip() or None

    reference_contexts = _to_list_of_str(
        row.get("reference_contexts")
        or row.get("ground_truth_contexts")
        or row.get("reference")
        or row.get("contexts")
    )
    expected_chunk_ids = _to_list_of_str(
        row.get("expected_chunk_ids")
        or row.get("relevant_chunk_ids")
        or row.get("chunk_ids")
    )
    expected_refusal = row.get("expected_refusal")
    if expected_refusal is not None:
        expected_refusal = bool(expected_refusal)

    required_citations = row.get("required_citations")
    if required_citations is not None:
        required_citations = bool(required_citations)

    forbidden_chunk_ids = _to_list_of_str(
        row.get("forbidden_chunk_ids")
        or row.get("blocked_chunk_ids")
    )
    allowed_doc_prefixes = _to_list_of_str(
        row.get("allowed_doc_prefixes")
        or row.get("doc_prefixes")
    )

    return EvalSample(
        sample_id=sample_id,
        query=query,
        reference_answer=reference_answer,
        reference_contexts=reference_contexts,
        expected_chunk_ids=expected_chunk_ids,
        expected_refusal=expected_refusal,
        required_citations=required_citations,
        forbidden_chunk_ids=forbidden_chunk_ids,
        allowed_doc_prefixes=allowed_doc_prefixes,
    )


def load_eval_samples(dataset_path: str) -> list[EvalSample]:
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"dataset not found: {path}")

    if path.suffix.lower() == ".jsonl":
        rows = []
        with path.open("r", encoding="utf-8-sig") as handle:
            for line_no, line in enumerate(handle, start=1):
                payload = line.strip()
                if not payload:
                    continue
                try:
                    rows.append(json.loads(payload))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid jsonl at line {line_no}: {exc}") from exc
    elif path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8-sig") as handle:
            parsed = json.load(handle)
        if isinstance(parsed, dict):
            rows = parsed.get("samples") or parsed.get("data") or []
        else:
            rows = parsed
    else:
        raise ValueError("unsupported dataset format, use .json or .jsonl")

    if not isinstance(rows, list):
        raise ValueError("dataset content must be a list")

    samples = [_parse_row(row=row, row_index=index) for index, row in enumerate(rows)]
    if not samples:
        raise ValueError("dataset is empty")
    return samples
