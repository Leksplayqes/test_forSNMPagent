"""Persistence helpers for test job metadata."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from .config import JOBS_DIR
from .state import TEST_JOBS


def job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def save_job(job_id: str) -> None:
    path = job_path(job_id)
    try:
        with path.open("w", encoding="utf-8") as file:
            json.dump(TEST_JOBS[job_id], file, ensure_ascii=False, indent=2)
    except Exception as exc:  # pragma: no cover - logging only
        print(f"[jobs] save file for {job_id}: {exc}")


def load_jobs_on_startup() -> None:
    for path in JOBS_DIR.glob("*.json"):
        try:
            with path.open("r", encoding="utf-8") as file:
                job = json.load(file)
            job_id = job.get("id") or path.stem
            TEST_JOBS[job_id] = job
        except Exception as exc:  # pragma: no cover - logging only
            print(f"[jobs] load failed {path.name}: {exc}")


__all__ = ["job_path", "save_job", "load_jobs_on_startup"]
