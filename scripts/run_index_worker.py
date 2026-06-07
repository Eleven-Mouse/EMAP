from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / "eleven-agent-platform") not in sys.path:
    sys.path.insert(0, str(ROOT / "eleven-agent-platform"))

from services.indexing_service import IndexingService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Process pending indexing jobs")
    parser.add_argument("--limit", type=int, default=20, help="Maximum jobs to process")
    args = parser.parse_args()

    service = IndexingService()
    jobs = service.process_pending_jobs(limit=max(1, args.limit))
    for job in jobs:
        print(f"{job.job_id} {job.job_type} {job.action} -> {job.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
