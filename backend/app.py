"""Application factory and FastAPI wiring."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .common import router as common_router
from .device import router as device_router
from .tests_routes import router as tests_router, load_jobs_on_startup
from .utils_routes import router as utils_router


def create_app() -> FastAPI:
    app = FastAPI(title="OSM-K Tester API", version="4.5.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(common_router)
    app.include_router(device_router)
    app.include_router(tests_router)
    app.include_router(utils_router)

    @app.on_event("startup")
    async def _startup() -> None:  # pragma: no cover - FastAPI lifecycle
        load_jobs_on_startup()

    return app


app = create_app()

__all__ = ["app", "create_app"]
