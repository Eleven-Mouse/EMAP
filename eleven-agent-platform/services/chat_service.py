from core.config import settings
from qa.answering import IntelligentQA


class ChatService:
    def __init__(self) -> None:
        self._qa = IntelligentQA()

    def ask(
        self,
        user_id: str,
        session_id: str,
        query: str,
        top_k: int | None,
        doc_id_prefixes: list[str] | None = None,
    ):
        k = top_k or settings.top_k
        return self._qa.ask(
            user_id=user_id,
            session_id=session_id,
            query=query,
            top_k=k,
            doc_id_prefixes=doc_id_prefixes,
        )
