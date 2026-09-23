"""S02 synthetic fixtures only: no research inputs, detector or policy calls."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.evidence.paired244 import build_paired_evidence
from hybridguard_agent.research.manipulation_eval.adapter import (
    AdaptationError, PAYLOAD_KEYS, SECTIONS, STATES, adapt_payload, association_rows,
    collect_source, convert_unit, mapping_contract, project_payload, selected_fields,
    sha256_value, validate_inference_payload,
)


def put(target, path, value):
    keys = path.split(".")
    for key in keys[:-1]:
        target = target.setdefault(key, {})
    target[keys[-1]] = value


def fixture(flat=False, alias_status=False):
    raw = {"collector_app": "featureapp", "schema_version": "expanded-v2.2-status",
           "collection_status": {"status_schema_version": "field-status-v1", "fixed_signal_count": 177, "fields": {}}}
    for spec in mapping_contract()["fields"]:
        value = {"number": 1, "string": "fixture", "boolean": False, "array": []}[spec["type"]]
        put(raw, spec["legacy_alias"] if flat else spec["source_logical_path"], copy.deepcopy(value))
        raw["collection_status"]["fields"][spec["legacy_alias"] if alias_status else spec["source_logical_path"]] = "observed"
    return raw


def fact(candidate="fixture:1", phase="clean_pre", kind="attack"):
    return {"candidate_id": candidate, "bundle_id": "fixture", "session_id": "synthetic-session",
            "triplet_id": "synthetic-triplet", "phase": phase, "kind": kind, "environment_group_id": "synthetic-group",
            "raw_session_ref": "raw.jsonl#session_id=synthetic-session", "manifest_ref": "manifest.jsonl#line=1",
            "payload_binding": {"status": "BOUND", "raw_line": 1},
            "eligible_triplet": False, "eligible_temporal_control": False, "no_intervention": {"status": "UNKNOWN"}}


class AdapterTests(unittest.TestCase):
    def spec(self, suffix):
        return next(s for s in mapping_contract()["fields"] if s["field"].endswith(suffix))

    def rejected_codes(self, raw):
        with self.assertRaises(AdaptationError) as context:
            adapt_payload(raw)
        return {issue["code"] for issue in context.exception.issues}

    def test_flat_nested_and_explicit_legacy_status_are_equivalent(self):
        payload = adapt_payload(fixture())
        self.assertEqual(payload, adapt_payload(fixture(flat=True)))
        self.assertEqual(payload, adapt_payload(fixture(flat=True, alias_status=True)))
        self.assertEqual(set(payload), PAYLOAD_KEYS)
        self.assertEqual(len(payload["features"]), 177)
        self.assertEqual(mapping_contract()["surface_counts"], {"native84": 84, "app_web67": 67, "host26": 26})
        self.assertFalse(any(key.startswith("browser.") for key in payload["features"]))

    def test_status_set_not_just_count_and_no_observed_inference(self):
        raw = fixture()
        states = raw["collection_status"]["fields"]
        states.pop(next(iter(states)))
        states["unregistered.field"] = "observed"
        self.assertEqual(len(states), 177)
        self.assertTrue({"MISSING_STATUS_KEYS", "UNREGISTERED_STATUS_KEY"} <= self.rejected_codes(raw))
        raw = fixture()
        del raw["collection_status"]
        self.assertIn("MISSING_EXPLICIT_FIELD_STATUS", self.rejected_codes(raw))

    def test_duplicate_status_aliases_and_unknown_states_reject(self):
        spec = self.spec(".webdriver")
        for alias_state, code in (("observed", "DUPLICATE_STATUS_ALIAS"), ("timeout", "STATUS_ALIAS_CONFLICT")):
            with self.subTest(alias_state=alias_state):
                raw = fixture()
                raw["collection_status"]["fields"][spec["legacy_alias"]] = alias_state
                self.assertIn(code, self.rejected_codes(raw))
        raw = fixture()
        raw["collection_status"]["fields"][spec["source_logical_path"]] = "guessed_observed"
        self.assertIn("INVALID_FIELD_STATUS", self.rejected_codes(raw))

    def test_value_alias_conflict_and_equal_alias_acceptance(self):
        spec = self.spec(".webdriver")
        raw = fixture()
        put(raw, spec["legacy_alias"], False)
        self.assertEqual(adapt_payload(raw), adapt_payload(fixture()))
        put(raw, spec["legacy_alias"], 0)  # bool False must not compare equal to number 0
        self.assertIn("VALUE_ALIAS_CONFLICT", self.rejected_codes(raw))

    def test_wrong_types_observed_null_and_nonfinite_reject(self):
        spec = self.spec(".device_memory")
        for value, code in ((False, "INVALID_FIELD_TYPE"), ("4", "INVALID_FIELD_TYPE"),
                            (None, "OBSERVED_VALUE_MISSING_OR_NULL"), (float("nan"), "NONFINITE_OR_NON_JSON_VALUE"),
                            (float("inf"), "NONFINITE_OR_NON_JSON_VALUE")):
            with self.subTest(value=value):
                raw = fixture()
                put(raw, spec["source_logical_path"], value)
                self.assertIn(code, self.rejected_codes(raw))
        array_spec = self.spec(".languages")
        raw = fixture()
        put(raw, array_spec["source_logical_path"], [float("-inf")])
        self.assertIn("NONFINITE_OR_NON_JSON_VALUE", self.rejected_codes(raw))
        raw = fixture()
        raw["web_data"] = []
        self.assertIn("INVALID_LAYER_SHAPE", self.rejected_codes(raw))

    def test_false_zero_and_empty_arrays_retained_with_sentinel_quality(self):
        raw = fixture()
        for suffix in (".device_memory", ".hardware_concurrency", ".max_touch_points"):
            put(raw, self.spec(suffix)["source_logical_path"], 0)
        payload = adapt_payload(raw)
        for suffix in (".device_memory", ".hardware_concurrency"):
            spec = self.spec(suffix)
            self.assertEqual(payload["features"][spec["field"]], 0)
            self.assertEqual(payload["field_status"][spec["field"]], "observed")
            self.assertEqual(payload["field_quality"][spec["field"]], "ambiguous_sentinel")
        self.assertEqual(payload["field_quality"][self.spec(".max_touch_points")["field"]], "observed_value")
        self.assertIs(payload["features"][self.spec(".webdriver")["field"]], False)
        self.assertEqual(payload["features"][self.spec(".languages")["field"]], [])

    def test_all_six_states_retained_without_inferring_availability(self):
        raw = fixture()
        specs = [self.spec(".webdriver"), self.spec(".max_touch_points"), self.spec(".languages")]
        for state in sorted(STATES):
            with self.subTest(state=state):
                for spec, value in zip(specs, (False, 0, [])):
                    put(raw, spec["source_logical_path"], value)
                    raw["collection_status"]["fields"][spec["source_logical_path"]] = state
                payload = adapt_payload(raw)
                for spec, value in zip(specs, (False, 0, [])):
                    self.assertEqual(payload["features"][spec["field"]], value)
                    self.assertEqual(payload["field_status"][spec["field"]], state)
                    self.assertEqual(payload["field_quality"][spec["field"]], "observed_value" if state == "observed" else "source_unavailable")
        put(raw, specs[0]["source_logical_path"], None)
        self.assertIsNone(adapt_payload(raw)["features"][specs[0]["field"]])

    def test_metadata_permutation_and_arbitrary_leaf_collisions_are_isolated(self):
        raw = fixture()
        ua = self.spec(".navigator_layer.user_agent")
        put(raw, ua["source_logical_path"], "legitimate HeadlessChrome current-session UA")
        expected = adapt_payload(raw)
        for marker in ("first-label", "opposite-label"):
            polluted = copy.deepcopy(raw)
            polluted.update({key: {"secret": marker} for key in (
                "label", "phase", "tool", "config", "source_path", "session_id", "collector_install_id", "group_id",
                "runtime_context", "execution_receipt", "expected_modified_fields", "clean_post", "browser", "field_status")})
            polluted["web_data"]["unexpected_metadata"] = {"user_agent": marker, "webdriver": True}
            self.assertEqual(adapt_payload(polluted), expected)
        self.assertIn("HeadlessChrome", expected["features"][ua["field"]])

    def test_future_post_and_evaluation_facts_do_not_change_current_payload(self):
        pre, active, post = fixture(), fixture(), fixture()
        a = self.spec(".webdriver")
        put(active, a["source_logical_path"], True)
        before = [adapt_payload(pre), adapt_payload(active)]
        put(post, a["source_logical_path"], True)
        mapping_contract()  # warm only static field contracts before prohibiting IO
        with patch.object(Path, "read_text", side_effect=AssertionError("projection must not read sidecars or future stages")):
            self.assertEqual(before, [adapt_payload(pre), adapt_payload(active)])
        first = convert_unit(pre, fact(), {"future_post": post, "label": "clean"})
        changed = convert_unit(pre, fact(), {"future_post": {"other": "future"}, "label": "attack"})
        self.assertEqual(first[0]["payload"], changed[0]["payload"])

    def test_view_masking_never_reads_hidden_values_status_quality_or_summaries(self):
        payload = adapt_payload(fixture())
        for view, count in (("Native84", 84), ("Host26", 26), ("AppWeb67", 67), ("NativePlusAppWeb151", 151), ("App177", 177)):
            allowed = selected_fields(view)

            class Guarded(dict):
                def __getitem__(self, key):
                    if key not in allowed:
                        raise AssertionError("read hidden field")
                    return super().__getitem__(key)

            guarded = {name: Guarded(payload[name]) for name in SECTIONS}
            guarded.update(derived_facts={"hidden": "must disappear"}, present_surfaces=["browser67"], session_id="secret")
            actual = project_payload(guarded, view)
            self.assertEqual(set(actual), PAYLOAD_KEYS)
            for name in SECTIONS:
                self.assertEqual(set(actual[name]), allowed)
                self.assertEqual(len(actual[name]), count)
        with self.assertRaises(ValueError):
            project_payload(payload, "Full244")

    def test_synthetic_derived_facts_have_only_selected_field_dependencies(self):
        payload = adapt_payload(fixture())
        for view in ("Native84", "Host26", "AppWeb67", "NativeAppWeb151"):
            selected = project_payload(payload, view)
            # Pure evidence extraction on a synthetic fixture; no detector or policy.
            bundle = build_paired_evidence(selected, input_view=view)
            self.assertEqual(set(bundle["fields"]), selected_fields(view))
            for derived in bundle["derived_facts"].values():
                self.assertLessEqual(set(derived["source_fields"]), selected_fields(view))
            self.assertNotIn("browser67", bundle["present_surfaces"])

    def test_identical_payload_units_and_unknown_control_keep_all_three_phases(self):
        units = []
        for index, phase in enumerate(("clean_pre", "control_mid", "clean_post"), 1):
            frozen = fact(f"fixture:{index}", phase, "control")
            unit = convert_unit(fixture(), frozen, {"cohort": "temporal_control_unknown", "sequence_index": index, "round": 1})
            self.assertIsNone(unit[3])
            self.assertEqual(unit[2]["admission_fact"], frozen)
            self.assertFalse(unit[2]["admission_fact"]["eligible_temporal_control"])
            units.append(unit)
        self.assertEqual(len({u[0]["opaque_id"] for u in units}), 3)
        self.assertTrue(all(u[0]["payload"] == units[0][0]["payload"] for u in units))
        linked = association_rows([u[2] for u in units])
        self.assertTrue(linked[0]["complete_source_triplet"])
        self.assertEqual(len(linked[0]["phases"]), 3)

    def test_mixed_success_and_rejection_preserve_unique_units_and_reason(self):
        good = convert_unit(fixture(), fact(), {})
        bad_raw = fixture()
        del bad_raw["collection_status"]
        bad = convert_unit(bad_raw, fact("fixture:2", "clean_post"), {})
        self.assertEqual([good[1]["status"], bad[1]["status"]], ["ADAPTED", "REJECTED"])
        self.assertNotEqual(good[1]["opaque_id"], bad[1]["opaque_id"])
        self.assertIsNone(bad[0])
        self.assertEqual(bad[3]["reason_codes"], ["MISSING_EXPLICIT_FIELD_STATUS"])
        self.assertEqual(bad[2]["admission_fact"], fact("fixture:2", "clean_post"))

    def test_source_binding_and_incomplete_attempt_remain_independent_of_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = fixture()
            raw["session_id"] = "synthetic-session"
            frozen = fact()
            frozen["payload_binding"]["actual_payload_digest"] = sha256_value(raw)
            stage = {"line": 1, "session_id": "synthetic-session"}
            inventory = {"raw_ref": "raw.jsonl", "run_ref": "run.json", "complete_nine_stage_candidate": False, "original_release": {}}
            (root / "raw.jsonl").write_text(json.dumps(raw) + "\n")
            (root / "manifest.jsonl").write_text(json.dumps({"session_id": "synthetic-session", "pair": {
                "pair_id": "synthetic-triplet", "pair_role": "clean_pre", "sequence_index": 0}}) + "\n")
            (root / "run.json").write_text(json.dumps({"sessions": [{"session_id": "synthetic-session", "round": 1}]}))
            value, metadata, errors = collect_source(stage, frozen, inventory, root, {})
            self.assertFalse(errors)
            self.assertEqual(metadata["cohort"], "incomplete_attempt")
            self.assertEqual(value, raw)
            frozen["payload_binding"]["actual_payload_digest"] = "wrong binding"
            self.assertEqual(collect_source(stage, frozen, inventory, root, {})[2][0]["code"], "SOURCE_PAYLOAD_BINDING_MISMATCH")

    def test_inference_validator_rejects_control_plane_metadata(self):
        payload = adapt_payload(fixture())
        payload["label"] = "clean"
        with self.assertRaises(ValueError):
            validate_inference_payload(payload)
        del payload["label"]
        payload["features"]["browser.web_data.navigator_layer.user_agent"] = "invented"
        with self.assertRaises(ValueError):
            validate_inference_payload(payload)


if __name__ == "__main__":
    unittest.main()
