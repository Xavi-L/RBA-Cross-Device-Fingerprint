"""Describe saved collector observations; never invoke a candidate or detector."""
from collections import Counter

WD_KEYS = (
    "api_present", "presence_read_status", "value_read_status", "value_type",
    "boolean_value", "observer_revision", "realm_binding",
)
FIELD_PREFIX = "web_data.navigator_layer."
IDENTITY_KEYS = (
    "device_manifest_id", "collector_install_id", "collector_package",
    "collector_version_name", "collector_version_code", "android_api",
    "webview_provider_package", "webview_provider_version",
)


def raw_tuple_issues(observation):
    if not isinstance(observation, dict):
        return ["webdriver_observation_not_object"]
    issues = []
    if any(key not in observation for key in WD_KEYS):
        issues.append("webdriver_raw_keys_missing")
    for key in ("api_present", "boolean_value"):
        if observation.get(key) is not None and type(observation[key]) is not bool:
            issues.append(f"webdriver_{key}_invalid_type")
    presence, read = observation.get("presence_read_status"), observation.get("value_read_status")
    present, kind, value = observation.get("api_present"), observation.get("value_type"), observation.get("boolean_value")
    if presence not in ("observed", "runtime_error"):
        issues.append("webdriver_presence_status_invalid")
    if read not in ("observed", "runtime_error", "not_attempted"):
        issues.append("webdriver_value_status_invalid")
    if kind is not None and kind not in ("undefined", "object", "boolean", "number", "bigint", "string", "symbol", "function"):
        issues.append("webdriver_value_type_invalid")
    for key in ("observer_revision", "realm_binding"):
        if type(observation.get(key)) is not str or not observation[key]:
            issues.append(f"webdriver_{key}_invalid")
    if presence == "runtime_error" and not (present is None and read == "not_attempted" and kind is None and value is None):
        issues.append("webdriver_presence_error_contradiction")
    if presence == "observed" and type(present) is not bool:
        issues.append("webdriver_observed_presence_without_boolean")
    if present is False and not (read == "not_attempted" and kind is None and value is None):
        issues.append("webdriver_absent_api_has_getter_observation")
    if present is True and read == "not_attempted":
        issues.append("webdriver_present_api_getter_not_attempted")
    if read in ("observed", "runtime_error") and present is not True:
        issues.append("webdriver_getter_without_present_api")
    if read in ("runtime_error", "not_attempted") and (kind is not None or value is not None):
        issues.append("webdriver_unread_getter_has_value")
    if read == "observed" and kind is None:
        issues.append("webdriver_observed_getter_without_type")
    if kind == "boolean" and type(value) is not bool:
        issues.append("webdriver_boolean_type_without_boolean")
    if kind != "boolean" and value is not None:
        issues.append("webdriver_nonboolean_type_has_boolean")
    return issues


def campaign_plan(campaign_id):
    result = []
    for group, rounds, configuration in (
        ("no_attack", 3, None),
        ("debug_transport_control", 1, None),
        ("webdriver", 3, "cdp_webdriver_only_v1"),
        ("language", 3, "stealth_languages_only_v1"),
    ):
        phases = ("clean_pre", "attack" if configuration else "control_mid", "clean_post")
        for round_number in range(1, rounds + 1):
            for phase in phases:
                step_id = f"{group}-r{round_number}-{phase}"
                result.append({
                    "step_id": step_id, "group": group, "round": round_number,
                    "phase": phase, "configuration": configuration if phase == "attack" else None,
                    "debug_transport_only": group == "debug_transport_control" and phase == "control_mid",
                    "runtime_context": f"{campaign_id}:{step_id}",
                })
    return result


def smoke_plan(campaign_id):
    return {"step_id": "smoke", "group": "smoke", "round": 1, "phase": "smoke",
            "configuration": None, "debug_transport_only": False,
            "runtime_context": f"{campaign_id}:smoke"}


def describe_payload(payload):
    manifest = payload.get("collection_manifest") or {}
    web = payload.get("web_data") or {}
    navigator = web.get("navigator_layer") or {}
    automation = web.get("automation_surface_layer") or {}
    observations = payload.get("collection_observations")
    observation = observations.get("webdriver") if isinstance(observations, dict) else None
    raw_issues = raw_tuple_issues(observation)
    wd_class = "FAILED" if raw_issues else "U"
    if not raw_issues and (
        observation.get("api_present") is True
        and observation.get("presence_read_status") == "observed"
        and observation.get("value_read_status") == "observed"
        and observation.get("value_type") == "boolean"
        and type(observation.get("boolean_value")) is bool
    ):
        wd_class = "BOOLEAN_TRUE" if observation["boolean_value"] else "BOOLEAN_FALSE"
    fields = (payload.get("collection_status") or {}).get("fields") or {}
    language, languages = navigator.get("language"), navigator.get("languages")
    language_available = (
        type(language) is str and type(languages) is list
        and all(type(value) is str for value in languages)
        and fields.get(FIELD_PREFIX + "language") == "observed"
        and fields.get(FIELD_PREFIX + "languages") == "observed"
    )
    return {
        "session_id": payload.get("session_id"),
        "identity": {key: manifest.get(key) for key in IDENTITY_KEYS},
        "runtime_context": manifest.get("runtime_context"),
        "collection_round": manifest.get("collection_round"),
        "observation_schema_version": observations.get("observation_schema_version") if isinstance(observations, dict) else None,
        "webdriver_raw": observation,
        "webdriver_raw_keys_present": [key for key in WD_KEYS if isinstance(observation, dict) and key in observation],
        "webdriver_value_class": wd_class,
        "webdriver_raw_issues": raw_issues,
        "legacy_webdriver": automation.get("webdriver"),
        "legacy_webdriver_field_status": fields.get("web_data.automation_surface_layer.webdriver"),
        "language": language, "languages_ordered": languages,
        "language_field_status": fields.get(FIELD_PREFIX + "language"),
        "languages_field_status": fields.get(FIELD_PREFIX + "languages"),
        "language_observation_availability": "OBSERVED" if language_available else "U",
        "fixed_signal_count": (payload.get("collection_status") or {}).get("fixed_signal_count"),
        "collection_diagnostics": payload.get("collection_diagnostics"),
    }


def payload_issues(payload, step, config, release, expected_field_paths):
    issues = []
    manifest = payload.get("collection_manifest") or {}
    for key, expected in {"collector_app": "featureapp", "schema_version": release["schema_version"]}.items():
        if payload.get(key) != expected:
            issues.append(f"payload.{key} mismatch")
    for key, expected in {
        "runtime_context": step["runtime_context"], "collection_round": step["round"],
        "device_manifest_id": config["device_manifest_id"],
        "collector_package": release["application_id"],
        "collector_version_name": release["version_name"],
        "collector_version_code": release["version_code"],
        "schema_version": release["schema_version"],
    }.items():
        if manifest.get(key) != expected:
            issues.append(f"manifest.{key} mismatch")
    for key in IDENTITY_KEYS:
        if manifest.get(key) in (None, ""):
            issues.append(f"manifest.{key} missing")
    status = payload.get("collection_status") or {}
    fields = status.get("fields") or {}
    allowed = {"observed", "unsupported_by_os", "permission_denied", "runtime_error", "timeout", "not_applicable"}
    counts = Counter(fields.values())
    if (status.get("status_schema_version") != "field-status-v1"
            or status.get("fixed_signal_count") != release["fixed_signal_count"]
            or set(fields) != set(expected_field_paths)
            or not set(counts).issubset(allowed)
            or any((status.get("counts") or {}).get(key, 0) != counts[key] for key in allowed)):
        issues.append("field_status_contract_mismatch")
    observations = payload.get("collection_observations")
    if not isinstance(observations, dict) or observations.get("observation_schema_version") != release["observation_schema_version"]:
        issues.append("observation_schema_missing_or_mismatch")
    observation = observations.get("webdriver") if isinstance(observations, dict) else None
    issues.extend(raw_tuple_issues(observation))
    if isinstance(observation, dict) and (observation.get("observer_revision") != release["observer_revision"]
          or observation.get("realm_binding") != f"featureapp:{payload.get('session_id')}:main-frame"):
        issues.append("webdriver_observer_or_realm_binding_mismatch")
    return issues


def compare_observations(left, right):
    """Unknown observations never become evidence of equal known values."""
    webdriver_known = left["webdriver_value_class"] in ("BOOLEAN_TRUE", "BOOLEAN_FALSE") and right["webdriver_value_class"] in ("BOOLEAN_TRUE", "BOOLEAN_FALSE")
    tuple_known = not left["webdriver_raw_issues"] and not right["webdriver_raw_issues"]
    language_known = left["language_observation_availability"] == right["language_observation_availability"] == "OBSERVED"
    return {
        "webdriver_known_values_equal": left["webdriver_value_class"] == right["webdriver_value_class"] if webdriver_known else None,
        "webdriver_comparison_status": "OBSERVED" if webdriver_known else "U",
        "webdriver_raw_tuple_equal_excluding_realm": (
            all(left["webdriver_raw"][key] == right["webdriver_raw"][key] for key in WD_KEYS if key != "realm_binding")
        ) if tuple_known else None,
        "webdriver_raw_tuple_comparison_status": "RECORDED_OBSERVATIONS" if tuple_known else "UNAVAILABLE_OR_INVALID",
        "language_and_ordered_languages_equal": (
            left["language"] == right["language"] and left["languages_ordered"] == right["languages_ordered"]
        ) if language_known else None,
        "language_comparison_status": "OBSERVED" if language_known else "U",
    }


def summarize_sessions(sessions, plan):
    by_step = {row["step_id"]: row for row in sessions}
    triplets = []
    for index in range(0, len(plan), 3):
        steps = plan[index:index + 3]
        rows = [by_step.get(step["step_id"]) for step in steps]
        item = {"group": steps[0]["group"], "round": steps[0]["round"],
                "session_ids": [row["observation"]["session_id"] if row else None for row in rows],
                "status": "INCOMPLETE"}
        if all(row and row["accepted"] for row in rows):
            pre, middle, post = [row["observation"] for row in rows]
            item.update(status="COMPLETE", pre_vs_middle=compare_observations(pre, middle),
                        pre_vs_post=compare_observations(pre, post))
            if item["group"] == "webdriver":
                item["declared_active_value_observed"] = middle["webdriver_value_class"] == "BOOLEAN_TRUE"
            elif item["group"] == "language":
                item["declared_active_value_observed"] = (
                    middle["language_observation_availability"] == "OBSERVED"
                    and middle["languages_ordered"] == ["fr-FR", "fr"]
                )
        triplets.append(item)
    return {
        "planned_campaign_sessions": len(plan), "planned_smoke_sessions": 1,
        "saved_sessions": len(sessions),
        "accepted_sessions": sum(row["accepted"] for row in sessions),
        "webdriver_value_classes_all_saved": dict(Counter(row["observation"]["webdriver_value_class"] for row in sessions)),
        "triplets": triplets,
        "scope": "New local development observations only; no candidate evaluation, fit, prediction, or population FPR estimate.",
        "control_limit": "debug_transport_control matches CDP attach/navigation without injection, not all Puppeteer internals.",
    }
