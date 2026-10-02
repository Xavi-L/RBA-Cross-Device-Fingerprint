"""Pure, versioned WebGL parameter-equivalence observations, outside selectors.

No filesystem, network, environment, model or label reads. Realm binding must
come from the caller's collection context; it is not hardware/authenticity proof.
"""
from __future__ import annotations

import math
from typing import Any

OBSERVATION_SCHEMA_VERSION = "webgl-parameter-equivalence-observation-v1"
OBSERVER_REVISION = "webgl-parameter-observer-v1"
OBSERVATION_SCOPE = "fresh-webgl-contexts-v1"
EVALUATOR_REVISION = "webgl-parameter-equivalence-v1"
CONTEXT_TYPES = ("webgl", "webgl2")
PARAMETERS = {"vendor": 37445, "renderer": 37446}
SENTINELS = frozenset({"", "unknown", "null", "masked", "redacted", "unsupported", "error", "not available"})


def _result(outcome: str, reason: str, **details: Any) -> dict:
    return {"outcome": outcome, "reason": reason, **details}


def _unknown(reason: str, **details: Any) -> dict:
    return _result("UNKNOWN", reason, **details)


def _finite_number(value: Any) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _query_issue(sample: Any, argument: int | str, value_kind: str) -> str | None:
    if not isinstance(sample, dict):
        return "QUERY_MISSING"
    if sample.get("read_status") != "observed":
        return "QUERY_NOT_OBSERVED"
    if "exception" in sample:
        return "QUERY_EXCEPTION"
    numeric = type(argument) is int
    if sample.get("argument_kind") != ("number" if numeric else "string"):
        return "ARGUMENT_KIND_MISMATCH"
    actual = sample.get("argument")
    argument_type_valid = _finite_number(actual) if numeric else type(actual) is str
    if not argument_type_valid or actual != argument:
        return "ARGUMENT_MISMATCH"
    if sample.get("pre_errors") != [] or sample.get("drained") is not True:
        return "QUERY_PREEXISTING_ERROR"
    if sample.get("context_lost_before") is not False or sample.get("context_lost_after") is not False:
        return "QUERY_CONTEXT_STATE_UNAVAILABLE"
    if type(sample.get("error")) is not int or sample["error"] != 0:
        return "QUERY_GL_ERROR_OR_MISSING"
    if sample.get("value_kind") != value_kind:
        return "VALUE_KIND_MISMATCH"
    value = sample.get("value")
    if value_kind == "string":
        if type(value) is not str or value.strip().casefold() in SENTINELS:
            return "VALUE_UNAVAILABLE"
    elif not _finite_number(value) or not 0 < value <= 2147483647 or value != math.floor(value):
        return "CONTROL_VALUE_INVALID"
    return None


def evaluate_parameter_triplet(reads: Any, *, parameter: int, value_kind: str = "string") -> dict:
    """Evaluate recorded number/string/number calls only, never infer observation.

    This lower-level function does not validate a collection/realm envelope.
    It is useful for explicit saved-query replay, not automatic data admission.
    """
    if type(parameter) is not int or parameter not in (*PARAMETERS.values(), 34921):
        return _unknown("UNSUPPORTED_PARAMETER")
    if value_kind != ("number" if parameter == 34921 else "string"):
        return _unknown("UNSUPPORTED_VALUE_KIND")
    if not isinstance(reads, dict):
        return _unknown("TRIPLET_MISSING")
    keys = ("numeric_before", "numeric_string", "numeric_after")
    for key, argument in zip(keys, (parameter, str(parameter), parameter)):
        issue = _query_issue(reads.get(key), argument, value_kind)
        if issue:
            return _unknown(issue, query=key)
    first, middle, last = (reads[key]["value"] for key in keys)
    if first != last:
        return _unknown("TEMPORAL_INSTABILITY")
    if first != middle:
        return _result("COUNTEREXAMPLE", "EQUIVALENT_ARGUMENTS_DIFFER")
    return _result("MATCH", "EQUIVALENT_ARGUMENTS_AGREE")


def _combine(results: list[dict]) -> dict:
    states = [result["outcome"] for result in results]
    if "COUNTEREXAMPLE" in states:
        return _result("COUNTEREXAMPLE", "OBSERVED_PARAMETER_CONFLICT")
    if states and all(state == "MATCH" for state in states):
        return _result("MATCH", "ALL_REQUESTED_COMPARISONS_MATCH")
    return _unknown("INCOMPLETE_COMPARISON")


def _evaluate_context(context: dict) -> dict:
    if context.get("context_creation_status") != "observed" or "exception" in context:
        return _unknown("CONTEXT_UNAVAILABLE_OR_FAILED")
    if context.get("context_lost_at_end") is not False:
        return _unknown("CONTEXT_LOST_OR_STATE_MISSING")
    if context.get("extension_read_status") != "observed" or "extension_exception" in context:
        return _unknown("EXTENSION_READ_FAILED")
    if context.get("extension_available") is not True:
        return _unknown("EXTENSION_UNAVAILABLE")
    if context.get("extension_constants") != PARAMETERS:
        return _unknown("EXTENSION_CONSTANTS_MISMATCH")
    preflight = context.get("preflight")
    if not isinstance(preflight, dict) or preflight.get("read_status") != "observed" or "exception" in preflight:
        return _unknown("PREFLIGHT_UNAVAILABLE")
    if preflight.get("errors") != [] or preflight.get("drained") is not True:
        return _unknown("PREFLIGHT_ERRORS")
    if preflight.get("context_lost_before") is not False or preflight.get("context_lost_after") is not False:
        return _unknown("PREFLIGHT_CONTEXT_STATE_UNAVAILABLE")
    control = context.get("control")
    if not isinstance(control, dict) or control.get("parameter") != "MAX_VERTEX_ATTRIBS" or control.get("enum_value") != 34921:
        return _unknown("CONTROL_MISSING_OR_MISMATCHED")
    control_result = evaluate_parameter_triplet(control.get("queries"), parameter=34921, value_kind="number")
    if control_result["outcome"] != "MATCH":
        return _unknown("POSITIVE_CONTROL_NOT_MATCHED", control=control_result)
    parameters = context.get("parameters")
    parameters = parameters if isinstance(parameters, dict) else {}
    results = {name: evaluate_parameter_triplet(parameters.get(name), parameter=enum) for name, enum in PARAMETERS.items()}
    return {**_combine(list(results.values())), "control": control_result, "parameters": results}


def evaluate_observation(observation: Any, *, expected_realm_binding: str) -> dict:
    """Validate version/binding/scope, then return relation outcomes without a model decision.

    COUNTEREXAMPLE is an API inconsistency, not an attack classification or a
    selector predicate. A valid conflict can coexist with an UNKNOWN context;
    MATCH requires both requested contexts and both parameters to match.
    """
    base = {"evaluator_revision": EVALUATOR_REVISION, "decision_role": "observation_only"}

    def unavailable(reason):
        return {**base, **_unknown(reason), "contexts": {}}

    if not isinstance(observation, dict):
        return unavailable("OBSERVATION_MISSING")
    for key, expected in (("observation_schema_version", OBSERVATION_SCHEMA_VERSION),
                          ("observer_revision", OBSERVER_REVISION), ("observation_scope", OBSERVATION_SCOPE)):
        if observation.get(key) != expected:
            return unavailable(key.upper() + "_MISMATCH")
    if type(expected_realm_binding) is not str or not expected_realm_binding.strip():
        return unavailable("CALLER_REALM_BINDING_REQUIRED")
    if observation.get("realm_binding") != expected_realm_binding:
        return unavailable("REALM_BINDING_MISMATCH")
    contexts = observation.get("contexts")
    if not isinstance(contexts, list) or any(not isinstance(c, dict) for c in contexts) or [c.get("context_type") for c in contexts] != list(CONTEXT_TYPES):
        return unavailable("CONTEXT_SET_MISMATCH")
    results = {c["context_type"]: _evaluate_context(c) for c in contexts}
    return {**base, **_combine(list(results.values())), "contexts": results}
