from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repositories.index_job_repository import StoredIndexJob
from services.indexing_service import IndexingService


class FakeIndexJobRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, StoredIndexJob] = {}

    def create_job(self, job_id: str, job_type: str, entity_id: str, action: str, payload: dict):
        job = StoredIndexJob(
            job_id=job_id,
            job_type=job_type,
            entity_id=entity_id,
            action=action,
            status="pending",
            payload=dict(payload),
            attempts=0,
        )
        self.jobs[job_id] = job
        return job

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def list_jobs_by_status(self, statuses: list[str], limit: int):
        return [
            job for job in self.jobs.values() if job.status in statuses
        ][:limit]

    def mark_processing(self, job_id: str):
        job = self.jobs[job_id]
        job.status = "processing"
        job.attempts += 1
        return job

    def mark_ready(self, job_id: str):
        job = self.jobs[job_id]
        job.status = "ready"
        job.error_message = None
        return job

    def mark_failed(self, job_id: str, error_message: str):
        job = self.jobs[job_id]
        job.status = "failed"
        job.error_message = error_message
        return job


class FakePipeline:
    def __init__(self) -> None:
        self.calls = []

    def ingest(self, **kwargs):
        self.calls.append(dict(kwargs))
        return 1


class FakeVectorRepository:
    def __init__(self) -> None:
        self.removed: list[list[str]] = []
        self.indexed: list[list[tuple[str, str]]] = []

    def remove_document_chunks(self, chunk_ids: list[str]) -> None:
        self.removed.append(list(chunk_ids))

    def index_chunks(self, items: list[tuple[str, str]]) -> None:
        self.indexed.append(list(items))


class FakeKnowledgeMemory:
    def __init__(self, memory_id: str, status: str = "active") -> None:
        self.memory_id = memory_id
        self.status = status
        self.title = "检索约定"
        self.content = "知识记忆需要进入统一索引链路。"


class FakeKnowledgeRepository:
    def __init__(self) -> None:
        self.memories = {"km-1": FakeKnowledgeMemory("km-1")}

    def get_memory(self, memory_id: str, include_deleted: bool = True):
        return self.memories.get(memory_id)


def test_indexing_service_processes_document_and_knowledge_jobs(monkeypatch):
    service = IndexingService()
    job_repository = FakeIndexJobRepository()
    pipeline = FakePipeline()
    vector_repository = FakeVectorRepository()
    knowledge_repository = FakeKnowledgeRepository()

    service._pipeline = pipeline
    monkeypatch.setattr(service, "_get_job_repository", lambda: job_repository)
    monkeypatch.setattr(service, "_get_vector_repository", lambda: vector_repository)
    monkeypatch.setattr(service, "_get_knowledge_repository", lambda: knowledge_repository)
    monkeypatch.setattr("services.indexing_service.settings.index_job_autoprocess", False)

    document_job = service.submit_document_job(
        document_id="doc-1",
        content="hello world",
        file_path=None,
        source="manual",
        chunk_strategy="recursive",
        chunk_size=200,
        chunk_overlap=20,
    )
    knowledge_job = service.submit_knowledge_job(memory_id="km-1", action="upsert")
    assert job_repository.get_job(document_job.job_id).status == "pending"
    assert job_repository.get_job(knowledge_job.job_id).status == "pending"

    results = service.process_pending_jobs(limit=5)

    assert len(results) == 2
    assert all(job.status == "ready" for job in results)
    assert pipeline.calls[0]["document_id"] == "doc-1"
    assert vector_repository.removed[-1] == ["km-1"]
    assert vector_repository.indexed[-1][0][0] == "km-1"


def test_indexing_service_marks_failed_job(monkeypatch):
    service = IndexingService()
    job_repository = FakeIndexJobRepository()
    service._pipeline = FakePipeline()
    monkeypatch.setattr(service, "_get_job_repository", lambda: job_repository)
    monkeypatch.setattr(service, "_get_vector_repository", lambda: FakeVectorRepository())
    monkeypatch.setattr(service, "_get_knowledge_repository", lambda: FakeKnowledgeRepository())
    monkeypatch.setattr("services.indexing_service.settings.index_job_autoprocess", False)

    broken_job = job_repository.create_job(
        job_id="idx-broken",
        job_type="unknown",
        entity_id="bad",
        action="upsert",
        payload={},
    )
    result = service.process_job(broken_job.job_id)

    assert result.status == "failed"
    assert "Unsupported index job type" in (result.error_message or "")
