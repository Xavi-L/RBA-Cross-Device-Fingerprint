"""Explicit WebGL1-only candidate semantics; not registered with a selector.

The v1 envelope, external realm binding and WebGL1 quality gates remain intact.
WebGL2 outcomes remain diagnostics and never supply this candidate's state.
"""
from __future__ import annotations

from typing import Any

from .webgl_parameter_equivalence import evaluate_observation

CANDIDATE_REVISION = "webgl1-parameter-equivalence-candidate-v1"
CANDIDATE_SCOPE = "webgl1-vendor-renderer-numeric-string-equivalence"


def evaluate_webgl1_candidate(observation: Any, *, expected_realm_binding: str) -> dict:
    """Return T for a verified WebGL1 conflict, F for WebGL1 match, else U.

F means this specific conflict was not observed. It is not a conclusion about
WebGL2, attack intent, GPU identity, or the final detector decision.
"""
    full = evaluate_observation(observation, expected_realm_binding=expected_realm_binding)
    selected = full["contexts"].get("webgl")
    if selected is None:
        selected = {"outcome": "UNKNOWN", "reason": full["reason"]}
    outcome = selected["outcome"]
    return {
        "candidate_revision": CANDIDATE_REVISION,
        "candidate_scope": CANDIDATE_SCOPE,
        "decision_role": "research_candidate_not_registered",
        "outcome": outcome,
        "state": {"COUNTEREXAMPLE": "T", "MATCH": "F", "UNKNOWN": "U"}[outcome],
        "reason": selected["reason"],
        "webgl1": selected,
        "diagnostics": {
            "full_observation_outcome": full["outcome"],
            "envelope_evaluator_revision": full["evaluator_revision"],
            "webgl2": full["contexts"].get("webgl2"),
        },
    }
