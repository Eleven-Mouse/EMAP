from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eleven-agent-platform"))

from services.container import vector_repository  # noqa: E402


def main() -> int:
    vector_repository.warmup()
    print("Embedding model warmed up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

