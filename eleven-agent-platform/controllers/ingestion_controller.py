from fastapi import APIRouter

from schemas.ingestion import DeleteDocumentResponse, IngestRequest, IngestResponse
from agent_system import AgentSystem

router = APIRouter(tags=["ingestion"])
system = AgentSystem()


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


@router.delete("/ingest/{document_id}", response_model=DeleteDocumentResponse)
def delete_document(document_id: str) -> DeleteDocumentResponse:
    deleted_chunk_count = system.delete_document(document_id=document_id)
    status = "ok" if deleted_chunk_count > 0 else "not_found"
    return DeleteDocumentResponse(
        document_id=document_id,
        deleted_chunk_count=deleted_chunk_count,
        status=status,
    )

