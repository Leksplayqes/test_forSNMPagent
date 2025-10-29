"""Pydantic models used by API endpoints."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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


__all__ = [
    "LogEntry",
    "LogsResponse",
    "LoopbackSettings",
    "ViaviTypeOfPort",
    "ViaviUnitSettings",
    "ViaviSettings",
    "DeviceInfoRequest",
    "TestsRunRequest",
]
