"""Backend-facing adapter for the deterministic HybridGuard Agent Runtime.

This module deliberately has no dependency on ``backend_server.main``.  That
keeps the Agent Runtime read-only: importing or calling it cannot start a
collection batch, merge a session, or write any collection artifact.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


# ``uvicorn main:app`` is commonly launched after ``cd backend_server``.  In
# that mode Python cannot otherwise import the sibling ``hybridguard_agent``
# package at repository root.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from hybridguard_agent.adapters.rule_kb_adapter import KnowledgeDriftError
from hybridguard_agent.runtime.service import (
    RuntimeContractError,
    analyze_payload,
    runtime_readiness,
)


def analyze_agent_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Analyze one inline fingerprint payload without persisting it."""
    return analyze_payload(payload)


def get_agent_runtime_readiness() -> dict[str, Any]:
    """Return configuration readiness without creating runtime state."""
    return runtime_readiness()
