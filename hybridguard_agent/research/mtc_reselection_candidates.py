"""Label-free WEBGL50 candidate inputs for the MTC constrained study.

The two entry points retain their source contracts. Historical projections are
never declared raw observations, and numeric values remain unfitted until the
caller encodes its controlled training fold. No data is loaded on import.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from . import mtc_cap8_replay as legacy
from . import rule_semantics_webgl1_cap8 as cap8
from . import webgl1_selector_integration as webgl
from .rule_learning.contracts import cell, ledger
from .rule_learning.matrix import (Unavailable, field_state, mapped_state,
                                   measurement_domain, original_relation,
                                   _ua_class, _platform_class)
from .rule_learning_v2.adapter import approved_atoms
from .rule_semantics_runtime_matrix import _CONTROL_CONTRACT
from .rule_semantics_revision_v1.language import web_language_first_difference
from .rule_semantics_revision_v1.webdriver import LEGACY_MODE, RAW_MODE, webdriver_reported_state

VERSION = "mtc-constrained-webgl50-input-adapter-v2"
ROOT = Path(__file__).resolve().parents[2]
DEFINITIONS_PATH = ROOT / "deliverables/webgl1_fresh_comparison_v1/prepared/DEFINITIONS.json"
_SEMANTIC = (cap8.LANG_ID, cap8.WD_ID, webgl.CANDIDATE_ID)
# The registered v9/v11 collector uses -1 for these unavailable numeric reads.
# P1 preserved several as observed_value, which is not proof of a measurement.
# This declaration comes from defaultScreen/Audio/Connection/WebGLFeatures and
# their getters at HISTORICAL_SOURCE_COMMIT, not from model outcomes. In
# particular, timezone_offset is deliberately absent: negative offsets are real.
HISTORICAL_MINUS_ONE_FIELDS = frozenset("app.web_data." + field for field in (
    "audio_layer.audio_output_latency", "audio_layer.audio_sample_rate",
    "graphics_layer.webgl_max_texture_size", "network_api_layer.downlink_mbps",
    "network_api_layer.rtt_ms", "screen_layer.device_pixel_ratio",
    "screen_layer.color_depth", "screen_layer.pixel_depth", "screen_layer.avail_width",
    "screen_layer.avail_height", "screen_layer.inner_width", "screen_layer.inner_height",
    "screen_layer.outer_width", "screen_layer.outer_height", "screen_layer.visual_viewport_width",
    "screen_layer.visual_viewport_height", "screen_layer.visual_viewport_scale",
    "screen_layer.orientation_angle",
))
_UNITS = {
    "audio_output_latency": "seconds; outputLatency or fallback baseLatency",
    "audio_sample_rate": "Hz", "mime_types_count": "reported entry count",
    "plugins_count": "reported entry count", "timezone_offset": "minutes; UTC minus local",
    "font_probe_count": "matched probe-font count", "webgl_extensions_count": "extension count",
    "webgl_max_texture_size": "texture pixels", "device_memory": "rounded/clamped navigator GiB exposure",
    "hardware_concurrency": "exposed logical processor count", "max_touch_points": "exposed touch count",
    "downlink_mbps": "Mbps", "rtt_ms": "milliseconds", "color_depth": "bits", "pixel_depth": "bits",
    "device_pixel_ratio": "dimensionless CSS-to-device ratio", "orientation_angle": "degrees",
    "visual_viewport_scale": "dimensionless scale", "languages": "list entry count (no deduplication)",
}


def definitions(path=None):
    """Return the original full WEBGL50 pool, with no outcome-based filtering."""
    source = json.loads(Path(path or DEFINITIONS_PATH).read_text())
    result = cap8.group_definitions(source, "WEBGL50")
    if len(approved_atoms(result)) != 50:
        raise ValueError("EXACT_WEBGL50_BASE_POOL_REQUIRED")
    return result


@lru_cache(maxsize=1)
def _canonical():
    return definitions()


def _atoms(defs):
    result = approved_atoms(_canonical() if defs is None else defs)
    if result != approved_atoms(_canonical()):
        raise ValueError("UNCHANGED_WEBGL50_DEFINITIONS_REQUIRED")
    return result


@lru_cache(maxsize=1)
def _catalog():
    candidates = {c["atom_id"]: c for c in ledger()}
    rules = json.loads((ROOT / "hybridguard_agent/config/paired244_rule_catalog.v3.json").read_text())
    return candidates, {r["rule_id"]: r for r in rules["rules"]}


def _refs(atom):
    return atom.provenance.get("field_refs", [atom.provenance.get("field")])


def _historical_field_state(record, spec):
    gate = field_state(record, spec)
    field = spec["field"]
    if (gate["available"] and field in HISTORICAL_MINUS_ONE_FIELDS
            and record["features"][field] == -1):
        gate = dict(gate, available=False, reason="HISTORICAL_COLLECTOR_MINUS_ONE_UNAVAILABLE")
    return gate


def _measure_catalog(record, atom):
    candidates, rules = _catalog()
    candidate, rule = candidates[atom.atom_id], rules[atom.atom_id.removeprefix("CAT:")]
    if (candidate["dependencies"] != _refs(atom) or rule["dependencies"] != _refs(atom)
            or candidate["measurement"]["condition"] != atom.provenance["condition"]):
        raise ValueError("UNCHANGED_CATALOG_SEMANTICS_REQUIRED")
    payload = legacy._projection(record, _refs(atom))
    try:
        gates = {s["field"]: _historical_field_state(payload, s) for s in candidate["dependency_schema"]}
        for gate in gates.values():
            if not gate["available"]:
                raise Unavailable(gate["reason"])
        measurement_domain(candidate, payload)
        original = original_relation(rule, payload)
        state = mapped_state(candidate, original["outcome"])
        return cell(state, "CONDITION_DEFINED" if state != "U" else original["reason"])
    except Unavailable as exc:
        return cell("U", exc.reason)
    except Exception as exc:
        return cell("FAILED", type(exc).__name__ + ":" + str(exc))


def _measure_control(record, atom):
    """Same field gate and conversions as matrix.control_input, no fake envelope.

    That existing function requires the app177-triplet adapter identity. This
    historical entry instead shares its field gate/parsers and its exact fixed
    conversion, without labeling a standalone normal record as a triplet.
    """
    field = atom.provenance["field"]
    kind, encoder = _CONTROL_CONTRACT[field]
    if encoder != atom.provenance["encoder"]:
        raise ValueError("UNCHANGED_CONTROL_ENCODER_REQUIRED")
    try:
        gate = _historical_field_state(record, {"field": field, "type": kind})
        if not gate["available"]:
            return cell("U", gate["reason"])
        value = deepcopy(record["features"][field])
        if encoder == "UA_CLASS":
            value = _ua_class(value)
        elif encoder == "PLATFORM_CLASS":
            value = _platform_class(value)
        elif encoder == "LIST_LENGTH_TRAIN_QUANTILE":
            if any(type(v) is not str or not v.strip() for v in value):
                raise Unavailable("INVALID_LANGUAGE_LIST_ELEMENT")
            value = len(value)
        if value == "unknown":
            raise Unavailable("UNKNOWN_PARSER_CLASS")
        if atom.orientation == "CONTROL_EQUALITY":
            value = value == atom.provenance["equals"]
        return {"value": value, "available": True, "evaluation_status": "OK",
                "reason": "OBSERVED_FIXED_CONTROL_INPUT"}
    except Unavailable as exc:
        return cell("U", exc.reason)
    except Exception as exc:
        return cell("FAILED", type(exc).__name__ + ":" + str(exc))


def _details(atom, measured, fields, source):
    numeric = atom.atom_id.startswith("UNFITTED_CONTROL:")
    state = ("FAILED" if measured.get("evaluation_status") != "OK" else
             "U" if not measured.get("available") else "UNFITTED_NUMERIC" if numeric else
             "T" if measured["value"] is True else "F")
    return {"field_refs": _refs(atom), "fields": fields, "state": state,
            "available": measured["available"], "evaluation_status": measured["evaluation_status"],
            "reason": measured.get("reason"), "measurement_value": deepcopy(measured.get("value")),
            "measurement_source": source}


def adapt_controlled(prepared, defs=None):
    """Use saved full fresh inputs; source/label/ID metadata never enters raw."""
    atoms = _atoms(defs)
    if (type(prepared) is not dict or prepared.get("observation_mode") != RAW_MODE
            or type(prepared.get("features")) is not dict
            or type(prepared.get("candidate_cells")) is not dict):
        raise PermissionError("FRESH_PREPARED_RAW_OBSERVATION_REQUIRED")
    saved = prepared["candidate_cells"]
    cap8._check_cell_mode(saved.get(cap8.WD_ID), RAW_MODE)
    raw, inputs = {}, {}
    for atom in atoms:
        aid = atom.atom_id
        measured = (webgl.kernel_cell(saved[aid]) if aid == webgl.CANDIDATE_ID else
                    cap8.kernel_cell(saved[aid], aid) if aid in _SEMANTIC else
                    deepcopy(prepared["features"][aid]))
        raw[aid] = measured
        # Saved base cells contain projected values, not the original fields.
        # Do not represent a parsed category, relation boolean, or list length
        # as if it were a raw navigator value.
        is_direct_number = (atom.atom_id.startswith("UNFITTED_CONTROL:")
                            and atom.provenance["encoder"] == "TRAIN_QUANTILE_LE")
        fields = [{"field": field, "value_present": is_direct_number and measured["available"],
                   "value": deepcopy(measured["value"]) if is_direct_number else None,
                   "source_status": None, "source_quality": None,
                   "value_origin": "prepared_projection" if is_direct_number else
                                   "original_field_not_in_saved_projection"} for field in _refs(atom)]
        inputs[aid] = _details(atom, measured, fields, "prepared_projection")
    return {"raw": raw, "candidate_inputs": inputs, "adapter_version": VERSION,
            "source_observation_mode": RAW_MODE}


def adapt_mtc(observation, defs=None):
    """Measure all 50 candidates on one untouched registered historical P1 row."""
    legacy._validate_historical(observation)
    atoms = _atoms(defs)
    raw, inputs = {}, {}
    for atom in atoms:
        aid, refs = atom.atom_id, _refs(atom)
        if aid == webgl.CANDIDATE_ID:
            measured = webgl.kernel_cell(webgl._saved(
                "U", "LEGACY_WEBGL1_RAW_QUERY_OBSERVATION_ABSENT",
                {"source_mode": LEGACY_MODE, "collector_contract": legacy._SOURCE_CONTRACT}))
        elif aid == cap8.WD_ID:
            measured = cap8.kernel_cell(webdriver_reported_state(
                legacy._projection(observation, refs, semantic=True), mode=LEGACY_MODE,
                source_binding=legacy._WD_BINDING).to_dict(), aid)
        elif aid == cap8.LANG_ID:
            measured = cap8.kernel_cell(web_language_first_difference(
                legacy._projection(observation, refs, semantic=True),
                source_binding=legacy._LANG_BINDING).to_dict(), aid)
        elif atom.orientation == "CATALOG_CONDITION":
            measured = _measure_catalog(observation, atom)
        else:
            measured = _measure_control(observation, atom)
        raw[aid] = measured
        inputs[aid] = _details(atom, measured, legacy._field_observations(observation, refs),
                               "historical_p1_observation")
    return {"raw": raw, "candidate_inputs": inputs, "adapter_version": VERSION,
            "source_observation_mode": LEGACY_MODE,
            "collector_version_code": observation["app"]["collector_version_code"]}


def input_mapping(defs=None):
    """Static dependency/meaning map; no train or evaluation records are read."""
    result = []
    for atom in _atoms(defs):
        refs = _refs(atom)
        field = atom.provenance.get("field", "")
        if atom.atom_id == webgl.CANDIDATE_ID:
            meaning, limitation = ("WebGL1 数字/数字字符串/再次数字查询的一致性",
                                   "旧采集完全缺少原始查询，固定 U；GPU 名称不能补造结果")
        elif atom.atom_id == cap8.WD_ID:
            meaning, limitation = ("legacy navigator.webdriver === true 投影",
                                   "true 可计算；false 丢失属性缺失/非布尔等信息，固定 U")
        elif atom.atom_id == cap8.LANG_ID:
            meaning, limitation = ("同次同步采集 language 与 languages[0] 的已定义标签差异",
                                   "保留既有语言可解释域；缺失、空列表、不可解释首项为 U")
        elif atom.orientation == "CATALOG_CONDITION":
            meaning = atom.provenance["condition"]["operator"]
            limitation = "原 catalog typed gate、适用域及 T/F 映射；未知不补为 F"
        else:
            meaning = atom.provenance["encoder"] + (" == " + repr(atom.provenance["equals"])
                       if atom.orientation == "CONTROL_EQUALITY" else "，受控训练侧分位数阈值尚未拟合")
            limitation = "保留原类型、status、quality；缺失/不可用为 U，不强制转型"
            if field.endswith((".device_memory", ".hardware_concurrency")):
                limitation += "；旧 ||0 默认值为 U，不解释成真实容量/核心数"
            elif field.endswith((".mime_types_count", ".plugins_count")):
                limitation += "；0 是原 length-or-0 投影，不能区分 API 缺失与空列表"
            elif field.endswith(".save_data"):
                limitation += "；原 !!connection.saveData 投影，false 不能证明独立 API 存在"
            elif field.endswith(".audio_output_latency"):
                limitation += "；秒，优先 outputLatency，回退 baseLatency，不能还原具体来源"
            elif field.endswith(".timezone_offset"):
                limitation += "；分钟，Date.getTimezoneOffset 的 UTC 减本地偏移"
            elif field.endswith(".device_pixel_ratio"):
                limitation += "；无量纲 CSS-to-device 比例，保留旧 ||1 投影"
            elif ".screen_layer." in field:
                limitation += "；宽高为 CSS 像素、depth 为位数、angle 为度、scale 无量纲；保留采集哨兵 quality"
        result.append({"atom_id": atom.atom_id, "orientation": atom.orientation,
                       "field_refs": refs, "original_paths": [p.removeprefix("app.") for p in refs],
                       "meaning": meaning, "historical_limits": limitation,
                       "historical_minus_one_unavailable_fields": [p for p in refs if p in HISTORICAL_MINUS_ONE_FIELDS],
                       "field_type": _CONTROL_CONTRACT.get(field, (None, None))[0],
                       "unit": (_UNITS.get(field.rsplit(".", 1)[-1], "CSS pixels")
                                if atom.orientation == "UNFITTED_NUMERIC_MEASUREMENT" else None),
                       "historical_source": legacy.HISTORICAL_SOURCE_COMMIT + ":web_probe/canonical_web_probe.js",
                       "fresh_source": "deliverables/webgl1_fresh_comparison_v1/prepared/inputs/",
                       "historical_collector_versions": deepcopy(legacy.REGISTERED_COLLECTORS),
                       "historical_probe": legacy.HISTORICAL_PROBE,
                       "controlled_mode": RAW_MODE, "mtc_mode": LEGACY_MODE})
    return result
