from document_processing.document_processor import DocumentProcessor


class DocumentParserService:
    def __init__(self) -> None:
        self._processor = DocumentProcessor()

    def parse_from_text(self, content: str) -> str:
        return self._processor.parse_text(content)

    def parse_from_file(self, file_path: str) -> str:
        return self._processor.parse_file_to_text(file_path)

    def load_documents_from_file(self, file_path: str):
        return self._processor.parse_file(file_path)
