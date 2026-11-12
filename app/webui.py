"""Web UI launcher for the API server.

Two modes, chosen automatically by ``PCC_WEB_UI`` (default ``auto``):

* **Production** - when ``web-ui/dist/index.html`` exists (run ``npm run build``
  inside ``web-ui`` once), the static build is served by the API process itself
  and the browser opens on the API origin. No Node.js needed at run time.
* **Development** - otherwise the Vite dev server (``npm run dev``) is spawned
  in ``web-ui`` and the browser opens on http://localhost:3100. Dependencies
  are installed automatically the first time.

Set ``PCC_WEB_UI=off`` (or pass ``--no-web``) to disable both the launcher and
the automatic browser window.
"""
from __future__ import annotations

import logging
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import List, Optional

from .config import BASE_DIR

log = logging.getLogger(__name__)

WEBUI_DIR = BASE_DIR / "web-ui"
DIST_DIR = WEBUI_DIR / "dist"
DEV_PORT = 3100
READY_TIMEOUT_S = 90.0


def web_ui_enabled(mode: Optional[str]) -> bool:
    """True unless the user turned the web UI off."""
    return str(mode or "auto").strip().lower() not in {"0", "off", "false", "no"}


def mount_static_webui(app) -> bool:
    """Serve the production build of the web UI from the API process.

    Registered last, so /docs, /api/v1/* and /health keep precedence.
    Returns False when no build exists.
    """
    index = DIST_DIR / "index.html"
    if not index.is_file():
        return False

    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from starlette.staticfiles import StaticFiles

    assets = DIST_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="webui-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def webui_spa(full_path: str):
        # Unknown API paths must stay JSON 404s, not the SPA index.
        if full_path.startswith(("api/", "docs", "redoc", "openapi", "health")):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (DIST_DIR / full_path).resolve()
        if full_path and candidate.is_file() and str(candidate).startswith(str(DIST_DIR)):
            return FileResponse(candidate)
        # Client-side routes (/cameras, /reports, ...) fall back to the SPA.
        return FileResponse(index)

    log.info("Serving web UI build from %s", DIST_DIR)
    return True


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _npm_command() -> Optional[str]:
    return shutil.which("npm") or shutil.which("npm.cmd")


def start_dev_webui() -> Optional[subprocess.Popen]:
    """Spawn the Vite dev server; returns None when that is not possible.

    If the port is already serving, a dev server is assumed to be running and
    nothing new is started.
    """
    if not (WEBUI_DIR / "package.json").is_file():
        log.info("No web UI sources at %s - skipping", WEBUI_DIR)
        return None
    if _port_in_use(DEV_PORT):
        log.info("Web UI dev server already running on port %d", DEV_PORT)
        return None
    npm = _npm_command()
    if npm is None:
        log.warning("npm not found on PATH - start the web UI manually (cd web-ui && npm run dev)")
        return None
    if not (WEBUI_DIR / "node_modules").is_dir():
        log.info("Installing web UI dependencies (first run, npm install)...")
        result = subprocess.run(
            [npm, "install", "--no-audit", "--no-fund"],
            cwd=str(WEBUI_DIR),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log.warning("npm install failed: %s", (result.stderr or "").strip()[:400])
            return None
    try:
        proc = subprocess.Popen(
            [npm, "run", "dev", "--", "--strictPort"],
            cwd=str(WEBUI_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        log.warning("Could not start the web UI dev server: %s", exc)
        return None
    log.info("Web UI dev server starting on http://localhost:%d (pid %d)", DEV_PORT, proc.pid)
    return proc


def _wait_http(url: str, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return True
        except (urllib.error.URLError, OSError, ValueError):
            pass
        time.sleep(0.5)
    return False


def open_browser_when_ready(target_url: str, probe_url: str) -> threading.Thread:
    """Open ``target_url`` in the browser once ``probe_url`` answers."""

    def _run() -> None:
        if _wait_http(probe_url, READY_TIMEOUT_S):
            webbrowser.open(target_url)
            log.info("Web UI opened at %s", target_url)
        else:
            log.warning("Web UI not ready yet - open %s manually", target_url)

    thread = threading.Thread(target=_run, name="webui-opener", daemon=True)
    thread.start()
    return thread


def launch_webui(app, settings, host: str, port: int) -> Optional[subprocess.Popen]:
    """One-call helper used by the server entry point.

    Mounts the static build when present, otherwise spawns the dev server.
    Returns the dev-server process (if one was spawned) so the caller can
    stop it on shutdown.
    """
    if not web_ui_enabled(settings.web_ui):
        log.info("Web UI launcher disabled (PCC_WEB_UI=%s)", settings.web_ui)
        return None

    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
    api_url = f"http://{browser_host}:{port}"

    if mount_static_webui(app):
        open_browser_when_ready(f"{api_url}/", f"{api_url}/health")
        return None

    proc = start_dev_webui()
    if proc is not None or _port_in_use(DEV_PORT):
        dev_url = f"http://localhost:{DEV_PORT}/"
        open_browser_when_ready(dev_url, dev_url)
        return proc
    return None


def stop_dev_webui(proc: Optional[subprocess.Popen]) -> None:
    """Terminate the spawned Vite dev server, if we own one."""
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
        log.info("Web UI dev server stopped")
    except Exception:  # pragma: no cover - best effort
        try:
            proc.kill()
        except Exception:
            pass
