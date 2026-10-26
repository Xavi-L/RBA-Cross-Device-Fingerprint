"""Read the frozen 60-position linked-browser study without running a detector.

Returned objects are private intermediate data. The caller must sanitize them.
Source identities, receipts and capture paths never belong in a public export.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path


MEMBERS = "deliverables/cross_endpoint_constrained_extension_v1/results/members.jsonl"
PREDICTIONS = "deliverables/cross_endpoint_constrained_extension_v1/results/predictions.jsonl"
PILOT = "deliverables/browser67_pilot_intake_v1"
MATCHED = "deliverables/cross_endpoint_matched_controls_v1"


def _require(condition, message):
    if not condition:
        raise ValueError("linked_browser: " + message)


def _flatten(payload, prefix):
    return {
        f"{prefix}.{top}.{layer}.{key}": value
        for top in ("android_native_data", "webview_data", "web_data")
        for layer, values in payload.get(top, {}).items()
        for key, value in values.items()
    }


def _operands(payload):
    web = payload["web_data"]
    return {**{k: web["navigator_layer"][k] for k in ("language", "languages")},
            **{k: web["execution_layer"][k] for k in ("timezone_id", "timezone_offset")}}


def extract(repo: Path):
    """Return source audits and private records from original archives/sidecars."""
    repo = Path(repo).resolve()
    inputs = set()
    cache = {}

    def path(relative):
        candidate = (repo / relative).resolve()
        _require(candidate.is_relative_to(repo), "reference escapes repository")
        inputs.add(relative)
        return candidate

    def rows(relative):
        if relative not in cache:
            cache[relative] = [json.loads(s) for s in path(relative).read_text().splitlines() if s.strip()]
        return cache[relative]

    def document(relative):
        return json.loads(path(relative).read_text())

    def reference(text):
        relative, line = text.rsplit(":", 1)
        line = int(line)
        _require(line > 0, "invalid physical line")
        # Physical-line addressing must not silently collapse blank records.
        content = path(relative).read_text().splitlines()
        _require(line <= len(content) and bool(content[line - 1].strip()), "missing physical line")
        return json.loads(content[line - 1]), {"path": relative, "line": line}

    selected = [(i, m) for i, m in enumerate(rows(MEMBERS), 1)
                if m["cohort"] in ("pilot18", "b2b42")]
    _require(collections.Counter(m["cohort"] for _, m in selected) == {"pilot18": 18, "b2b42": 42},
             "frozen cohort sizes differ")
    _require(len({m["sample_id"] for _, m in selected}) == 60, "duplicate evaluation position")
    chosen_ids = {m["sample_id"] for _, m in selected}
    saved = collections.defaultdict(list)
    for line, row in enumerate(rows(PREDICTIONS), 1):
        if row["sample_id"] in chosen_ids:
            saved[row["sample_id"]].append((line, row))
    model_ids = sorted({r["model_id"] for values in saved.values() for _, r in values})
    _require(len(model_ids) == 3, "expected three saved model configurations")
    pilot_verification = document(PILOT + "/local_acceptance/verification.json")
    _require(pilot_verification["verification"] == "passed" and pilot_verification["verified_stages"] == 18,
             "pilot recorded verification unavailable")
    replacement = document(MATCHED + "/ATTEMPT_SELECTION.json")
    _require(replacement["selected_before_repair_results"] is True, "replacement policy unavailable")
    replaced = set(replacement["replacement_sample_ids"])
    positions_path = MATCHED + "/private_runs/formal01/evaluation/positions.jsonl"
    positions = {p["meta"]["sample_id"]: (i, p) for i, p in enumerate(rows(positions_path), 1)}
    groups = collections.defaultdict(list)
    bundles = []
    for member_line, m in selected:
        meta = m["source_meta"]
        app_archive, app_ref = reference(meta["app_reference"])
        browser_archive, browser_ref = reference(meta["browser_reference"])
        capture, capture_ref = reference(meta["capture_reference"])
        provenance = [dict(path=MEMBERS, line=member_line), app_ref, browser_ref, capture_ref]
        if m["cohort"] == "pilot18":
            prov_ref_text = PILOT + "/evidence_archive/data/browser_pair_provenance.jsonl:" + str(capture["archives"]["provenance"]["line"])
            inventory, inventory_ref = reference(meta["evaluation_basis"])
            paired, paired_ref = reference(meta["pair_reference"])
            provenance.extend([inventory_ref, paired_ref, {"path": PILOT + "/local_acceptance/verification.json"}])
            _require(inventory["sample_id"] == m["sample_id"] and inventory["pair_binding_checked"] is True,
                     "pilot inventory identity mismatch")
            _require(capture["result"] == "completed" and capture["pair_completed"] is True,
                     "pilot capture incomplete")
        else:
            prov_ref_text = meta["provenance_reference"]
            expected = replacement["replacement_run"] if m["sample_id"] in replaced else replacement["original_run"]
            _require(meta["source_run"] == expected, "canonical attempt differs from frozen replacement policy")
            _require(capture["sample_id"] == m["sample_id"] and capture["result"] == "COMPLETED",
                     "matched capture identity mismatch")
            qline, position = positions[m["sample_id"]]
            _require(position["meta"]["app_reference"] == meta["app_reference"] and
                     position["meta"]["browser_reference"] == meta["browser_reference"], "qualification reference mismatch")
            _require(not any(position[k] for k in ("app_errors", "browser_errors", "pair_errors")), "saved binding failure")
            _require(position["qualification"]["fully_qualified"] is True, "recorded qualification incomplete")
            provenance.extend([{"path": positions_path, "line": qline}, {"path": MATCHED + "/ATTEMPT_SELECTION.json"}])
        pair, pair_ref = reference(prov_ref_text)
        provenance.append(pair_ref)
        app = app_archive["canonical_received_payload"]
        browser = browser_archive["canonical_received_payload"]
        _require(pair["pair_status"] == "completed", "pair not completed")
        _require(app["session_id"] == app_archive["session_id"] == pair["app_session_id"] == browser_archive["app_session_id"], "App session binding failure")
        for key in ("receipt_id", "payload_sha256", "collection_batch_id"):
            pkey = key if key == "collection_batch_id" else "app_" + key
            _require(pair[pkey] == app_archive[key], "App provenance mismatch")
        for key in ("browser_session_id", "browser_receipt_id", "browser_payload_sha256", "pair_id", "app_receipt_id", "collection_batch_id"):
            _require(pair[key] == browser_archive[key], "Browser provenance mismatch")
        _require(browser["browser_session_id"] == pair["browser_session_id"] and browser["pair_id"] == pair["pair_id"], "Browser payload binding failure")
        _require(capture["binding"]["app_session_id"] == app_archive["session_id"] and
                 capture["binding"]["browser_session_id"] == browser_archive["browser_session_id"], "capture binding failure")
        flat_app, flat_browser = _flatten(app, "app"), _flatten(browser, "browser")
        _require(len(flat_app) == 177 and len(flat_browser) == 67, "raw view does not have 177 plus 67 recorded fields")
        if m["cohort"] == "pilot18":
            _require(paired["sample_id"] == m["sample_id"] and paired["features"] == {**flat_app, **flat_browser}, "pilot snapshot disagrees with original payloads")
        _require(len(saved[m["sample_id"]]) == 3 and len({x["model_id"] for _, x in saved[m["sample_id"]]}) == 3,
                 "saved detector outputs duplicated or missing")
        bundles.append(dict(member=m, app=app, browser=browser, capture=capture, provenance=provenance))
        groups[m["group_id"]].append(bundles[-1])

    # Verify observable effects from the raw sibling observations. This is an
    # extraction check, not execution of an attack, relation, or learned model.
    for group in groups.values():
        _require(len(group) == 3, "incomplete three-phase experiment group")
        by_phase = {x["member"]["phase"]: x for x in group}
        pilot = group[0]["member"]["cohort"] == "pilot18"
        names = ("clean_pre", "attack_active", "clean_post") if pilot else ("pre", "change", "post")
        _require(set(by_phase) == set(names), "three-phase group has repeated phase")
        pre, active, post = [by_phase[k] for k in names]
        m = active["member"]
        if m["identity"] == "EFFECTIVE_INTERVENTION":
            endpoint = "browser" if m["family"].startswith("Browser") else "app"
            before, current, after = [_operands(x[endpoint]) for x in (pre, active, post)]
            keys = ("language", "languages") if m["family"].endswith("language") else ("timezone_id", "timezone_offset")
            expected = {"language": "fr-FR", "languages": ["fr-FR"]} if keys[0] == "language" else {"timezone_id": "Asia/Tokyo", "timezone_offset": -540}
            _require(all(current[k] == expected[k] for k in keys), "target values not present in original payload")
            _require(any(before[k] != current[k] for k in keys), "recorded effective intervention has no field change")
            _require(all(after[k] == before[k] for k in keys), "target recovery not supported by raw siblings")
            other = "app" if endpoint == "browser" else "browser"
            _require(_operands(pre[other]) == _operands(active[other]), "non-target endpoint changed")

    records = []
    for b in bundles:
        m, app, browser, capture = (b[k] for k in ("member", "app", "browser", "capture"))
        effective = m["identity"] == "EFFECTIVE_INTERVENTION"
        normal = m["identity"] == "NORMAL" and m["normal_identity_supported"] is True
        _require(effective or normal, "unconfirmed original experiment identity")
        detector = {}
        for line, output in saved[m["sample_id"]]:
            detector["saved_configuration_" + str(model_ids.index(output["model_id"]) + 1)] = {
                "app": output["base_state"], "app_plus_browser_C1": output["state"]}
            b["provenance"].append({"path": PREDICTIONS, "line": line})
        manifest = app["collection_manifest"]
        # Execution evidence is read independently of the effective-modification
        # label. A recorded installation alone never proves a feature changed.
        installation = capture.get("control_installation")
        if isinstance(installation, dict) and installation.get("method") == "none":
            tool_status = "NOT_APPLICABLE"
        elif isinstance(installation, dict) and installation.get("method"):
            response = installation.get("result", {})
            tool_status = ("RECORDED_SUCCESS" if "result" in installation and
                           not any(k in response for k in ("error", "exceptionDetails"))
                           else "UNKNOWN")
        elif capture.get("control_installed") is True:
            tool_status = "RECORDED_CONTROL_INSTALLED"
        else:
            tool_status = capture.get("setting", {}).get("status", "NOT_APPLICABLE")
        records.append({
            "source_id": "linked_browser_" + m["cohort"],
            "record_key": app["session_id"],
            "app": app,
            "browser": browser["web_data"],
            "browser_status": browser["field_statuses"],
            "metadata": {"cohort": m["cohort"], "environment": m["environment"],
                         "schema_version": app["schema_version"], "browser_schema_version": browser["schema_version"],
                         "android_api": manifest["android_api"], "android_release": manifest["android_release"],
                         "pair_status": "completed", "study_role": "extension_development",
                         "label_scope": "controlled_candidate_run_scope_not_physical_device_ground_truth"},
            "annotation": {"label": "modified" if effective else "normal_control",
                           "label_verification": "verified_recorded_evidence",
                           "tool_execution_status": tool_status,
                           "target_effect_status": m["operation_effect"],
                           "detector_outcome": detector,
                           "manipulation_type": m["family"] if effective else "none",
                           "normal_scenario": m["scenario"] if normal else None,
                           "restoration_status": "verified_recorded_evidence" if m["runtime_restored"] else "unknown",
                           "annotation_basis": "Saved operation qualification and linked raw three-phase target comparison; saved detector output kept separate."},
            "group_key": manifest.get("collector_install_id") or m["environment"],
            "group_basis": "collector_installation_within_emulator_environment_not_independent_physical_device",
            "triplet_key": m["group_id"], "phase": m["phase"], "provenance": b["provenance"],
        })
    _require(len({r["record_key"] for r in records}) == 60, "same raw App observation reused")
    sources = []
    for cohort in ("pilot18", "b2b42"):
        rr = [r for r in records if r["metadata"]["cohort"] == cohort]
        sources.append({
            "source_id": "linked_browser_" + cohort, "source_type": "controlled_linked_browser_development",
            "record_count": len(rr), "view": "Paired244", "schema_version": "expanded-v2.2-status + browser-web-v1-status",
            "status": "release_candidate", "permission_status": "PENDING_CONFIRMATION",
            "privacy_status": "raw_archives_restricted_candidate_requires_sanitization_and_review",
            "paper_experiment": "RQ4 linked Browser extension: shared 60 positions",
            "labels": dict(collections.Counter(r["annotation"]["label"] for r in rr)),
            "available_field_counts": {"native": 84, "webview_host": 26, "app_web": 67, "browser_web": 67},
            "experiment_groups": len({r["triplet_key"] for r in rr}), "independent_physical_device_count": None,
            "source_paths": sorted({p["path"] for r in rr for p in r["provenance"]}),
            "overlap": "Pilot snapshot contains these exact 18 positions; never add it again." if cohort == "pilot18" else "42 canonical positions from 48 attempts; six superseded original language-preference attempts excluded.",
            "label_basis": "Recorded operation qualification, raw target change and recovery, completed endpoint binding; detector outputs are separate saved evidence.",
        })
    return {"sources": sources, "records": records, "inputs": sorted(inputs), "issues": [
        "All 60 positions were used in extension development; no independent test split is created.",
        "There are 20 correlated three-phase groups across two emulator environments, not 60 devices.",
        "Pilot18 is included once; its 18-row paired snapshot is an overlapping representation.",
        "Six superseded original matched-control attempts remain in the source archive and are excluded by the original predeclared replacement policy.",
        "All source ownership, contributor permission and public redistribution decisions remain PENDING_CONFIRMATION.",
    ]}
