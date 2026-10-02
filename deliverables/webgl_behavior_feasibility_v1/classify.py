"""Frozen, three-state behavior checks; no model and no renderer vocabulary."""
SENTINELS = {"", "unknown", "masked", "redacted", "null", "unsupported", "error"}


def available(sample):
    return (isinstance(sample, dict) and sample.get("pre_errors") == []
            and sample.get("drained") is True and sample.get("context_lost_before") is False
            and sample.get("context_lost_after") is False and "exception" not in sample
            and "value" in sample and "value_kind" in sample and type(sample.get("error")) is int)


def combine(states):
    if "COUNTEREXAMPLE" in states:
        return "COUNTEREXAMPLE"
    return "MATCH" if states and all(s == "MATCH" for s in states) else "UNKNOWN"


def disabled(sample):
    if not available(sample):
        return "UNKNOWN"
    # Querying this extension enum before enabling it has defined invalid-enum semantics.
    return "MATCH" if sample["value_kind"] == "null" and sample["value"] is None and sample["error"] == 1280 else "COUNTEREXAMPLE"


def coerced(samples):
    values = [samples.get(k) for k in ("numeric_before", "numeric_string", "numeric_after")]
    if not all(available(s) and s["error"] == 0 and s["value_kind"] == "string"
               and isinstance(s["value"], str) and s["value"].strip().casefold() not in SENTINELS for s in values):
        return "UNKNOWN"
    first, middle, last = (s["value"] for s in values)
    if first != last:  # Temporal instability is not a conversion conflict.
        return "UNKNOWN"
    return "MATCH" if first == middle else "COUNTEREXAMPLE"


def classify(context):
    keys = ("extension_gate", "argument_coercion", "capability_control", "render_control", "behavior_relation")
    if context.get("status") != "MEASURED" or context.get("context_lost_at_end") is not False:
        return dict.fromkeys(keys, "UNKNOWN")
    off = context.get("extension_disabled", {})
    gate = combine([disabled(off.get(k)) for k in ("vendor", "renderer")])
    enabled = context.get("extension_enabled", {})
    coercion = "UNKNOWN"
    if context.get("extension_available") is True and context.get("extension_constants") == {"vendor": 37445, "renderer": 37446}:
        coercion = combine([coerced(enabled.get(k, {})) for k in ("vendor", "renderer")])
    cap = context.get("capability", {})
    samples = [cap.get(k) for k in ("numeric", "numeric_string", "last_valid_index", "first_invalid_index")]
    capability = "UNKNOWN"
    if all(available(s) for s in samples):
        number, string, valid, invalid = samples
        limit = number["value"]
        if type(limit) is int and 0 < limit <= 1024 and number["value_kind"] == string["value_kind"] == "number":
            capability = "MATCH" if (number["error"] == string["error"] == valid["error"] == 0
                                         and string["value"] == limit and invalid["error"] == 1281) else "COUNTEREXAMPLE"
    render = context.get("render")
    drawing = "UNKNOWN"
    if available(render) and render["error"] == 0 and isinstance(render["value"], dict) and render["value"].get("status") == "EXECUTED":
        drawing = "MATCH" if render["value"].get("pixels") == [255, 0, 0, 255] * 64 else "COUNTEREXAMPLE"
    # Positive controls establish an operational context; failure is not an attack alert.
    behavior = combine([gate, coercion]) if capability == drawing == "MATCH" else "UNKNOWN"
    return dict(extension_gate=gate, argument_coercion=coercion, capability_control=capability,
                render_control=drawing, behavior_relation=behavior)
