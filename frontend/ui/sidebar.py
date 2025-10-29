"""Sidebar widgets for quick actions and exports."""
from __future__ import annotations

import streamlit as st

from ..api import api_get


def sidebar_ui() -> None:
    st.markdown("")
    st.subheader("Быстрые действия")

    api_base = st.session_state.get("api_base_url")
    jobs = api_get(api_base, "/tests/jobs") or []
    if not jobs:
        st.info("Пока нет сохранённых тестов.")
        st.button("📊 Экспорт результатов", disabled=True, use_container_width=True)
        st.button("🧾 Экспорт JUnit XML", disabled=True, use_container_width=True)
    else:
        job_ids = [job["id"] for job in jobs]
        default = st.session_state.get("current_job_id") or job_ids[0]
        if default not in job_ids:
            default = job_ids[0]
        selected = st.selectbox(
            "Выберите тест (job_id) для экспорта:",
            job_ids,
            index=job_ids.index(default),
            key="export_job_id",
        )
        job_url = f"{api_base}/tests/jobfile?job_id={selected}"
        st.markdown(
            f'<a href="{job_url}" download>'
            f'<button class="st-emotion-cache-1vt4y43 ef3psqc12" style="width:100%;">📊 Экспорт результатов (JSON)</button>'
            f'</a>',
            unsafe_allow_html=True,
        )
        xml_url = f"{api_base}/tests/report?job_id={selected}"
        st.markdown(
            f'<a href="{xml_url}" download>'
            f'<button class="st-emotion-cache-1vt4y43 ef3psqc12" style="width:100%;">🧾 Экспорт JUnit XML</button>'
            f'</a>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.subheader("Инструкция:")
    st.markdown(
        "\n".join(
            [
                "1. Настройте устройство во вкладке конфигурации",
                "2. Запустите тесты",
                "3. Просмотрите результаты",
                "4. Экспортируйте JSON/JUnit при необходимости",
            ]
        )
    )
