"""Opt-in WebGL1 registration, raw-input compilation and saved-row projection.

No file access, labels, threshold fitting or selection occurs here. The caller
must independently register a collector source and supply receipt-derived
session IDs. Old studies and their atom pools remain unchanged. The frozen
observer and candidate are reused, including their original WebGL2 diagnostics.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass

from .rule_learning.models import Atom
from .webgl1_parameter_candidate import CANDIDATE_REVISION, CANDIDATE_SCOPE, evaluate_webgl1_candidate

VERSION = "webgl1-selector-integration-v1"
CANDIDATE_ID = "RSR-WEBGL1-PARAMETER-EQUIVALENCE-v1"
FIELD = "app.collection_observations.webgl_parameter.observation"
COLLECTION_REVISION = "featureapp-webgl-parameter-collection-v1"
COLLECTOR_VERSION_CODE = 14
COLLECTOR_VERSION_NAME = "1.6.7-expanded-v2.2-webgl1"
GATE_VERSION = "webgl1-parameter-quality-gate-v1"


@dataclass(frozen=True)
class SourceRegistration:
    """External reviewed source reference, never constructed from payload claims."""
    source_reference: str
    collector_version_code: int = COLLECTOR_VERSION_CODE
    collector_version_name: str = COLLECTOR_VERSION_NAME
    collection_revision: str = COLLECTION_REVISION


def registered_atom():
    return Atom(CANDIDATE_ID, "webgl_parameter_equivalence", ("app_web67",),
                ("REGISTERED_WEBGL_PARAMETER_OBSERVATION_V1",), (CANDIDATE_ID,),
                "SAVED_SEMANTIC_STATE", {
                    "field": FIELD, "field_refs": [FIELD], "signal_group": "graphics_identity",
                    "candidate_id": CANDIDATE_ID, "candidate_revision": CANDIDATE_REVISION,
                    "candidate_scope": CANDIDATE_SCOPE, "registration_version": VERSION,
                    "input_schema_version": "webgl-parameter-equivalence-observation-v1",
                    "observer_revision": "webgl-parameter-observer-v1",
                    "evaluator_revision": "webgl-parameter-equivalence-v1",
                    "collection_revision": COLLECTION_REVISION,
                    "gate_version": GATE_VERSION, "mode": "featureapp_main_frame_raw_v1",
                    "input_origin": "SAVED_CANDIDATE_RESULTS_NO_REEVALUATION",
                    "independent_cross_layer_evidence": False,
                })


def registered_semantics(atom, field, refs):
    """Structural selector identity; display names and raw GPU strings excluded."""
    expected = registered_atom().provenance
    keys = ("candidate_revision", "candidate_scope", "registration_version", "input_schema_version",
            "observer_revision", "evaluator_revision", "collection_revision", "gate_version",
            "mode", "input_origin", "signal_group", "independent_cross_layer_evidence")
    if field != FIELD or refs != [FIELD] or any(atom.provenance.get(k) != expected[k] for k in keys):
        raise ValueError("UNREGISTERED_WEBGL1_SEMANTIC_CONTRACT")
    predicate = {"operator": "STABLE_NUMERIC_VS_NUMERIC_STRING_NEQ", "operands": [FIELD],
                 "context": "webgl", "parameters": [37445, 37446], "control_parameter": 34921,
                 "sequence": ["numeric_before", "numeric_string", "numeric_after"],
                 "parameter_aggregation": "T_IF_ANY_VALID_CONFLICT_F_IF_BOTH_MATCH_ELSE_U",
                 "webgl2_decision_contribution": False}
    gate = {k: expected[k] for k in keys if k not in ("signal_group", "independent_cross_layer_evidence")}
    gate.update(external_source_and_session_required=True, original_full_envelope_required=True,
                preflight_errors="EMPTY", context_and_extension="OBSERVED_AVAILABLE",
                per_parameter_queries="OBSERVED_TYPED_ERROR_FREE", per_parameter_numeric_endpoints="STABLE",
                control="MATCH", global_gate_failure="U", invalid_or_unstable_parameter="U",
                valid_parameter_conflict_survives_other_parameter_unknown=True)
    # Adding a new field has no demonstrated semantic preference over another
    # predicate. Keep the existing score/quality policy and give no extra bonus.
    return predicate, gate, 0


def _saved(state, reason, diagnostics=None):
    return {"candidate_id": CANDIDATE_ID, "candidate_revision": CANDIDATE_REVISION,
            "registration_version": VERSION, "state": state,
            "value": {"T": True, "F": False}.get(state), "available": state in ("T", "F"),
            "evaluation_status": "OK", "reason": reason, "diagnostics": deepcopy(diagnostics or {})}


def compile_payload(raw_payload, *, expected_session_id, source_registration):
    """Compile a fresh raw App payload; missing/invalid source or envelope is U.

    Source/API/GPU/tool/phase/label metadata never enter the exported feature.
    A valid source gate does not attest to getter authenticity or attack truth.
    After context/control gates pass, one validated parameter conflict is T
    even if the other parameter is U; F requires both parameters to match.
    """
    if (type(source_registration) is not SourceRegistration
            or type(source_registration.source_reference) is not str or not source_registration.source_reference.strip()
            or type(source_registration.collector_version_code) is not int
            or source_registration.collector_version_code != COLLECTOR_VERSION_CODE
            or source_registration.collector_version_name != COLLECTOR_VERSION_NAME
            or source_registration.collection_revision != COLLECTION_REVISION):
        return _saved("U", "EXTERNAL_SOURCE_REGISTRATION_REQUIRED")
    if type(expected_session_id) is not str or not expected_session_id.strip():
        return _saved("U", "EXTERNAL_SESSION_BINDING_REQUIRED")
    if type(raw_payload) is not dict:
        return _saved("U", "RAW_PAYLOAD_INVALID")
    if raw_payload.get("session_id") != expected_session_id:
        return _saved("U", "RAW_SESSION_BINDING_MISMATCH")
    if raw_payload.get("collector_app") != "featureapp" or raw_payload.get("schema_version") != "expanded-v2.2-status":
        return _saved("U", "UNREGISTERED_RAW_SOURCE_SCHEMA")
    manifest = raw_payload.get("collection_manifest")
    if (type(manifest) is not dict
            or type(manifest.get("collector_version_code")) is not int
            or manifest.get("collector_version_code") != source_registration.collector_version_code
            or manifest.get("collector_version_name") != source_registration.collector_version_name
            or manifest.get("web_probe_revision") != "expanded-web-67-v2"):
        return _saved("U", "UNREGISTERED_COLLECTOR_VERSION")
    bundle = raw_payload.get("collection_observations")
    if type(bundle) is not dict or bundle.get("observation_schema_version") != "app-web-observations-v1":
        return _saved("U", "APP_OBSERVATIONS_MISSING_OR_INVALID")
    entry = bundle.get("webgl_parameter")
    if type(entry) is not dict or entry.get("collection_revision") != COLLECTION_REVISION:
        return _saved("U", "WEBGL_COLLECTION_MISSING_OR_UNREGISTERED")
    if entry.get("read_status") != "observed":
        return _saved("U", "WEBGL_OBSERVATION_NOT_OBSERVED", {"collection_read_status": entry.get("read_status"),
                                                           "collection_reason": entry.get("reason")})
    if entry.get("reason") is not None:
        return _saved("U", "WEBGL_COLLECTION_STATUS_CONTRADICTION")
    candidate = evaluate_webgl1_candidate(entry.get("observation"),
                                         expected_realm_binding="featureapp:" + expected_session_id + ":main-frame")
    return _saved(candidate["state"], candidate["reason"], {
        "webgl1": candidate["webgl1"], **candidate["diagnostics"],
        "candidate_scope": candidate["candidate_scope"]})


def kernel_cell(saved):
    """Use only a validated saved result, without re-evaluating an observation."""
    if (type(saved) is not dict or saved.get("candidate_id") != CANDIDATE_ID
            or saved.get("candidate_revision") != CANDIDATE_REVISION
            or saved.get("registration_version") != VERSION):
        raise ValueError("SAVED_WEBGL1_IDENTITY_MISMATCH")
    s = saved.get("state")
    if (type(s) is not str or s not in ("T", "F", "U") or saved.get("evaluation_status") != "OK"
            or saved.get("value") is not {"T": True, "F": False, "U": None}[s]
            or saved.get("available") is not (s != "U")
            or type(saved.get("reason")) is not str or not saved["reason"]):
        raise ValueError("SAVED_WEBGL1_STATE_INVALID")
    return {k: deepcopy(saved[k]) for k in ("value", "available", "evaluation_status", "reason")}


def register_definitions(base_definitions):
    """Explicit opt-in extension, preserving every existing atom and allowlist."""
    from .rule_learning_v2.adapter import approved_atoms
    result = deepcopy(base_definitions)
    if any(a["atom_id"] == CANDIDATE_ID for a in result["atoms"]):
        raise ValueError("WEBGL1_ALREADY_REGISTERED")
    approved_atoms(result)
    result["atoms"].append(asdict(registered_atom()))
    result["single_surface_allowlists"]["app_web67"].append(CANDIDATE_ID)
    approved_atoms(result)
    return result


def project_rows(base_rows, registered_definitions, candidate_rows):
    """No row filtering, default F, label lookup, fit, or candidate re-execution."""
    from .rule_learning_v2.adapter import approved_atoms
    atoms = approved_atoms(registered_definitions)
    registered = next((a for a in atoms if a.atom_id == CANDIDATE_ID), None)
    if registered is None:
        raise ValueError("WEBGL1_DEFINITION_REQUIRED")
    registered_semantics(registered, registered.provenance.get("field"), registered.provenance.get("field_refs"))
    if type(base_rows) is not dict or type(candidate_rows) is not dict or set(base_rows) != set(candidate_rows):
        raise ValueError("EXACT_SAVED_WEBGL1_MEMBERS_REQUIRED")
    return {sid: {**{a.atom_id: deepcopy(raw[a.atom_id]) for a in atoms if a.atom_id != CANDIDATE_ID},
                  CANDIDATE_ID: kernel_cell(candidate_rows[sid])} for sid, raw in base_rows.items()}
