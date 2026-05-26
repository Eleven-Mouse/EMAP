from fastapi import APIRouter

from core.config import settings
from schemas.retrieval import RetrieveRequest, RetrieveResponse
from agent_system import AgentSystem

router = APIRouter(tags=["retrieval"])
system = AgentSystem()


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(payload: RetrieveRequest) -> RetrieveResponse:
    top_k = payload.top_k or settings.top_k
    hits = system.retrieve(query=payload.query, top_k=top_k)
    return RetrieveResponse(query=payload.query, hits=hits)

