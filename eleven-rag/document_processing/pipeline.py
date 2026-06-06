from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.config import settings
from document_processing.document_processor import DocumentProcessor


def _split_documents(file_path: str, chunk_size: int, overlap: int) -> list[tuple[str, dict]]:
    parser = DocumentProcessor()
    documents = parser.parse_file(file_path)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", "。", "！", "？", " ", ""],
    )

    chunks: list[tuple[str, dict]] = []
    for document in documents:
        base_metadata = dict(document.metadata or {})
        for chunk in splitter.split_text(document.page_content):
            chunk = chunk.strip()
            if chunk:
                chunks.append((chunk, base_metadata))
    return chunks


class Pipeline:
    def _get_repositories(self):
        from services.container import metadata_repository, vector_repository

        return metadata_repository, vector_repository

    def ingest(self, document_id: str, content: str | None, file_path: str | None, source: str) -> int:
        metadata_repository, vector_repository = self._get_repositories()
        if file_path:
            pieces = _split_documents(file_path, settings.chunk_size, settings.chunk_overlap)
        elif content:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                separators=["\n\n", "\n", "。", "！", "？", " ", ""],
            )
            pieces = [(chunk.strip(), {}) for chunk in splitter.split_text(content) if chunk.strip()]
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
