class QdrantVectorStore:
    def __init__(self) -> None:
        self._vector_repository = None

    def _get_vector_repository(self):
        if self._vector_repository is None:
            from services.container import vector_repository

            self._vector_repository = vector_repository
        return self._vector_repository

    def add_texts(self, items: list[tuple[str, str]]) -> None:
        self._get_vector_repository().index_chunks(items)

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        self._get_vector_repository().remove_document_chunks(chunk_ids)

    def search(self, query: str, top_k: int):
        return self._get_vector_repository().query(query, top_k)
