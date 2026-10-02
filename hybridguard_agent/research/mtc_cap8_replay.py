"""Read-only CAP8 replay on explicitly registered historical MTC observations.

The original raw-only CAP8 entry is unchanged.  This adapter reuses its saved
encoder, predicates and three-valued predictor, but never claims that a legacy
projection is a raw webdriver or WebGL observation.  Labels, identities and
device descriptions remain outside the feature projection.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from . import rule_semantics_webgl1_cap8 as cap8
from . import webgl1_selector_integration as webgl
from .rule_learning.baselines import transform_numeric
from .rule_learning.contracts import cell, ledger
from .rule_learning.matrix import (Unavailable, field_state,
                                   mapped_state, measurement_domain, original_relation)
from .rule_learning.predictor import predict
from .rule_semantics_revision_v1.contracts import INPUT_SCHEMA_VERSION, SourceBinding
from .rule_semantics_revision_v1.language import web_language_first_difference
from .rule_semantics_revision_v1.webdriver import LEGACY_MODE, RAW_MODE, webdriver_reported_state

VERSION = "mtc-cap8-historical-replay-v1"
HISTORICAL_SCHEMA = "hybridguard-mtc-observation-v2"
HISTORICAL_PROBE = "expanded-web-67-v1"
HISTORICAL_SOURCE_COMMIT = "134201114a8a15a682bb41ee94c796d14e550c9e"
REGISTERED_COLLECTORS = {
    9: "1.6.2-expanded-v2.2-mtc",
    11: "1.6.4-expanded-v2.2-mtc-https",
}
_SECTIONS = ("features", "field_status", "field_quality")
_PREFIX = "app.web_data."
_SOURCE_CONTRACT = "mtc-20260922-featureapp-v9-v11-expanded-web-67-v1"
_LANG_BINDING = SourceBinding(_SOURCE_CONTRACT, "navigator_sync_v1")
_WD_BINDING = SourceBinding(_SOURCE_CONTRACT, "webdriver_legacy_projection_v1")
_NUMERIC_UNITS = {
    _PREFIX + "automation_surface_layer.mime_types_count": "reported MIME entry count",
    _PREFIX + "execution_layer.timezone_offset": "minutes, JS Date.getTimezoneOffset (UTC minus local)",
    _PREFIX + "navigator_layer.device_memory": "navigator.deviceMemory approximate rounded/clamped GiB exposure",
    _PREFIX + "navigator_layer.hardware_concurrency": "logical processor count exposure",
    _PREFIX + "screen_layer.device_pixel_ratio": "CSS-to-device pixel ratio (dimensionless)",
}


def _validate_historical(record):
    if (type(record) is not dict or record.get("record_schema_version") != HISTORICAL_SCHEMA
            or any(type(record.get(s)) is not dict for s in _SECTIONS)):
        raise ValueError("HISTORICAL_MTC_ENVELOPE_REQUIRED")
    if record.get("source_observation_mode", LEGACY_MODE) != LEGACY_MODE:
        raise PermissionError("HISTORICAL_REPLAY_CANNOT_ACCEPT_RAW_MODE")
    app = record.get("app")
    if type(app) is not dict:
        raise ValueError("HISTORICAL_COLLECTOR_METADATA_REQUIRED")
    code = app.get("collector_version_code")
    if (type(code) is not int or code not in REGISTERED_COLLECTORS
            or app.get("collector_version_name") != REGISTERED_COLLECTORS[code]):
        raise ValueError("UNREGISTERED_HISTORICAL_COLLECTOR")


def _projection(record, refs, *, semantic=False):
    # rsr-input-v1 describes this in-memory semantic envelope, not a collector
    # upgrade or raw_observation_v1. The webdriver mode remains explicit legacy.
    return {"record_schema_version": INPUT_SCHEMA_VERSION if semantic else HISTORICAL_SCHEMA,
            **{s: {p: deepcopy(record[s][p]) for p in refs if p in record[s]} for s in _SECTIONS}}


def measure_historical_numeric(record, field):
    """Use the existing fixed field gate, including legacy navigator-zero U.

    Values are never coerced, rescaled or filled. Wrong types are U; malformed
    state enums are execution/contract failures, as in the original kernel.
    """
    _validate_historical(record)
    if field not in _NUMERIC_UNITS:
        raise ValueError("UNREGISTERED_HISTORICAL_NUMERIC_FIELD:" + str(field))
    payload = _projection(record, [field])
    try:
        fs = field_state(payload, {"field": field, "type": "number"})
        if not fs["available"]:
            return dict(cell("U", fs["reason"]), field_state=fs)
        return {"value": deepcopy(payload["features"][field]), "available": True,
                "evaluation_status": "OK", "reason": "OBSERVED_FIXED_CONTROL_INPUT", "field_state": fs}
    except Exception as exc:
        return cell("FAILED", type(exc).__name__ + ":" + str(exc))


@lru_cache(maxsize=1)
def _ua_definitions():
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / "config/paired244_rule_catalog.v3.json").read_text())
    rule = next(r for r in catalog["rules"] if r["rule_id"] == "NW-006")
    candidate = next(c for c in ledger() if c["atom_id"] == "CAT:NW-006")
    return candidate, rule


def _measure_ua(record, atom):
    candidate, rule = _ua_definitions()
    if (atom.provenance.get("condition") != candidate["measurement"]["condition"]
            or atom.provenance.get("field_refs") != candidate["dependencies"]):
        raise ValueError("SAVED_UA_SEMANTICS_MISMATCH")
    payload = _projection(record, candidate["dependencies"])
    try:
        gates = {s["field"]: field_state(payload, s) for s in candidate["dependency_schema"]}
        for gate in gates.values():
            if not gate["available"]:
                raise Unavailable(gate["reason"])
        measurement_domain(candidate, payload)
        original = original_relation(rule, payload)
        s = mapped_state(candidate, original["outcome"])
        return dict(cell(s, "CONDITION_DEFINED" if s != "U" else original["reason"]),
                    relation_result=original, field_states=gates)
    except Unavailable as exc:
        return cell("U", exc.reason)
    except Exception as exc:
        return cell("FAILED", type(exc).__name__ + ":" + str(exc))


def _field_observations(record, refs):
    return [{"field": field, "original_path": field.removeprefix("app."),
             "value_present": field in record["features"],
             "value": deepcopy(record["features"].get(field)),
             "source_status": deepcopy(record["field_status"].get(field)),
             "source_quality": deepcopy(record["field_quality"].get(field))} for field in refs]


def model_input_mapping(model):
    """Small per-selected-rule map; no MTC outcomes or model selection involved."""
    result = []
    for atom in model.atoms:
        refs = atom.provenance.get("field_refs", [atom.provenance.get("field")])
        if not refs or any(type(p) is not str for p in refs):
            raise ValueError("SAVED_ATOM_FIELD_REFERENCE_REQUIRED")
        field = atom.provenance.get("field")
        unavailable = None
        if atom.atom_id == webgl.CANDIDATE_ID:
            meaning = "WebGL1 numeric / numeric-string / numeric query comparison"
            availability = "unavailable_in_registered_legacy_collectors"
            unavailable = "LEGACY_WEBGL1_RAW_QUERY_OBSERVATION_ABSENT"
            limits = "GPU vendor/renderer strings cannot reconstruct these queries."
        elif atom.atom_id == cap8.WD_ID:
            meaning = "legacy navigator.webdriver === true projection"
            availability = "true_evaluable_false_unknown"
            limits = "False also represents absent/nonboolean property; legacy false remains U."
        elif atom.atom_id == cap8.LANG_ID:
            meaning = "same synchronous navigator read: language versus languages[0]"
            availability = "conditional_on_observed_typed_supported_tags"
            limits = "No trimming or broad language normalization; frozen supported tag domain."
        elif atom.atom_id == "CAT:NW-006":
            meaning = "frozen desktop/script UA or desktop platform predicate"
            availability = "conditional_on_observed_interpretable_UA_and_platform"
            limits = "Both parser classes must be interpretable under original NW-006 domain."
        elif atom.orientation == "CONTROL_LE" and field in _NUMERIC_UNITS:
            meaning = _NUMERIC_UNITS[field]
            availability = "conditional_on_observed_finite_number"
            limits = ("Legacy || 0 sentinel is U; positive exposure is not physical installed RAM."
                      if field.endswith((".device_memory", ".hardware_concurrency")) else
                      "Legacy MIME zero is the reported length-or-zero projection; API absence and empty list are not separable."
                      if field.endswith(".mime_types_count") else "No coercion or unit conversion; saved threshold/polarity unchanged.")
        else:
            raise ValueError("UNSUPPORTED_SELECTED_REPLAY_ATOM:" + atom.atom_id)
        result.append({"atom_id": atom.atom_id, "field_refs": refs,
                       "original_paths": [p.removeprefix("app.") for p in refs],
                       "collector_versions": deepcopy(REGISTERED_COLLECTORS),
                       "web_probe_revision": HISTORICAL_PROBE, "meaning": meaning,
                       "availability": availability, "unavailable_reason": unavailable,
                       "limitations": limits, "threshold": atom.provenance.get("threshold"),
                       "polarities": [l.polarity for c in model.clauses for l in c.literals if l.atom_id == atom.atom_id]})
    return result


def adapt_historical_mtc(model, record):
    """Build selected inputs from a P1 row without changing it or the model.

    Source bindings refer to the externally reviewed v9/v11 collector contract
    at HISTORICAL_SOURCE_COMMIT; they are not inferred from a sample's outcomes,
    labels, session identity or claimed device model.
    """
    _validate_historical(record)
    cap8._model_identity(model)
    mapping = {r["atom_id"]: r for r in model_input_mapping(model)}
    raw, candidates, inputs = {}, {}, {}
    for atom in model.atoms:
        aid = atom.atom_id
        refs = mapping[aid]["field_refs"]
        inputs[aid] = _field_observations(record, refs)
        if aid == webgl.CANDIDATE_ID:
            # These collector contracts predate the raw query observer. Even
            # an added GPU string or foreign raw key cannot upgrade that fact.
            candidates[aid] = webgl._saved("U", "LEGACY_WEBGL1_RAW_QUERY_OBSERVATION_ABSENT",
                                           {"source_mode": LEGACY_MODE, "collector_contract": _SOURCE_CONTRACT})
        elif aid == cap8.WD_ID:
            candidates[aid] = webdriver_reported_state(_projection(record, refs, semantic=True),
                                              mode=LEGACY_MODE, source_binding=_WD_BINDING).to_dict()
        elif aid == cap8.LANG_ID:
            candidates[aid] = web_language_first_difference(
                _projection(record, refs, semantic=True), source_binding=_LANG_BINDING).to_dict()
        elif aid == "CAT:NW-006":
            raw[aid] = _measure_ua(record, atom)
        elif atom.orientation == "CONTROL_LE":
            field = atom.provenance["field"]
            raw["UNFITTED_CONTROL:" + field] = measure_historical_numeric(record, field)
    return {"raw": raw, "candidate_cells": candidates, "rule_inputs": inputs,
            "adapter_version": VERSION, "source_observation_mode": LEGACY_MODE,
            "original_record_schema_version": record["record_schema_version"],
            "collector_version_code": record["app"]["collector_version_code"]}


def predict_replay(model, opaque_id, raw, candidate_cells=None, *, source_mode):
    """Explicit low-level mode routing; raw input retains the original gate.

    This is useful for parity tests on saved complete raw inputs. Production
    historical replay should use predict_historical_mtc so fields are compiled
    under the registered historical collector contract first.
    """
    if source_mode == RAW_MODE:
        result = cap8.predict_current(model, opaque_id, raw, candidate_cells, source_mode=source_mode)
    elif source_mode == LEGACY_MODE:
        cap8._model_identity(model)
        cap8.source_mode_manifest({opaque_id: source_mode}, [opaque_id])
        try:
            current = deepcopy(raw)
            selected = [a.atom_id for a in model.atoms]
            for aid in model.view["new_candidate_ids"]:
                if aid not in selected:
                    continue
                if type(candidate_cells) is not dict or aid not in candidate_cells:
                    raise ValueError("MISSING_HISTORICAL_CANDIDATE_CELL:" + aid)
                if aid == cap8.WD_ID:
                    cap8._check_cell_mode(candidate_cells[aid], source_mode)
                current[aid] = (webgl.kernel_cell(candidate_cells[aid]) if aid == webgl.CANDIDATE_ID
                                else cap8.kernel_cell(candidate_cells[aid], aid))
            encoded = transform_numeric(current, model.encoder, required_atoms=selected)
            result = predict(model, opaque_id, {"features": encoded, "view_id": model.view["view_id"]})
        except Exception as exc:
            result = predict(model, opaque_id, {})
            result.update(decision="FAILED", failure_reason="HISTORICAL_REPLAY:" + type(exc).__name__ + ":" + str(exc))
        result["source_observation_mode"] = source_mode
    else:
        raise PermissionError("EXPLICIT_LEGACY_OR_RAW_REPLAY_MODE_REQUIRED")
    result["adapter_version"] = VERSION
    return result


def predict_historical_mtc(model, record):
    """Replay one original P1 row; return rule values, reasons and final output."""
    opaque_id = record.get("sample_id", "missing-sample-id") if type(record) is dict else "invalid-record"
    try:
        adapted = adapt_historical_mtc(model, record)
        result = predict_replay(model, opaque_id, adapted["raw"], adapted["candidate_cells"], source_mode=LEGACY_MODE)
        explanations = {r["atom_id"]: r for r in result["atom_explanations"]}
        clauses = {r["clause_id"]: r for r in result["clause_explanations"]}
        details = []
        for clause in model.clauses:
            # The three retained CAP8 models contain exactly eight singleton
            # rules. Do not silently invent a per-atom attribution for a DNF.
            if len(clause.literals) != 1:
                raise ValueError("SINGLE_LITERAL_REPLAY_EXPLANATION_REQUIRED")
            literal = clause.literals[0]
            aid = literal.atom_id
            explanation = explanations.get(aid, {})
            c = clauses.get(clause.id, {})
            atom = next(a for a in model.atoms if a.atom_id == aid)
            raw_key = "UNFITTED_CONTROL:" + atom.provenance["field"] if atom.orientation == "CONTROL_LE" else aid
            original = adapted["candidate_cells"].get(aid, adapted["raw"].get(raw_key, {}))
            details.append({"atom_id": aid, "clause_id": clause.id, "polarity": literal.polarity,
                            "state": c.get("state") or "FAILED", "atom_state": explanation.get("state") or "FAILED",
                            "reason": explanation.get("reason", original.get("reason")),
                            "input_reason": original.get("reason"),
                            "input_evaluation_status": original.get("evaluation_status"),
                            "fields": adapted["rule_inputs"][aid], "triggered": c.get("state") == "T"})
        result.update(rule_results=details,
                      triggered_rules=[r["atom_id"] for r in details if r["triggered"]],
                      original_record_schema_version=adapted["original_record_schema_version"],
                      collector_version_code=adapted["collector_version_code"])
        return result
    except Exception as exc:
        result = predict(model, opaque_id, {})
        failure = "HISTORICAL_ADAPTER:" + type(exc).__name__ + ":" + str(exc)
        safe_record = {s: record[s] if type(record) is dict and type(record.get(s)) is dict else {} for s in _SECTIONS}
        by_id = {a.atom_id: a for a in model.atoms}
        details = []
        for clause in model.clauses:
            for literal in clause.literals:
                atom = by_id[literal.atom_id]
                refs = atom.provenance.get("field_refs", [atom.provenance.get("field")])
                details.append({"atom_id": atom.atom_id, "clause_id": clause.id, "polarity": literal.polarity,
                                "state": "FAILED", "atom_state": "FAILED", "reason": failure,
                                "input_reason": "ADAPTER_REJECTED_RECORD", "input_evaluation_status": "FAILED",
                                "fields": _field_observations(safe_record, [p for p in refs if type(p) is str]),
                                "triggered": False})
        result.update(decision="FAILED", failure_reason=failure,
                      adapter_version=VERSION, source_observation_mode=LEGACY_MODE,
                      rule_results=details, triggered_rules=[])
        return result
