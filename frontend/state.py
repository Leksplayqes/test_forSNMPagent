"""State management helpers for the Streamlit frontend."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import streamlit as st

from constants import DEFAULT_API_BASE_URL, STATE_FILE


def initialize_session_state() -> None:
    """Populate frequently used keys in :mod:`streamlit.session_state`."""
    st.session_state.setdefault("test_results", None)
    st.session_state.setdefault("test_history", [])
    st.session_state.setdefault("api_base_url", DEFAULT_API_BASE_URL)
    st.session_state.setdefault("device_info", None)
    st.session_state.setdefault("ip_address_input", "")
    st.session_state.setdefault("password_input", "")
    st.session_state.setdefault("snmp_type_select", "SnmpV2")
    st.session_state.setdefault("test_type_radio", "alarm")
    st.session_state.setdefault("selected_tests", [])
    st.session_state.setdefault("selected_test_labels", [])
    st.session_state.setdefault("current_job_id", None)
    st.session_state.setdefault("viavi_config", {
        "NumOne": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
        "NumTwo": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
    })


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state() -> None:
    state = {
        "api_base_url": st.session_state.get("api_base_url", DEFAULT_API_BASE_URL),
        "device_info": st.session_state.get("device_info"),
        "ip_address_input": st.session_state.get("ip_address_input", ""),
        "password_input": st.session_state.get("password_input", ""),
        "snmp_type_select": st.session_state.get("snmp_type_select", "SnmpV2"),
        "test_type_radio": st.session_state.get("test_type_radio", "alarm"),
        "viavi_config": st.session_state.get("viavi_config", {
            "NumOne": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
            "NumTwo": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
        }),
        "slot_loopback": st.session_state.get("slot_loopback"),
        "port_loopback": st.session_state.get("port_loopback"),
        "selected_tests": st.session_state.get("selected_tests"),
        "selected_test_labels": st.session_state.get("selected_test_labels"),
        "test_results": st.session_state.get("test_results"),
        "test_history": st.session_state.get("test_history", []),
        "current_job_id": st.session_state.get("current_job_id"),
    }
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def apply_state() -> None:
    saved = load_state()
    if not saved:
        return

    if "device_info" in saved and "device_info" not in st.session_state:
        st.session_state["device_info"] = saved["device_info"]

    for key in [
        "api_base_url",
        "ip_address_input",
        "password_input",
        "snmp_type_select",
        "test_type_radio",
        "viavi_config",
        "slot_loopback",
        "port_loopback",
        "test_results",
        "test_history",
        "current_job_id",
        "selected_tests",
        "selected_test_labels",
    ]:
        if key in saved and key not in st.session_state:
            st.session_state[key] = saved[key]

    viavi = st.session_state.get("viavi_config", {
        "NumOne": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
        "NumTwo": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
    })
    st.session_state.setdefault("viavi1_ip", viavi["NumOne"]["ipaddr"])
    st.session_state.setdefault("viavi1_port1", viavi["NumOne"]["typeofport"]["Port1"])
    st.session_state.setdefault("viavi1_port2", viavi["NumOne"]["typeofport"]["Port2"])
    st.session_state.setdefault("viavi2_ip", viavi["NumTwo"]["ipaddr"])
    st.session_state.setdefault("viavi2_port1", viavi["NumTwo"]["typeofport"]["Port1"])
    st.session_state.setdefault("viavi2_port2", viavi["NumTwo"]["typeofport"]["Port2"])


def on_change() -> None:
    save_state()


def _commit_test_result(job: Optional[Dict[str, Any]], save_history: bool = True) -> None:
    if not job:
        return
    st.session_state["test_results"] = job
    summary = job.get("summary") or {}
    status = (summary.get("status") or "").lower()
    finished = status in {"passed", "failed", "error", "stopped"}
    if save_history and finished:
        jid = job.get("id")
        history = st.session_state.get("test_history") or []
        if not any(x.get("id") == jid for x in history):
            history.append(job)
            st.session_state["test_history"] = history


def viavi_sync_from_widgets() -> None:
    viavi = st.session_state.setdefault("viavi_config", {
        "NumOne": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
        "NumTwo": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
    })
    viavi["NumOne"]["ipaddr"] = st.session_state.get("viavi1_ip", "")
    viavi["NumOne"]["typeofport"]["Port1"] = st.session_state.get("viavi1_port1", "")
    viavi["NumOne"]["typeofport"]["Port2"] = st.session_state.get("viavi1_port2", "")
    viavi["NumTwo"]["ipaddr"] = st.session_state.get("viavi2_ip", "")
    viavi["NumTwo"]["typeofport"]["Port1"] = st.session_state.get("viavi2_port1", "")
    viavi["NumTwo"]["typeofport"]["Port2"] = st.session_state.get("viavi2_port2", "")
    save_state()
