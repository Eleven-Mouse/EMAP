from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.config import settings
from document_processing.document_processor import DocumentProcessor


def _build_splitter(chunk_size: int, overlap: int, chunk_strategy: str):
    strategy = (chunk_strategy or "recursive").strip().lower()
    separators = ["\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", " ", ""]
    if strategy == "markdown":
        separators = ["\n# ", "\n## ", "\n### ", "\n\n", "\n", "。", "！", "？", " ", ""]
    elif strategy == "sentence":
        separators = ["。", "！", "？", ". ", "! ", "? ", "\n", " ", ""]
    elif strategy != "recursive":
        raise ValueError(
            f"Unsupported chunk strategy: {chunk_strategy}. "
            "Use one of: recursive, markdown, sentence."
        )

    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=separators,
    )


def _split_documents(
    file_path: str,
    chunk_size: int,
    overlap: int,
    chunk_strategy: str,
) -> list[tuple[str, dict]]:
    parser = DocumentProcessor()
    documents = parser.parse_file(file_path)
    splitter = _build_splitter(
        chunk_size=chunk_size,
        overlap=overlap,
        chunk_strategy=chunk_strategy,
    )

    chunks: list[tuple[str, dict]] = []
    for document in documents:
        base_metadata = dict(document.metadata or {})
        base_metadata["chunk_strategy"] = chunk_strategy
        for chunk in splitter.split_text(document.page_content):
            chunk = chunk.strip()
            if chunk:
                chunks.append((chunk, base_metadata))
    return chunks


class Pipeline:
    def _get_repositories(self):
        from services.container import metadata_repository, vector_repository

        return metadata_repository, vector_repository

    def ingest(
        self,
        document_id: str,
        content: str | None,
        file_path: str | None,
        source: str,
        chunk_strategy: str = "recursive",
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> int:
        metadata_repository, vector_repository = self._get_repositories()
        size = chunk_size or settings.chunk_size
        overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
        if overlap >= size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if file_path:
            pieces = _split_documents(
                file_path=file_path,
                chunk_size=size,
                overlap=overlap,
                chunk_strategy=chunk_strategy,
            )
        elif content:
            splitter = _build_splitter(
                chunk_size=size,
                overlap=overlap,
                chunk_strategy=chunk_strategy,
            )
            pieces = [
                (chunk.strip(), {"chunk_strategy": chunk_strategy})
                for chunk in splitter.split_text(content)
                if chunk.strip()
            ]
        else:
            raise ValueError("Either content or file_path must be provided")

        old_chunk_ids = [
            chunk.chunk_id for chunk in metadata_repository.list_chunks_by_doc(document_id)
        ]
        if old_chunk_ids:
            vector_repository.remove_document_chunks(old_chunk_ids)

        count = metadata_repository.replace_chunks(
            document_id=document_id, source=source, chunks=pieces
        )
        new_chunks = metadata_repository.list_chunks_by_doc(document_id)
        vector_repository.index_chunks([(c.chunk_id, c.content) for c in new_chunks])
        return count

    def delete_document(self, document_id: str) -> int:
        metadata_repository, vector_repository = self._get_repositories()
        old_chunks = metadata_repository.list_chunks_by_doc(document_id)
        if not old_chunks:
            return 0

        old_chunk_ids = [chunk.chunk_id for chunk in old_chunks]
        deleted = metadata_repository.delete_document(document_id)
        if not deleted:
            return 0

        vector_repository.remove_document_chunks(old_chunk_ids)
        return len(old_chunk_ids)
