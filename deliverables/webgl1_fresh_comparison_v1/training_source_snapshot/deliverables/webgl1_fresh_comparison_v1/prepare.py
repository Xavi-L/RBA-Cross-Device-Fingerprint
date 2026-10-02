#!/usr/bin/env python3
"""Audit this fresh cohort and compile unfitted inputs; never fit or predict.

Labels come solely from declared intervention values, execution receipts and
paired restoration. Candidate values cannot admit, remove or label a member.
Incomplete and failed positions remain in the audit and block the whole cohort.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from hybridguard_agent.research.manipulation_eval.adapter import adapt_payload
from hybridguard_agent.research.rule_semantics_runtime_input import adapt_runtime_payload, RuntimeInputError
from hybridguard_agent.research.rule_semantics_runtime_matrix import measure_w0_base_inputs, W0_ATOM_IDS
from hybridguard_agent.research.rule_semantics_revision_v1 import web_language_first_difference, webdriver_reported_state
from hybridguard_agent.research.rule_semantics_revision_v1.contracts import SourceBinding, make_cell
from hybridguard_agent.research.rule_semantics_capacity import group_definitions
from hybridguard_agent.research import webgl1_selector_integration as webgl

EXPERIMENT = "webgl1-fresh-cap7-comparison-v1"
PHASES = ("clean_pre", "attack", "clean_post")
LANG_ID, WD_ID = "RSR-LANG-FIRST-v1", "RSR-WEBDRIVER-STATE-v1"
MODES = {"LANGUAGE": (LANG_ID, "navigator_sync_v1"),
         "WEBDRIVER_RAW": (WD_ID, "webdriver_raw_observation_v1")}
PROFILE_FIELDS = dict(zip(
    ("webdriver", "platform", "hardwareConcurrency", "deviceMemory", "userAgent",
     "webglVendor", "webglRenderer", "languages", "pluginsCount", "mimeTypesCount",
     "pluginsHash", "mimeTypesHash", "timezoneId", "timezoneOffset", "availWidth",
     "availHeight", "devicePixelRatio", "innerWidth", "innerHeight", "outerWidth",
     "outerHeight", "screenResolutionLogical", "visualViewportWidth", "visualViewportHeight"),
    ("webdriver", "platform", "hardware_concurrency", "device_memory", "user_agent",
     "webgl_vendor", "webgl_renderer", "languages", "plugins_count", "mime_types_count",
     "plugins_hash", "mime_types_hash", "timezone_id", "timezone_offset", "avail_width",
     "avail_height", "device_pixel_ratio", "inner_width", "inner_height", "outer_width",
     "outer_height", "screen_resolution_logical", "visual_viewport_width", "visual_viewport_height"), strict=True))
SCREEN_TOLERANCES = {"device_pixel_ratio": .01, "visual_viewport_width": 1, "visual_viewport_height": 1}


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()] if Path(path).exists() else []


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def unique(rows, key):
    result = {r[key]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError("DUPLICATE_" + key)
    return result


def same(left, right, tolerance=0):
    """JS-like typed equality, with only predeclared screen tolerances."""
    if left is None or right is None:
        return False
    numbers = type(left) in (int, float) and type(right) in (int, float)
    if numbers:
        return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= tolerance
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right, strict=True))
    return left == right


def observable(payload, field):
    matches = [(name, layer[field]) for name, layer in payload.get("web_data", {}).items()
               if isinstance(layer, dict) and field in layer]
    if len(matches) != 1:
        return None, False
    layer, value = matches[0]
    observed = payload.get("collection_status", {}).get("fields", {}).get("web_data." + layer + "." + field) == "observed"
    return value, observed


def audit_triplet(configuration, payloads, execution, session_ids):
    """Independent intervention audit. No candidate module or sidecar is read."""
    if len(payloads) != 3 or any(type(p) is not dict for p in payloads):
        return {"status": "INCOMPLETE", "reason": "THREE_RAW_PAYLOADS_REQUIRED"}
    fields = configuration["observableFields"]
    tolerances = SCREEN_TOLERANCES if configuration["id"] == "cdp_screen_metrics_only_v1" else {}
    values = [{f: observable(p, f)[0] for f in fields} for p in payloads]
    observed = all(observable(p, f)[1] for p in payloads for f in fields)
    expected = {PROFILE_FIELDS[k]: v for k, v in configuration["profile"].items()}
    profile = all(same(values[1].get(f), v, tolerances.get(f, 0)) for f, v in expected.items())
    if configuration["id"] == "stealth":
        languages, plugins = values[1].get("languages"), values[1].get("plugins_count")
        profile = profile and type(languages) is list and "en-US" in languages and "en" in languages
        profile = profile and type(plugins) in (int, float) and plugins > 0
    changed = [f for f in fields if not same(values[0][f], values[1][f], tolerances.get(f, 0))]
    restored = all(same(values[0][f], values[2][f], tolerances.get(f, 0)) for f in fields)
    execution = execution if isinstance(execution, dict) else {}
    executed = (execution.get("status") == "MEASURED"
                and execution.get("configId") == configuration["configId"]
                and execution.get("configurationId") == configuration["id"]
                and execution.get("measuredSessionIds") == [session_ids[1]]
                and execution.get("injected") == configuration["profile"]
                and execution.get("declaredObservableFields") == fields
                and execution.get("declaredStealthEvasions") == configuration.get("stealthEvasions"))
    if configuration.get("cdpEmulation"):
        executed = (executed and execution.get("declaredCdpEmulation") == configuration["cdpEmulation"]
                    and execution.get("cdpEmulation", {}).get("rollback", {}).get("rollback_verified") is True)
    checks = {"declared_fields_observed": observed, "active_profile_observed": bool(profile),
              "declared_effect_present": bool(changed), "declared_fields_restored": restored,
              "execution_receipt_valid": executed}
    return {"status": "PASS" if all(checks.values()) else "REVIEW_REQUIRED", **checks,
            "changed_declared_fields": changed, "declared_values": dict(zip(PHASES, values, strict=True)),
            "tolerances": {f: tolerances.get(f, 0) for f in fields}}


def metadata_contract():
    # Definitions and measurement specifications only; no historical rows.
    frozen = ROOT / "hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R04_freeze_r1"
    protocol = frozen / "snapshot/hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol"
    return {"definitions": read(frozen / "data/definitions.json"),
            "candidate_definitions": lines(protocol / "CANDIDATE_LEDGER.jsonl"),
            "control_specs": read(protocol / "SINGLE_SURFACE_FIELDS.json")["fields"],
            "rule_definitions": read(ROOT / "hybridguard_agent/config/paired244_rule_catalog.v3.json")["rules"]}


def compile_record(payload, *, expected_session_id, source_reference, measurement_contract):
    """Pure compilation with caller/receipt-owned binding; preserve U/FAILED."""
    bindings = {mode: SourceBinding(source_reference, scope,
                 observer_revision="app-webdriver-observer-v1" if mode == "WEBDRIVER_RAW" else None,
                 realm_binding="featureapp:" + expected_session_id + ":main-frame" if mode == "WEBDRIVER_RAW" else None)
                for mode, (_, scope) in MODES.items()}
    adapted = adapt_runtime_payload(payload, expected_session_id=expected_session_id, source_bindings=bindings)
    cells = {}
    for mode, (cid, _) in MODES.items():
        try:
            projected, binding = adapted.input_for(mode)
            cell = (web_language_first_difference(projected, binding) if mode == "LANGUAGE" else
                    webdriver_reported_state(projected, mode="raw_observation_v1", source_binding=binding))
        except RuntimeInputError as error:
            cell = make_cell(cid, error.state, error.reason,
                             diagnostics={"mode": "raw_observation_v1"} if mode == "WEBDRIVER_RAW" else {})
        cells[cid] = cell.to_dict()
    cells[webgl.CANDIDATE_ID] = webgl.compile_payload(payload, expected_session_id=expected_session_id,
        source_registration=webgl.SourceRegistration(source_reference))
    errors = []
    try:
        full = adapt_payload(payload)
        if len(full["features"]) != 177:
            raise ValueError("FULL_APP177_REQUIRED")
        features = measure_w0_base_inputs(full, **measurement_contract)
    except (ValueError, TypeError, KeyError) as error:
        errors.append(type(error).__name__ + ": " + str(error))
        features = {name: {"value": None, "available": False, "evaluation_status": "FAILED",
                           "reason": "RAW_BASE_COMPILATION_FAILED"} for name in sorted(W0_ATOM_IDS)}
    return {"observation_mode": "raw_observation_v1", "features": features, "candidate_cells": cells,
            "source_bindings": {m: asdict(b) for m, b in bindings.items()}, "compilation_errors": errors}


def make_folds(metadata):
    """Exact environment-held-out partition; never drop failed/missing members."""
    environments = sorted({row["environment_group_id"] for row in metadata.values()})
    configs = {row["config_id"] for row in metadata.values()}
    if len(metadata) != 378 or len(environments) != 3 or len(configs) != 14:
        raise ValueError("EXACT_378_THREE_ENV_FOURTEEN_CONFIG_MEMBERS_REQUIRED")
    seen = set()
    for row in metadata.values():
        key = (row["environment_group_id"], row["config_id"], row["triplet_id"], row["phase"])
        if key in seen:
            raise ValueError("DUPLICATE_TRIPLET_PHASE")
        seen.add(key)
    folds = []
    for number, env in enumerate(environments, 1):
        train = sorted(i for i, m in metadata.items() if m["environment_group_id"] != env)
        test = sorted(set(metadata) - set(train))
        if len(train) != 252 or len(test) != 126:
            raise ValueError("UNBALANCED_ENVIRONMENT_FOLD")
        groups = defaultdict(list)
        for i in test:
            groups[metadata[i]["config_id"]].append(metadata[i])
        if set(groups) != configs:
            raise ValueError("MISSING_FOLD_CONFIGURATION")
        for rows in groups.values():
            trios = defaultdict(set)
            for row in rows:
                trios[row["triplet_id"]].add(row["phase"])
            if len(rows) != 9 or len(trios) != 3 or any(p != set(PHASES) for p in trios.values()):
                raise ValueError("EXACT_THREE_COMPLETE_TRIPLETS_REQUIRED")
        if {metadata[i]["bundle_id"] for i in train} & {metadata[i]["bundle_id"] for i in test}:
            raise ValueError("BUNDLE_LEAKAGE")
        folds.append({"fold_id": f"WEBGL1-LOEO-v1-{number:02}", "heldout_environment": env,
                      "train_ids": train, "outer_test_ids": test})
    return folds


def _association_issues(step, saved, attempt, raw, receipt, exported, registration, api):
    if not all(isinstance(v, dict) for v in (saved, attempt, raw, receipt, exported)):
        return ["MISSING_COLLECTION_ASSOCIATION"]
    sid = receipt.get("session_id")  # External receipt owns the expected session.
    payload = raw.get("canonical_received_payload", {})
    manifest = payload.get("collection_manifest", {})
    checks = {
        "ACCEPTED_ATTEMPT": saved.get("accepted") is True and attempt.get("status") == "ACCEPTED",
        "SESSION_ASSOCIATION": bool(sid) and raw.get("session_id") == payload.get("session_id") ==
             saved.get("observation", {}).get("session_id") == attempt.get("session_id") == exported.get("session_id") == sid,
        "RECEIPT_ASSOCIATION": raw.get("receipt_id") == receipt.get("receipt_id") and
             raw.get("collection_batch_id") == receipt.get("collection_batch_id") and
             receipt.get("validation_status") == "accepted" and receipt.get("raw_payload_archived") is True,
        "PHASE_ASSOCIATION": saved.get("phase") == attempt.get("phase") == step["phase"] and
             saved.get("step_id") == attempt.get("step_id") == step["step_id"],
        "CONTEXT_ASSOCIATION": manifest.get("runtime_context") == saved.get("runtime_context") == step["runtime_context"],
        "FRESH_REGISTERED_INSTALL": manifest.get("collector_install_id") == registration.get("identity", {}).get("collector_install_id")
             and bool(registration.get("identity", {}).get("collector_install_id")) and manifest.get("android_api") == api,
        "REGISTERED_IDENTITY": bool(registration.get("identity")) and all(
             manifest.get(k) == v and v not in (None, "") for k, v in registration.get("identity", {}).items()),
        "V14_SOURCE": payload.get("schema_version") == "expanded-v2.2-status" and payload.get("collector_app") == "featureapp"
             and type(manifest.get("collector_version_code")) is int and manifest["collector_version_code"] == 14
             and manifest.get("collector_version_name") == webgl.COLLECTOR_VERSION_NAME
             and manifest.get("web_probe_revision") == "expanded-web-67-v2",
        "OBSERVATION_STORAGE_ROUNDTRIP": payload.get("collection_observations") == exported.get("collection_observations"),
    }
    return [name for name, passed in checks.items() if not passed]


def cell_state(cell):
    if cell["evaluation_status"] == "FAILED":
        return "FAILED"
    if not cell["available"]:
        return "U"
    return "T" if cell["value"] else "F"


def prepare(output, *, directory=HERE):
    """Read only this protocol's newly collected runs, retaining every position."""
    directory, output = Path(directory).resolve(), Path(output)
    if output.exists():
        raise FileExistsError("OUTPUT_EXISTS_NO_OVERWRITE")
    protocol = read(directory / "PROTOCOL.json")
    if protocol["experiment_id"] != EXPERIMENT:
        raise ValueError("UNREGISTERED_EXPERIMENT")
    registry = unique(read(directory / "CONFIGURATIONS.json"), "id")
    if len(registry) != 14 or len({c["configId"] for c in registry.values()}) != 14:
        raise ValueError("EXACT_FOURTEEN_CONFIGURATIONS_REQUIRED")
    if (protocol.get("expected_primary_n") != 378 or protocol.get("expected_total_raw_n") != 381
            or protocol.get("rounds_per_configuration") != 3 or protocol.get("phases") != list(PHASES)
            or set(protocol.get("configuration_ids", [])) != set(registry)
            or len(protocol.get("configuration_ids", [])) != 14):
        raise ValueError("EXACT_FROZEN_COLLECTION_PROTOCOL_REQUIRED")
    registered_envs = unique(protocol["environments"], "android_api")
    if set(registered_envs) != {29, 30, 36}:
        raise ValueError("THREE_REGISTERED_API_ENVIRONMENTS_REQUIRED")
    measurement = metadata_contract()
    inputs, metadata, triplets, roles, global_issues, environments = {}, {}, [], [], [], {}
    started_path = directory / "STARTED.json"
    if not started_path.exists() or read(started_path).get("protocol") != protocol:
        global_issues.append({"reason": "PRECOLLECTION_PROTOCOL_SNAPSHOT_MISMATCH"})
    finished_path = directory / "FINISHED.json"
    finished = read(finished_path) if finished_path.exists() else {}
    completed = finished.get("environments", [])
    if len(completed) != 3 or any(r.get("status") != "COMPLETE" for r in completed):
        global_issues.append({"reason": "ALL_THREE_ENVIRONMENTS_FINISHED_COMPLETE_REQUIRED"})
    for api in (29, 30, 36):
        registered_env = registered_envs[api]
        run = ROOT / registered_env["run_path"]
        env = f"api{api}_swiftshader"
        if (run.resolve() != directory / "runs" / env or registered_env["environment_group_id"] != env
                or registered_env.get("gpu") != "swiftshader"):
            raise ValueError("REGISTERED_FRESH_RUN_PATH_REQUIRED")
        required = ("protocol_snapshot.json", "plan.json", "configurations_snapshot.json", "SOURCE_REGISTRATION.json")
        if any(not (run / name).exists() for name in required):
            global_issues.append({"environment": env, "reason": "RUN_NOT_STARTED"})
            for cid in registry:
                for number in (1, 2, 3):
                    triplets.append({"environment": env, "configuration_id": cid,
                        "config_id": registry[cid]["configId"], "round": number,
                        "status": "SOURCE_NOT_REGISTERED", "session_ids": [None, None, None],
                        "step_ids": [f"{cid}-r{number}-{p}" for p in PHASES],
                        "reason": "Frozen positions retained; no independently registered input available."})
            for raw in lines(run / "backend/raw_expanded_payloads.jsonl"):
                roles.append({"environment": env, "session_id": raw.get("session_id"),
                    "role": "UNREGISTERED_SOURCE_RETAINED",
                    "raw_file": str((run / "backend/raw_expanded_payloads.jsonl").relative_to(ROOT))})
            continue
        config, plan = read(run / required[0]), read(run / required[1])
        registration = read(run / required[3])
        summary_path = run / "SUMMARY.json"
        if not summary_path.exists() or read(summary_path).get("status") != "COMPLETE":
            global_issues.append({"environment": env, "reason": "RUN_SUMMARY_COMPLETE_REQUIRED"})
        if (registration.get("source_reference") != str((directory / "PROTOCOL.json").relative_to(ROOT))
                or registration.get("environment_group_id") != env
                or registration.get("binding_rule") != "FIRST_NEW_INSTALL_SMOKE_THEN_REQUIRE_STABLE"
                or registration.get("independent_of_candidate_state") is not True):
            global_issues.append({"environment": env, "reason": "SOURCE_REGISTRATION_MISMATCH"})
        if read(run / required[2]) != registry:
            raise ValueError("RUN_CONFIGURATION_SNAPSHOT_MISMATCH")
        main_plan = [s for s in plan if s["phase"] in PHASES]
        expected = {(cid, r, p) for cid in registry for r in (1, 2, 3) for p in PHASES}
        actual = [(s["group"], s["round"], s["phase"]) for s in main_plan]
        if len(actual) != 126 or set(actual) != expected:
            raise ValueError("FROZEN_PLAN_MEMBERSHIP_MISMATCH")
        saved = unique(lines(run / "sessions.jsonl"), "step_id")
        raws = unique(lines(run / "backend/raw_expanded_payloads.jsonl"), "session_id")
        receipts = unique(lines(run / "backend/collection_receipts.jsonl"), "session_id")
        exports = unique(lines(run / "backend/expanded_collected_data.jsonl"), "session_id")
        smoke_sid = registration.get("smoke_session_id")
        smoke = saved.get("smoke")
        smoke_raw, smoke_receipt = raws.get(smoke_sid), receipts.get(smoke_sid)
        if (not smoke_sid or not smoke or smoke.get("accepted") is not True or
                smoke.get("observation", {}).get("session_id") != smoke_sid or
                smoke.get("observation", {}).get("identity") != registration.get("identity") or
                not smoke_raw or not smoke_receipt or smoke_receipt.get("validation_status") != "accepted"):
            global_issues.append({"environment": env, "reason": "FIRST_FRESH_SMOKE_REGISTRATION_REQUIRED"})
        identities = set()
        used = set()
        source = str((directory / "PROTOCOL.json").relative_to(ROOT)) + "#" + env
        env_id = config["device_manifest_id"]
        for cid in registry:
            for number in (1, 2, 3):
                steps = [next(s for s in main_plan if (s["group"], s["round"], s["phase"]) == (cid, number, p)) for p in PHASES]
                payloads, sids, phase_issues, retained = [], [], [], []
                for step in steps:
                    s = saved.get(step["step_id"])
                    sid = s.get("observation", {}).get("session_id") if s else None
                    raw, receipt = raws.get(sid), receipts.get(sid)
                    attempt_path = run / "attempts" / step["step_id"] / "attempt.json"
                    attempt = read(attempt_path) if attempt_path.exists() else None
                    issues = _association_issues(step, s, attempt, raw, receipt, exports.get(sid), registration, api)
                    payload = raw.get("canonical_received_payload") if raw else None
                    payloads.append(payload); sids.append(sid)
                    phase_issues.append({"step_id": step["step_id"], "issues": issues,
                                         "attempt_status": attempt.get("status") if attempt else "NOT_ATTEMPTED"})
                    if payload is None or not receipt or not isinstance(receipt.get("session_id"), str):
                        continue
                    expected_sid = receipt["session_id"]
                    oid = "webgl1fresh-" + expected_sid
                    if oid in inputs:
                        raise ValueError("DUPLICATE_FRESH_SESSION")
                    inputs[oid] = {"opaque_id": oid, **compile_record(payload, expected_session_id=expected_sid,
                                   source_reference=source, measurement_contract=measurement)}
                    manifest = payload.get("collection_manifest", {})
                    identities.add(tuple(manifest.get(k) for k in ("collector_install_id", "android_api", "webview_provider_package", "webview_provider_version", "collector_version_code")))
                    metadata[oid] = {"opaque_id": oid, "phase": step["phase"], "environment_group_id": env_id,
                        "config_id": registry[cid]["configId"], "bundle_id": env_id + ":" + registry[cid]["configId"],
                        "triplet_id": env_id + ":" + registry[cid]["configId"] + ":r" + str(number),
                        "proposed_supervised_label": None, "proposed_supervised_member": False,
                        "fit_permission": "DENIED_PREPARATION_ONLY", "label_scope": "Declared controlled intervention present/absent only",
                        "observation_mode": "raw_observation_v1", "source_ref": str(run.relative_to(ROOT)),
                        "step_id": step["step_id"], "session_id": expected_sid, "admission_ref": "EFFECT_AUDIT.json"}
                    retained.append(oid); used.add(sid)
                logdir = run / "attempts" / steps[1]["step_id"] / "automation"
                logs = list(logdir.glob("*.json"))
                execution = read(logs[0]) if len(logs) == 1 else None
                effect = audit_triplet(registry[cid], payloads, execution, sids)
                if any(p["issues"] for p in phase_issues):
                    effect["effect_only_status"] = effect["status"]
                    effect["status"] = "COLLECTION_ASSOCIATION_FAILED"
                item = {"environment": env, "configuration_id": cid, "config_id": registry[cid]["configId"],
                        "round": number, "step_ids": [s["step_id"] for s in steps], "session_ids": sids,
                        "collection_checks": phase_issues, **effect}
                triplets.append(item)
                if effect["status"] == "PASS":
                    for oid in retained:
                        metadata[oid]["proposed_supervised_member"] = True
                        metadata[oid]["proposed_supervised_label"] = int(metadata[oid]["phase"] == "attack")
        if len(identities) != 1:
            global_issues.append({"environment": env, "reason": "STABLE_SINGLE_INSTALLATION_REQUIRED"})
        environments[env] = [list(v) for v in sorted(identities, key=str)]
        for sid in raws:
            saved_row = next((s for s in saved.values() if s.get("observation", {}).get("session_id") == sid), None)
            role = "PRIMARY_CAPTURE" if sid in used else "SMOKE_ONLY" if saved_row and saved_row.get("group") == "smoke" else "UNASSOCIATED_RAW_RETAINED"
            roles.append({"environment": env, "session_id": sid, "role": role,
                          "raw_file": str((run / "backend/raw_expanded_payloads.jsonl").relative_to(ROOT))})
            if role == "UNASSOCIATED_RAW_RETAINED":
                global_issues.append({"environment": env, "reason": role, "session_id": sid})
    installation_ids = {identity[0] for identities in environments.values() for identity in identities}
    if len(installation_ids) != 3 or None in installation_ids:
        global_issues.append({"reason": "THREE_DISTINCT_CURRENT_INSTALLATIONS_REQUIRED"})
    if len(roles) != 381 or sum(r["role"] == "SMOKE_ONLY" for r in roles) != 3:
        global_issues.append({"reason": "EXACT_381_RAW_ROWS_WITH_THREE_EXCLUDED_SMOKES_REQUIRED"})
    folds = []
    try:
        folds = make_folds(metadata)
    except ValueError as error:
        global_issues.append({"reason": str(error)})
    base_states = Counter("FAILED" if c["evaluation_status"] == "FAILED" else "AVAILABLE" if c["available"] else "U"
                          for row in inputs.values() for c in row["features"].values())
    candidate_states = Counter(cid + ":" + cell_state(c)
                              for row in inputs.values() for cid, c in row["candidate_cells"].items())
    if base_states["FAILED"] or any(row["compilation_errors"] for row in inputs.values()):
        global_issues.append({"reason": "BASE_COMPILATION_FAILED_RETAINED"})
    semantic_failed = any(c["evaluation_status"] == "FAILED" for row in inputs.values() for c in row["candidate_cells"].values())
    if semantic_failed:
        global_issues.append({"reason": "SEMANTIC_COMPILATION_FAILED_RETAINED"})
    ready = not global_issues and len(triplets) == 126 and all(t["status"] == "PASS" for t in triplets)
    status = "WEBGL1_FRESH_INPUTS_READY" if ready else "BLOCKED_INCOMPLETE_OR_FAILED_COHORT"
    summary = {"schema_version": "webgl1-fresh-input-preparation-v1", "status": status, "readiness": status,
               "sample_ids": sorted(inputs), "folds": folds,
               "source_modes": {oid: "raw_observation_v1" for oid in sorted(inputs)},
               "source_collection_protocol": str((directory / "PROTOCOL.json").relative_to(ROOT)),
               "planned_members": 378, "captured_primary_members": len(inputs),
               "planned_triplets": 126, "triplet_statuses": dict(Counter(t["status"] for t in triplets)),
               "base_input_cells": dict(base_states), "candidate_states": dict(candidate_states),
               "raw_roles": dict(Counter(r["role"] for r in roles)), "environments": environments,
               "issues": global_issues, "fit_calls": 0, "prediction_calls": 0,
               "historical_rows_included": False, "candidate_states_used_for_admission": False,
               "evaluation_role": protocol["scope"], "normal_app_population_fpr": "NOT_EVALUATED"}
    output.mkdir(parents=True); (output / "inputs").mkdir(); (output / "evaluation").mkdir()
    for oid in sorted(inputs):
        write(output / "inputs" / (oid + ".json"), inputs[oid])
        write(output / "evaluation" / (oid + ".json"), metadata[oid])
    audit = {"status": "PRIMARY_EFFECTS_PASS" if ready else "PRIMARY_NOT_READY", "triplets": triplets,
             "scope": "Declared raw intervention values, execution and restoration; no candidate labels."}
    contract = {"experiment_id": EXPERIMENT, "registered_at": datetime.now(timezone.utc).isoformat(),
                "sample_ids": sorted(inputs), "source_modes": {oid: "raw_observation_v1" for oid in sorted(inputs)},
                "folds": folds, "groups": ["BASE49", "WEBGL50"], "evaluation_role": summary["evaluation_role"],
                "readiness": status, "execution_started": False, "protocol": protocol,
                "admission_basis": audit["scope"], "fit_permission": "DENIED_PREPARATION_ONLY"}
    artifacts = {"PREPARATION.json": summary, "SUMMARY.json": summary, "EFFECT_AUDIT.json": audit,
                 "DEFINITIONS.json": measurement["definitions"],
                 "BASE_DEFINITIONS.json": group_definitions(measurement["definitions"], "LANG_ADD_WD_REPLACE"),
                 "FOLDS.json": folds, "RAW_ROLE_INDEX.json": roles, "CONTRACT.json": contract,
                 "SAVED_WEBGL1_CANDIDATES.json": {oid: row["candidate_cells"][webgl.CANDIDATE_ID] for oid, row in inputs.items()}}
    for name, value in artifacts.items():
        write(output / name, value)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "prepared")
    args = parser.parse_args()
    result = prepare(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "WEBGL1_FRESH_INPUTS_READY" else 1)
