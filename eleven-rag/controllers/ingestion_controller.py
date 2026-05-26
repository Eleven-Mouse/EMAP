from fastapi import APIRouter

from schemas.ingestion import IngestRequest, IngestResponse
from rag_system import RAGSystem

router = APIRouter(tags=["ingestion"])
system = RAGSystem()


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
