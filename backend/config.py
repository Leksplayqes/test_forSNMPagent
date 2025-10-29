"""Helpers for working with project paths and persistent JSON configuration."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
REPORT_DIR: Path = PROJECT_ROOT / "pytest_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR: Path = REPORT_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG: Dict[str, Any] = {"CurrentEQ": {"name": "", "ipaddr": "", "pass": "", "slots_dict": {}}}


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


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
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


__all__ = [
    "PROJECT_ROOT",
    "REPORT_DIR",
    "JOBS_DIR",
    "CONFIG_FILE",
    "DEFAULT_CONFIG",
    "ensure_config",
    "json_input",
    "json_set",
]
