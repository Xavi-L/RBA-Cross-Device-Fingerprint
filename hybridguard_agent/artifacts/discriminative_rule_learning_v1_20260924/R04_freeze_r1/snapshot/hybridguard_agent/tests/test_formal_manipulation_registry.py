"""Static catalog plus synthetic scope fixtures only; no actual sample reads."""
import copy
import unittest

from hybridguard_agent.evidence.paired244 import field_contract
from hybridguard_agent.research.manipulation_eval.provenance import (
    COMMON_GATES, EXACT, PROPOSED_CANDIDATES, build_registry, decision_role,
    evaluate_applicability, family_registry, provenance_group, source_conditions, validate_registry,
)


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog, cls.rows, cls.scopes, cls.roles, cls.uncertainties = build_registry()
        cls.by_id = {r["rule_id"]: r for r in cls.rows}
        cls.scope = {r["rule_id"]: r for r in cls.scopes}
        cls.families, cls.overlaps = family_registry(cls.rows)
        cls.conditions = source_conditions(cls.rows)

    def payload(self, rid, **overrides):
        features = {}
        kinds = field_contract()
        for path in self.scope[rid]["required_fields"]:
            features[path] = copy.deepcopy({"string": "synthetic", "number": 1, "boolean": False, "array": []}[kinds[path]])
        for leaf, value in overrides.items():
            matches = [p for p in features if p.rsplit(".", 1)[-1] == leaf]
            self.assertTrue(matches, leaf)
            for path in matches:
                features[path] = value
        return {"features": features, "field_status": {p: "observed" for p in features},
                "field_quality": {p: "observed_value" for p in features}}

    def gate(self, rid, payload):
        return evaluate_applicability(self.scope[rid], payload)

    def test_all_active_ids_and_stored_sources_close_exactly(self):
        checks = validate_registry(self.catalog, self.rows, self.scopes, self.roles, self.families, self.conditions)
        self.assertTrue(all(checks.values()), checks)
        self.assertEqual(self.conditions["groups"]["O_u"], sorted([
            "OFFDER-OS-001", "OFFDER-OS-002", "OFFDER-UA-001", "OFFDER-UA-002", "OFFDER-TOUCH-001",
            "OFFDER-BRIDGE-001", "OFFDER-DEVCONFIG-001", "OFFDER-GPU-001", "OFFDER-NET-001"]))
        self.assertEqual(len(self.conditions["groups"]["H"]), 14)
        self.assertNotIn("CORE-001", self.by_id)

    def test_source_flag_change_does_not_manufacture_role_or_target_count(self):
        rule = copy.deepcopy(next(r for r in self.catalog["rules"] if r["rule_id"] == "OFFDER-OS-001"))
        self.assertEqual(provenance_group(rule), "O_u")
        rule["empirical_selection_applied"] = True
        self.assertEqual(provenance_group(rule), "H")
        self.assertEqual(decision_role(rule), "observation_only")
        rule["source_lane"] = "collector_derived_consistency"
        self.assertEqual(provenance_group(rule), "C")
        rule["source_lane"] = "unreviewed"
        with self.assertRaises(ValueError):
            provenance_group(rule)

    def test_every_reviewed_candidate_retains_its_unobservable_condition(self):
        reviewed = [r for r in self.rows if r["proposed_alert_candidate_reviewed"]]
        self.assertEqual({r["rule_id"] for r in reviewed}, PROPOSED_CANDIDATES)
        for row in reviewed:
            self.assertEqual(row["decision_role"], "observation_only")
            self.assertTrue(row["unobservable_alert_preconditions"])
            self.assertTrue(row["known_counterexamples"])
        self.assertFalse(any(r["decision_role"] == "alert_candidate" for r in self.rows))

    def test_eight_source_conditions_and_four_aliases_use_exact_ids(self):
        expected_counts = {"000": 11, "001": 34, "010": 25, "011": 48, "100": 20, "101": 43, "110": 34, "111": 57}
        for condition in self.conditions["conditions"]:
            bits = condition["condition_id"][-3:]
            self.assertEqual(condition["rule_count"], expected_counts[bits])
            expected = set(self.conditions["groups"]["C"])
            for bit, group in zip(bits, ("O_u", "H", "E")):
                if bit == "1":
                    expected.update(self.conditions["groups"][group])
            self.assertEqual(set(condition["rule_ids"]), expected)
            self.assertEqual(condition["common_gate_ids"], COMMON_GATES)
            self.assertFalse(condition["official_knowledge_completely_removed"])
        self.assertEqual(self.conditions["four_source_mapping"], {"C": "SRC-000", "B0": "SRC-000", "E": "SRC-001", "O": "SRC-110", "EO": "SRC-111"})

    def test_common_gates_survive_removal_of_official_derived_predicates(self):
        empirical = next(c for c in self.conditions["conditions"] if c["condition_id"] == "SRC-001")
        self.assertFalse(set(empirical["rule_ids"]) & set(self.conditions["groups"]["O_u"]))
        self.assertIn("product_specific_ua_scope", empirical["common_gate_ids"])
        self.assertIn("gpu_render_path_not_inferred", empirical["common_gate_ids"])

    def test_shared_family_and_exact_equivalence_are_not_conflated(self):
        gpu = next(f for f in self.families["families"] if f["decision_family"] == "native_app_gpu_family")
        self.assertEqual(gpu["rule_ids"], ["NW-005", "OFFDER-GPU-001", "P3-GPU-COPY"])
        self.assertEqual(len(gpu["provenance_groups"]), 3)
        pair = next(p for p in self.overlaps if {p["rule_a"], p["rule_b"]} == {"NW-005", "OFFDER-GPU-001"})
        self.assertEqual(pair["relation"], "related_not_equivalent")
        self.assertIn(frozenset(("NW-002", "OFFDER-OS-001")), EXACT)
        self.assertNotIn(frozenset(("OFFDER-UA-002", "P3-UA-DEFAULT")), EXACT)
        self.assertEqual(self.by_id["OFFDER-GPU-001"]["original_evidence_family"], "OFFDER-GPU-001")

    def test_app_and_browser_ua_reduction_scopes_are_separate(self):
        full = "Mozilla/5.0 (Linux; Android 10; ModelX Build/QP1A; wv) Chrome/107.0.0.0"
        app = self.payload("NW-002", os_version="16", user_agent=full, default_ua_native=full, settings_user_agent=full)
        self.assertEqual(self.gate("NW-002", app)["status"], "UNKNOWN")  # no copied Browser >=107 condition
        reduced = "Mozilla/5.0 (Linux; Android 10; K; wv) Chrome/140.0.0.0"
        app = self.payload("NW-002", os_version="17", user_agent=reduced, default_ua_native=reduced, settings_user_agent=reduced)
        self.assertEqual(self.gate("NW-002", app)["status"], "NOT_APPLICABLE")
        for version in (100, 107, 110, 140):
            browser = self.payload("P3-UA-REDUCED-BROWSER", os_version="16", user_agent=f"Mozilla/5.0 (Linux; Android 10; K) Chrome/{version}.0.0.0")
            self.assertEqual(self.gate("P3-UA-REDUCED-BROWSER", browser)["status"], "NOT_APPLICABLE")
        ordinary = self.payload("P3-UA-REDUCED-BROWSER", os_version="16", user_agent=full.replace("; wv", ""))
        self.assertEqual(self.gate("P3-UA-REDUCED-BROWSER", ordinary)["status"], "UNKNOWN")

    def test_default_settings_snapshot_does_not_prove_origin_or_temporal_stability(self):
        ua = "Mozilla/5.0 (Linux; Android 14; ModelX Build/UP1A; wv) Chrome/120.0.0.0"
        payload = self.payload("NW-001", device_model="ModelX", user_agent=ua, default_ua_native=ua, settings_user_agent=ua)
        self.assertEqual(self.gate("NW-001", payload)["status"], "UNKNOWN")
        path = next(p for p in payload["features"] if p.endswith(".settings_user_agent"))
        payload["features"][path] = "legitimate custom UA"
        self.assertEqual(self.gate("NW-001", payload)["status"], "NOT_APPLICABLE")

    def test_dalvik_is_required_but_not_proof_of_an_unmodified_property(self):
        rid = "NVW-001"
        payload = self.payload(rid, device_model="ModelX", system_http_agent="Dalvik/2.1.0 (Linux; U; Android 14; ModelX Build/UP1A)")
        self.assertEqual(self.gate(rid, payload)["status"], "UNKNOWN")
        for key in payload["features"]:
            if key.endswith(".system_http_agent"):
                payload["features"][key] = "Mozilla/5.0 (Linux; Android 14; ModelX Build/UP1A)"
        self.assertEqual(self.gate(rid, payload)["status"], "NOT_APPLICABLE")
        opaque = self.payload("NVW-002", os_version="bananas", system_http_agent="Dalvik/2.1.0 (Linux; Android 14; ModelX Build/UP1A)")
        self.assertEqual(self.gate("NVW-002", opaque)["status"], "UNKNOWN")

    def test_gpu_software_angle_and_desktop_backend_are_not_automatic_alerts(self):
        for renderer in ("SwiftShader", "llvmpipe", "lavapipe", "ANGLE (SwANGLE)"):
            payload = self.payload("NW-005", native_gpu_renderer="Adreno (TM) 650", webgl_renderer=renderer)
            self.assertEqual(self.gate("NW-005", payload)["status"], "NOT_APPLICABLE")
        for renderer in ("ANGLE (Adreno 650)", "Mali-G78", "ANGLE (NVIDIA Direct3D11)", "masked"):
            payload = self.payload("NW-005", native_gpu_renderer="Adreno (TM) 650", webgl_renderer=renderer)
            self.assertEqual(self.gate("NW-005", payload)["status"], "UNKNOWN")
        payload = self.payload("OFFDER-GPU-001", native_gpu_renderer="Adreno 650", egl_renderer="Adreno 650", webgl_vendor="Google", webgl_renderer="ANGLE (NVIDIA Direct3D11)")
        self.assertEqual(self.gate("OFFDER-GPU-001", payload)["status"], "UNKNOWN")

    def test_no_browser_fabrication_and_field_availability_boundaries(self):
        self.assertEqual(self.gate("P3-UA-REDUCED-BROWSER", {"features": {}, "field_status": {}, "field_quality": {}})["status"], "UNKNOWN")
        payload = self.payload("NW-007", user_agent="Mozilla/5.0 Android 14", max_touch_points=0)
        self.assertEqual(self.gate("NW-007", payload)["status"], "SUPPORTED")
        touch = next(p for p in payload["features"] if p.endswith(".max_touch_points"))
        for value in (False, float("nan"), -1):
            changed = copy.deepcopy(payload); changed["features"][touch] = value
            self.assertEqual(self.gate("NW-007", changed)["status"], "UNKNOWN")
        payload["field_status"].pop(touch)
        self.assertEqual(self.gate("NW-007", payload)["status"], "UNKNOWN")

    def test_false_sensor_flag_and_empty_lists_remain_valid_observations(self):
        payload = self.payload("P3-SENSOR-ACCELEROMETER", has_accelerometer=False, sensor_type_list=[])
        self.assertEqual(self.gate("P3-SENSOR-ACCELEROMETER", payload)["status"], "NOT_APPLICABLE")
        empty = self.payload("P3-SENSOR-TYPE-ORDER", sensor_type_list=[])
        self.assertEqual(self.gate("P3-SENSOR-TYPE-ORDER", empty)["status"], "SUPPORTED")
        payload = self.payload("P3-SENSOR-ACCELEROMETER", has_accelerometer=True, sensor_type_list=[float("inf")])
        self.assertEqual(self.gate("P3-SENSOR-ACCELEROMETER", payload)["status"], "UNKNOWN")

    def test_metadata_and_unselected_fields_cannot_satisfy_unknown_gates(self):
        ua = "Mozilla/5.0 (Linux; Android 14; ModelX Build/UP1A; wv) Chrome/120.0.0.0"
        payload = self.payload("NW-002", os_version="14", user_agent=ua, default_ua_native=ua, settings_user_agent=ua)
        expected = self.gate("NW-002", payload)
        for marker in ("clean", "attack"):
            polluted = copy.deepcopy(payload)
            for key in ("label", "phase", "tool", "config", "session_id", "install_id", "group_id", "receipt", "log", "future_post", "runtime_context"):
                polluted[key] = {"origin_verified": True, "state": marker}
            polluted["features"]["unregistered.authorized_default_chain"] = True
            self.assertEqual(self.gate("NW-002", polluted), expected)

    def test_unselected_fields_are_not_read_and_selected_quality_is_required(self):
        payload = self.payload("CORE-002", jsbridge_injected=False)
        selected = set(self.scope["CORE-002"]["required_fields"])

        class Guarded(dict):
            def get(self, key, default=None):
                if key not in selected:
                    raise AssertionError("scope gate read an undeclared field")
                return super().get(key, default)

        guarded = {name: Guarded(value) for name, value in payload.items()}
        self.assertEqual(self.gate("CORE-002", guarded)["status"], "SUPPORTED")
        guarded["field_quality"][next(iter(selected))] = "source_unavailable"
        self.assertEqual(self.gate("CORE-002", guarded)["status"], "UNKNOWN")

    def test_provenance_versions_and_unavailable_conditions_are_not_filled_in(self):
        self.assertTrue(any(u["code"] == "DOCUMENT_REVISION_UNKNOWN" for u in self.uncertainties))
        self.assertTrue(any(u["code"] == "BROWSER_UA_MILESTONE_SCOPE_DISCREPANCY" for u in self.uncertainties))
        for rid in self.conditions["groups"]["O_u"]:
            self.assertIn("not pure", self.by_id[rid]["O_u_definition"])
            self.assertFalse(self.by_id[rid]["researcher_derivation"]["is_official_risk_verdict"])
        for row in self.rows:
            if row["decision_role"] == "alert_candidate":
                self.assertFalse(row["unobservable_alert_preconditions"])


if __name__ == "__main__":
    unittest.main()
