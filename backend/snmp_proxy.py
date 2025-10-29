"""Helpers to manage the SNMP-over-SSH proxy process."""
from __future__ import annotations

import threading

from snmpsubsystem import ProxyController

SNMP_PROXY = ProxyController()
SNMP_PROXY_LOCK = threading.Lock()
_TUNNEL_LOCK = threading.RLock()
_ACTIVE_TUNNEL_JOBS: set[str] = set()


def tunnel_alive() -> bool:
    return bool(SNMP_PROXY.proxy and SNMP_PROXY.proxy._proc_alive())


def ensure_tunnel(ip: str, username: str, password: str) -> None:
    with _TUNNEL_LOCK:
        if not tunnel_alive():
            SNMP_PROXY.start(ip=ip, username=username, password=password)


def register_tunnel_user(job_id: str) -> None:
    with _TUNNEL_LOCK:
        _ACTIVE_TUNNEL_JOBS.add(job_id)


def release_tunnel_user(job_id: str) -> None:
    with _TUNNEL_LOCK:
        _ACTIVE_TUNNEL_JOBS.discard(job_id)
        if not _ACTIVE_TUNNEL_JOBS:
            try:
                SNMP_PROXY.close()
            except Exception:  # pragma: no cover - defensive
                pass


__all__ = [
    "SNMP_PROXY",
    "SNMP_PROXY_LOCK",
    "tunnel_alive",
    "ensure_tunnel",
    "register_tunnel_user",
    "release_tunnel_user",
]
