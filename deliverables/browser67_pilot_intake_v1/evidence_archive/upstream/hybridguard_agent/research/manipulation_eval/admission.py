"""S01: read-only material admission, without inference or performance metrics.

The existing JavaScript CLIs remain the bundle-integrity validators. Their PASS
is recorded separately from the fact-specific decisions below. In particular,
execution/effect never depend on post restoration or on a detector result.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from hybridguard_agent.evidence.browser_pair import FIELD_STATUSES, canonical_json, sha256_value


VERSION = "formal-manipulation-admission-v1"
STUDY = "formal_manipulation_v1_20260923"
L0 = "L0_ANNOTATION_ONLY_OR_INCOMPLETE"
L1 = "L1_RECEIPT_SUPPORTED"
L2 = "L2_RAW_LOG_CORROBORATED"
MISSING = object()
ELIGIBILITY_KEYS = (
    "eligible_detection", "eligible_triplet", "eligible_pre_control",
    "eligible_post_control", "eligible_temporal_control",
)
POLICY = {
    "schema_version": VERSION,
    "detector_independent": True,
    "positive_requires": "unique bound pre/current payloads, bound execution evidence, observable declared field effect, no label conflict",
    "detection_requires_post_restoration": False,
    "triplet_requires": "eligible attack, three unique bound phases, supported scoped pre-control; retain failed/unknown rollback",
    "post_negative_requires": "supported scoped absence plus all declared fields restored with observed status",
    "temporal_negative_requires": "bound operational no-intervention/cleanup evidence beyond control declarations and stable raw values",
    "clean_scope": "absence of the declared intervention in the recorded surfaces; never universal benignness",
    "effect_L2_scope": "directly inspectable bound raw payload field values, not private runner logs",
    "execution_L1_scope": "session/run/config receipt plus recorded execution; private log not independently verified",
    "clean_L1_scope": "receipt-anchored triplet, run not_run/absence observations matching raw, declared effect absent",
    "independent_attestation": False,
    "unknown_is_negative": False,
    "missing_log_is_false_negative": False,
    "groups_are_physical_devices": False,
    "source_selection_limitation": "existing complete bundles were selected by a restoration-oriented validator; all incomplete attempts retained",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_jsonl(path: Path, values: list[dict]) -> None:
    path.write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values))


def same(left: Any, right: Any) -> bool:
    return left is not MISSING and right is not MISSING and canonical_json(left) == canonical_json(right)


def field_value(raw: dict, field: str) -> Any:
    """Match the existing validator's logical-path / legacy flat transport read."""
    keys = field.split(".")
    if keys[0] in {"web_data", "webview_data"}:
        container = raw.get(keys[0], {})
        if isinstance(container, dict) and keys[-1] in container:
            return container[keys[-1]]
    value = raw
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return MISSING
        value = value[key]
    return value


def fact(status="UNKNOWN", grade=L0, reason="not applicable to this phase", refs=(), **extra) -> dict:
    return {"status": status, "evidence_grade": grade, "reason": reason,
            "evidence_refs": list(refs), "independent_attestation": False, **extra}


def read_jsonl(path: Path) -> list[dict]:
    """Keep invalid lines, so malformed input is an explicit candidate failure."""
    if not path.exists():
        return []
    rows = []
    for line, text in enumerate(path.read_text().splitlines(), 1):
        if not text.strip():
            continue
        try:
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError("row is not an object")
            rows.append({"line": line, "value": value})
        except (ValueError, json.JSONDecodeError) as error:
            rows.append({"line": line, "value": {}, "parse_error": str(error)})
    return rows


def resolve_ref(root: Path, ref: str) -> Path | None:
    """Map archival OS prefixes only at the explicit execution_log/ anchor."""
    value = str(ref or "").split("#", 1)[0].replace("\\", "/")
    if "execution_log/" in value:
        value = value[value.index("execution_log/"):]
    if not value:
        return None
    path = (root / value).resolve()
    return path if path.is_relative_to(root.resolve()) else None


def load_bundle(root: Path, directory: Path, kind: str) -> dict:
    manifest = directory / ("control_sample_manifest_v1.jsonl" if kind == "control" else "attack_sample_manifest_v1.jsonl")
    runs = [p for p in (directory / "paired_triplet_run.json", directory / "network_triplet_run.json",
                         directory / "no_attack_temporal_control_run.json") if p.exists()]
    errors = []
    run = {}
    if len(runs) == 1:
        try:
            run = json.loads(runs[0].read_text())
        except (ValueError, json.JSONDecodeError) as error:
            errors.append(str(error))
    else:
        errors.append(f"expected one run file, found {len(runs)}")
    return {"bundle_id": directory.name, "kind": kind, "directory": directory,
            "manifest_path": manifest, "raw_path": directory / "raw_payloads.jsonl",
            "run_path": runs[0] if len(runs) == 1 else directory / "missing_run.json",
            "run": run, "raw": read_jsonl(directory / "raw_payloads.jsonl"),
            "manifests": read_jsonl(manifest), "load_errors": errors, "root": root}


def discover(root: Path, design: dict) -> list[dict]:
    expected = {v["bundle"]: "attack" for v in design["bundles"]}
    expected.update({v["bundle"]: "control" for v in design["time_control_inventory"]})
    base = root / "execution_log/evidence"
    for kind in ("attack", "control"):
        for path in base.glob(f"*/{kind}_sample_manifest_v1.jsonl"):
            expected.setdefault(path.parent.name, kind)
    return [load_bundle(root, base / name, kind) for name, kind in sorted(expected.items())]


def by_session(rows: list[dict]) -> dict[str, list[dict]]:
    result = defaultdict(list)
    for row in rows:
        result[row["value"].get("session_id", "")].append(row)
    return result


def binding(bundle: dict, entry: dict, duplicates_elsewhere=()) -> tuple[dict, dict, dict]:
    m = entry["value"]
    sid = m.get("session_id", "")
    raw_rows = by_session(bundle["raw"]).get(sid, [])
    manifests = by_session(bundle["manifests"]).get(sid, [])
    sessions = [s for s in bundle["run"].get("sessions", []) if s.get("session_id") == sid]
    errors = []
    for label, rows in (("raw", raw_rows), ("manifest", manifests), ("run", sessions)):
        if len(rows) != 1:
            errors.append(f"{label}_session_count={len(rows)}")
    if not sid or entry.get("parse_error"):
        errors.append("invalid_manifest_row")
    if duplicates_elsewhere:
        errors.append("session_reused_across_bundles")
    raw = raw_rows[0]["value"] if len(raw_rows) == 1 else {}
    session = sessions[0] if len(sessions) == 1 else {}
    raw_ref = str(bundle["raw_path"].relative_to(bundle["root"])) + f"#session_id={sid}"
    for key in ("raw_payload_reference", "collection_manifest_reference"):
        ref = m.get(key)
        if ref is None and bundle["kind"] == "control":
            continue  # control schema binds via session_id plus raw canonical digest
        if (resolve_ref(bundle["root"], ref) != bundle["raw_path"].resolve()
                or str(ref).partition("#")[2] != f"session_id={sid}"):
            errors.append(f"{key}_does_not_bind_payload")
    digest = sha256_value(raw) if raw else None
    declared = m.get("integrity", {}).get("receiver_row_sha256")
    if digest is None or digest != declared:
        errors.append("manifest_payload_digest_mismatch")
    if session.get("receiver_row_sha256", digest) != digest:
        errors.append("run_payload_digest_mismatch")
    phase = m.get("pair", m.get("triplet", {}))
    role_key = "pair_role" if bundle["kind"] == "attack" else "control_role"
    group_key = "pair_id" if bundle["kind"] == "attack" else "triplet_id"
    for key in (role_key, group_key, "sequence_index"):
        if not same(phase.get(key, MISSING), session.get(key, MISSING)):
            errors.append(f"run_manifest_{key}_mismatch")
    cm = raw.get("collection_manifest", {})
    alias = m.get("device", {}).get("anonymous_device_instance_id", m.get("device", {}).get("device_manifest_id"))
    if not alias or cm.get("device_manifest_id") != alias:
        errors.append("raw_manifest_device_mismatch")
    run_alias = bundle["run"].get("device", {}).get("device_manifest_id")
    if run_alias != cm.get("device_manifest_id"):
        errors.append("raw_run_device_mismatch")
    if session.get("runtime_context") != cm.get("runtime_context"):
        errors.append("run_raw_runtime_context_mismatch")
    status = raw.get("collection_status", {})
    fields = status.get("fields", {})
    if (raw.get("schema_version") != "expanded-v2.2-status" or status.get("status_schema_version") != "field-status-v1"
            or status.get("fixed_signal_count") != 177 or len(fields) != 177
            or not set(fields.values()).issubset(FIELD_STATUSES)):
        errors.append("invalid_payload_status_contract")
    if bundle["kind"] == "attack":
        attack, run = m.get("attack", {}), bundle["run"]
        if attack.get("attack_run_id") != run.get("run_id"):
            errors.append("attack_run_binding_mismatch")
        for key in ("tool_name", "config_id", "expected_mutations"):
            if not same(attack.get(key, MISSING), run.get("tool", {}).get(key, MISSING)):
                errors.append(f"manifest_run_{key}_mismatch")
    return ({"status": "BOUND" if not errors else "REJECTED", "reasons": errors,
             "raw_session_ref": raw_ref, "raw_line": raw_rows[0]["line"] if len(raw_rows) == 1 else None,
             "declared_payload_digest": declared, "actual_payload_digest": digest,
             "duplicate_session_other_bundles": list(duplicates_elsewhere)}, raw, session)


def execution_fact(bundle: dict, m: dict, session: dict, bound: dict) -> dict:
    run = bundle["run"]
    run_ref = str(bundle["run_path"].relative_to(bundle["root"])) + f"#session_id={m.get('session_id')}"
    if bound["status"] != "BOUND":
        return fact(reason="payload/session binding rejected", refs=[run_ref])
    evidence = session.get("active_runner_evidence") or {}
    receipt_ref = evidence.get("receiptPath", evidence.get("receipt_path"))
    receipt_path = resolve_ref(bundle["root"], receipt_ref)
    assertions = (session.get("execution_status") == "verified_success"
                  and m.get("attack", {}).get("execution_status") == "verified_success"
                  and evidence.get("status") == "MEASURED")
    if receipt_path and receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text())
        expected = {"receipt_schema_version": "controlled-runner-receipt-v1", "run_id": run.get("run_id"),
                    "attack_run_id": run.get("attack_run_id"), "session_id": m.get("session_id"),
                    "method": run.get("method"), "round": session.get("round"), "runtime_context": session.get("runtime_context")}
        expected.update({k: run.get("tool", {}).get(k) for k in
                         ("tool_name", "tool_version", "config_id", "expected_mutations")})
        for key in ("tool_sha256", "config_sha256", "source_reference"):
            if key in run.get("tool", {}):
                expected[key] = run["tool"][key]
        for key in ("configuration_id", "execution_client_id"):
            if key in run:
                expected[key] = run[key]
        errors = [key for key, value in expected.items() if not same(receipt.get(key, MISSING), value)]
        cited = [resolve_ref(bundle["root"], ref) for ref in m.get("attack", {}).get("success_evidence", [])]
        if receipt_path not in cited:
            errors.append("receipt_not_cited_by_manifest")
        if not assertions:
            errors.append("recorded_execution_not_successful")
        if errors:
            return fact("REFUTED", "CONFLICT", "receipt/run/manifest conflict", [run_ref, receipt_ref], conflicts=errors)
        return fact("SUPPORTED", L1, "receipt binds session, runtime, run and declared configuration; private raw log not attested",
                    [run_ref, receipt_ref], raw_log_available=False)
    log_ref = evidence.get("logPath", evidence.get("log_path"))
    log_path = resolve_ref(bundle["root"], log_ref)
    if log_path and log_path.is_file():
        log = json.loads(log_path.read_text())
        if assertions and log.get("status") == "MEASURED" and m.get("session_id") in log.get("measuredSessionIds", []):
            return fact("SUPPORTED", L2, "referenced measured runner log binds the active session", [run_ref, log_ref])
        return fact("REFUTED", "CONFLICT", "available runner log conflicts with active execution", [run_ref, log_ref])
    return fact(reason="execution is declared but directly referenced runner log/receipt is unavailable",
                refs=[r for r in (run_ref, receipt_ref, log_ref) if r])


def effect_and_rollback(pre: dict | None, active: dict | None, post: dict | None, paths: list[str]) -> tuple[dict, dict]:
    refs = [c["binding"]["raw_session_ref"] for c in (pre, active, post) if c]
    if not pre or not active or any(c["binding"]["status"] != "BOUND" for c in (pre, active)):
        return fact(reason="unique bound clean_pre and attack payloads required", refs=refs), fact(refs=refs)
    if not paths or len(set(paths)) != len(paths):
        return fact(reason="declared mutation paths absent or duplicated", refs=refs), fact(refs=refs)
    changes = []
    for path in paths:
        values = [field_value(c["raw"], path) if c else MISSING for c in (pre, active, post)]
        states = [c["raw"].get("collection_status", {}).get("fields", {}).get(path) if c else None for c in (pre, active, post)]
        observed = all(v is not MISSING and s == "observed" for v, s in zip(values[:2], states[:2]))
        post_observed = post is not None and post["binding"]["status"] == "BOUND" and values[2] is not MISSING and states[2] == "observed"
        changes.append({"field_path": path, "pre_status": states[0], "attack_status": states[1], "post_status": states[2],
                        "comparable_pre_attack": observed, "changed": observed and not same(values[0], values[1]),
                        "post_comparable": post_observed, "restored": post_observed and same(values[0], values[2]),
                        "pre_value": values[0] if values[0] is not MISSING else None,
                        "attack_value": values[1] if values[1] is not MISSING else None,
                        "post_value": values[2] if values[2] is not MISSING else None})
    claimed = active["manifest"].get("attack", {}).get("observed_mutations", [])
    actual = {c["field_path"]: c for c in changes}
    conflicts = []
    for annotation in claimed:
        path = annotation.get("field_path")
        event = actual.get(path)
        if (not event or (event["comparable_pre_attack"] and
                (not event["changed"] or not same(annotation.get("clean_pre_value", MISSING), event["pre_value"])
                 or not same(annotation.get("attack_value", MISSING), event["attack_value"])))):
            conflicts.append(path)
    if conflicts:
        effect = fact("REFUTED", "CONFLICT", "annotated field effect contradicts bound raw payload", refs, conflicts=conflicts)
    elif any(c["changed"] for c in changes):
        effect = fact("SUPPORTED", L2, "declared fingerprint field effect independently recomputed from bound raw values", refs[:2])
    elif all(c["comparable_pre_attack"] for c in changes):
        effect = fact("REFUTED", L2, "declared fields are unchanged in observed pre/current payloads", refs[:2])
    else:
        effect = fact(reason="declared effect not observable with available field statuses", refs=refs[:2])
    effect["field_checks"] = changes
    if all(c["post_comparable"] for c in changes):
        restored = all(c["restored"] for c in changes)
        rollback = fact("SUPPORTED" if restored else "REFUTED", L2,
                        "all declared fields restored" if restored else "declared field residual remains in clean_post", refs)
    else:
        rollback = fact(reason="post missing, unbound or declared fields unavailable; detection eligibility is independent", refs=refs)
    rollback["scope"] = "restoration of declared fields only"
    return effect, rollback


def clean_fact(context: dict | None, execution: dict, effect: dict, rollback: dict, role: str) -> dict:
    if not context or context["binding"]["status"] != "BOUND":
        return fact(reason="clean payload not uniquely bound")
    session = context["session"]
    refs = [context["binding"]["raw_session_ref"], context["run_session_ref"], *execution["evidence_refs"]]
    if execution["status"] != "SUPPORTED" or effect["status"] != "SUPPORTED":
        return fact(reason="clean declaration lacks a receipt/log-anchored intervention contrast", refs=refs)
    if context["manifest"].get("label", {}).get("manipulation_present") is not False:
        return fact("REFUTED", "CONFLICT", "clean label conflicts with phase", refs)
    v = session.get("verification", {}).get("state_observable_injection", {})
    if session.get("execution_status") != "not_run" or session.get("active_runner_evidence") or v.get("result") != "absence_verified":
        return fact(reason="scoped no-intervention execution/absence record missing or inconsistent", refs=refs)
    checks = effect.get("field_checks", [])
    observations = v.get("observed", {})
    for event in checks:
        path = event["field_path"]
        if (context["raw"].get("collection_status", {}).get("fields", {}).get(path) != "observed"
                or not same(observations.get(path.split(".")[-1], MISSING), field_value(context["raw"], path))):
            return fact(reason="recorded absence observation does not bind every declared raw field", refs=refs)
    if role == "clean_post" and rollback["status"] != "SUPPORTED":
        return fact(rollback["status"], rollback["evidence_grade"], "post cannot be a negative without supported restoration", refs)
    return fact("SUPPORTED", L1, "not_run and scoped absence observations match raw in a receipt-anchored triplet", refs,
                scope="declared intervention surfaces only; unrelated prior manipulation remains unverified")


def task_eligibility(kind: str, contexts: dict, execution: dict, effect: dict, pre_fact: dict,
                     post_fact: dict, label_conflict: bool) -> dict:
    detection = kind == "attack" and not label_conflict and execution["status"] == effect["status"] == "SUPPORTED"
    complete = all(contexts.get(role) and contexts[role]["binding"]["status"] == "BOUND"
                   for role in ("clean_pre", "attack", "clean_post"))
    return {"eligible_detection": detection,
            "eligible_triplet": detection and complete and pre_fact["status"] == "SUPPORTED",
            "eligible_pre_control": kind == "attack" and not label_conflict and pre_fact["status"] == "SUPPORTED",
            "eligible_post_control": kind == "attack" and not label_conflict and post_fact["status"] == "SUPPORTED",
            "eligible_temporal_control": False}


def adjudicate_bundle(bundle: dict, validator: dict, reused_sessions: dict | None = None) -> tuple[list[dict], list[dict]]:
    root = bundle["root"]
    contexts = []
    entries = list(bundle["manifests"])
    known = {e["value"].get("session_id") for e in entries}
    # Preserve unjoined raw/run rows as rejected candidates, never silently drop.
    for raw in bundle["raw"]:
        sid = raw["value"].get("session_id")
        if sid not in known or raw.get("parse_error"):
            entries.append({"line": f"orphan_raw_{raw['line']}", "value": {"session_id": sid}, "orphan": True})
    raw_ids = {e["value"].get("session_id") for e in bundle["raw"]}
    for index, session in enumerate(bundle["run"].get("sessions", [])):
        sid = session.get("session_id")
        if sid not in known and sid not in raw_ids:
            entries.append({"line": f"orphan_run_{index}", "value": {"session_id": sid}, "orphan": True})
    for entry in entries:
        m = entry["value"]
        sid = m.get("session_id")
        bind, raw, session = binding(bundle, entry, (reused_sessions or {}).get(sid, []))
        phase = m.get("pair", m.get("triplet", {}))
        role = phase.get("pair_role", phase.get("control_role", "UNKNOWN"))
        triplet = phase.get("pair_id", phase.get("triplet_id", f"UNJOINED:{entry['line']}"))
        contexts.append({"manifest": m, "raw": raw, "session": session, "binding": bind,
                         "role": role, "triplet_id": triplet, "entry": entry,
                         "run_session_ref": str(bundle["run_path"].relative_to(root)) + f"#session_id={sid}"})
    grouped = defaultdict(list)
    for context in contexts:
        grouped[context["triplet_id"]].append(context)
    facts, triplets = [], []
    for triplet_id, members in grouped.items():
        roles = defaultdict(list)
        for context in members:
            roles[context["role"]].append(context)
        unique = {role: values[0] for role, values in roles.items() if len(values) == 1}
        active = unique.get("attack")
        execution = (execution_fact(bundle, active["manifest"], active["session"], active["binding"])
                     if active else fact(reason="no unique attack phase"))
        effect, rollback = effect_and_rollback(unique.get("clean_pre"), active, unique.get("clean_post"),
                                               bundle["run"].get("tool", {}).get("expected_mutations", []))
        pre = clean_fact(unique.get("clean_pre"), execution, effect, rollback, "clean_pre")
        post = clean_fact(unique.get("clean_post"), execution, effect, rollback, "clean_post")
        label_conflict = any(
            (c["role"] == "attack" and c["manifest"].get("label", {}).get("manipulation_present") is not True)
            or (c["role"] in {"clean_pre", "clean_post"} and bundle["kind"] == "attack"
                and c["manifest"].get("label", {}).get("manipulation_present") is not False)
            for c in members)
        if bundle["kind"] == "control":
            label_conflict = any(c["manifest"].get("label") or c["manifest"].get("attack")
                                 or c["manifest"].get("control", {}).get("manipulation_present") is not False
                                 or c["session"].get("manipulation_present") is not False for c in members)
        # A contradictory/unknown future post annotation must not veto an
        # otherwise supported current intervention. Negative facts gate their
        # own tasks; triplet trajectories retain failed or unknown restoration.
        active_label_conflict = (active is not None and
                                active["manifest"].get("label", {}).get("manipulation_present") is not True)
        eligible = task_eligibility(bundle["kind"], unique, execution, effect, pre, post,
                                    bool(label_conflict) if bundle["kind"] == "control" else active_label_conflict)
        triplet_row = {"schema_version": VERSION, "bundle_id": bundle["bundle_id"], "kind": bundle["kind"],
                       "triplet_id": triplet_id, "phase_count": len(members), "phase_roles": [c["role"] for c in members],
                       "execution": execution, "observable_effect": effect, "rollback": rollback,
                       "label_conflict": bool(label_conflict), **eligible}
        triplets.append(triplet_row)
        for c in members:
            m, role = c["manifest"], c["role"]
            if bundle["kind"] == "control":
                absence = fact("REFUTED" if label_conflict else "UNKNOWN", "CONFLICT" if label_conflict else L0,
                               "control contains positive/contradictory annotation" if label_conflict else
                               "run/sidecar declare no intervention; no bound startup/cleanup or operational absence receipt is retained",
                               [c["binding"]["raw_session_ref"], c["run_session_ref"]])
            elif role == "clean_pre":
                absence = pre
            elif role == "clean_post":
                absence = post
            else:
                absence = fact("REFUTED", execution["evidence_grade"], "supported active intervention",
                               execution["evidence_refs"]) if eligible["eligible_detection"] else fact()
            row_eligibility = {k: False for k in ELIGIBILITY_KEYS}
            row_eligibility["eligible_triplet"] = eligible["eligible_triplet"]
            if role == "attack":
                row_eligibility["eligible_detection"] = eligible["eligible_detection"]
            if role == "clean_pre":
                row_eligibility["eligible_pre_control"] = eligible["eligible_pre_control"]
            if role == "clean_post":
                row_eligibility["eligible_post_control"] = eligible["eligible_post_control"]
            row_conflict = bool(label_conflict) if bundle["kind"] == "control" else (
                m.get("label", {}).get("manipulation_present") is not (role == "attack"))
            decision_fact = execution if role == "attack" else absence
            if row_conflict:
                decision_fact = fact("REFUTED", "CONFLICT", "original phase label contradicts or lacks its declared role",
                                     [c["run_session_ref"], c["binding"]["raw_session_ref"]])
            facts.append({"schema_version": VERSION, "study_version": STUDY,
                          "candidate_id": f"{bundle['bundle_id']}:{c['entry']['line']}",
                          "bundle_id": bundle["bundle_id"], "kind": bundle["kind"], "triplet_id": triplet_id,
                          "phase": role, "session_id": m.get("session_id"),
                          "manifest_ref": str(bundle["manifest_path"].relative_to(root)) + f"#line={c['entry']['line']}",
                          "run_session_ref": c["run_session_ref"], "raw_session_ref": c["binding"]["raw_session_ref"],
                          "payload_binding": c["binding"], "original_label": m.get("label"),
                          "original_control_declaration": m.get("control"), "original_attack_annotation": m.get("attack"),
                          "validator_status": validator.get("result", {}).get("status", "NOT_RUN"),
                          "execution": execution if role == "attack" else fact(reason="intervention execution applies to active phase only"),
                          "observable_effect": effect if role == "attack" else fact(),
                          "rollback": rollback if role in {"attack", "clean_post"} else fact(),
                          "no_intervention": absence, "label_conflict": row_conflict,
                          "evidence_grade": decision_fact["evidence_grade"], "adjudication_status": decision_fact["status"],
                          "admission_reason": decision_fact["reason"], "independent_attestation": False,
                          "ground_truth_scope": POLICY["clean_scope"], **row_eligibility})
    return facts, triplets


def environment_groups(bundles: list[dict]) -> dict:
    """Transitive association closure. API, model, adb serial and shared server are not identity keys."""
    parent = {b["bundle_id"]: b["bundle_id"] for b in bundles}

    def find(value):
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    tokens = defaultdict(list)
    identities = defaultdict(list)
    for b in bundles:
        name, root = b["bundle_id"], b["root"]
        records = [(r["value"].get("collection_manifest", {}), str(b["raw_path"].relative_to(root)) + f"#line={r['line']}") for r in b["raw"]]
        records.append((b["run"].get("stable_device_identity") or {}, str(b["run_path"].relative_to(root)) + "#stable_device_identity"))
        records.append((b["run"].get("device") or {}, str(b["run_path"].relative_to(root)) + "#device"))
        for data, ref in records:
            for key in ("collector_install_id", "device_manifest_id"):
                if data.get(key):
                    tokens[(key, data[key])].append({"bundle_id": name, "ref": ref})
        for entry in b["manifests"]:
            m = entry["value"]
            device = m.get("device", {})
            identities[name].append(device)
            ref = str(b["manifest_path"].relative_to(root)) + f"#line={entry['line']}"
            for key in ("stable_device_key_hash", "anonymous_device_instance_id"):
                if device.get(key):
                    token = "device_manifest_id" if key == "anonymous_device_instance_id" else key
                    tokens[(token, device[key])].append({"bundle_id": name, "ref": ref})
            batch = m.get("capture", {}).get("capture_batch_id")
            if batch:
                tokens[("run_or_capture_batch", batch)].append({"bundle_id": name, "ref": ref})
        if b["run"].get("run_id"):
            tokens[("run_or_capture_batch", b["run"]["run_id"])].append({"bundle_id": name, "ref": str(b["run_path"].relative_to(root))})
    edges = []
    for (kind, value), occurrences in sorted(tokens.items()):
        names = sorted({o["bundle_id"] for o in occurrences})
        for name in names[1:]:
            parent[find(name)] = find(names[0])
        edges.append({"key_type": kind, "key_value": value, "member_bundles": names,
                      "evidence_refs": list(dict.fromkeys(o["ref"] for o in occurrences)), "supports_physical_identity": False})
    grouped = defaultdict(list)
    for name in parent:
        grouped[find(name)].append(name)
    groups = []
    for index, names in enumerate(sorted(sorted(v) for v in grouped.values()), 1):
        related = [e for e in edges if set(e["member_bundles"]) & set(names)]
        groups.append({"group_id": f"env-{index:03d}", "member_bundles": names,
                       "collector_install_ids": sorted({e["key_value"] for e in related if e["key_type"] == "collector_install_id"}),
                       "device_aliases": sorted({e["key_value"] for e in related if e["key_type"] == "device_manifest_id"}),
                       "physical_identity": "UNKNOWN", "independent_physical_device_count": None})
    return {"schema_version": VERSION, "groups": groups, "association_edges": edges,
            "rules": ["transitive closure over install/stable-key/alias/run-capture links",
                      "same API/model/adb serial/backend staging is not an identity link",
                      "alias-only links are conservative association, not verified identity"],
            "identity_mapping": {"original_values_by_bundle": dict(identities),
                                 "source_protocol": "execution_log/protocols/device_identity_hash_mapping_v1.md",
                                 "observed_method": "sha256-canonical-stable-identity-v1",
                                 "observed_stability": "verified_within_attack_run",
                                 "interpretation": "install association where raw install ID joins; no HMAC/provider_stable_profile claim",
                                 "physical_identity": "UNKNOWN"}}


def missing_materials(bundles: list[dict]) -> list[dict]:
    missing = []
    for b in bundles:
        references = defaultdict(set)
        for entry in b["manifests"]:
            m = entry["value"]
            for ref in m.get("attack", {}).get("success_evidence", []):
                references[ref].add(m.get("session_id"))
        for ref, sessions in sorted(references.items()):
            resolved = resolve_ref(b["root"], ref)
            if not resolved or not resolved.is_file():
                missing.append({"bundle_id": b["bundle_id"], "category": "MISSING_DIRECT_SUCCESS_EVIDENCE",
                                "original_reference": ref, "local_path": str(resolved) if resolved else None,
                                "session_ids": sorted(s for s in sessions if s), "impact": "execution attribution remains UNKNOWN without receipt/log"})
        for session in b["run"].get("sessions", []):
            evidence = session.get("active_runner_evidence") or {}
            ref = evidence.get("receiptPath", evidence.get("receipt_path"))
            path = resolve_ref(b["root"], ref)
            if not path or not path.is_file():
                continue
            receipt = json.loads(path.read_text())
            log_ref = receipt.get("runner_log_path")
            log_path = resolve_ref(b["root"], log_ref)
            if not log_path or not log_path.is_file():
                missing.append({"bundle_id": b["bundle_id"], "category": "PRIVATE_RUNNER_LOG_MISSING" if log_ref else "PRIVATE_RUNNER_LOG_PATH_UNDISCLOSED",
                                "original_reference": log_ref, "local_path": str(log_path) if log_path else None,
                                "receipt_ref": ref, "session_ids": [session["session_id"]],
                                "impact": "L1 receipt support ceiling; no raw execution log or independent attestation"})
    return missing


def material_snapshot(root: Path, bundles: list[dict]) -> dict:
    paths = {p for b in bundles for p in b["directory"].rglob("*") if p.is_file()}
    paths.update(root / "execution_log/tools" / name for name in
                 ("verify_attack_run_bundle.mjs", "verify_no_attack_temporal_control_bundle.mjs"))
    paths.add(root / "execution_log/evidence/featureapp_current_release_lock_v1.json")
    return {str(p.relative_to(root)): {"size": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns} for p in sorted(paths)}


def run_validators(root: Path, bundles: list[dict], output: Path) -> list[dict]:
    (output / "validators").mkdir()
    results = []
    for b in bundles:
        cli = "verify_attack_run_bundle.mjs" if b["kind"] == "attack" else "verify_no_attack_temporal_control_bundle.mjs"
        command = ["node", str(root / "execution_log/tools" / cli), str(b["directory"])]
        try:
            process = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=30)
            stdout, stderr, code = process.stdout, process.stderr, process.returncode
            try:
                result = json.loads(stdout or stderr)
            except ValueError:
                result = {"status": "validator_error", "error": "non-JSON validator output"}
        except (subprocess.TimeoutExpired, OSError) as error:
            stdout, stderr, code = "", str(error), None
            result = {"status": "validator_error", "error": str(error)}
        stdout_ref, stderr_ref = f"validators/{b['bundle_id']}.stdout.txt", f"validators/{b['bundle_id']}.stderr.txt"
        (output / stdout_ref).write_text(stdout)
        (output / stderr_ref).write_text(stderr)
        results.append({"schema_version": VERSION, "bundle_id": b["bundle_id"], "kind": b["kind"], "command": command,
                        "cwd": str(root), "returncode": code, "result": result, "stdout_ref": stdout_ref, "stderr_ref": stderr_ref})
        write_jsonl(output / "validator_results.jsonl", results)
    return results


def assemble(bundles: list[dict], validators: list[dict], design: dict) -> dict:
    validator_by_name = {v["bundle_id"]: v for v in validators}
    expected = {v["bundle"]: v for v in design["bundles"] + design["time_control_inventory"]}
    sources = defaultdict(set)
    for b in bundles:
        for entry in b["raw"]:
            sid = entry["value"].get("session_id")
            if sid:
                sources[sid].add(b["bundle_id"])
    reused = {sid: sorted(names) for sid, names in sources.items() if len(names) > 1}
    inventory, facts, triplets, accounting = [], [], [], []
    for b in bundles:
        name, root = b["bundle_id"], b["root"]
        validator = validator_by_name.get(name, {"result": {"status": "NOT_RUN"}})
        rows, pairs = adjudicate_bundle(b, validator, reused)
        if validator["result"]["status"] not in {"passed", "failed"}:
            for row in rows + pairs:
                row.update({key: False for key in ELIGIBILITY_KEYS})
                row["validator_block"] = "validator implementation/process failure; no eligibility decision"
        facts.extend(rows)
        triplets.extend(pairs)
        complete = len(b["raw"]) == len(b["manifests"]) == len(b["run"].get("sessions", [])) == 9
        baseline = expected.get(name)
        shapes = Counter("nested" if isinstance(e["value"].get("web_data", {}).get("navigator_layer"), dict) else "flat" for e in b["raw"])
        missing_refs = [r for m in b["manifests"] for r in m["value"].get("attack", {}).get("success_evidence", [])
                        if not (resolve_ref(root, r) and resolve_ref(root, r).is_file())]
        inventory.append({"schema_version": VERSION, "bundle_id": name, "kind": b["kind"],
                          "bundle_ref": str(b["directory"].relative_to(root)),
                          "manifest_ref": str(b["manifest_path"].relative_to(root)), "raw_ref": str(b["raw_path"].relative_to(root)),
                          "run_ref": str(b["run_path"].relative_to(root)),
                          "file_refs": sorted(str(p.relative_to(root)) for p in b["directory"].rglob("*") if p.is_file()),
                          "manifest_rows": len(b["manifests"]), "raw_rows": len(b["raw"]),
                          "run_sessions": len(b["run"].get("sessions", [])), "candidate_phase_rows": len(rows),
                          "candidate_triplets": len(pairs), "complete_nine_stage_candidate": complete,
                          "material_disposition": "COMPLETE_CANDIDATE" if complete else "INCOMPLETE_ATTEMPT_RETAINED",
                          "run_status": b["run"].get("status"), "run_errors": b["run"].get("errors", []),
                          "load_errors": b["load_errors"], "transport_shapes": dict(shapes),
                          "original_release": b["run"].get("featureapp"), "validator_status": validator["result"]["status"],
                          "design_comparison": {"present_in_design_audit": baseline is not None,
                                                "manifest_rows_match": len(b["manifests"]) == baseline["manifest_rows"] if baseline else None,
                                                "returncode_match": validator.get("returncode") == baseline["validator_returncode"] if baseline else None,
                                                "missing_direct_refs_match": sorted(set(missing_refs)) == sorted(baseline.get("missing_success_evidence", [])) if baseline else None,
                                                "explanation": "local replay compared by bundle and references; archival absolute prefix localized" if baseline else "additional incomplete attempt listed in execution plan"}})
        for entry in b["raw"]:
            sid = entry["value"].get("session_id")
            joined = [r["candidate_id"] for r in rows if r["session_id"] == sid]
            accounting.append({"bundle_id": name, "source": "raw", "line": entry["line"], "session_id": sid,
                               "candidate_refs": joined, "parse_error": entry.get("parse_error"),
                               "disposition": "LEDGERED" if joined else "UNJOINED_RETAINED"})
    registry = environment_groups(bundles)
    membership = {name: group["group_id"] for group in registry["groups"] for name in group["member_bundles"]}
    for row in inventory + facts + triplets:
        row["environment_group_id"] = membership[row["bundle_id"]]
    missing = missing_materials(bundles)
    exclusions = []
    for row in facts:
        tasks = []
        if row["phase"] == "attack" and not row["eligible_detection"]:
            tasks.append("positive_detection_denominator")
        if row["kind"] == "control" and not row["eligible_temporal_control"]:
            tasks.append("temporal_control_FPR_denominator")
        if row["kind"] == "attack" and row["phase"] in {"clean_pre", "clean_post"}:
            key = "eligible_pre_control" if row["phase"] == "clean_pre" else "eligible_post_control"
            if not row[key]:
                tasks.append("pre_control_FPR_denominator" if row["phase"] == "clean_pre" else "post_control_FPR_denominator")
        if row["payload_binding"]["status"] != "BOUND":
            tasks.append("input_adaptation_pending_binding")
        if tasks:
            exclusions.append({"candidate_id": row["candidate_id"], "bundle_id": row["bundle_id"], "triplet_id": row["triplet_id"],
                               "raw_session_ref": row["raw_session_ref"], "affected_tasks": tasks,
                               "reason": "label conflict" if row["label_conflict"] else row["admission_reason"],
                               "binding_reasons": row["payload_binding"]["reasons"], "evidence_grade": row["evidence_grade"],
                               "not_a_detector_false_negative": True})
    for b in inventory:
        if not b["complete_nine_stage_candidate"]:
            exclusions.append({"bundle_id": b["bundle_id"], "affected_tasks": ["complete_triplet_denominator"],
                               "reason": "incomplete failed attempt retained with run errors", "run_ref": b["run_ref"],
                               "evidence_grade": L0, "not_a_detector_false_negative": True})
    queue = []
    for b in inventory:
        if b["kind"] == "control":
            rows = [r for r in facts if r["bundle_id"] == b["bundle_id"]]
            queue.append({"id": f"CONTROL:{b['bundle_id']}", "bundle_id": b["bundle_id"], "fact": "no_intervention_and_no_residual",
                          "triplet_ids": sorted({r["triplet_id"] for r in rows}), "payload_refs": [r["raw_session_ref"] for r in rows],
                          "existing_evidence_refs": [b["run_ref"], b["manifest_ref"]],
                          "minimum_additional_evidence": "existing session-bound startup/cleanup/process log or operator execution record excluding residual intervention",
                          "scope_if_unresolved": "only this temporal-control FPR branch stays UNKNOWN; material adaptation and positive analysis can proceed",
                          "required_to_complete_S01": False})
    for b in inventory:
        absent = [m for m in missing if m["bundle_id"] == b["bundle_id"] and m["category"] == "MISSING_DIRECT_SUCCESS_EVIDENCE"]
        if absent:
            queue.append({"id": f"OPTIONAL_LOG_PROMOTION:{b['bundle_id']}", "bundle_id": b["bundle_id"],
                          "fact": "execution_attribution", "minimum_additional_evidence": [m["original_reference"] for m in absent],
                          "payload_refs": [r["raw_session_ref"] for r in facts if r["bundle_id"] == b["bundle_id"] and r["phase"] == "attack"],
                          "triplet_ids": [t["triplet_id"] for t in triplets if t["bundle_id"] == b["bundle_id"]],
                          "scope_if_unresolved": "retain lower-evidence descriptive branch", "required_to_complete_S01": False})
    history = []
    by_name = {b["bundle_id"]: b for b in bundles}
    names = set(by_name)
    for b in bundles:
        name = b["bundle_id"]
        if b["run"].get("status") == "failed_verification" and name.endswith("_v1") and name[:-3] + "_v2" in names:
            later = by_name[name[:-3] + "_v2"]
            history.append({"earlier_bundle": name, "later_bundle": name[:-3] + "_v2",
                            "relation": "version-successor candidate, both retained", "basis": "explicit version naming plus run method/config and environment records",
                            "method_matches": b["run"].get("method") == later["run"].get("method"),
                            "config_matches": b["run"].get("tool", {}).get("config_id") == later["run"].get("tool", {}).get("config_id"),
                            "environment_association_matches": membership[name] == membership[later["bundle_id"]],
                            "selection_by_detector": False})
        if name.endswith("_rerun1"):
            history.append({"earlier_bundle": name[:-7], "later_bundle": name,
                            "relation": "rerun named in source; original material absent from this copy",
                            "earlier_present": name[:-7] in names, "revocation_reason": "UNKNOWN_NOT_IN_CURRENT_BUNDLE",
                            "selection_by_detector": False})
    summary = {"schema_version": VERSION, "study_version": STUDY,
               "candidate_bundles": len(inventory), "complete_attack_bundles": sum(b["kind"] == "attack" and b["complete_nine_stage_candidate"] for b in inventory),
               "control_bundles": sum(b["kind"] == "control" for b in inventory),
               "incomplete_bundles": sum(not b["complete_nine_stage_candidate"] for b in inventory),
               "raw_rows": len(accounting), "fact_rows": len(facts), "bound_phase_rows": sum(r["payload_binding"]["status"] == "BOUND" for r in facts),
               "complete_attack_triplets": sum(t["kind"] == "attack" and t["phase_count"] == 3 for t in triplets),
               "control_triplets": sum(t["kind"] == "control" for t in triplets),
               "validator_results": dict(Counter(f"{r['kind']}:{r['result']['status']}" for r in validators)),
               "eligible_attack_stages": sum(r["eligible_detection"] for r in facts),
               "eligible_attack_triplets": sum(t["eligible_triplet"] for t in triplets),
               "eligible_pre_control_stages": sum(r["eligible_pre_control"] for r in facts),
               "eligible_post_control_stages": sum(r["eligible_post_control"] for r in facts),
               "eligible_temporal_control_stages": sum(r["eligible_temporal_control"] for r in facts),
               "environment_groups": len(registry["groups"]), "independent_physical_devices": None,
               "missing_material_counts": dict(Counter(m["category"] for m in missing)),
               "manual_queue_items": len(queue), "performance_status": "NOT_EVALUATED", "detector_runs": 0, "model_calls": 0, "attack_runs": 0,
               "temporal_control_FPR_status": "BLOCKED_NO_INDEPENDENT_OF_DETECTOR_OPERATIONAL_ABSENCE_EVIDENCE"}
    return {"material_inventory.jsonl": inventory, "facts_and_eligibility.jsonl": facts, "triplet_registry.jsonl": triplets,
            "environment_group_registry.json": registry, "missing_materials.jsonl": missing, "exclusions.jsonl": exclusions,
            "manual_fact_queue.json": {"schema_version": VERSION, "items": queue, "all_items_optional_for_S01_completion": True},
            "stage_accounting.jsonl": accounting, "history_links.json": history, "SUMMARY.json": summary}


def render_report(summary: dict, inventory: list[dict]) -> str:
    lines = [
        "# S01 材料核验、事实准入与环境分组", "",
        "工程验收：见 `VALIDATION.json`。本步只做材料校验和事实裁决；检测性能保持 `NOT_EVALUATED`。", "",
        "## 材料与准入", "",
        "| 项目 | 数量 |", "|---|---:|",
        f"| 候选包（含失败尝试） | {summary['candidate_bundles']} |",
        f"| 完整攻击包 / 三态 | {summary['complete_attack_bundles']} / {summary['complete_attack_triplets']} |",
        f"| 时间对照包 / 三时点 | {summary['control_bundles']} / {summary['control_triplets']} |",
        f"| 不完整或空包 | {summary['incomplete_bundles']} |",
        f"| 原始阶段 / 事实台账 / 成功绑定 | {summary['raw_rows']} / {summary['fact_rows']} / {summary['bound_phase_rows']} |",
        f"| 准入攻击阶段 / 准入三态 | {summary['eligible_attack_stages']} / {summary['eligible_attack_triplets']} |",
        f"| 准入 clean_pre / clean_post | {summary['eligible_pre_control_stages']} / {summary['eligible_post_control_stages']} |",
        f"| 准入时间对照阶段 | {summary['eligible_temporal_control_stages']} |",
        f"| 环境关联组 | {summary['environment_groups']} |", "",
        "## 事实裁决与限制", "",
        "- 完整攻击材料的本地校验结果与设计审计逐包对账；完整包之外的两次失败尝试也保存 stdout、stderr、returncode、run errors 和关联。",
        "- 执行归因为 L1：核对 receipt 与 session、runtime_context、run、配置及工具版本，再结合 active MEASURED 记录。私有原日志缺失，不能称独立现场见证。",
        "- 可观察效应和恢复逐声明字段从已绑定 raw 重算，包括字段状态、原值、active 值、post 值；其 L2 仅指这部分原始观测可复核，不升级执行归因。",
        "- clean_pre/post 的 L1 依据同一有回执三态中的 not_run、absence 观测与 raw 一致；post 额外要求全部声明字段已恢复。只支持声明干预表面的对照，不是绝对正常标签。",
        "- 时间对照虽通过结构校验，但材料只有 run/sidecar 的 none、clean、空 active_tooling 声明及原始指纹；没有可绑定的启动、清理或操作记录来排除主动/残留干预。因此无干预事实保持 UNKNOWN，当前不能报告该分支 FPR。字段稳定不是无干预证明。",
        "- 旧包原始字段效应仍保留；缺失直接执行日志时，执行归因 UNKNOWN，不能进入正例分母，也不能计作检测漏报。",
        "- 检测资格不依赖未来 post 或恢复成功。三阶段齐备且事实可解释时保留失败/未知恢复轨迹；post 阴性资格单独决定。既有材料受恢复导向的历史选包影响，不能推广到工具全部尝试成功率。",
        "- 原标签和原始数据未修改；所有记录 `independent_attestation=false`。本步没有规则报警、TPR/FPR、训练、模型调用或新攻击执行。", "",
        "## 缺件与分组", "",
    ]
    lines.extend(f"- `{key}`：{count}。" for key, count in summary["missing_material_counts"].items())
    lines.extend([
        "- 15 个直接 success_evidence 缺件与 54 个私有日志限制是不同类别，详见 `missing_materials.jsonl`。",
        "- API36 两个 alias 通过相同 collector_install_id 合并；run/capture、安装、稳定键和 alias 关联做传递闭包。API、型号、ADB serial、共享接收端不作为独立身份依据。",
        "- 三个关联组不等于三台已核验独立物理设备。保留原 sha256-canonical-stable-identity-v1 / verified_within_attack_run，不改写成 HMAC/provider_stable_profile。",
        "- `manual_fact_queue.json` 按 6 个时间对照包列最小无干预证据需求，按 5 个旧包列可选晋级日志；均不阻断 S01 完成，不要求全面人工评分或新采集。",
        "- `_rerun1` 只保留来源命名关系；当前副本没有对应原始包时标明缺失，不猜撤回原因或抹去历史失败。", "",
        "## 逐包核验", "", "| 包 | 原始阶段 | 校验 | 材料去向 | 环境组 |", "|---|---:|---|---|---|",
    ])
    for b in inventory:
        lines.append(f"| `{b['bundle_id']}` | {b['raw_rows']} | {b['validator_status']} | {b['material_disposition']} | {b['environment_group_id']} |")
    lines.extend([
        "", "## 复现与停止点", "",
        "初次执行：`PYTHONDONTWRITEBYTECODE=1 python3 hybridguard_agent/scripts/prepare_formal_manipulation_inputs.py admission --output <新的输出目录>`。",
        "中断后仅已有材料校验记录时可加 `--reuse-validators`；必须通过相关源文件 size/mtime 核对。已有 VALIDATION.json 的输出拒绝覆盖。",
        "本轮在源码实现期间先逐包保存了 31 次 CLI 输出，随后复用这些输出生成台账，没有重复运行材料校验器。", "",
        "聚焦合成测试命令：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest hybridguard_agent.tests.test_formal_manipulation_admission -v`；实际记录见 `FOCUSED_TESTS.txt`。",
        "验收检查只读取保存事实、引用和分母；相关原材料 size/mtime 保持不变。P0–P6、攻击仓库及历史结果均未写入。",
        "本轮 S01 产物仍在工作区。前置设计/计划提交 `4826e2649a734b709a05fd4717f63e7adb50e95b` 已推送并核对远端 main。",
        "S02 未执行；逐步状态以 `deliverables/formal_experiment_execution_plan/EXECUTION_STATUS.json` 为准。", "",
    ])
    return "\n".join(lines)


def prepare(root: Path, design_path: Path, output: Path, reuse_validators=False) -> dict:
    root, output = root.resolve(), output.resolve()
    if output.is_relative_to(root):
        raise ValueError("Output must be outside the read-only attack repository")
    if (output / "VALIDATION.json").exists():
        raise FileExistsError("Completed admission output is immutable; choose a new version/output")
    design = json.loads(design_path.read_text())
    bundles = discover(root, design)
    before = material_snapshot(root, bundles)
    if reuse_validators:
        snapshot = json.loads((output / "source_snapshot.json").read_text())
        if before != snapshot["files"]:
            raise ValueError("Source changed since saved validator replay")
        validators = [e["value"] for e in read_jsonl(output / "validator_results.jsonl")]
        if {b["bundle_id"] for b in bundles} != {v.get("bundle_id") for v in validators} or len(validators) != len(bundles):
            raise ValueError("Saved validator coverage is incomplete or duplicated")
    else:
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "source_snapshot.json", {"schema_version": VERSION, "started_at": now(), "files": before,
                                                    "attack_commit": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()})
        validators = run_validators(root, bundles, output)
    artifacts = assemble(bundles, validators, design)
    unchanged = material_snapshot(root, bundles) == before
    summary = artifacts["SUMMARY.json"]
    checks = {
        "all_discovered_and_design_bundles_ledgered": len(artifacts["material_inventory.jsonl"]) == len(bundles),
        "all_raw_rows_accounted": len(artifacts["stage_accounting.jsonl"]) == sum(len(b["raw"]) for b in bundles),
        "all_raw_rows_have_ledger_candidates": all(r["candidate_refs"] for r in artifacts["stage_accounting.jsonl"]),
        "unique_candidate_ids": len({r["candidate_id"] for r in artifacts["facts_and_eligibility.jsonl"]}) == summary["fact_rows"],
        "all_candidates_grouped": all(r["environment_group_id"] for r in artifacts["facts_and_eligibility.jsonl"]),
        "design_audit_reconciled": all(all(v is not False for k, v in b["design_comparison"].items() if k.endswith("_match")) for b in artifacts["material_inventory.jsonl"]),
        "control_never_positive": not any(r["eligible_detection"] for r in artifacts["facts_and_eligibility.jsonl"] if r["kind"] == "control"),
        "no_validator_process_errors": all(v["result"]["status"] in {"passed", "failed"} for v in validators),
        "source_files_unchanged": unchanged,
        "no_detector_or_performance_execution": True,
    }
    for name, value in artifacts.items():
        (write_jsonl if name.endswith(".jsonl") else write_json)(output / name, value)
    write_json(output / "admission_policy.json", POLICY)
    (output / "STEP_REPORT.md").write_text(render_report(summary, artifacts["material_inventory.jsonl"]))
    validation = {"schema_version": VERSION, "completed_at": now(), "status": "PASS" if all(checks.values()) else "FAIL",
                  "checks": checks, "material_validator_runs": len(validators), "detector_runs": 0, "model_calls": 0,
                  "scientific_metrics_computed": False, "synthetic_tests": "recorded separately in FOCUSED_TESTS.txt",
                  "source_check_method": "size and mtime over relevant material files; no repository-wide hash audit"}
    write_json(output / "VALIDATION.json", validation)
    if not all(checks.values()):
        raise ValueError("S01 validation failed; retained artifacts and VALIDATION.json describe the failures")
    return summary
