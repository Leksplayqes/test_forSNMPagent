# backend_single.py
from __future__ import annotations

# =========[ МОДУЛЬ: импорты и глобалы ]=====================================================
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import List, Dict, Any, Optional
from pathlib import Path
import json, subprocess, re
from datetime import datetime
from MainConnectFunc import equpimentV7, get_device_info
from pydantic import BaseModel
import os, sys, uuid, time, xml.etree.ElementTree as ET
from snmpsubsystem import ProxyController
from checkFunctions.check_conf import main
from checkFunctions.check_hash import compare_directories_by_hash
from checkFunctions.check_KSequal import fpga_reload
import threading
from subprocess import Popen, PIPE, STDOUT


PROJECT_ROOT: Path = Path(__file__).resolve().parent
REPORT_DIR: Path = PROJECT_ROOT / "pytest_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR = REPORT_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
UTIL_JOBS: Dict[str, Dict[str, Any]] = {}
RUNNING_UTIL_PROCS: Dict[str, Any] = {}
TEST_JOBS: Dict[str, Dict[str, Any]] = {}

# Читабельные названия → nodeid (запуск pytest)
SYNC_TESTS_CATALOG = {
    "Создание/удаление приоритетов (STM/E1)": "OSMK_Mv7/test_syncV7.py::test_STM_E1_create_del",
    "Режим QL: выключить": "OSMK_Mv7/test_syncV7.py::test_QLmodeDOWN",
    "Режим QL: включить": "OSMK_Mv7/test_syncV7.py::test_QLmodeUP",
    "Создание внешнего источника синхронизации": "OSMK_Mv7/test_syncV7.py::test_extPortID",
    "Занятие/очистка шины SYNC": "OSMK_Mv7/test_syncV7.py::test_busSYNC",
    "Установка качества для extPort": "OSMK_Mv7/test_syncV7.py::test_extPortQL",
    "Конфигурация частоты extPort": "OSMK_Mv7/test_syncV7.py::test_extPortConf",
    "STM как источник для extPort": "OSMK_Mv7/test_syncV7.py::test_extSourceID",
    "Статус приоритета (STM)": "OSMK_Mv7/test_syncV7.py::test_prior_statusSTM",
    "Получение уровня QL на STM-входе": "OSMK_Mv7/test_syncV7.py::test_QLSTM_get",
    "Передача QL через STM": "OSMK_Mv7/test_syncV7.py::test_QLSTM_set",
    "Запись STM как источника выхода": "OSMK_Mv7/test_syncV7.py::test_STM_extport",
    "Соответствие QL extPort ↔ STM": "OSMK_Mv7/test_syncV7.py::test_STM_QL_extport",
    "Аварии по порогам QL (блоки)": "OSMK_Mv7/test_syncV7.py::test_ThresQL_AlarmBlock",
    "Аварии по порогам QL (SETS)": "OSMK_Mv7/test_syncV7.py::test_ThreshQL_AlarmSETS",
}
ALARM_TESTS_CATALOG = {
    "Физические аварии STM": "OSMK_Mv7/test_alarmV7.py::test_physical_alarmSTM",
    "Аварии связности STM": "OSMK_Mv7/test_alarmV7.py::test_connective_alarmSTM",
    "Аварии связности E1": "OSMK_Mv7/test_alarmV7.py::test_connective_alarmE1",
    "Аварии связности GE": "OSMK_Mv7/test_alarmV7.py::test_connective_alarmGE",
}

DEFAULT_CONFIG: Dict[str, Any] = {"CurrentEQ": {"name": "", "ipaddr": "", "pass": "", "slots_dict": {}}}
_VERBOSE_LINE = re.compile(r'^(?P<nodeid>[^ ]+::[^\s]+?)\s+(?P<status>PASSED|FAILED|ERROR|SKIPPED|XPASS|XFAIL)')

SNMP_PROXY = ProxyController()
SNMP_PROXY_LOCK = threading.Lock()
_TUNNEL_LOCK = threading.RLock()
_ACTIVE_TUNNEL_JOBS: set[str] = set()
RUNNING_PROCS: Dict[str, Popen] = {}
api_logs: List[Dict[str, str]] = []

app = FastAPI(title="OSM-K Tester API (single-file)", version="4.4.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)


# =========[ МОДУЛЬ: работа с конфигом (OIDstatusNEW.json) ]=================================

def _detect_project_root(start: Path) -> Path:
    for p in start.parents:
        if p.name.lower() == "backend":
            return p.parent
    for p in start.parents:
        if (p / "backend").is_dir() and (p / "frontend").is_dir():
            return p
    return start.parents[0]


def _config_path() -> Path:
    env_path = os.getenv("OSMK_CONFIG_PATH")
    if env_path:
        return Path(env_path)
    here = Path(__file__).resolve()
    root = _detect_project_root(here)
    return root / "OIDstatusNEW.json"


CONFIG_FILE: Path = _config_path()


def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def ensure_config() -> Dict[str, Any]:
    try:
        if not CONFIG_FILE.exists():
            _atomic_write(CONFIG_FILE, DEFAULT_CONFIG)
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        _atomic_write(CONFIG_FILE, DEFAULT_CONFIG)
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


def json_input(path: List[str], payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise TypeError("json_input expects dict payload")
    data = ensure_config()
    d = data
    for k in path:
        if k not in d or not isinstance(d[k], dict):
            d[k] = {}
        d = d[k]
    _deep_merge(d, payload)
    _atomic_write(CONFIG_FILE, data)


def json_set(path: List[str], value: Any) -> None:
    data = ensure_config()
    d = data
    for k in path[:-1]:
        if k not in d or not isinstance(d[k], dict):
            d[k] = {}
        d = d[k]
    d[path[-1]] = value
    _atomic_write(CONFIG_FILE, data)


# =========[ МОДУЛЬ: сервисные утилиты ]=====================================================

def add_log(message: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    api_logs.append({"timestamp": ts, "level": level, "message": message})
    if len(api_logs) > 4000:
        del api_logs[:2000]


def _norm_nodeid(s: str) -> str:
    return s.replace(" ::", "::").replace(":: ", "::").replace(" / ", "/").strip()


# =========[ МОДЕЛИ API ]====================================================================

class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str


class LogsResponse(BaseModel):
    total: int
    logs: List[LogEntry]


class LoopbackSettings(BaseModel):
    slot: Optional[int] = None
    port: Optional[int] = None


class ViaviTypeOfPort(BaseModel):
    Port1: str = "STM-1"
    Port2: str = "STM-1"


class ViaviUnitSettings(BaseModel):
    ipaddr: Optional[str] = None
    port: Optional[int] = None
    typeofport: Optional[ViaviTypeOfPort] = None


class ViaviSettings(BaseModel):
    NumOne: Optional[ViaviUnitSettings] = None
    NumTwo: Optional[ViaviUnitSettings] = None


class DeviceInfoRequest(BaseModel):
    ip_address: str
    password: Optional[str] = ""
    viavi: Optional[ViaviSettings] = None
    loopback: Optional[LoopbackSettings] = None


class TestsRunRequest(BaseModel):
    test_type: str = "manual"
    selected_tests: List[str]
    settings: Optional[Dict[str, Any]] = None


# =========[ МОДУЛЬ: ручки общего назначения ]==============================================

@app.get("/health")
async def health():
    return {"ok": True, "config_path": str(CONFIG_FILE)}


@app.get("/")
async def root():
    return {"message": "OSM-K Tester API (single-file) running", "version": "4.4.1"}


@app.post("/ping")
async def ping(req: Dict[str, Any]):
    ip = req.get("ip_address", "")
    add_log(f"Ping {ip}")
    try:
        cmd = ["ping", "-n", "2", ip]  # Windows
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
        except Exception:
            res = subprocess.run(["ping", "-c", "2", ip], capture_output=True, text=True)  # *nix
        return {"success": res.returncode == 0, "output": res.stdout, "error": res.stderr}
    except Exception as e:
        add_log(f"Ping error: {e}", "ERROR")
        return {"success": False, "error": str(e)}


# =========[ МОДУЛЬ: SNMP-over-SSH туннель ]================================================

def _tunnel_alive() -> bool:
    return bool(SNMP_PROXY.proxy and SNMP_PROXY.proxy._proc_alive())


def _ensure_tunnel(ip: str, username: str, password: str):
    with _TUNNEL_LOCK:
        if not _tunnel_alive():
            SNMP_PROXY.start(ip=ip, username=username, password=password)


def _register_tunnel_user(job_id: str):
    with _TUNNEL_LOCK:
        _ACTIVE_TUNNEL_JOBS.add(job_id)


def _release_tunnel_user(job_id: str):
    with _TUNNEL_LOCK:
        _ACTIVE_TUNNEL_JOBS.discard(job_id)
        if not _ACTIVE_TUNNEL_JOBS:
            try:
                SNMP_PROXY.close()
            except Exception:
                pass


# =========[ МОДУЛЬ: device/info — сохранение и старт туннеля ]=============================

def save_viavi_to_json(vs: ViaviSettings):
    def set_unit(unit_name: str, u: Optional[ViaviUnitSettings]):
        if u is None:
            return
        base = ["VIAVIcontrol", "settings", unit_name]
        if u.ipaddr is not None:
            json_set(base + ["ipaddr"], u.ipaddr)
        if u.port is not None:
            json_set(base + ["port"], int(u.port))
        if u.typeofport is not None:
            tp = u.typeofport
            if tp.Port1 is not None:
                json_set(base + ["typeofport", "Port1"], tp.Port1)
            if tp.Port2 is not None:
                json_set(base + ["typeofport", "Port2"], tp.Port2)

    set_unit("NumOne", vs.NumOne)
    set_unit("NumTwo", vs.NumTwo)


@app.post("/device/info")
async def device_info(req: DeviceInfoRequest) -> Dict[str, Any]:
    try:
        ensure_config()
    except Exception as e:
        add_log(f"ensure_config failed: {e}", "ERROR")

    try:
        if req.ip_address:
            json_set(["CurrentEQ", "ipaddr"], req.ip_address)
        json_set(["CurrentEQ", "pass"], req.password or "")
    except Exception as e:
        add_log(f"json_set (ip/pass) failed: {e}", "ERROR")

    # Туннель SNMP-over-SSH
    ip = req.ip_address
    password = req.password or ""
    username = "admin"

    def _run_proxy():
        try:
            with SNMP_PROXY_LOCK:
                SNMP_PROXY.start(ip=ip, username=username, password=password)
        except Exception as e:
            add_log(f"SNMP proxy start failed: {e}", "ERROR")

    if not SNMP_PROXY.proxy or not SNMP_PROXY.proxy._proc_alive():
        threading.Thread(target=_run_proxy, daemon=True).start()
        add_log(f"SNMP proxy started for {ip}", "INFO")
    else:
        add_log(f"SNMP proxy already running on {ip}", "INFO")

    try:
        if req.viavi is not None:
            save_viavi_to_json(req.viavi)
    except Exception as e:
        add_log(f"save_viavi_to_json failed: {e}", "ERROR")

    try:
        if req.loopback is not None:
            payload = {k: v for k, v in req.loopback.model_dump().items() if v is not None}
            if payload:
                json_input(["CurrentEQ", "loopback"], payload)
    except Exception as e:
        add_log(f"save loopback failed: {e}", "ERROR")

    try:
        await get_device_info()
    except Exception as e:
        add_log(f"Get_device_info failed: {e}", "ERROR")
    try:
        await equpimentV7()
    except Exception as e:
        add_log(f"EqupimentV7 failed: {e}", "ERROR")

    data = ensure_config()
    cur = (data or {}).get("CurrentEQ", {}) or {}
    return {
        "name": cur.get("name") or "",
        "ipaddr": cur.get("ipaddr") or req.ip_address,
        "slots_dict": cur.get("slots_dict") or {},
        "viavi": (data or {}).get("VIAVIcontrol", {}).get("settings", {}),
        "loopback": cur.get("loopback", {}),
    }


# =========[ МОДУЛЬ: job-файлы и список прогонов ]==========================================

def _job_path(job_id: str) -> Path: return JOBS_DIR / f"{job_id}.json"


def _save_job(job_id: str) -> None:
    p = _job_path(job_id)
    try:
        with p.open("w", encoding="utf-8") as file:
            json.dump(TEST_JOBS[job_id], file, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[jobs] save file for {job_id}: {e}")


def _load_jobs_on_startup() -> None:
    for p in JOBS_DIR.glob("*.json"):
        try:
            with p.open("r", encoding="utf-8") as f:
                job = json.load(f)
            jid = job.get("id") or p.stem
            TEST_JOBS[jid] = job
        except Exception as e:
            print(f"[jobs] load failed {p.name}: {e}")


@app.on_event("startup")
def _load_jobs(): _load_jobs_on_startup()


@app.get("/tests/jobs")
def list_jobs():
    out = []
    for jid, job in TEST_JOBS.items():
        out.append({
            "id": jid,
            "started": job.get("started"),
            "finished": job.get("finished"),
            "summary": job.get("summary"),
            "report": job.get("report"),
        })
    out.sort(key=lambda x: x["started"] or 0, reverse=True)
    return out


# =========[ МОДУЛЬ: парсер JUnit XML ]======================================================

def _parse_junit_report(xml_path: str):
    cases = []
    passed = failed = skipped = errors = 0
    total_time = 0.0

    root = ET.parse(xml_path).getroot()
    for ts in root.findall(".//testsuite"):
        for tc in ts.findall("testcase"):
            name = tc.get("name") or ""
            classname = tc.get("classname") or ""
            duration = float(tc.get("time") or 0.0)
            nodeid = f"{classname}::{name}" if classname else name

            status = "PASSED"
            message = None
            f = tc.find("failure")
            e = tc.find("error")
            s = tc.find("skipped")
            if f is not None:
                status, message, failed = "FAILED", (f.get("message") or "").strip(), failed + 1
            elif e is not None:
                status, message, errors = "ERROR", (e.get("message") or "").strip(), errors + 1
            elif s is not None:
                status, message, skipped = "SKIPPED", (s.get("message") or "").strip(), skipped + 1
            else:
                passed += 1

            total_time += duration
            cases.append({"name": name, "nodeid": nodeid, "status": status, "duration": duration, "message": message})

    summary = {
        "status": ("failed" if (failed or errors) else "passed"),
        "total": len(cases), "passed": passed, "failed": failed + errors, "skipped": skipped, "duration": total_time,
    }
    return cases, summary


# =========[ МОДУЛЬ: запуск/стоп тестов ]====================================================

@app.get("/tests/types")
async def get_types(): return {"alarm_tests": ALARM_TESTS_CATALOG, "sync_tests": SYNC_TESTS_CATALOG}


@app.post("/tests/run")
def tests_run(req: TestsRunRequest, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex[:12]
    nodeids = [_norm_nodeid(x) for x in (req.selected_tests or []) if x.strip()]
    if not nodeids:
        raise HTTPException(status_code=400, detail="Не выбраны тесты для запуска")

    _register_tunnel_user(job_id)

    try:
        cfg = ensure_config()
        ip = (cfg.get("CurrentEQ") or {}).get("ipaddr") or ""
        pw = (cfg.get("CurrentEQ") or {}).get("pass") or ""
        if ip and not _tunnel_alive():
            threading.Thread(target=_ensure_tunnel, args=(ip, "admin", pw), daemon=True).start()
    except Exception:
        pass

    TEST_JOBS[job_id] = {
        "id": job_id,
        "config": req.model_dump(),
        "started": time.time(),
        "finished": None,
        "summary": {"status": "running", "total": 0, "passed": 0, "failed": 0, "skipped": 0, "duration": 0.0},
        "cases": [], "stdout": "", "stderr": "", "returncode": None,
        "report": str((REPORT_DIR / f"{job_id}.xml").resolve()),
    }

    background_tasks.add_task(_execute_tests, job_id, nodeids)
    return {"success": True, "job_id": job_id}


@app.get("/tests/status")
def tests_status(job_id: str):
    job = TEST_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.post("/tests/stop")
def tests_stop(job_id: str = Query(...)):
    job = TEST_JOBS.get(job_id)
    proc = RUNNING_PROCS.get(job_id)
    if not job:
        return {"success": False, "error": "job not found"}
    if not proc:
        if (job.get("summary") or {}).get("status") == "running":
            job["summary"]["status"] = "stopped"
            job["finished"] = time.time()
            _save_job(job_id)
        return {"success": True, "message": "job is not running"}
    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        code = proc.returncode
    except Exception as e:
        return {"success": False, "error": f"terminate failed: {e}"}
    finally:
        RUNNING_PROCS.pop(job_id, None)
    cases = job.get("cases") or []
    job["returncode"] = code
    job["finished"] = time.time()
    job["summary"] = {
        "status": "stopped", "total": len(cases),
        "passed": sum(1 for c in cases if c.get("status") == "PASSED"),
        "failed": sum(1 for c in cases if c.get("status") in ("FAILED", "ERROR")),
        "skipped": sum(1 for c in cases if c.get("status") == "SKIPPED"),
        "duration": sum(float(c.get("duration") or 0.0) for c in cases),
    }
    _save_job(job_id)
    try:
        _release_tunnel_user(job_id)
    except Exception:
        pass
    return {"success": True, "message": "job stopped"}


def _recalc_summary(cases, finished: bool):
    total = len(cases)
    passed = sum(1 for c in cases if c["status"] == "PASSED")
    failed = sum(1 for c in cases if c["status"] in ("FAILED", "ERROR"))
    skipped = sum(1 for c in cases if c["status"] == "SKIPPED")
    duration = sum(float(c.get("duration") or 0.0) for c in cases)
    status = "running" if not finished else ("passed" if failed == 0 else "failed")
    return {"status": status, "total": total, "passed": passed, "failed": failed, "skipped": skipped,
            "duration": duration}


def _execute_tests(job_id: str, nodeids: list[str]):
    COLLECT_RE = re.compile(r"collected\s+(\d+)\s+items?")
    TEST_JOBS[job_id]["expected_total"] = None
    report_path = str(REPORT_DIR / f"{job_id}.xml")

    cmd = [sys.executable, "-m", "pytest", "-vv", "-rA", "--tb=short", "--color=no", f"--junitxml={report_path}",
           *nodeids]
    proc = Popen(cmd, cwd=str(PROJECT_ROOT), text=True, stdout=PIPE, stderr=STDOUT, bufsize=1, universal_newlines=True)
    RUNNING_PROCS[job_id] = proc

    try:
        cases_map: dict[str, dict] = {}
        TEST_JOBS[job_id].update({"stdout": "", "stderr": "", "cases": [],
                                  "summary": {"status": "running", "total": 0, "passed": 0, "failed": 0, "skipped": 0,
                                              "duration": 0.0}})
        if proc.stdout is not None:
            for line in proc.stdout:
                mcol = COLLECT_RE.search(line)
                if mcol:
                    try:
                        TEST_JOBS[job_id]["expected_total"] = int(mcol.group(1))
                    except Exception:
                        pass
                TEST_JOBS[job_id]["stdout"] += line
                m = _VERBOSE_LINE.match(line.strip())
                if m:
                    nodeid = m.group("nodeid").strip()
                    status = m.group("status")
                    nodeid = nodeid.replace(" ::", "::").replace(":: ", "::").replace(" / ", "/")
                    case = cases_map.get(nodeid) or {"name": nodeid.split("::")[-1], "nodeid": nodeid, "status": status,
                                                     "duration": None, "message": None}
                    case["status"] = status
                    cases_map[nodeid] = case
                    TEST_JOBS[job_id]["cases"] = list(cases_map.values())
                    TEST_JOBS[job_id]["summary"] = _recalc_summary(TEST_JOBS[job_id]["cases"], finished=False)
                    _save_job(job_id)
        proc.wait()
        TEST_JOBS[job_id]["returncode"] = proc.returncode
        TEST_JOBS[job_id]["finished"] = time.time()
        _save_job(job_id)

        try:
            if os.path.exists(report_path):
                final_cases, _ = _parse_junit_report(report_path)
                final_map = {c["nodeid"]: c for c in final_cases}
                for nid, live in list(cases_map.items()):
                    if nid in final_map:
                        f = final_map[nid]
                        live["status"] = f["status"]
                        live["duration"] = f.get("duration")
                        live["message"] = f.get("message")
                        final_map[nid] = live
                TEST_JOBS[job_id]["cases"] = list(final_map.values())
                TEST_JOBS[job_id]["summary"] = _recalc_summary(TEST_JOBS[job_id]["cases"], finished=True)
                _save_job(job_id)
            else:
                if not TEST_JOBS[job_id]["cases"]:
                    TEST_JOBS[job_id]["summary"] = {"status": "error", "total": 0, "passed": 0, "failed": 1,
                                                    "skipped": 0, "duration": 0.0,
                                                    "message": "pytest did not produce junit xml; check stdout/stderr"}
                    _save_job(job_id)
        except Exception as e:
            TEST_JOBS[job_id]["summary"] = {"status": "error", "total": len(TEST_JOBS[job_id].get("cases") or []),
                                            "passed": 0, "failed": 1, "skipped": 0, "duration": 0.0,
                                            "message": f"junit merge failed: {e}"}
            _save_job(job_id)
    finally:
        RUNNING_PROCS.pop(job_id, None)
        try:
            _release_tunnel_user(job_id)
        except Exception:
            pass
        _save_job(job_id)


# =========[ МОДУЛЬ: дополнительные тестовые функции ]=======================================
# ================== общий статус/лог/стоп для утилит ==================

@app.get("/utils/jobs")
def util_jobs():
    items = [{"id": j["id"], "type": j["type"], "status": j["status"], "started": j["started"],
              "finished": j.get("finished")} for j in UTIL_JOBS.values()]
    items.sort(key=lambda x: x["started"], reverse=True)
    return items


@app.get("/utils/status")
def util_status(job_id: str):
    j = UTIL_JOBS.get(job_id)
    if not j: raise HTTPException(404, "util job not found")
    return j


# =========[ МОДУЛЬ: утилиты из внешней директории checkFunctions ]=======================
# Эти ручки просто вызывают твои исходные функции без переписывания логики.

@app.post("/utils/check_conf")
def util_check_conf(req: Dict[str, Any]):
    ip = req.get("ip") or ""
    password = req.get("password") or ""
    if not ip:
        raise HTTPException(status_code=400, detail="ip is required")
    try:
        result = main()
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/utils/check_hash")
def util_check_hash(req: Dict[str, Any]):
    dir1 = req.get("dir1")
    dir2 = req.get("dir2")
    if not dir1 or not dir2:
        raise HTTPException(status_code=400, detail="dir1 and dir2 are required")
    try:
        result = compare_directories_by_hash(dir1, dir2)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/utils/fpga_reload")
def util_fpga_reload(req: Dict[str, Any]):
    ip = req.get("ip") or ""
    password = req.get("password") or ""
    slot = int(req.get("slot", 9))
    if not ip:
        raise HTTPException(status_code=400, detail="ip is required")
    try:
        result = fpga_reload()
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =========[ МОДУЛЬ: отдача файлов (экспорт) ]===============================================

@app.get("/tests/jobfile")
def download_jobfile(job_id: str):
    p = JOBS_DIR / f"{job_id}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="job file not found")
    return FileResponse(str(p), media_type="application/json", filename=f"{job_id}.json")


@app.get("/tests/report")
def download_junit_xml(job_id: str):
    job = TEST_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    report_path = job.get("report")
    if not report_path or not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="report not found")
    return FileResponse(report_path, media_type="application/xml", filename=f"{job_id}.xml")
