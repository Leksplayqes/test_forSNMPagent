"""Utility endpoints that wrap helper scripts from checkFunctions."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from checkFunctions.check_KSequal import fpga_reload
from checkFunctions.check_conf import check_conf
from checkFunctions.check_hash import compare_directories_by_hash

from .state import UTIL_JOBS

router = APIRouter(prefix="/utils")


@router.get("/jobs")
def util_jobs():
    items = [
        {
            "id": job["id"],
            "type": job.get("type"),
            "status": job.get("status"),
            "started": job.get("started"),
            "finished": job.get("finished"),
        }
        for job in UTIL_JOBS.values()
    ]
    items.sort(key=lambda x: x["started"], reverse=True)
    return items


@router.get("/status")
def util_status(job_id: str):
    job = UTIL_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="util job not found")
    return job


@router.post("/check_conf")
def util_check_conf(req: Dict[str, Any]):
    ip = (req or {}).get("ip") or ""
    password = (req or {}).get("password") or ""
    iterations = int((req or {}).get("iterations", 3))
    delay = int((req or {}).get("delay", 30))
    if not ip:
        raise HTTPException(status_code=400, detail="ip is required")
    try:
        result = check_conf(ip=ip, password=password, iterations=iterations, delay_between=delay)
        return {"success": True, "result": result}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.post("/check_hash")
def util_check_hash(req: Dict[str, Any]):
    dir1 = (req or {}).get("dir1")
    dir2 = (req or {}).get("dir2")
    if not dir1 or not dir2:
        raise HTTPException(status_code=400, detail="dir1 and dir2 are required")
    try:
        result = compare_directories_by_hash(dir1, dir2)
        return {"success": True, "result": result}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.post("/fpga_reload")
def util_fpga_reload(req: Dict[str, Any]):
    ip = (req or {}).get("ip") or ""
    password = (req or {}).get("password") or ""
    slot = int((req or {}).get("slot", 9))
    max_attempts = int((req or {}).get("max_attempts", 1000))
    if not ip:
        raise HTTPException(status_code=400, detail="ip is required")
    try:
        result = fpga_reload(ip=ip, password=password, slot=slot, max_attempts=max_attempts)
        return {"success": True, "result": result}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


__all__ = ["router"]
