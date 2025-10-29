import asyncio
import os
import json
import datetime
import time
from typing import Tuple, List, Dict, Any

import paramiko
from scp import SCPClient

# Импорт твоих SNMP-хелперов
from MainConnectFunc import snmp_getBulk, oidsSNMP

STATE_FILE = "OIDstatusNEW.json"
LOCAL_BASE_PATH = "LogConf"


# ---------- SSH / SCP ----------
def ssh_exec(ip: str, username: str, password: str, command: str, timeout: int = 15) -> str:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, port=22, username=username, password=password, timeout=timeout)
    try:
        stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        return stdout.read().decode(errors="replace")
    finally:
        ssh.close()


def ssh_reload(ip: str, password: str) -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, port=22, username="admin", password=password)
    try:
        shell = ssh.invoke_shell()
        shell.send("reload\n")
        time.sleep(0.5)
        shell.send("y\n")
        time.sleep(0.5)
    finally:
        ssh.close()


def scp_copy_remote_dir(ip: str, username: str, password: str, remote_path: str, local_dir: str) -> str:
    os.makedirs(local_dir, exist_ok=True)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, port=22, username=username, password=password, timeout=10)
    try:
        with SCPClient(ssh.get_transport()) as scp:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            target = os.path.join(local_dir, f"{os.path.basename(remote_path)}_{ts}")
            os.makedirs(target, exist_ok=True)
            scp.get(remote_path, target, recursive=True)
            return target
    finally:
        ssh.close()


# ---------- Загрузка STM слотов и OID ----------
def load_stm_slots_and_oids() -> List[Dict[str, Any]]:
    fallback_alarm = "1.3.6.1.4.1.5756.3.3.2.17.2.3.2.1.5.{slot}"
    fallback_check = "1.3.6.1.4.1.5756.3.3.2.17.2.3.2.1.21.{slot}"

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    slots_dict = (((data or {}).get("CurrentEQ") or {}).get("slots_dict")) or {}
    result = []

    for k, v in slots_dict.items():
        try:
            slot = int(k)
        except Exception:
            continue
        typ = str(v or "").upper()
        if "STM" not in typ:
            continue

        s_oid = (data.get("OID") or {}).get("SFP") or {}
        alarm_oid = None
        check_oid = None
        if s_oid:
            if isinstance(s_oid.get("alarm"), dict):
                alarm_oid = s_oid["alarm"].get(str(slot))
            if isinstance(s_oid.get("check"), dict):
                check_oid = s_oid["check"].get(str(slot))
        alarm_oid = alarm_oid or fallback_alarm.format(slot=slot)
        check_oid = check_oid or fallback_check.format(slot=slot)
        result.append({"slot": slot, "alarm_oid": alarm_oid, "check_oid": check_oid})
    return sorted(result, key=lambda x: x["slot"])


# ---------- SNMP SFP check ----------
def snmp_check_sfp_status_for_stm_slots(ip: str) -> Tuple[bool, bool, Dict[str, Any]]:
    items = load_stm_slots_and_oids()
    if not items:
        return True, True, {"note": "no STM slots found"}

    all_alarm_vals, all_check_vals, per_slot = [], [], {}

    for it in items:
        slot = it["slot"]
        a_oid = it["alarm_oid"]
        c_oid = it["check_oid"]
        try:
            alarms_result = asyncio.run(snmp_getBulk(a_oid, 8))
            check_result = asyncio.run(snmp_getBulk(c_oid, 8))
            a_vals = list(alarms_result.values()) if isinstance(alarms_result, dict) else []
            c_vals = list(check_result.values()) if isinstance(check_result, dict) else []
            all_alarm_vals.extend(a_vals)
            all_check_vals.extend(c_vals)
            per_slot[slot] = {
                "alarm_oid": a_oid,
                "check_oid": c_oid,
                "alarm_vals": a_vals,
                "check_vals": c_vals,
            }
        except Exception as e:
            per_slot[slot] = {"error": f"slot {slot}: {e}"}

    no_alarms = len(set(all_alarm_vals)) <= 1
    no_blocking = len(set(all_check_vals)) <= 1
    return no_alarms, no_blocking, {"per_slot": per_slot}


# ---------- Основная функция с циклом итераций ----------
def check_conf(ip: str, password: str, iterations: int = 3, delay_between: int = 30) -> Dict[str, Any]:
    """
    Запуск конфигурационного теста на заданное число итераций.
    - ip, password: приходят с фронта
    - user всегда admin
    - iterations: сколько повторов сделать
    - delay_between: пауза между итерациями, секунд
    """
    summary = {
        "ip": ip,
        "iterations": iterations,
        "started": datetime.datetime.now().isoformat(timespec="seconds"),
        "results": []
    }

    for i in range(1, iterations + 1):
        iter_result = {
            "iteration": i,
            "start_time": datetime.datetime.now().isoformat(timespec="seconds"),
            "steps": []
        }
        try:
            # 1. show running-config
            config = ssh_exec(ip, "admin", password, "show running-config")
            iter_result["steps"].append({"get_config": len(config)})

            # 2. SNMP check STM slots
            no_alarms, no_blocking, details = snmp_check_sfp_status_for_stm_slots(ip)
            iter_result["steps"].append({
                "sfp_check": {"no_alarms": no_alarms, "no_blocking": no_blocking},
                "details": details
            })
            if not (no_alarms and no_blocking):
                iter_result["status"] = "alarm_detected"
                summary["results"].append(iter_result)
                continue

            # 3. copy configs and logs
            cfg_dir = scp_copy_remote_dir(ip, "root", "", "/var/volatile/tmp/osmkm/config", LOCAL_BASE_PATH)
            log_dir = scp_copy_remote_dir(ip, "root", "", "/var/volatile/log", LOCAL_BASE_PATH)
            iter_result["steps"].append({"copy": {"config": cfg_dir, "log": log_dir}})

            # 4. reload if config unchanged
            new_conf = ssh_exec(ip, "admin", password, "show running-config")
            if new_conf == config:
                ssh_reload(ip, password)
                iter_result["steps"].append({"reload": "sent"})
                time.sleep(220)
            else:
                iter_result["steps"].append({"reload": "skipped - config changed"})

            iter_result["status"] = "ok"
        except Exception as e:
            iter_result["status"] = f"error: {e}"

        iter_result["end_time"] = datetime.datetime.now().isoformat(timespec="seconds")
        summary["results"].append(iter_result)

        if i < iterations:
            time.sleep(delay_between)

    summary["finished"] = datetime.datetime.now().isoformat(timespec="seconds")
    ok_count = sum(1 for r in summary["results"] if r.get("status") == "ok")
    summary["status"] = f"OK {ok_count}/{iterations}"
    return summary
