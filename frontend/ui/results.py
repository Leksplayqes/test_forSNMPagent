"""Widgets showing test run progress and results."""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from ..api import api_get, stop_test_job
from ..state import _commit_test_result


def render_results(api_base_url: str) -> None:
    st.header("Результаты тестирования")

    jobs = api_get(api_base_url, "/tests/jobs", timeout=20) or []
    if not jobs:
        st.info("Пока нет ни одного прогона.")
        return

    job_ids = [job["id"] for job in jobs]
    default_id = st.session_state.get("current_job_id") or job_ids[0]
    if default_id not in job_ids:
        default_id = job_ids[0]

    st.write("Выберите прогон (job_id):")
    col1, col2 = st.columns([4, 1], gap="small")
    with col1:
        selected_job = st.selectbox(
            "null",
            options=job_ids,
            index=job_ids.index(default_id),
            label_visibility="collapsed",
        )
        st.session_state["current_job_id"] = selected_job
    with col2:
        if st.button("🛑 Остановить тест", type="secondary", use_container_width=True):
            stop_test_job(api_base_url, selected_job)

    status_box = st.empty()
    table_box = st.empty()
    progress_box = st.empty()

    for _ in range(900):  # до 30 минут
        job = api_get(api_base_url, f"/tests/status?job_id={selected_job}", timeout=20) or {}
        _commit_test_result(job, save_history=True)

        summary = job.get("summary", {})
        cases = job.get("cases", [])
        expected_total = job.get("expected_total")
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        skipped = summary.get("skipped", 0)
        done = int(passed) + int(failed) + int(skipped)

        status_text = (
            f"Статус: {summary.get('status', 'running')} — {passed}✅ / {failed}❌ / {skipped}⏭"
        )
        if expected_total:
            status_text += f" (готово {done} из {expected_total})"
        status_box.write(status_text)

        if cases:
            df = pd.DataFrame(
                [
                    {
                        "Тест": (case.get("nodeid") or case.get("name")),
                        "Статус": case.get("status"),
                        "Время, c": case.get("duration"),
                        "Сообщение": (case.get("message") or "")[:300],
                    }
                    for case in cases
                ]
            )
            table_box.dataframe(df, use_container_width=True, hide_index=True)
        else:
            table_box.info("Идёт сбор результатов…")

        if expected_total:
            progress_box.progress(min(done / max(expected_total, 1), 1.0))
        else:
            progress_box.progress(0.0 if done == 0 else min(done / max(len(cases), 1), 1.0))

        if summary.get("status") in {"passed", "failed", "error", "stopped"}:
            break
        time.sleep(2)
