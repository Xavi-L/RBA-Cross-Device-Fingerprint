"""Closed long-table schemas and a stdlib validator for the emitted subset."""
import math

from hybridguard_agent.research.manipulation_eval.contract import VERSION, POLICY_VERSION, STUDY_VERSION
from hybridguard_agent.research.manipulation_eval.policy import C_UNKNOWN, DECISION_SCHEMA

TEXT = {"type": "string"}
BOOL = {"type": "boolean"}
INTEGER = {"type": "integer", "minimum": 0}
NUMBER = {"type": "number", "minimum": 0}
OBJECT = {"type": "object"}
STRINGS = {"type": "array", "items": TEXT}


def closed(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def constant(value):
    return {"const": value}


def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


AXIS_A = closed({"status": {"enum": ["SUPPORTED", "UNKNOWN", "NOT_APPLICABLE"]}, "reason": TEXT})
AXIS_B = closed({"status": {"enum": ["ELIGIBLE", "NOT_ELIGIBLE", "UNKNOWN", "NOT_APPLICABLE"]}, "reason": TEXT})
RISK = closed({"decision_schema_version": constant(DECISION_SCHEMA), "contract_version": constant(VERSION),
               "policy_version": constant(POLICY_VERSION), "research_scope_id": constant("featureapp-reported-identity-coherence-research-v2"),
               "decision": {"enum": ["MANIPULATION_ALERT", "NO_ALERT", "INSUFFICIENT_EVIDENCE", "FAILED"]},
               "alert_score": nullable(INTEGER), "score_meaning": constant("count_of_distinct_qualifying_conflict_families_not_probability"),
               "threshold": constant(1), "reason_codes": STRINGS,
               "eligible_family_count": INTEGER, "eligible_family_ids": STRINGS,
               "evaluated_family_count": INTEGER, "evaluated_family_ids": STRINGS,
               "triggered_family_ids": STRINGS, "unavailable_family_ids": STRINGS,
               "partial_coverage": BOOL, "family_coverage": nullable({"type": "number", "minimum": 0, "maximum": 1}),
               "verification_valid": BOOL, "calibrated_attack_probability": constant(None),
               "attribution_certainty": constant(C_UNKNOWN), "attack_classification": constant("NOT_EVALUATED"),
               "claim_boundary": TEXT})
KEY = {"study_version": constant(STUDY_VERSION), "run_id": TEXT, "protocol_digest": TEXT,
       "opaque_id": TEXT, "variant_id": TEXT, "condition_id": TEXT, "input_view": TEXT, "method": TEXT}
PREDICTION = closed({**KEY, "schema_version": constant("formal-prediction-v2"), "contract_version": constant(VERSION),
                    "policy_version": constant(POLICY_VERSION), "adapter_version": constant("app177-triplet-adapter-v1"),
                    "execution_status": {"enum": ["COMPLETED", "FAILED"]}, "risk": RISK,
                    "timings_ms": {"type": "object", "additionalProperties": NUMBER}, "catalog_version": TEXT, "runtime_adapter_version": TEXT})
EVENT = closed({**KEY, "schema_version": constant("formal-rule-event-v2"), "rule_id": TEXT, "catalog_status": TEXT,
                "source_condition_included": BOOL, "original_outcome": nullable(TEXT), "original_result": nullable(OBJECT),
                "original_outcome_recorded": BOOL, "original_source_lane": TEXT, "provenance_group": nullable(TEXT),
                "original_evidence_family": TEXT, "decision_family": nullable(TEXT), "decision_role": TEXT,
                "required_fields": STRINGS, "used_fields": STRINGS, "additional_risk_required_fields": STRINGS,
                "field_states": OBJECT, "relation_applicability": AXIS_A, "risk_candidate_eligibility": AXIS_B,
                "attribution_certainty": constant(C_UNKNOWN), "participates_in_risk": BOOL, "triggers_family": BOOL,
                "participation_reason": TEXT, "verification_valid": BOOL, "contract_version": constant(VERSION)})
SCHEMAS = {"predictions": PREDICTION, "rule_events": EVENT,
           "failures": closed({**KEY, "schema_version": constant("formal-failure-v2"), "stage": TEXT, "error_type": TEXT,
                               "reason_code": TEXT, "retry_of": constant(None), "prediction_status_row_saved": constant(True)}),
           "abstentions": closed({**KEY, "schema_version": constant("formal-abstention-v2"), "reason_codes": STRINGS, "unavailable_family_ids": STRINGS}),
           "runtime_records": closed({**KEY, "schema_version": constant("formal-runtime-record-v2"), "runtime": nullable(OBJECT), "risk_verification": nullable(OBJECT)})}


def validate_schema(value, schema):
    if "anyOf" in schema:
        for choice in schema["anyOf"]:
            try:
                validate_schema(value, choice)
                return
            except ValueError:
                pass
        raise ValueError("Schema union mismatch")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ValueError("Schema constant mismatch")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Schema enumeration mismatch")
    kind = schema.get("type")
    types = {"string": str, "boolean": bool, "integer": int, "object": dict, "array": list, "null": type(None)}
    if kind == "number":
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Schema number mismatch")
    elif kind and type(value) is not types[kind]:
        raise ValueError("Schema type mismatch")
    if kind in {"integer", "number"}:
        if value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf):
            raise ValueError("Schema numeric range")
    if kind == "object":
        if not set(schema.get("required", [])) <= set(value):
            raise ValueError("Missing schema properties")
        props = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        if additional is False and set(value) - set(props):
            raise ValueError("Forbidden extra schema properties")
        for key, child in value.items():
            if key in props:
                validate_schema(child, props[key])
            elif isinstance(additional, dict):
                validate_schema(child, additional)
    if kind == "array" and "items" in schema:
        for child in value:
            validate_schema(child, schema["items"])


def validate_record(table, row):
    validate_schema(row, SCHEMAS[table])
    if table == "predictions":
        r = row["risk"]
        failed = row["execution_status"] == "FAILED"
        if failed != (r["decision"] == "FAILED") or failed == r["verification_valid"]:
            raise ValueError("Failure/decision/verification mismatch")
        for count, field in (("eligible_family_count", "eligible_family_ids"), ("evaluated_family_count", "evaluated_family_ids")):
            if r[count] != len(set(r[field])) or len(r[field]) != len(set(r[field])):
                raise ValueError("Family count mismatch")
        if failed:
            if r["alert_score"] is not None or r["evaluated_family_ids"] or r["triggered_family_ids"]:
                raise ValueError("Failed unit cannot masquerade as a score or assessed family")
        else:
            trigger, evaluated = set(r["triggered_family_ids"]), set(r["evaluated_family_ids"])
            expected = "MANIPULATION_ALERT" if trigger else "NO_ALERT" if evaluated else "INSUFFICIENT_EVIDENCE"
            if not trigger <= evaluated <= set(r["eligible_family_ids"]) or r["alert_score"] != len(trigger) or r["decision"] != expected:
                raise ValueError("Risk arithmetic mismatch")
