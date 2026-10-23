"""CLI entry point: `python -m app.worker --once`."""
import argparse

from app.database import SessionLocal
from app.services.extraction_worker import run_next_job


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process one queued extraction job")
    args = parser.parse_args()
    with SessionLocal() as session:
        job = run_next_job(session)
        if job is None:
            print("No queued extraction jobs.")
        else:
            print(f"Job {job.id}: {job.state.value} — {job.message}")


if __name__ == "__main__":
    main()
