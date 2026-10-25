"""Extract frozen controlled observations without executing research experiments.

This module uses only the Python standard library. Returned records contain
private source identifiers and original payloads: callers MUST normalize and
redact them before producing a candidate package. Recorded evidence is checked
against original payloads; detector outputs never determine intervention labels.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path


PHASES = ("clean_pre", "attack", "clean_post")
APP_ROOTS = ("android_native_data", "webview_data", "web_data")
MEMORY = "web_data.navigator_layer.device_memory"
TZ = ("android_native_data.locale_timezone_layer.native_timezone_id",
      "android_native_data.locale_timezone_layer.native_timezone_offset_min",
      "web_data.execution_layer.timezone_id", "web_data.execution_layer.timezone_offset")


def at_path(value, path):
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def flat(value, prefix=""):
    result = {}
    for key, item in value.items():
        path = prefix + "." + key if prefix else key
        if isinstance(item, dict):
            result.update(flat(item, path))
        else:
            result[path] = item
    return result


def same(left, right, tolerance=0):
    if left is None or right is None:
        return False
    if type(left) in (int, float) and type(right) in (int, float):
        return math.isfinite(left) and math.isfinite(right) and abs(left-right) <= tolerance
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return left == right


class Reader:
    def __init__(self, repo):
        self.repo = Path(repo).resolve()
        self.inputs = set()

    def path(self, name):
        path = (self.repo/name).resolve()
        if not path.is_relative_to(self.repo):
            raise ValueError("Source path escapes repository")
        self.inputs.add(str(path.relative_to(self.repo)))
        return path

    def object(self, name):
        return json.loads(self.path(name).read_text())

    def rows(self, name):
        path = self.path(name)
        with (gzip.open if path.suffix == ".gz" else open)(path, "rt") as stream:
            return [(line, json.loads(text)) for line, text in enumerate(stream, 1) if text.strip()]


def unique(rows, key):
    result = {row[key]: (line, row) for line, row in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate source identity: " + key)
    return result


def source_summary(source_id, base, rows, raw_count, groups, **extra):
    return {
        "source_id": source_id,
        "source_type": "controlled_manipulation" if source_id == "controlled_main" else "specialist_experiment",
        "collection_batch": base.split("/")[-1],
        "classification": "release_candidate",
        "public_permission": "PENDING_CONFIRMATION",
        "data_ownership": "PENDING_CONFIRMATION",
        "privacy_review": "PENDING_CONFIRMATION",
        "redistribution_permission": "PENDING_CONFIRMATION",
        "source_schema": "expanded-v2.2-status",
        "raw_archive_schema": "expanded-raw-payload-v1",
        "record_count": len(rows),
        "raw_archive_count": raw_count,
        "view": "App177",
        "field_counts": {"native": 84, "host": 26, "app_web": 67},
        "source_status_counts": dict(Counter(s for r in rows for s in r["app"]["collection_status"]["fields"].values())),
        "labels": dict(Counter(r["annotation"]["label"] for r in rows)),
        "label_verification": dict(Counter(r["annotation"]["label_verification"] for r in rows)),
        "triplet_count": groups,
        "environment_count": len({r["metadata"]["environment"] for r in rows}),
        "independent_physical_device_count": None,
        "statistical_unit": "Repeated current-session observations in controlled emulator environments; not independent devices",
        "complete_field_structure": True,
        "availability_note": "All 177 source statuses are observed. Value quality and sentinel ambiguity still require canonical normalization.",
        "label_scope": "Presence or absence of the declared target intervention only; not comprehensive benignness",
        "recommended_split": None,
        **extra,
    }


def payload_checked(raw, sid):
    payload = raw.get("canonical_received_payload", {})
    if not sid or raw.get("session_id") != sid or payload.get("session_id") != sid:
        raise ValueError("Raw session binding mismatch")
    if raw.get("raw_payload_archive_schema_version") != "expanded-raw-payload-v1":
        raise ValueError("Unexpected raw archive schema")
    if payload.get("schema_version") != "expanded-v2.2-status":
        raise ValueError("Unexpected App schema")
    if tuple(len(flat(payload.get(k, {}))) for k in APP_ROOTS) != (84, 26, 67):
        raise ValueError("Unexpected App177 feature structure")
    statuses = payload.get("collection_status", {}).get("fields", {})
    if len(statuses) != 177:
        raise ValueError("Missing explicit field statuses")
    return payload


def make_record(source_id, payload, annotation, env, triplet, phase, provenance, **metadata):
    return {
        "source_id": source_id,
        "record_key": payload["session_id"],
        "app": payload,
        "metadata": {"cohort": source_id, "environment": env,
                     "schema_version": payload["schema_version"],
                     "android_api": payload.get("collection_manifest", {}).get("android_api"),
                     "development_role": "development_exposed_controlled_study", **metadata},
        "annotation": annotation,
        "group_key": "emulator_environment:" + env,
        "group_basis": "emulator_environment",
        "triplet_key": triplet,
        "phase": phase,
        "provenance": provenance,
    }


def controlled(reader):
    base = "deliverables/webgl1_fresh_comparison_v1"
    configs = {c["configId"]: c for c in reader.object(base+"/CONFIGURATIONS.json")}
    audit = reader.object(base+"/prepared/EFFECT_AUDIT.json")
    roles = reader.object(base+"/prepared/RAW_ROLE_INDEX.json")
    protocol = reader.object(base+"/PROTOCOL.json")
    role_map = {(r["environment"], r["session_id"]): r["role"] for r in roles}
    if Counter(r["role"] for r in roles) != {"PRIMARY_CAPTURE": 378, "SMOKE_ONLY": 3}:
        raise ValueError("Controlled raw-role membership changed")
    rows, archives, used = [], {}, set()
    receipts, registrations, sessions = {}, {}, {}
    for env in protocol["environments"]:
        eid = env["environment_group_id"]
        run = base+"/runs/"+eid
        path = run+"/backend/raw_expanded_payloads.jsonl"
        archives[eid] = (path, unique(reader.rows(path), "session_id"))
        receipts[eid] = unique(reader.rows(run+"/backend/collection_receipts.jsonl"), "session_id")
        registrations[eid] = reader.object(run+"/SOURCE_REGISTRATION.json")
        sessions[eid] = unique(reader.rows(run+"/sessions.jsonl"), "step_id")
    for number, trio in enumerate(audit["triplets"]):
        eid, cid = trio["environment"], trio["config_id"]
        config = configs[cid]
        if trio["status"] != "PASS" or not all(trio[k] is True for k in (
                "declared_fields_observed", "active_profile_observed", "declared_effect_present",
                "declared_fields_restored", "execution_receipt_valid")):
            raise ValueError("Controlled effect evidence no longer passes")
        if any(c["issues"] for c in trio["collection_checks"]):
            raise ValueError("Controlled saved collection checks failed")
        raw_path, index = archives[eid]
        payloads = [payload_checked(index[sid][1], sid) for sid in trio["session_ids"]]
        for payload, phase in zip(payloads, PHASES):
            values = {}
            for field, saved in trio["declared_values"][phase].items():
                found = [(layer, data[field]) for layer, data in payload["web_data"].items()
                         if isinstance(data, dict) and field in data]
                if len(found) != 1:
                    raise ValueError("Target field absent or ambiguous")
                layer, value = found[0]
                if payload["collection_status"]["fields"].get("web_data."+layer+"."+field) != "observed" or not same(value, saved):
                    raise ValueError("Saved target evidence does not match raw field")
                values[field] = value
        pre, active, post = (trio["declared_values"][p] for p in PHASES)
        tolerances = trio["tolerances"]
        changed = [f for f in pre if not same(pre[f], active[f], tolerances.get(f, 0))]
        if changed != trio["changed_declared_fields"] or not changed or not all(same(pre[f], post[f], tolerances.get(f, 0)) for f in pre):
            raise ValueError("Controlled target effect or restoration mismatch")
        run = base+"/runs/"+eid
        logs = sorted((reader.repo/run/"attempts"/trio["step_ids"][1]/"automation").glob("*.json"))
        if len(logs) != 1:
            raise ValueError("Controlled execution receipt is missing or ambiguous")
        log_path = str(logs[0].relative_to(reader.repo))
        execution = reader.object(log_path)
        if not (execution.get("status") == "MEASURED" and execution.get("configId") == cid
                and execution.get("configurationId") == config["id"]
                and execution.get("measuredSessionIds") == [trio["session_ids"][1]]
                and execution.get("injected") == config["profile"]
                and execution.get("declaredObservableFields") == config["observableFields"]):
            raise ValueError("Controlled execution receipt mismatch")
        for pos, (payload, phase, sid, step) in enumerate(zip(payloads, PHASES, trio["session_ids"], trio["step_ids"])):
            raw_line, raw = index[sid]
            receipt_line, receipt = receipts[eid][sid]
            saved_line, saved = sessions[eid][step]
            attempt_path = run+"/attempts/"+step+"/attempt.json"
            attempt = reader.object(attempt_path)
            manifest = payload["collection_manifest"]
            registration = registrations[eid]
            if (role_map.get((eid, sid)) != "PRIMARY_CAPTURE" or sid in used
                    or receipt.get("receipt_id") != raw.get("receipt_id")
                    or receipt.get("validation_status") != "accepted"
                    or receipt.get("raw_payload_archived") is not True
                    or saved.get("accepted") is not True or attempt.get("status") != "ACCEPTED"
                    or saved.get("observation", {}).get("session_id") != sid or attempt.get("session_id") != sid
                    or saved.get("phase") != phase or attempt.get("phase") != phase
                    or manifest.get("collector_install_id") != registration.get("identity", {}).get("collector_install_id")):
                raise ValueError("Controlled source association failed")
            used.add(sid)
            annotation = {
                "label": "modified" if phase == "attack" else "normal_control",
                "label_verification": "verified_recorded_evidence",
                "tool_execution_status": "executed" if phase == "attack" else "control_collection",
                "target_effect_status": "observed_target_change" if phase == "attack" else "restored" if phase == "clean_post" else "baseline_observation",
                "detector_outcome": "not_recomputed",
                "manipulation_type": cid,
                "configuration_name": config["id"],
                "attack_tool": execution["toolName"],
                "annotation_basis": "Saved independent effect audit, raw declared fields, execution receipt, accepted collection association and pre/post restoration agree.",
                "restoration_status": "verified",
            }
            provenance = [{"path": raw_path, "line": raw_line},
                          {"path": base+"/prepared/EFFECT_AUDIT.json", "selector": "/triplets/"+str(number)},
                          {"path": run+"/backend/collection_receipts.jsonl", "line": receipt_line},
                          {"path": run+"/sessions.jsonl", "line": saved_line},
                          {"path": attempt_path}, {"path": log_path}]
            rows.append(make_record("controlled_main", payload, annotation, eid,
                                   "controlled_main:"+eid+":"+cid+":"+str(trio["round"]), phase,
                                   provenance, repetition=trio["round"]))
    if len(rows) != 378 or len(audit["triplets"]) != 126:
        raise ValueError("Controlled frozen membership changed")
    recipe_counts = Counter(r["annotation"]["manipulation_type"] for r in rows if r["phase"] == "attack")
    if len(recipe_counts) != 14 or set(recipe_counts.values()) != {9}:
        raise ValueError("Controlled fourteen-recipe membership changed")
    source = source_summary("controlled_main", base, rows, len(roles), 126,
                            paper_experiment="RQ1 and RQ3 controlled benchmark; 126 effective modifications and 252 normal positions",
                            excluded_count=3, exclusion_reason="Environment registration smoke observations are outside the frozen primary benchmark",
                            raw_paths=[p for p, _ in archives.values()],
                            effective_modifications_by_recipe=dict(recipe_counts),
                            label_evidence=base+"/prepared/EFFECT_AUDIT.json",
                            overlap_note="All model folds, methods, retention stages and historical replays reuse this same 378-observation set.")
    return source, rows


def specialist(reader, task, directory, saved_name):
    base = "deliverables/"+directory
    source_id = "specialist_"+task
    saved_path = base+"/"+saved_name
    saved_rows = reader.rows(saved_path)
    settings = reader.object(base+"/SETTINGS.json")
    raw_cache, operation_cache, groups = {}, {}, defaultdict(list)
    if task == "memory":
        summary = reader.object(base+"/summary.json")
        saved_effects = {(r["environment"], r["target_gib"], r["round"]): r
                        for r in summary["new_batch"]["triplets"]}
    for saved_line, row in saved_rows:
        eid = row["environment"]
        run = base+"/runs/"+eid
        if eid not in raw_cache:
            path = run+"/backend/raw_expanded_payloads.jsonl"
            raw_cache[eid] = (path, dict(reader.rows(path)))
            operation_cache[eid] = unique(reader.rows(run+"/operations.jsonl"), "step_id")
        path, index = raw_cache[eid]
        binding = row.get("source_binding", {})
        reference = binding.get("raw_reference", row.get("raw_reference", ""))
        ref_path, line = reference.rsplit(":", 1)
        if ref_path != path:
            raise ValueError("Specialist raw source path mismatch")
        line = int(line)
        raw = index[line]
        sid = binding["app_session_id"]
        payload = payload_checked(raw, sid)
        op_line, operation = operation_cache[eid][row["step_id"]]
        if (row.get("source_errors") or operation != row["operation"]
                or operation.get("session_id") != sid
                or operation.get("collector_install_id") != payload["collection_manifest"].get("collector_install_id")):
            raise ValueError("Specialist operation binding mismatch")
        receipt_path = run+"/"+row["step_id"]+".cdp.json"
        receipt = reader.object(receipt_path)
        if operation.get("cdp_status") != "COMPLETED" or receipt.get("status") != "COMPLETED":
            raise ValueError("Specialist operation did not complete")
        if task == "memory" and not same(receipt.get("current_runtime_observation", {}).get("deviceMemory"), at_path(payload, MEMORY)):
            raise ValueError("Memory runtime receipt differs from raw observation")
        if task == "memory":
            expected_target = row["target_gib"] if row["phase"] == "attack" else None
            expected_injections = ["navigator.deviceMemory"] if row["phase"] == "attack" else []
            if (receipt.get("target_gib") != expected_target
                    or receipt.get("injected_properties") != expected_injections
                    or receipt.get("future_document_script_removed") is not True
                    or operation.get("owned_app_process_absent_after") is not True):
                raise ValueError("Memory declared operation, no-op control or cleanup evidence mismatch")
        if task != "memory":
            if (row.get("workflow_evidence", {}).get("verified") is not True
                    or binding.get("binding_valid") is not True
                    or receipt.get("raw_receipt", {}).get("session_id") != sid
                    or receipt.get("raw_receipt", {}).get("received_before_rollback") is not True):
                raise ValueError("Specialist workflow or receipt binding failed")
        for field, operand in row.get("operands", {}).items():
            path_field = field.removeprefix("app.")
            if at_path(payload, path_field) != operand.get("value") or payload["collection_status"]["fields"].get(path_field) != operand.get("status"):
                raise ValueError("Specialist saved operand differs from original raw field")
        if task == "geometry" and payload["web_data"]["screen_layer"] != row["legacy_screen"]:
            raise ValueError("Geometry saved screen values differ from original raw fields")
        if task == "geometry":
            geometry = payload.get("collection_observations", {}).get("webview_geometry", {})
            web_values = {k: v.get("value") for k, v in geometry.get("web", {}).get("fields", {}).items() if isinstance(v, dict)}
            if (geometry.get("session_id") != sid or geometry.get("binding_valid") is not True
                    or geometry.get("host_before") != row["host_before"]
                    or geometry.get("host_after") != row["host_after"]
                    or web_values != row["web_geometry_values"]):
                raise ValueError("Geometry supplemental measurements differ from raw observation")
        key = ((eid, row["target_gib"], row["round"]) if task == "memory" else
               (eid, row["process_type"], row["target_timezone"], row["round"]) if task == "timezone" else
               (eid, row["process_type"], row["round"]))
        member = {"saved": row, "app": payload, "receipt": receipt,
                  "provenance": [{"path": path, "line": line}, {"path": saved_path, "line": saved_line},
                                 {"path": run+"/operations.jsonl", "line": op_line}, {"path": receipt_path}]}
        groups[key].append(member)
    result = []
    for key, members in groups.items():
        by_phase = {m["saved"]["phase"]: m for m in members}
        middle = "attack" if task == "memory" else "change"
        if len(members) != 3 or set(by_phase) != {"clean_pre", middle, "clean_post"}:
            raise ValueError("Specialist triplet is incomplete or repeated")
        pre, mid, post = [by_phase[p] for p in ("clean_pre", middle, "clean_post")]
        saved = mid["saved"]
        if task == "memory":
            values = [at_path(m["app"], MEMORY) for m in (pre, mid, post)]
            target = saved["target_gib"]
            evidence = saved_effects[key]
            changed = not same(values[0], values[1])
            restored = same(values[0], values[2])
            effective = changed and same(values[1], target)
            if (evidence["execution"] != "EXECUTED" or evidence["recovery"] != "RESTORED"
                    or evidence["values_pre_active_post"] != values or not restored
                    or evidence["effect_positive"] is not effective
                    or mid["receipt"].get("target_gib") != target):
                raise ValueError("Memory saved effect or restoration mismatch")
            effect_status = "observed_target_change" if effective else "no_observable_effect" if not changed else "changed_target_unconfirmed"
            manipulation = "web_device_memory_override"
        else:
            evidence = saved["trio_evidence"]
            if (evidence["sample_ids"] != [m["saved"]["sample_id"] for m in (pre, mid, post)]
                    or evidence["execution"] != "EXECUTED" or evidence["recovery"] != "RESTORED"
                    or evidence["rollback_evidence"].get("verified") is not True):
                raise ValueError("Specialist trio execution or restoration evidence mismatch")
            if task == "timezone":
                before, active, after = [[at_path(m["app"], f) for f in TZ] for m in (pre, mid, post)]
                changed = before[2:] != active[2:]
                if before != after or changed != evidence["web_changed"]:
                    raise ValueError("Timezone effect or restoration differs from raw values")
                effective = saved["process_type"] == "A" and changed
                manipulation = "web_timezone_override" if saved["process_type"] == "A" else "legitimate_system_timezone_change"
            else:
                changed = bool(evidence["target_changes"])
                for field, vals in evidence["target_changes"].items():
                    raw_vals = [at_path(m["app"], field.removeprefix("app.")) for m in (pre, mid, post)]
                    if raw_vals != vals:
                        raise ValueError("Geometry target effect differs from raw values")
                effective = saved["process_type"] == "A" and changed
                manipulation = {"A": "web_screen_metrics_override", "L1": "legitimate_orientation_change",
                                "L2": "legitimate_host_layout_change", "L3": "legitimate_webview_zoom"}[saved["process_type"]]
            if effective != evidence["observable_intervention"] or effective != saved.get("observable_intervention", False):
                raise ValueError("Specialist intervention label differs from raw evidence")
            effect_status = "observed_target_change" if effective else "legitimate_change" if changed else "no_observable_effect"
        for phase in ("clean_pre", middle, "clean_post"):
            member = by_phase[phase]
            row = member["saved"]
            if task == "memory":
                label = "normal_control" if phase != middle else "modified" if effective else "no_effect" if not changed else "unknown"
            else:
                label = "modified" if phase == middle and effective else "normal_control" if row.get("normal_basis", {}).get("supported") is True else "unknown"
            annotation = {
                "label": label,
                "label_verification": "verified_recorded_evidence" if label != "unknown" else "unknown",
                "tool_execution_status": "executed" if phase == middle else "control_collection",
                "target_effect_status": effect_status if phase == middle else "restored" if phase == "clean_post" else "baseline_observation",
                "detector_outcome": "not_recomputed",
                "recorded_detector_states": {k: v["state"] for k, v in row["conditions"].items()},
                "manipulation_type": manipulation,
                "annotation_basis": "Saved specialist source binding, recorded operation/receipt and raw target values checked; target effect and restoration are separate from detector states.",
                "restoration_status": "verified",
            }
            record = make_record(source_id, member["app"], annotation, key[0],
                                 source_id+":"+":".join(map(str, key)), phase,
                                 member["provenance"], repetition=saved["round"],
                                 process_type=saved.get("process_type", "memory_only"))
            if task == "memory":
                record["annotation"]["target_memory_gib"] = saved["target_gib"]
            if task == "geometry":
                record["extras"] = {k: row[k] for k in ("geometry_evidence", "geometry_module_status", "web_geometry_values", "host_before", "host_after")}
            result.append(record)
    expected = {"memory": 72, "timezone": 36, "geometry": 72}[task]
    if len(result) != expected:
        raise ValueError("Specialist frozen membership changed")
    source = source_summary(source_id, base, result, sum(len(v) for _, v in raw_cache.values()), len(groups),
                            raw_paths=[p for p, _ in raw_cache.values()], label_evidence=saved_path,
                            paper_experiment="RQ2 standalone "+task+" mechanism study",
                            overlap_note="Separate collected batch; historical replays and all method/model outputs are not additional observations.",
                            excluded_material="Engineering smoke and later geometry v16 workflow studies are outside the frozen formal v15 task" if task == "geometry" else "Historical replay outputs are source duplicates, not new records")
    return source, result


def extract(repo: Path):
    """Return private, auditable records. Does not write any output or run models."""
    reader = Reader(repo)
    sources, records = [], []
    source, current = controlled(reader)
    sources.append(source)
    records.extend(current)
    for task, directory, name in (
            ("memory", "memory_relation_validation_v1", "new_batch.jsonl.gz"),
            ("timezone", "timezone_relation_validation_v1", "new_batch.jsonl.gz"),
            ("geometry", "screen_geometry_observation_v1", "predictions.jsonl.gz")):
        source, current = specialist(reader, task, directory, name)
        sources.append(source)
        records.extend(current)
    if len({r["record_key"] for r in records}) != len(records):
        raise ValueError("Controlled/specialist source observations overlap")
    return {"sources": sources, "records": records, "inputs": sorted(reader.inputs),
            "issues": ["All public permissions remain PENDING_CONFIRMATION.",
                       "Emulator environments and repeated observations do not establish independent physical devices.",
                       "Complete 177-field structure does not remove observed-value sentinel ambiguity."]}
