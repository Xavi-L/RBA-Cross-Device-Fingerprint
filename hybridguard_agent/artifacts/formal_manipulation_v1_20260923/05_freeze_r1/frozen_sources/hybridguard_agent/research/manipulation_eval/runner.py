"""Blind worker and durable prediction stage. This module never reads facts."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

from hybridguard_agent.evidence.paired244 import build_paired_evidence
from hybridguard_agent.retrieval.paired244 import build_paired_context
from hybridguard_agent.rules.paired244 import execute_paired_rules, paired_decision
from hybridguard_agent.verification.paired244 import verify_paired_output
from hybridguard_agent.research.manipulation_eval.adapter import PAYLOAD_KEYS, SECTIONS, selected_fields, project_payload, VERSION as ADAPTER_VERSION
from hybridguard_agent.research.manipulation_eval.baselines import legacy19_catalog
from hybridguard_agent.research.manipulation_eval.contract import VERSION, POLICY_VERSION, STUDY_VERSION, read_json, strict_json
from hybridguard_agent.research.manipulation_eval.policy import build_events, decide
from hybridguard_agent.research.manipulation_eval.verification import verify_policy_output

APP_VIEWS = ("App177", "Native84", "Host26", "AppWeb67", "NativeAppWeb151")
METHODS = ("final_v3_v2", "legacy19_v2")


from hybridguard_agent.research.manipulation_eval.persistence import new_output, write_json, write_jsonl


def worker(payload, *, contract, condition_id, input_view="App177", method="final_v3_v2"):
    """No opaque IDs, metadata, labels, file paths, histories or evaluation API."""
    if condition_id not in contract["conditions"] or method not in METHODS or input_view not in APP_VIEWS:
        raise ValueError("Unregistered worker variant")
    catalog = contract["catalog"] if method == "final_v3_v2" else legacy19_catalog()
    started = time.perf_counter()
    timings, runtime, events, verification = {}, None, [], None
    stage = "parse"

    def timed(name, fn):
        before = time.perf_counter()
        try:
            return fn()
        finally:
            timings[name] = (time.perf_counter() - before) * 1000

    try:
        def projection():
            if not isinstance(payload, dict) or set(payload) != PAYLOAD_KEYS:
                raise ValueError("Payload-only schema violation")
            # Check envelope/key topology before masking, selected values only after.
            if any(not isinstance(payload[s], dict) or set(payload[s]) != selected_fields("App177") for s in SECTIONS):
                raise ValueError("Incomplete or unregistered App177 field set")
            if payload["record_schema_version"] != "hybridguard-mtc-observation-v2" or payload["adapter_version"] != ADAPTER_VERSION:
                raise ValueError("Adapter version mismatch")
            return project_payload(payload, input_view)
        projected = timed("parse", projection)
        stage = "evidence"
        bundle = timed(stage, lambda: build_paired_evidence(projected, input_view))
        stage = "rules"
        execution = timed(stage, lambda: execute_paired_rules(bundle, catalog))
        stage = "retrieval"
        context = timed(stage, lambda: build_paired_context(bundle, execution, catalog))
        original_decision = paired_decision(execution)
        runtime = {"evidence_bundle": bundle, "rule_execution": execution, "context_pack": context, "decision": original_decision}
        stage = "original_verifier"
        original_verification = timed(stage, lambda: verify_paired_output(bundle, execution, context, original_decision, catalog))
        runtime["verification"] = original_verification
        if not original_verification["valid"]:
            raise ValueError("Original verification failed")
        stage = "risk_policy"
        def risk():
            current_events = build_events(runtime, contract, condition_id=condition_id, catalog=catalog)
            return current_events, decide(current_events, contract, condition_id=condition_id, catalog=catalog)
        events, decision = timed(stage, risk)
        stage = "risk_verifier"
        verification = timed(stage, lambda: verify_policy_output(runtime, events, decision, contract, condition_id=condition_id, catalog=catalog))
        if not verification["valid"]:
            raise ValueError("Risk verification failed")
        error = None
    except Exception as exc:
        # Exception text can contain raw data/paths. Keep only bounded stage/type.
        error = {"stage": stage, "error_type": type(exc).__name__, "reason_code": "UNIT_EXECUTION_FAILED", "retry_of": None}
        events = build_events(runtime, contract, condition_id=condition_id, catalog=catalog, failure=True)
        decision = decide(events, contract, condition_id=condition_id, catalog=catalog, failure=True)
    timings["total"] = (time.perf_counter() - started) * 1000
    return {"execution_status": "FAILED" if error else "COMPLETED", "risk": decision,
            "rule_events": events, "original_runtime": runtime, "verification": verification,
            "failure": error, "timings_ms": timings, "catalog_version": catalog["catalog_version"],
            "runtime_adapter_version": catalog.get("benchmark_adapter_version", "original-paired244-chain-v3"),
            "external_model_calls": 0}


def validate_protocol(protocol, contract):
    required = {"schema_version", "study_version", "run_id", "protocol_digest", "contract_version", "policy_version",
                "execution_scope", "variants", "expected_units"}
    formal = protocol.get("execution_scope") == "FROZEN_FORMAL_EVALUATION"
    if set(protocol) != required | ({"freeze"} if formal else set()) or protocol["schema_version"] != "formal-prediction-job-v2":
        raise ValueError("Blind job schema: only IDs, fixed versions, variants and expected units")
    if (protocol["contract_version"] != VERSION or protocol["policy_version"] != POLICY_VERSION
            or protocol["study_version"] != STUDY_VERSION or not protocol["protocol_digest"]):
        raise ValueError("Job version conflict")
    if formal:
        freeze = protocol["freeze"]
        if (set(freeze) != {"status", "protocol_version", "authorized_execution_step"}
                or freeze["status"] != "FROZEN" or freeze["protocol_version"] != "formal-manipulation-protocol-v2"
                or freeze["authorized_execution_step"] not in {"S06", "S07", "S08", "S09", "S10", "S11"}):
            raise ValueError("Formal prediction requires a separately authorized frozen S05 job")
    elif protocol["execution_scope"] != "SYNTHETIC_CONTRACT_TEST":
        raise ValueError("Unsupported execution scope")
    variants = {}
    for v in protocol["variants"]:
        if (set(v) != {"variant_id", "condition_id", "input_view", "method"} or v["variant_id"] in variants
                or v["condition_id"] not in contract["conditions"] or v["input_view"] not in APP_VIEWS or v["method"] not in METHODS):
            raise ValueError("Invalid or duplicated variant")
        variants[v["variant_id"]] = v
    unique_variants = {(v["condition_id"], v["input_view"], v["method"]) for v in variants.values()}
    if len(unique_variants) != len(variants):
        raise ValueError("Aliases cannot duplicate executions")
    keys = set()
    for unit in protocol["expected_units"]:
        if (set(unit) != {"opaque_id", "variant_id", "input_line"} or unit["variant_id"] not in variants
                or not re.fullmatch(r"sample-[A-Za-z0-9_-]+", unit["opaque_id"])
                or type(unit["input_line"]) is not int or unit["input_line"] < 1):
            raise ValueError("Invalid blind expected unit")
        key = (unit["opaque_id"], unit["variant_id"])
        if key in keys:
            raise ValueError("Duplicate expected unit")
        keys.add(key)
    return variants


def run_predictions(*, input_path, protocol, contract, output):
    # Packaging gate precedes contract validation, output creation and input IO.
    # The single-session worker and every relation/risk predicate stay unchanged.
    from hybridguard_agent.research.manipulation_eval.runtime_resources import preflight
    preflight(require_manifest=protocol.get("execution_scope") == "FROZEN_FORMAL_EVALUATION",
              config_dir=contract.get("config_dir") if contract else None)
    variants = validate_protocol(protocol, contract)
    out = new_output(output, inputs=[input_path, contract["config_dir"]])
    base = {k: protocol[k] for k in ("study_version", "run_id", "protocol_digest")}
    manifest = {**base, "schema_version": "formal-run-manifest-v2", "status": "RUNNING",
                "execution_scope": protocol["execution_scope"], "contract_version": VERSION, "policy_version": POLICY_VERSION,
                "expected_units": protocol["expected_units"], "variants": protocol["variants"],
                "started_at": datetime.now(timezone.utc).isoformat(), "prediction_files_closed": False,
                "facts_read": False, "LLM_calls": 0, "real_sample_predictions": 0,
                "freeze": protocol.get("freeze"),
                "authorization_boundary": "Job binding is a reproducibility contract, not proof of user permission; real execution requires separate step authorization."}
    write_json(out / "run_manifest.json", manifest)
    try:
        lines = Path(input_path).read_text().splitlines()
    except (OSError, UnicodeError):
        lines = []
    predictions, events, failures, abstentions, runtimes = [], [], [], [], []
    for unit in protocol["expected_units"]:
        v = variants[unit["variant_id"]]
        error = None
        try:
            envelope = strict_json(lines[unit["input_line"] - 1])
            if set(envelope) != {"opaque_id", "payload"} or envelope["opaque_id"] != unit["opaque_id"]:
                raise ValueError("Input envelope mismatch")
            payload = envelope["payload"]
        except (IndexError, ValueError, TypeError):
            payload, error = {}, "INPUT_PARSE_OR_BINDING_FAILURE"
        result = worker(payload, contract=contract, condition_id=v["condition_id"], input_view=v["input_view"], method=v["method"])
        if error:
            result["failure"]["reason_code"] = error
        key = {**base, "opaque_id": unit["opaque_id"], **v}
        prediction = {**key, "schema_version": "formal-prediction-v2", "contract_version": VERSION,
                      "policy_version": POLICY_VERSION, "adapter_version": ADAPTER_VERSION,
                      **{k: result[k] for k in ("execution_status", "risk", "timings_ms", "catalog_version", "runtime_adapter_version")}}
        predictions.append(prediction)
        events.extend({**key, "schema_version": "formal-rule-event-v2", **e} for e in result["rule_events"])
        runtimes.append({**key, "schema_version": "formal-runtime-record-v2", "runtime": result["original_runtime"], "risk_verification": result["verification"]})
        if result["failure"]:
            failures.append({**key, "schema_version": "formal-failure-v2", **result["failure"], "prediction_status_row_saved": True})
        elif result["risk"]["decision"] == "INSUFFICIENT_EVIDENCE":
            abstentions.append({**key, "schema_version": "formal-abstention-v2", "reason_codes": result["risk"]["reason_codes"],
                                "unavailable_family_ids": result["risk"]["unavailable_family_ids"]})
    from hybridguard_agent.research.manipulation_eval.schemas import validate_record
    tables = {"predictions": predictions, "rule_events": events, "failures": failures, "abstentions": abstentions, "runtime_records": runtimes}
    for name, rows in tables.items():
        for row in rows:
            validate_record(name, row)
        write_jsonl(out / (name + ".jsonl"), rows)
    manifest.update(status="PREDICTIONS_CLOSED", prediction_files_closed=True,
                    completed_at=datetime.now(timezone.utc).isoformat(), prediction_count=len(predictions),
                    failure_count=len(failures), rule_event_count=len(events), output_files=list(tables),
                    real_sample_predictions=len(predictions) if protocol["execution_scope"] == "FROZEN_FORMAL_EVALUATION" else 0)
    write_json(out / "run_manifest.json", manifest)
    return manifest
