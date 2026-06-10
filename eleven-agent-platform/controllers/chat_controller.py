from fastapi import APIRouter, Request

from agent_system import AgentSystem
from schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])
system = AgentSystem()


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    trace_id = request.headers.get("x-request-id") or getattr(request.state, "trace_id", None)
    answer, sources = system.ask(
        user_id=payload.user_id,
        session_id=payload.session_id,
        query=payload.query,
        top_k=payload.top_k,
        doc_id_prefixes=payload.doc_id_prefixes,
        trace_id=trace_id,
    )
    return ChatResponse(answer=answer, sources=sources)
