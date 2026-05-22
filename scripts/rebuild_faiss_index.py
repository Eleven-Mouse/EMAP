from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eleven-rag"))

from services.container import metadata_repository, vector_repository  # noqa: E402


def main() -> int:
    chunks = metadata_repository.list_chunks()
    if not chunks:
        print("No chunks to rebuild.")
        return 0

    vector_repository._index = None  # noqa: SLF001
    vector_repository._chunk_id_to_faiss_id.clear()  # noqa: SLF001
    vector_repository._next_faiss_id = 1  # noqa: SLF001
    vector_repository._persist()  # noqa: SLF001
    vector_repository.index_chunks([(c.chunk_id, c.content) for c in chunks])
    print(f"Rebuilt FAISS index for {len(chunks)} chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
