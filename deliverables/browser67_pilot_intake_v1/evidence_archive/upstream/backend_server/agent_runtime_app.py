"""Standalone, read-only ASGI application for the deterministic Agent Runtime.

Use ``uvicorn agent_runtime_app:app`` from ``backend_server/`` when the
runtime must not activate the collector application's batch lifecycle.  The
existing ``main:app`` also mounts this router for integrated deployments, but
its collection lifecycle remains intentionally unchanged.
"""

from __future__ import annotations

from fastapi import FastAPI

try:
    from agent_runtime_api import router as agent_runtime_router
except ModuleNotFoundError:
    from backend_server.agent_runtime_api import router as agent_runtime_router


app = FastAPI(
    title="HybridGuard Deterministic Agent Runtime",
    description="Read-only evidence, deterministic rules, exact retrieval, and verification.",
    version="1.0.0",
)
app.include_router(agent_runtime_router)
