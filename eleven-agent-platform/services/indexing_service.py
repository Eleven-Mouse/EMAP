from __future__ import annotations

from uuid import uuid4

from core.config import settings
from document_processing.pipeline import Pipeline
from repositories.index_job_repository import StoredIndexJob


class IndexingService:
    def __init__(self) -> None:
        self._pipeline = Pipeline()

    def _get_job_repository(self):
        from services.container import index_job_repository

        return index_job_repository

    def _get_knowledge_repository(self):
        from services.container import knowledge_repository

        return knowledge_repository

    def _get_vector_repository(self):
        from services.container import vector_repository

        return vector_repository

    def submit_document_job(
        self,
        document_id: str,
        content: str | None,
        file_path: str | None,
        source: str,
        chunk_strategy: str,
        chunk_size: int | None,
        chunk_overlap: int | None,
    ) -> StoredIndexJob:
        job = self._get_job_repository().create_job(
            job_id=f"idx-doc-{uuid4().hex[:16]}",
            job_type="document",
            entity_id=document_id,
            action="upsert",
            payload={
                "document_id": document_id,
                "content": content,
                "file_path": file_path,
                "source": source,
                "chunk_strategy": chunk_strategy,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            },
        )
        if settings.index_job_autoprocess:
            return self.process_job(job.job_id)
        return job

    def submit_knowledge_job(
        self,
        memory_id: str,
        action: str,
    ) -> StoredIndexJob:
        job = self._get_job_repository().create_job(
            job_id=f"idx-km-{uuid4().hex[:16]}",
            job_type="knowledge_memory",
            entity_id=memory_id,
            action=action,
            payload={"memory_id": memory_id},
        )
        if settings.index_job_autoprocess:
            return self.process_job(job.job_id)
        return job

    def get_job(self, job_id: str) -> StoredIndexJob | None:
        return self._get_job_repository().get_job(job_id)

    def process_job(self, job_id: str) -> StoredIndexJob:
        job_repository = self._get_job_repository()
        job = job_repository.get_job(job_id)
        if job is None:
            raise KeyError(f"Index job not found: {job_id}")
        if job.status == "ready":
            return job

        job_repository.mark_processing(job_id)
        try:
            if job.job_type == "document":
                self._process_document_job(job)
            elif job.job_type == "knowledge_memory":
                self._process_knowledge_job(job)
            else:
                raise ValueError(f"Unsupported index job type: {job.job_type}")
        except Exception as exc:  # noqa: BLE001
            return job_repository.mark_failed(job_id, str(exc))
        return job_repository.mark_ready(job_id)

    def process_pending_jobs(self, limit: int | None = None) -> list[StoredIndexJob]:
        max_items = limit or settings.index_job_poll_limit
        pending_jobs = self._get_job_repository().list_jobs_by_status(
            statuses=["pending", "failed"],
            limit=max_items,
        )
        return [self.process_job(job.job_id) for job in pending_jobs]

    def _process_document_job(self, job: StoredIndexJob) -> None:
        payload = job.payload
        self._pipeline.ingest(
            document_id=str(payload["document_id"]),
            content=payload.get("content"),
            file_path=payload.get("file_path"),
            source=str(payload.get("source") or "manual"),
            chunk_strategy=str(payload.get("chunk_strategy") or "recursive"),
            chunk_size=payload.get("chunk_size"),
            chunk_overlap=payload.get("chunk_overlap"),
        )

    def _process_knowledge_job(self, job: StoredIndexJob) -> None:
        memory_id = str(job.payload["memory_id"])
        vector_repository = self._get_vector_repository()
        vector_repository.remove_document_chunks([memory_id])

        if job.action == "delete":
            return

        knowledge = self._get_knowledge_repository().get_memory(
            memory_id,
            include_deleted=True,
        )
        if knowledge is None or knowledge.status != "active":
            return
        search_text = knowledge.content.strip()
        if knowledge.title.strip():
            search_text = f"{knowledge.title.strip()}\n{search_text}"
        vector_repository.index_chunks([(memory_id, search_text)])
