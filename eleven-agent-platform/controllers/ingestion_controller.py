from fastapi import APIRouter, HTTPException

from agent_system import AgentSystem
from schemas.indexing import IndexJobItem, IngestJobRequest
from schemas.ingestion import IngestRequest, IngestResponse
from services.ingestion_service import IngestionService

router = APIRouter(tags=["ingestion"])
system = AgentSystem()
ingestion_service = IngestionService()


@router.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest) -> IngestResponse:
    chunk_count = system.ingest(
        document_id=payload.document_id,
        content=payload.content,
        file_path=payload.file_path,
        source=payload.source,
        chunk_strategy=payload.chunk_strategy,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
    )
    return IngestResponse(document_id=payload.document_id, chunk_count=chunk_count)


@router.post("/ingest/jobs", response_model=IndexJobItem, status_code=202)
def create_ingest_job(payload: IngestJobRequest) -> IndexJobItem:
    return ingestion_service.submit_ingest_job(
        document_id=payload.document_id,
        content=payload.content,
        file_path=payload.file_path,
        source=payload.source,
        chunk_strategy=payload.chunk_strategy,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
    )


@router.get("/ingest/jobs/{job_id}", response_model=IndexJobItem)
def get_ingest_job(job_id: str) -> IndexJobItem:
    job = ingestion_service.get_ingest_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Index job not found: {job_id}")
    return job
