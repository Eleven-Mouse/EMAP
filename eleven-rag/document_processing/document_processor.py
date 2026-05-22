import pathlib

from langchain_core.documents import Document


class DocumentProcessor:
    _SUPPORTED_SUFFIXES = {".md", ".pdf", ".txt"}

    def parse_text(self, content: str) -> str:
        return content.strip()

    def parse_file(self, file_path: str):
        path = pathlib.Path(file_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        suffix = path.suffix.lower()
        if suffix not in self._SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported file type: {suffix}")

        return self._load_documents(path)

    def parse_file_to_text(self, file_path: str) -> str:
        documents = self.parse_file(file_path)
        parts: list[str] = []
        for document in documents:
            text = (getattr(document, "page_content", "") or "").strip()
            if text:
                parts.append(text)
        return "\n\n".join(parts).strip()

    def _load_documents(self, path: pathlib.Path) -> list[Document]:
        try:
            from langchain_unstructured import UnstructuredLoader
        except ImportError as exc:
            raise RuntimeError(
                "langchain-unstructured is required for document parsing. "
                "Run `uv sync` to install project dependencies."
            ) from exc

        loader = UnstructuredLoader(
            file_path=str(path),
            partition_via_api=False,
            strategy="fast",
        )
        try:
            return loader.load()
        except ImportError as exc:
            raise RuntimeError(
                f"Failed to load {path.name} with Unstructured. "
                "Install the unstructured extras for the target file type and run "
                "`uv sync` again."
            ) from exc
