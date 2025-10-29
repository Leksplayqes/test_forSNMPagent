"""Shared mutable state containers used across backend modules."""
from __future__ import annotations

from subprocess import Popen
from typing import Any, Dict

UTIL_JOBS: Dict[str, Dict[str, Any]] = {}
RUNNING_UTIL_PROCS: Dict[str, Any] = {}
TEST_JOBS: Dict[str, Dict[str, Any]] = {}
RUNNING_PROCS: Dict[str, Popen] = {}

__all__ = [
    "UTIL_JOBS",
    "RUNNING_UTIL_PROCS",
    "TEST_JOBS",
    "RUNNING_PROCS",
]
