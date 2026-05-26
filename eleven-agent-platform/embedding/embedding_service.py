class EmbeddingService:
    def __init__(self) -> None:
        self._vector_repository = None

    def _get_vector_repository(self):
        if self._vector_repository is None:
            from services.container import vector_repository

            self._vector_repository = vector_repository
        return self._vector_repository

    def warmup(self) -> None:
        self._get_vector_repository().warmup()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embedder = self._get_vector_repository()._get_embedder()
        return embedder.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        embedder = self._get_vector_repository()._get_embedder()
        return embedder.embed_query(text)
