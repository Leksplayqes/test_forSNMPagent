"""Miscellaneous small endpoints shared across the app."""
from __future__ import annotations

import subprocess
from typing import Any, Dict

from fastapi import APIRouter

from .config import CONFIG_FILE
from .logs import add_log

router = APIRouter()


@router.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True, "config_path": str(CONFIG_FILE)}


@router.get("/")
async def root() -> Dict[str, Any]:
    return {"message": "OSM-K Tester API", "version": "4.5.0"}


@router.post("/ping")
async def ping(req: Dict[str, Any]):
    ip = req.get("ip_address", "")
    add_log(f"Ping {ip}")
    try:
        cmd = ["ping", "-n", "2", ip]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
        except Exception:
            res = subprocess.run(["ping", "-c", "2", ip], capture_output=True, text=True)
        return {"success": res.returncode == 0, "output": res.stdout, "error": res.stderr}
    except Exception as exc:
        add_log(f"Ping error: {exc}", "ERROR")
        return {"success": False, "error": str(exc)}


__all__ = ["router"]
