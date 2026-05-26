from fastapi import APIRouter

from schemas.chat import ChatRequest, ChatResponse
from rag_system import RAGSystem

router = APIRouter(tags=["chat"])
system = RAGSystem()


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    answer, sources = system.ask(
        user_id=payload.user_id,
        session_id=payload.session_id,
        query=payload.query,
        top_k=payload.top_k,
    )
    return ChatResponse(answer=answer, sources=sources)
