"""Widgets exposing auxiliary backend utilities."""
from __future__ import annotations

import streamlit as st

from api import util_check_conf, util_check_hash, util_fpga_reload


def render_utils(api_base: str) -> None:
    st.header("Утилиты (из checkFunctions)")

    with st.expander("📄 Проверка конфигурации (check_conf)", expanded=True):
        ip = st.text_input(
            "IP устройства (для check_conf)",
            key="util_cc_ip",
            value=(st.session_state.get("device_info") or {}).get("ipaddr", ""),
        )
        pw = st.text_input(
            "Пароль (для check_conf)",
            type="password",
            key="util_cc_pw",
            value=st.session_state.get("password_input", ""),
        )
        if st.button("Запустить check_conf"):
            res = util_check_conf(api_base, ip, pw)
            if res and res.get("success"):
                st.success("Готово")
                st.json(res.get("result"))
            else:
                st.error(res.get("error") if res else "Ошибка запроса")

    with st.expander("🧮 Сравнение директорий по MD5 (check_hash)"):
        d1 = st.text_input("Директория A (на сервере)", key="util_h_a")
        d2 = st.text_input("Директория B (на сервере)", key="util_h_b")
        if st.button("Сравнить"):
            if not d1 or not d2:
                st.warning("Укажите обе директории")
            else:
                res = util_check_hash(api_base, d1, d2)
                if res and res.get("success"):
                    st.success("OK")
                    st.json(res.get("result"))
                else:
                    st.error(res.get("error") if res else "Ошибка запроса")

    with st.expander("🔁 FPGA reload (check_KSequal.fpga_reload)"):
        ip2 = st.text_input(
            "IP устройства (для fpga_reload)",
            key="util_fpga_ip",
            value=(st.session_state.get("device_info") or {}).get("ipaddr", ""),
        )
        pw2 = st.text_input(
            "Пароль (для fpga_reload)",
            type="password",
            key="util_fpga_pw",
            value=st.session_state.get("password_input", ""),
        )
        slot = st.number_input("Слот", min_value=1, max_value=16, value=9, step=1, key="util_fpga_slot")
        if st.button("Запустить fpga_reload"):
            res = util_fpga_reload(api_base, ip2, pw2, int(slot))
            if res and res.get("success"):
                st.success("Готово")
                st.json(res.get("result"))
            else:
                st.error(res.get("error") if res else "Ошибка запроса")
