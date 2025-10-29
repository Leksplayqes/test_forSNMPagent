# frontend_single.py
import json, time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import streamlit as st
import pandas as pd
import requests

from backend_single import SYNC_TESTS_CATALOG, ALARM_TESTS_CATALOG

# =========[ МОДУЛЬ: базовая конфигурация страницы ]=========================================
st.set_page_config(page_title="OSM-K Tester System", page_icon="🛠️", layout="wide",
                   initial_sidebar_state="expanded")
STATE_FILE = Path(__file__).resolve().with_name("ui_state.json")
DEFAULT_API_BASE_URL = "http://localhost:8000"

st.markdown("""
 <style>
 div.stButton > button:first-child {background-color: #800000; color: white;font-weight: bold;}
 div.stButton > button:first-child:hover {background-color: #560319;}
 </style>
""", unsafe_allow_html=True)

st.session_state.setdefault("test_results", None)
st.session_state.setdefault("test_history", [])


# =========[ МОДУЛЬ: сохранение/восстановление состояния ]===================================

def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state():
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
        "test_results": st.session_state.get("test_results"),
        "test_history": st.session_state.get("test_history", []),
        "current_job_id": st.session_state.get("current_job_id"),
    }
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def apply_state():
    saved = load_state()
    if not saved:
        return
    if "device_info" in saved and "device_info" not in st.session_state:
        st.session_state["device_info"] = saved["device_info"]
    # исправил опечатку `,istory` → `test_history`
    for k in ["api_base_url", "ip_address_input", "password_input", "snmp_type_select",
              "test_type_radio", "viavi_config", "slot_loopback", "port_loopback",
              "test_results", "test_history", "current_job_id", "selected_tests"]:
        if k in saved and k not in st.session_state:
            st.session_state[k] = saved[k]

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


def on_change(): save_state()


def _commit_test_result(job: dict, save_history: bool = True):
    if not job:
        return
    st.session_state["test_results"] = job
    summary = job.get("summary") or {}
    status = (summary.get("status") or "").lower()
    finished = status in ("passed", "failed", "error", "stopped")
    if save_history and finished:
        jid = job.get("id")
        if not any(x.get("id") == jid for x in (st.session_state.get("test_history") or [])):
            st.session_state["test_history"].append(job)


def viavi_sync_from_widgets():
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


# =========[ МОДУЛЬ: HTTP helpers ]==========================================================

def api_post(api_base: str, path: str, payload: Dict[str, Any] | None = None, timeout: int = 30):
    try:
        r = requests.post(f"{api_base}{path}", json=payload or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as he:
        try:
            st.error(f"POST {path}: {he} | body: {r.text[:400]}")
        except Exception:
            st.error(f"POST {path}: {he}")
        return None
    except Exception as e:
        st.error(f"POST {path}: {e}")
        return None


def api_get(api_base: str, path: str, timeout: int = 30):
    try:
        r = requests.get(f"{api_base}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"GET {path}: {e}")
        return None


def _norm_nodeid(s: str) -> str:
    return s.replace(" ::", "::").replace(":: ", "::").replace(" / ", "/").strip()


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




# =========[ МОДУЛЬ: API-обёртки ]==========================================================

def ping_device(api_base: str, ip: str) -> bool:
    data = api_post(api_base, "/ping", {"ip_address": ip})
    return bool(data and data.get("success"))


def get_device_info(api_base: str, ip: str, password: str, snmp: str):
    viavi_sync_from_widgets()
    loopback = {"slot": st.session_state.get("slot_loopback"), "port": st.session_state.get("port_loopback")}
    payload = {
        "ip_address": ip, "password": password, "snmp_type": snmp,
        "viavi": st.session_state.get("viavi_config", {}),
        "loopback": {k: v for k, v in loopback.items() if v},
    }
    data = api_post(api_base, "/device/info", payload, timeout=500)
    if not data:
        return None
    st.session_state["device_info"] = {"name": data.get("name"), "ipaddr": data.get("ipaddr"),
                                       "slots_dict": data.get("slots_dict") or {}}
    st.session_state["viavi_config"] = data.get("viavi") or st.session_state["viavi_config"]
    st.session_state["saved_loopback"] = data.get("loopback") or {}
    on_change()
    return st.session_state["device_info"]


def get_test_types(api_base: str):
    data = api_get(api_base, "/tests/types") or {}
    if not data:
        return {"alarm_tests": ALARM_TESTS_CATALOG, "sync_tests": SYNC_TESTS_CATALOG}
    return data


def run_tests(api_base: str, cfg: Dict[str, Any]):
    return api_post(api_base, "/tests/run", cfg, timeout=60)


def stop_test_job(api_base: str, job_id: str):
    try:
        r = requests.post(f"{api_base}/tests/stop?job_id={job_id}", timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            st.success(f"Тест {job_id} остановлен.")
        else:
            st.warning(f"Не удалось остановить тест: {data.get('error')}")
    except Exception as e:
        st.error(f"Ошибка остановки теста: {e}")


# =========[ МОДУЛЬ: UI — Конфигурация ]====================================================

def render_configuration(api_base: str):
    st.header("Конфигурация тестирования")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.subheader("Основные настройки")
        ip = st.text_input("**IP адрес устройства**",
                           value=(st.session_state.get("device_info") or {}).get("ipaddr", st.session_state.get(
                               "ip_address_input", "")),
                           key="ip_address_input", on_change=on_change)
        pw = st.text_input("**Пароль (для v7)**", type="password", key="password_input", on_change=on_change)
        snmp = st.selectbox("**Тип SNMP**", ["SnmpV2", "SnmpV3"], key="snmp_type_select", on_change=on_change)
        if st.button("Проверить подключение", use_container_width=False):
            if ping_device(api_base, ip):
                get_device_info(api_base, ip, pw, snmp)

    with col2:
        st.subheader("Конфигурация тестов")
        ttypes = get_test_types(api_base)
        test_type = st.radio("**Тип тестов**", ["alarm", "sync"],
                             format_func=lambda x: "Alarm Tests" if x == "alarm" else "Sync Tests",
                             horizontal=True, key="test_type_radio", on_change=on_change)
        if test_type == "alarm":
            alarm_map = ttypes["alarm_tests"] or {}
            available_labels = list(alarm_map.keys())
            default_labels = [x for x in (st.session_state.get("selected_test_labels") or []) if x in available_labels]
            selected_labels = st.multiselect("Выберите тесты:", options=available_labels, default=default_labels,
                                             on_change=on_change, key="tests_ms_alarm")
            selected_nodeids = [alarm_map[label] for label in selected_labels]
        else:
            sync_map = ttypes["sync_tests"] or {}
            available_labels = list(sync_map.keys())
            default_labels = [x for x in (st.session_state.get("selected_test_labels") or []) if x in available_labels]
            selected_labels = st.multiselect("Выберите тесты:", options=available_labels, default=default_labels,
                                             on_change=on_change, key="tests_ms_sync")
            selected_nodeids = [sync_map[label] for label in selected_labels]

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

    st.session_state.setdefault("viavi_config", {
        "NumOne": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
        "NumTwo": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
    })

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("**IP Viavi №1**", value=st.session_state.get("viavi1_ip", ""),
                          key="viavi1_ip", on_change=viavi_sync_from_widgets)
            d1, d2 = st.columns(2)
            with d1:
                st.selectbox("Port 1", ["", "STM-1", "STM-4", "STM-16"],
                             index=["", "STM-1", "STM-4", "STM-16"].index(st.session_state.get("viavi1_port1", "")),
                             key="viavi1_port1", on_change=viavi_sync_from_widgets)
            with d2:
                st.selectbox("Port 2", ["", "STM-1", "STM-4", "STM-16"],
                             index=["", "STM-1", "STM-4", "STM-16"].index(st.session_state.get("viavi1_port2", "")),
                             key="viavi1_port2", on_change=viavi_sync_from_widgets)
    with tab2:
        c3, c4 = st.columns(2)
        with c3:
            st.text_input("**IP Viavi №2**", value=st.session_state.get("viavi2_ip", ""),
                          key="viavi2_ip", on_change=viavi_sync_from_widgets)
            d3, d4 = st.columns(2)
            with d3:
                st.selectbox("Port 1", ["", "STM-1", "STM-4", "STM-16"],
                             index=["", "STM-1", "STM-4", "STM-16"].index(st.session_state.get("viavi2_port1", "")),
                             key="viavi2_port1", on_change=viavi_sync_from_widgets)
            with d4:
                st.selectbox("Port 2", ["", "STM-1", "STM-4", "STM-16"],
                             index=["", "STM-1", "STM-4", "STM-16"].index(st.session_state.get("viavi2_port2", "")),
                             key="viavi2_port2", on_change=viavi_sync_from_widgets)
    with tab3:
        c5, c6 = st.columns(2)
        with c5:
            st.selectbox("**Слот с loopback**", [3, 4, 5, 6, 7, 8, 11, 12, 13, 14], key="slot_loopback",
                         on_change=on_change)
            st.selectbox("**Порт с loopback**", [1, 2, 3, 4, 5, 6, 7, 8], key="port_loopback", on_change=on_change)

    st.markdown("---")
    center = st.columns([1, 1, 1])[1]
    nodeids = [_norm_nodeid(x) for x in (st.session_state.get("selected_tests") or []) if x.strip()]
    with center:
        if st.button("🚀 Запустить тесты", use_container_width=False):
            if not nodeids:
                st.warning("Не выбраны тесты.")
            else:
                payload = {"test_type": st.session_state.get("test_type_radio", "manual"),
                           "selected_tests": nodeids}
                try:
                    resp = api_post(api_base, "/tests/run", payload, timeout=120)
                    job_id = resp["job_id"]
                    st.session_state["current_job_id"] = job_id
                    st.session_state["test_results"] = None
                    st.success(f"Тесты запущены. job_id = {job_id}")
                except Exception as e:
                    st.error(f"Не удалось запустить тесты: {e}")


# ==========[ Модуль: UI - Доп. функции ]=====================================================

def render_utils(api_base: str):
    st.header("Утилиты (из checkFunctions)")

    with st.expander("📄 Проверка конфигурации (check_conf)", expanded=True):
        ip = st.text_input("IP устройства (для check_conf)", key="util_cc_ip",
                           value=(st.session_state.get("device_info") or {}).get("ipaddr", ""))
        pw = st.text_input("Пароль (для check_conf)", type="password", key="util_cc_pw",
                           value=st.session_state.get("password_input", ""))
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
        ip2 = st.text_input("IP устройства (для fpga_reload)", key="util_fpga_ip",
                            value=(st.session_state.get("device_info") or {}).get("ipaddr", ""))
        pw2 = st.text_input("Пароль (для fpga_reload)", type="password", key="util_fpga_pw",
                            value=st.session_state.get("password_input", ""))
        slot = st.number_input("Слот", min_value=1, max_value=16, value=9, step=1, key="util_fpga_slot")
        if st.button("Запустить fpga_reload"):
            res = util_fpga_reload(api_base, ip2, pw2, int(slot))
            if res and res.get("success"):
                st.success("Готово")
                st.json(res.get("result"))
            else:
                st.error(res.get("error") if res else "Ошибка запроса")

    # =========[ МОДУЛЬ: UI — Результаты] == == == == == == == == == == == == == == == == == == == == == == == == == == == =

def render_results(api_base_url: str):
    st.header("Результаты тестирования")

    jobs = api_get(api_base_url, "/tests/jobs", timeout=20) or []
    if not jobs:
        st.info("Пока нет ни одного прогона.")
        return

    job_ids = [j["id"] for j in jobs]
    default_id = st.session_state.get("current_job_id") or job_ids[0]
    if default_id not in job_ids: default_id = job_ids[0]

    st.write("Выберите прогон (job_id):")
    col1, col2 = st.columns([4, 1], gap="small")
    with col1:
        sel = st.selectbox("null", options=job_ids, index=job_ids.index(default_id), label_visibility="collapsed")
        st.session_state["current_job_id"] = sel
    with col2:
        if st.button("🛑 Остановить тест", type="secondary", width='stretch'):
            stop_test_job(api_base_url, sel)

    status_box = st.empty()
    table_box = st.empty()
    progress_box = st.empty()

    for _ in range(900):  # до 30 минут
        job = api_get(api_base_url, f"/tests/status?job_id={sel}", timeout=20) or {}
        _commit_test_result(job, save_history=True)

        summary = job.get("summary", {});
        cases = job.get("cases", []);
        expected_total = job.get("expected_total")
        passed = summary.get("passed", 0);
        failed = summary.get("failed", 0);
        skipped = summary.get("skipped", 0)
        done = int(passed) + int(failed) + int(skipped)

        status_text = f"Статус: {summary.get('status', 'running')} — {passed}✅ / {failed}❌ / {skipped}⏭"
        if expected_total: status_text += f" (готово {done} из {expected_total})"
        status_box.write(status_text)

        if cases:
            df = pd.DataFrame([{
                "Тест": (c.get("nodeid") or c.get("name")), "Статус": c.get("status"),
                "Время, c": c.get("duration"), "Сообщение": (c.get("message") or "")[:300]
            } for c in cases])
            table_box.dataframe(df, width='stretch', hide_index=True)
        else:
            table_box.info("Идёт сбор результатов…")

        if expected_total:
            progress_box.progress(min(done / max(expected_total, 1), 1.0))
        else:
            progress_box.progress(0.0 if done == 0 else (done % 10) / 10)

        if summary.get("status") in ("passed", "failed", "error", "stopped"):
            break
        time.sleep(2)


# =========[ МОДУЛЬ: Sidebar ]================================================================

def sidebar_ui():
    st.markdown("")
    st.subheader("Быстрые действия")

    api_base = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL)
    jobs = api_get(api_base, "/tests/jobs") or []
    if not jobs:
        st.info("Пока нет сохранённых тестов.")
        st.button("📊 Экспорт результатов", disabled=True, width='stretch')
        st.button("🧾 Экспорт JUnit XML", disabled=True, width='stretch')
    else:
        job_ids = [j["id"] for j in jobs]
        default = st.session_state.get("current_job_id") or job_ids[0]
        if default not in job_ids: default = job_ids[0]
        sel = st.selectbox("Выберите тест (job_id) для экспорта:", job_ids,
                           index=job_ids.index(default), key="export_job_id")
        job_url = f"{api_base}/tests/jobfile?job_id={sel}"
        st.markdown(f'<a href="{job_url}" download>'
                    f'<button class="st-emotion-cache-1vt4y43 ef3psqc12" style="width:100%;">📊 Экспорт результатов (JSON)</button>'
                    f'</a>', unsafe_allow_html=True)
        xml_url = f"{api_base}/tests/report?job_id={sel}"
        st.markdown(f'<a href="{xml_url}" download>'
                    f'<button class="st-emotion-cache-1vt4y43 ef3psqc12" style="width:100%;">🧾 Экспорт JUnit XML</button>'
                    f'</a>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Инструкция:")
    st.markdown("\n".join([
        "1. Настройте устройство во вкладке конфигурации",
        "2. Запустите тесты",
        "3. Просмотрите результаты",
        "4. Экспортируйте JSON/JUnit при необходимости",
    ]))


# =========[ МОДУЛЬ: Entry ]=================================================================

def main():
    st.markdown("<h1 style='display:flex;align-items:center;gap:12px;'>🛠️ OSM-K Tester System</h1>",
                unsafe_allow_html=True)
    st.markdown("---")
    apply_state()
    st.session_state.setdefault("api_base_url", DEFAULT_API_BASE_URL)

    with st.sidebar: sidebar_ui()

    api_base = st.session_state["api_base_url"]
    tab1, tab2, tab3 = st.tabs(["⚙️ Конфигурация тестирования", "📊 Результаты тестирования", "🔧 Утилиты"])
    with tab1: render_configuration(api_base)
    with tab2: render_results(api_base)
    with tab3: render_utils(api_base)  # ← новая функция ниже


if __name__ == "__main__":
    main()
