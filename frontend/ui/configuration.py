"""Widgets responsible for configuring test runs."""
from __future__ import annotations

from typing import Dict, List

import streamlit as st

from ..api import get_device_info, get_test_types, ping_device, run_tests, _norm_nodeid
from ..state import on_change, save_state, viavi_sync_from_widgets

PORT_OPTIONS = ["", "STM-1", "STM-4", "STM-16"]


def _safe_index(options: List[str], value: str, default: int = 0) -> int:
    try:
        return options.index(value)
    except ValueError:
        return default


def render_configuration(api_base: str) -> None:
    st.header("Конфигурация тестирования")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.subheader("Основные настройки")
        device = st.session_state.get("device_info") or {}
        ip = st.text_input(
            "**IP адрес устройства**",
            value=device.get("ipaddr", st.session_state.get("ip_address_input", "")),
            key="ip_address_input",
            on_change=on_change,
        )
        pw = st.text_input("**Пароль (для v7)**", type="password", key="password_input", on_change=on_change)
        snmp = st.selectbox(
            "**Тип SNMP**",
            ["SnmpV2", "SnmpV3"],
            key="snmp_type_select",
            on_change=on_change,
        )
        if st.button("Проверить подключение"):
            if ping_device(api_base, ip):
                get_device_info(api_base, ip, pw, snmp)

    with col2:
        st.subheader("Конфигурация тестов")
        ttypes = get_test_types(api_base)
        test_type = st.radio(
            "**Тип тестов**",
            ["alarm", "sync"],
            format_func=lambda x: "Alarm Tests" if x == "alarm" else "Sync Tests",
            horizontal=True,
            key="test_type_radio",
            on_change=on_change,
        )
        session_labels = st.session_state.get("selected_test_labels") or []
        if test_type == "alarm":
            test_map: Dict[str, str] = ttypes.get("alarm_tests") or {}
            multiselect_key = "tests_ms_alarm"
        else:
            test_map = ttypes.get("sync_tests") or {}
            multiselect_key = "tests_ms_sync"

        available_labels = list(test_map.keys())
        default_labels = [label for label in session_labels if label in available_labels]
        selected_labels = st.multiselect(
            "Выберите тесты:",
            options=available_labels,
            default=default_labels,
            on_change=on_change,
            key=multiselect_key,
        )
        selected_nodeids = [test_map[label] for label in selected_labels]
        st.session_state["selected_test_labels"] = selected_labels
        st.session_state["selected_tests"] = selected_nodeids
        save_state()

    with col3:
        st.subheader("Статус устройства")
        dev = st.session_state.get("device_info")
        if dev:
            st.write(f"**Имя:** {dev.get('name') or '—'}")
            st.write(f"**IP:** {dev.get('ipaddr') or '—'}")
            slots = dev.get("slots_dict") or {}
            if slots:
                with st.expander("Слоты устройства", expanded=True):
                    st.json(slots)
            st.success("✅ Устройство доступно")
        else:
            st.warning("⚠️ Устройство не проверено")

    st.markdown("---")
    st.subheader("Дополнительная кофигурация")
    tab1, tab2, tab3 = st.tabs(["**Viavi №1**", "**Viavi №2**", "**Loopback**"])

    st.session_state.setdefault(
        "viavi_config",
        {
            "NumOne": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
            "NumTwo": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
        },
    )

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.text_input(
                "**IP Viavi №1**",
                value=st.session_state.get("viavi1_ip", ""),
                key="viavi1_ip",
                on_change=viavi_sync_from_widgets,
            )
            d1, d2 = st.columns(2)
            with d1:
                st.selectbox(
                    "Port 1",
                    PORT_OPTIONS,
                    index=_safe_index(PORT_OPTIONS, st.session_state.get("viavi1_port1", "")),
                    key="viavi1_port1",
                    on_change=viavi_sync_from_widgets,
                )
            with d2:
                st.selectbox(
                    "Port 2",
                    PORT_OPTIONS,
                    index=_safe_index(PORT_OPTIONS, st.session_state.get("viavi1_port2", "")),
                    key="viavi1_port2",
                    on_change=viavi_sync_from_widgets,
                )
    with tab2:
        c3, c4 = st.columns(2)
        with c3:
            st.text_input(
                "**IP Viavi №2**",
                value=st.session_state.get("viavi2_ip", ""),
                key="viavi2_ip",
                on_change=viavi_sync_from_widgets,
            )
            d3, d4 = st.columns(2)
            with d3:
                st.selectbox(
                    "Port 1",
                    PORT_OPTIONS,
                    index=_safe_index(PORT_OPTIONS, st.session_state.get("viavi2_port1", "")),
                    key="viavi2_port1",
                    on_change=viavi_sync_from_widgets,
                )
            with d4:
                st.selectbox(
                    "Port 2",
                    PORT_OPTIONS,
                    index=_safe_index(PORT_OPTIONS, st.session_state.get("viavi2_port2", "")),
                    key="viavi2_port2",
                    on_change=viavi_sync_from_widgets,
                )
    with tab3:
        c5, c6 = st.columns(2)
        with c5:
            st.selectbox(
                "**Слот с loopback**",
                [3, 4, 5, 6, 7, 8, 11, 12, 13, 14],
                key="slot_loopback",
                on_change=on_change,
            )
        with c6:
            st.selectbox(
                "**Порт с loopback**",
                [1, 2, 3, 4, 5, 6, 7, 8],
                key="port_loopback",
                on_change=on_change,
            )

    st.markdown("---")
    center = st.columns([1, 1, 1])[1]
    nodeids = [_norm_nodeid(x) for x in (st.session_state.get("selected_tests") or []) if x.strip()]
    with center:
        if st.button("🚀 Запустить тесты"):
            if not nodeids:
                st.warning("Не выбраны тесты.")
            else:
                payload = {
                    "test_type": st.session_state.get("test_type_radio", "manual"),
                    "selected_tests": nodeids,
                }
                resp = run_tests(api_base, payload)
                if resp and resp.get("job_id"):
                    job_id = resp["job_id"]
                    st.session_state["current_job_id"] = job_id
                    st.session_state["test_results"] = None
                    st.success(f"Тесты запущены. job_id = {job_id}")
                else:
                    st.error("Не удалось запустить тесты.")
