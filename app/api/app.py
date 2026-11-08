"""FastAPI application factory."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..bootstrap import ensure_default_admin
from ..config import Settings, get_settings
from ..engine.runtime import EngineRuntime
from .v1.routers import auth, cameras, counts, reports, users, ws, zones
from .ws_manager import get_broadcaster

log = logging.getLogger(__name__)
API_PREFIX = "/api/v1"


def create_app(runtime: Optional[EngineRuntime] = None, settings: Optional[Settings] = None,
               manage_runtime: bool = True) -> FastAPI:
    """Build the FastAPI application.

    ``manage_runtime`` controls whether the app owns the runtime lifecycle.
    The standalone server starts and stops the engine itself, the embedded
    server does not: the desktop app owns the runtime, so stopping the API
    must not tear down the camera manager the GUI is still using.
    """
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine_runtime = getattr(app.state, "runtime", None) or runtime or EngineRuntime(settings)
        app.state.runtime = engine_runtime
        broadcaster = get_broadcaster()
        broadcaster.bind_loop(asyncio.get_running_loop())
        engine_runtime.subscribe_counts(
            lambda event: broadcaster.publish_threadsafe("counts", event.to_dict())
        )
        if manage_runtime:
            engine_runtime.start()
        ensure_default_admin(engine_runtime.db, settings)
        log.info("API ready on %s", API_PREFIX)
        try:
            yield
        finally:
            if manage_runtime:
                engine_runtime.stop()

    app = FastAPI(
        title=settings.app_name + " API",
        description="People counting system - REST and WebSocket API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)
    app.include_router(cameras.router, prefix=API_PREFIX)
    app.include_router(zones.router, prefix=API_PREFIX)
    app.include_router(counts.router, prefix=API_PREFIX)
    app.include_router(reports.router, prefix=API_PREFIX)
    app.include_router(ws.router, prefix=API_PREFIX)

    @app.get("/health", tags=["system"])
    def health(request: Request) -> dict:
        engine_runtime = getattr(request.app.state, "runtime", None)
        return {
            "status": "ok",
            "version": "1.0.0",
            "engine_running": bool(engine_runtime and engine_runtime._started),
            "detector_available": bool(engine_runtime and engine_runtime.detector.available),
        }

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):  # pragma: no cover
        log.exception("Unhandled API error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app
