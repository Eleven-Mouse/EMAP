from document_processing.pipeline import Pipeline


class IngestionService:
    def __init__(self) -> None:
        self._pipeline = Pipeline()

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
        return self._pipeline.ingest(
            document_id=document_id,
            content=content,
            file_path=file_path,
            source=source,
            chunk_strategy=chunk_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def delete_document(self, document_id: str) -> int:
        return self._pipeline.delete_document(document_id)
