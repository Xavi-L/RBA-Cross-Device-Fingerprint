"""Future loopback backend with isolated files and browser-origin protection.

This entry point does not change the wrapper used by the archived pilot.
Run it only after the current backend has stopped; it uses the same loopback
port but a fresh data directory and separate stop/lifecycle files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import TYPE_CHECKING

from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

if TYPE_CHECKING:
    from fastapi import FastAPI


ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / "upstream"
DATA = ROOT / "data"
STOP = ROOT / "backend.stop"
SUMMARY = ROOT / "backend_lifecycle_summary.json"
ALLOWED_ORIGIN = "http://127.0.0.1:8001"


class OriginGuardMiddleware:
    """Reject foreign browser origins before any HTTP handler executes."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            origins = [value for name, value in scope.get("headers", []) if name.lower() == b"origin"]
            if any(origin != ALLOWED_ORIGIN.encode("ascii") for origin in origins):
                response = JSONResponse({"detail": "Origin not allowed"}, status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def configure_origins(app: FastAPI) -> None:
    """Replace inherited CORS before startup, preserving every other middleware.

    CORS limits which responses a browser can read. The outer Origin guard
    also prevents foreign simple POST requests from reaching write handlers.
    Native Android requests without an Origin header continue normally.
    """
    if app.middleware_stack is not None:
        raise RuntimeError("Configure the Origin policy before serving requests.")
    app.user_middleware = [item for item in app.user_middleware if item.cls is not CORSMiddleware]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ALLOWED_ORIGIN],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "ngrok-skip-browser-warning"],
    )
    app.add_middleware(OriginGuardMiddleware)


def write_lifecycle_summary(elapsed_seconds: float) -> None:
    """Record the upstream batch's actual shutdown state without overwriting."""
    ledger_path = DATA / "collection_batches.jsonl"
    rows = []
    if ledger_path.exists():
        rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    starts = [row for row in rows if row.get("event") == "started"]
    closes = [row for row in rows if row.get("event") == "closed"]
    closed_cleanly = (
        len(starts) == len(closes) == 1
        and starts[0].get("collection_batch_id") == closes[0].get("collection_batch_id")
        and closes[0].get("lifecycle_status") == "closed_cleanly"
    )
    summary = {
        "schema_version": "rba-browser-pilot-backend-lifecycle-v1",
        "elapsed_seconds": round(elapsed_seconds, 3),
        "started_event_count": len(starts),
        "closed_event_count": len(closes),
        "closed_cleanly": closed_cleanly,
        "active_marker_removed": not (DATA / "active_collection_batch.json").exists(),
        "allowed_browser_origin": ALLOWED_ORIGIN,
        "foreign_origin_rejected_before_handler": True,
    }
    with SUMMARY.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(summary, indent=2) + "\n")


def main() -> None:
    """Start one fresh restricted batch and shut down cooperatively on STOP."""
    import uvicorn

    if STOP.exists() or SUMMARY.exists():
        raise RuntimeError("Restricted lifecycle artifacts already exist; use a fresh run directory.")
    DATA.mkdir(exist_ok=False)
    os.environ["HYBRIDGUARD_DATA_DIR"] = str(DATA)
    os.environ["HYBRIDGUARD_BROWSER_PROBE_ORIGINS"] = ALLOWED_ORIGIN
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(UPSTREAM / "backend_server"), str(UPSTREAM)]
    os.chdir(UPSTREAM / "backend_server")
    from main import app

    configure_origins(app)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000, workers=1))
    finished = threading.Event()

    def request_shutdown() -> None:
        while not finished.wait(0.25):
            if STOP.exists() and server.started:
                server.should_exit = True
                return

    watcher = threading.Thread(target=request_shutdown, name="rba-restricted-stop-watcher", daemon=True)
    watcher.start()
    started = time.monotonic()
    try:
        server.run()
    finally:
        finished.set()
        watcher.join(timeout=1)
        write_lifecycle_summary(time.monotonic() - started)


if __name__ == "__main__":
    main()
