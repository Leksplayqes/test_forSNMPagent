"""HTTP helper functions and backend integrations for the frontend."""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests
import streamlit as st

from backend import ALARM_TESTS_CATALOG, SYNC_TESTS_CATALOG

from .state import save_state, viavi_sync_from_widgets


def api_post(api_base: str, path: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 30):
    try:
        response = requests.post(f"{api_base}{path}", json=payload or {}, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as http_error:
        body = ""
        try:
            body = response.text[:400]
        except Exception:
            pass
        st.error(f"POST {path}: {http_error} | body: {body}")
        return None
    except Exception as exc:
        st.error(f"POST {path}: {exc}")
        return None


def api_get(api_base: str, path: str, timeout: int = 30):
    try:
        response = requests.get(f"{api_base}{path}", timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"GET {path}: {exc}")
        return None


def _norm_nodeid(node_id: str) -> str:
    return node_id.replace(" ::", "::").replace(":: ", "::").replace(" / ", "/").strip()


def util_jobs(api_base: str):
    return api_get(api_base, "/utils/jobs") or []


def util_status(api_base: str, job_id: str):
    return api_get(api_base, f"/utils/status?job_id={job_id}") or {}


def util_check_conf(api_base: str, ip: str, password: str):
    return api_post(api_base, "/utils/check_conf", {"ip": ip, "password": password})


def util_check_hash(api_base: str, dir1: str, dir2: str):
    return api_post(api_base, "/utils/check_hash", {"dir1": dir1, "dir2": dir2})


def util_fpga_reload(api_base: str, ip: str, password: str, slot: int = 9):
    return api_post(api_base, "/utils/fpga_reload", {"ip": ip, "password": password, "slot": slot})


def ping_device(api_base: str, ip: str) -> bool:
    data = api_post(api_base, "/ping", {"ip_address": ip})
    return bool(data and data.get("success"))


def get_device_info(api_base: str, ip: str, password: str, snmp: str):
    viavi_sync_from_widgets()
    loopback = {
        "slot": st.session_state.get("slot_loopback"),
        "port": st.session_state.get("port_loopback"),
    }
    payload = {
        "ip_address": ip,
        "password": password,
        "snmp_type": snmp,
        "viavi": st.session_state.get("viavi_config", {}),
        "loopback": {k: v for k, v in loopback.items() if v},
    }
    data = api_post(api_base, "/device/info", payload, timeout=500)
    if not data:
        return None

    st.session_state["device_info"] = {
        "name": data.get("name"),
        "ipaddr": data.get("ipaddr"),
        "slots_dict": data.get("slots_dict") or {},
    }
    st.session_state["viavi_config"] = data.get("viavi") or st.session_state["viavi_config"]
    st.session_state["saved_loopback"] = data.get("loopback") or {}
    save_state()
    return st.session_state["device_info"]


def _catalog_fallback() -> Dict[str, Dict[str, str]]:
    return {
        "alarm_tests": ALARM_TESTS_CATALOG,
        "sync_tests": SYNC_TESTS_CATALOG,
    }


def get_test_types(api_base: str, cache_ttl: int = 30):
    cache = st.session_state.get("_test_types_cache")
    now = time.time()
    if cache and now - cache.get("ts", 0) < cache_ttl:
        return cache["data"]

    data = api_get(api_base, "/tests/types") or _catalog_fallback()
    st.session_state["_test_types_cache"] = {"ts": now, "data": data}
    return data


def run_tests(api_base: str, cfg: Dict[str, Any]):
    return api_post(api_base, "/tests/run", cfg, timeout=120)


def stop_test_job(api_base: str, job_id: str):
    try:
        response = requests.post(f"{api_base}/tests/stop?job_id={job_id}", timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("success"):
            st.success(f"Тест {job_id} остановлен.")
        else:
            st.warning(f"Не удалось остановить тест: {data.get('error')}")
    except Exception as exc:
        st.error(f"Ошибка остановки теста: {exc}")


__all__ = [
    "api_get",
    "api_post",
    "get_device_info",
    "get_test_types",
    "ping_device",
    "run_tests",
    "stop_test_job",
    "util_check_conf",
    "util_check_hash",
    "util_fpga_reload",
    "util_jobs",
    "util_status",
    "viavi_sync_from_widgets",
    "_norm_nodeid",
]
