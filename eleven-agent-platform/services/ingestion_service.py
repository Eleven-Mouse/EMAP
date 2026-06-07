from document_processing.pipeline import Pipeline


class IngestionService:
    def __init__(self) -> None:
        self._pipeline = Pipeline()
        self._indexing_service = None

    def _get_indexing_service(self):
        if self._indexing_service is None:
            from services.indexing_service import IndexingService

            self._indexing_service = IndexingService()
        return self._indexing_service

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

    def submit_ingest_job(
        self,
        document_id: str,
        content: str | None,
        file_path: str | None,
        source: str,
        chunk_strategy: str = "recursive",
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        return self._get_indexing_service().submit_document_job(
            document_id=document_id,
            content=content,
            file_path=file_path,
            source=source,
            chunk_strategy=chunk_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def get_ingest_job(self, job_id: str):
        return self._get_indexing_service().get_job(job_id)
