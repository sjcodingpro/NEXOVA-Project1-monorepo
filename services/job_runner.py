"""Persistence and locking for the job_runs table (DEV-53).

The 'processing' status is the lock. No FastAPI imports: scripts use this directly.
"""
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "services" / "api" / ".env")
load_dotenv(ROOT / ".env")


@lru_cache(maxsize=1)
def get_engine():
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return create_engine(url, pool_pre_ping=True)


def create_run(job_name: str, target_date: date) -> int:
    """Insert a 'pending' record and return its id."""
    with get_engine().begin() as conn:
        return conn.execute(
            text("INSERT INTO public.job_runs (job_name, target_date, status) "
                 "VALUES (:j, :d, 'pending') RETURNING id"),
            {"j": job_name, "d": target_date},
        ).scalar_one()


def mark_processing(run_id: int) -> bool:
    """pending -> processing. Returns False if another run already holds the lock."""
    try:
        with get_engine().begin() as conn:
            conn.execute(
                text("UPDATE public.job_runs SET status='processing', started_at=NOW() "
                     "WHERE id=:id AND status='pending'"),
                {"id": run_id},
            )
        return True
    except IntegrityError:
        return False   # unique index job_runs_single_processing: lock is taken


def discard_run(run_id: int) -> None:
    """Remove a pending record that lost the lock race (keeps the table clean)."""
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM public.job_runs WHERE id=:id AND status='pending'"),
                     {"id": run_id})


def mark_completed(run_id: int) -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text("UPDATE public.job_runs SET status='completed', finished_at=NOW() WHERE id=:id"),
            {"id": run_id},
        )


def mark_failed(run_id: int, error_message: str) -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text("UPDATE public.job_runs SET status='failed', finished_at=NOW(), "
                 "error_message=:m WHERE id=:id"),
            {"id": run_id, "m": error_message[:2000]},
        )


def has_processing_lock(job_name: str) -> bool:
    with get_engine().connect() as conn:
        return conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM public.job_runs "
                 "WHERE job_name=:j AND status='processing')"),
            {"j": job_name},
        ).scalar_one()


def has_completed_for_date(job_name: str, target_date: date) -> bool:
    with get_engine().connect() as conn:
        return conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM public.job_runs "
                 "WHERE job_name=:j AND target_date=:d AND status='completed')"),
            {"j": job_name, "d": target_date},
        ).scalar_one()
