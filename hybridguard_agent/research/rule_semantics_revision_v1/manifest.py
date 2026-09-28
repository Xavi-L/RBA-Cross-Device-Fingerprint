"""Static identities for two standalone semantic modules; no experiment hooks."""

from __future__ import annotations

from types import MappingProxyType

from .contracts import INPUT_SCHEMA_VERSION, SOURCE_BINDING_VERSION, VERSION


CANDIDATES = MappingProxyType(
    {
        "RSR-LANG-FIRST-v1": MappingProxyType(
            {
                "version": VERSION,
                "gate_version": "rsr-language-first-gate-v1",
                "callable": "language.web_language_first_difference",
                "information_relation": "SAME_WEB_OBSERVATION_FIRST_ITEM_RELATION",
                "source_scopes": ("navigator_sync_v1",),
                "modes": (),
                "mode_gate_versions": MappingProxyType({}),
            }
        ),
        "RSR-WEBDRIVER-STATE-v1": MappingProxyType(
            {
                "version": VERSION,
                "gate_version": "rsr-webdriver-reported-state-gate-v1",
                "callable": "webdriver.webdriver_reported_state",
                "information_relation": "SINGLE_WEB_STATE_OBSERVATION",
                "source_scopes": ("webdriver_legacy_projection_v1", "webdriver_raw_observation_v1"),
                "modes": ("legacy_projection_v1", "raw_observation_v1"),
                "mode_gate_versions": MappingProxyType(
                    {
                        "legacy_projection_v1": "rsr-webdriver-legacy-gate-v1",
                        "raw_observation_v1": "rsr-webdriver-raw-gate-v1",
                    }
                ),
            }
        ),
    }
)


def module_manifest() -> dict:
    """Return a fresh JSON-compatible manifest without touching the filesystem."""
    return {
        "module": "rule_semantics_revision_v1",
        "version": VERSION,
        "input_schema_version": INPUT_SCHEMA_VERSION,
        "source_binding_version": SOURCE_BINDING_VERSION,
        "candidate_count": len(CANDIDATES),
        "candidates": {
            candidate_id: {
                key: (
                    list(value) if isinstance(value, tuple)
                    else dict(value) if isinstance(value, MappingProxyType)
                    else value
                )
                for key, value in entry.items()
            }
            for candidate_id, entry in CANDIDATES.items()
        },
        "webdriver_overlap": {
            "candidate_id": "RSR-WEBDRIVER-STATE-v1",
            "mode": "legacy_projection_v1",
            "branch": "observed/observed_value strict true with valid source binding",
            "old_rule_id": "W03",
            "old_atom_id": "CONTROL:app.web_data.automation_surface_layer.webdriver:EQ:True",
            "old_literal_id": "CONTROL:app.web_data.automation_surface_layer.webdriver:EQ:True:POSITIVE",
            "shared_discriminative_information": True,
            "independent_evidence_counting_allowed": False,
            "note": (
                "The legacy true branch shares W03's strict-true information. "
                "Legacy false -> U is a new report-state interpretation, not a "
                "correction to the old predicate or its historical outputs."
            ),
        },
        "source_binding_claim": "Caller-declared collection association; not getter integrity or authenticity proof.",
        "unknown_engine_policy": "No version-based gate for literal language consistency or reported webdriver value.",
        "mode_selection": "Explicit caller contract; never inferred from values or changed after a result.",
        "integration": "STANDALONE_OFFLINE_ONLY",
        "research_effectiveness": "NOT_EVALUATED",
        "historical_record_applicability": "NOT_AUDITED",
        "independent_confirmation": "NOT_PERFORMED",
    }
