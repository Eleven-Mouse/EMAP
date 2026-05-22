from qa.answering import IntelligentQA


class RetrievalService:
    def __init__(self) -> None:
        self._qa = IntelligentQA()

    def retrieve(self, query: str, top_k: int):
        return self._qa.retrieve(query, top_k)
