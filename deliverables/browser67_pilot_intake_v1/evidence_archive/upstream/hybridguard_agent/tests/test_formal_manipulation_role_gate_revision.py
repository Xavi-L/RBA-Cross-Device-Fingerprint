"""S03-R independent static/synthetic contract and output-isolation tests."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from hybridguard_agent.research.manipulation_eval import provenance as v1
from hybridguard_agent.research.manipulation_eval import provenance_revision as v2
from hybridguard_agent.research.manipulation_eval.registry_output import validate_destinations


class RoleGateRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = v2.build_revision()
        cls.scopes = {r["rule_id"]: r for r in cls.registry["scopes"]}
        cls.roles = {r["rule_id"]: r for r in cls.registry["roles"]}
        cls.cases = v2.synthetic_cases(cls.registry)
        cls.results = v2.check_synthetic_cases(cls.cases, cls.registry)

    def payload(self, rid):
        return v2.synthetic_payload(rid, self.registry)

    def assess(self, rid, payload):
        return v2.evaluate_contract(rid, payload, self.registry)

    def field(self, rid, leaf):
        scope = self.scopes[rid]
        return next(f for f in scope["relation_required_fields"] + scope["additional_risk_required_fields"] if f.endswith("." + leaf))

    def test_all_active_source_and_family_bindings_and_eight_sets_preserved(self):
        base = {r["rule_id"]: r for r in v2._read_jsonl(v1.STUDY_CONFIG / "source_registry.jsonl")}
        self.assertEqual(len(self.roles), 57)
        self.assertEqual(set(self.roles), set(base))
        for binding in self.registry["bindings"]:
            old = base[binding["rule_id"]]
            for key in ("provenance_group", "decision_family", "original_evidence_family", "dependencies"):
                self.assertEqual(binding[key], old[key])
            if binding["rule_id"] not in v2.REVIEWED:
                self.assertEqual(self.roles[binding["rule_id"]]["decision_role"], old["decision_role"])
        old = v1.read_json(v1.STUDY_CONFIG / "source_conditions.json")
        new = self.registry["conditions"]
        self.assertEqual(new["groups"], old["groups"])
        self.assertEqual(new["four_source_mapping"], old["four_source_mapping"])
        for a, b in zip(new["conditions"], old["conditions"]):
            self.assertEqual(a["rule_ids"], b["rule_ids"])
            self.assertEqual(a["common_C_ids"], b["common_C_ids"])
            self.assertEqual(a["common_gate_ids"], v2.COMMON_GATES)
            self.assertEqual(a["applicability_policy_version"], v2.VERSION)
            self.assertFalse(a["official_knowledge_completely_removed"])

    def test_every_approved_candidate_has_reachable_consistent_and_conflict_paths(self):
        self.assertTrue(self.results)
        self.assertTrue(all(r["passed"] for r in self.results), [r for r in self.results if not r["passed"]])
        report = v2.feasibility(self.registry, self.results)
        self.assertTrue(report["all_candidate_paths_reachable"])
        self.assertEqual(set(report["candidate_rule_ids"]), {r["rule_id"] for r in self.registry["roles"] if r["decision_role"] == "alert_candidate"})
        for reach in report["reachability"]:
            self.assertTrue(reach["consistent_path_reachable"])
            self.assertTrue(reach["conflict_path_reachable"])
            self.assertTrue(reach["attribution_stays_unknown"])
        self.assertEqual(report["actual_sample_predictions"], 0)
        self.assertEqual(report["actual_detection_performance"], "NOT_EVALUATED")

    def test_attribution_unknown_is_orthogonal_to_comparability_and_conflict(self):
        p = self.payload("NW-002")
        a = self.assess("NW-002", p)
        p["features"][self.field("NW-002", "user_agent")] = v2.FULL_UA.replace("Android 14", "Android 15")
        b = self.assess("NW-002", p)
        for result in (a, b):
            self.assertEqual(result["relation_applicability"]["status"], "SUPPORTED")
            self.assertEqual(result["risk_candidate_eligibility"]["status"], "ELIGIBLE")
            self.assertEqual(result["attribution_certainty"]["status"], "UNKNOWN")
            self.assertFalse(result["attribution_certainty"]["attack_proven"])
            self.assertIsNone(result["attribution_certainty"]["calibrated_attack_probability"])
            self.assertNotIn("alert_score", result)
            self.assertNotIn("decision", result)
        self.assertEqual(a["relation_result"]["outcome"], "MATCH")
        self.assertEqual(b["relation_result"]["outcome"], "COUNTEREXAMPLE")

    def test_source_redundancy_is_a_structural_limit_not_a_performance_result(self):
        report = v2.feasibility(self.registry, self.results)
        conditions = {r["condition_id"]: r for r in report["source_condition_candidate_membership"]}
        self.assertEqual(conditions["SRC-001"]["candidate_family_ids"], conditions["SRC-111"]["candidate_family_ids"])
        self.assertFalse(conditions["SRC-000"]["candidate_family_ids"])
        self.assertFalse(conditions["SRC-010"]["candidate_family_ids"])
        for a,b in (("NW-002", "OFFDER-OS-001"), ("NVW-002", "OFFDER-OS-002")):
            for case in ("consistent", "conflict", "missing", "not_applicable"):
                x = next(r for r in self.results if r["rule_id"]==a and r["case"]==case)
                y = next(r for r in self.results if r["rule_id"]==b and r["case"]==case)
                self.assertEqual(x["actual"], y["actual"])
        self.assertEqual(report["actual_detection_performance"], "NOT_EVALUATED")

    def test_missing_risk_reference_does_not_erase_comparable_relation(self):
        p = self.payload("NW-002")
        p["features"][self.field("NW-002", "user_agent")] = v2.FULL_UA.replace("Android 14", "Android 15")
        for mapping in p.values():
            mapping.pop(v2.DEFAULT_UA)
        result = self.assess("NW-002", p)
        self.assertEqual(result["relation_applicability"]["status"], "SUPPORTED")
        self.assertEqual(result["relation_result"]["outcome"], "COUNTEREXAMPLE")
        self.assertEqual(result["risk_candidate_eligibility"]["status"], "UNKNOWN")

    def test_custom_ua_and_unresolved_alias_reference_do_not_gain_eligibility(self):
        for rid in ("NW-001", "NW-002", "OFFDER-OS-001"):
            p = self.payload(rid)
            p["features"][v2.SETTINGS_UA] = "legitimate application-specific UA"
            result = self.assess(rid, p)
            self.assertEqual(result["relation_applicability"]["status"], "SUPPORTED")
            self.assertEqual(result["risk_candidate_eligibility"]["status"], "NOT_ELIGIBLE")
        for rid in ("NW-001", "NVW-001"):
            p = self.payload(rid)
            p["features"][v2.DEFAULT_UA] = v2.FULL_UA.replace("ModelX", "VendorAlias")
            if v2.SETTINGS_UA in p["features"]:
                p["features"][v2.SETTINGS_UA] = p["features"][v2.DEFAULT_UA]
            result = self.assess(rid, p)
            self.assertEqual(result["relation_applicability"]["status"], "SUPPORTED")
            self.assertEqual(result["risk_candidate_eligibility"]["status"], "UNKNOWN")

    def test_invalid_zero_opaque_reduced_and_semantic_mismatch_still_block(self):
        for value in ("0", "preview14", False, float("nan"), float("inf")):
            p = self.payload("NW-002")
            p["features"][self.field("NW-002", "os_version")] = value
            self.assertEqual(self.assess("NW-002", p)["relation_applicability"]["status"], "UNKNOWN")
        for version in (100, 107, 110, 140):
            p = self.payload("NW-002")
            p["features"][self.field("NW-002", "user_agent")] = f"Mozilla/5.0 (Linux; Android 10; K; wv) Chrome/{version}.0.0.0"
            self.assertEqual(self.assess("NW-002", p)["relation_applicability"]["status"], "NOT_APPLICABLE")
        p = self.payload("NW-001")
        p["features"][self.field("NW-001", "user_agent")] = v2.FULL_UA + " " + v2.FULL_UA
        self.assertEqual(self.assess("NW-001", p)["relation_applicability"]["status"], "UNKNOWN")
        p["features"][self.field("NW-001", "user_agent")] = v2.SYSTEM_UA
        self.assertEqual(self.assess("NW-001", p)["relation_applicability"]["status"], "NOT_APPLICABLE")

    def test_system_property_is_comparable_but_unmodified_origin_is_not_proven(self):
        for rid in ("NVW-001", "NVW-002", "OFFDER-OS-002"):
            p = self.payload(rid)
            result = self.assess(rid, p)
            self.assertEqual(result["relation_applicability"]["status"], "SUPPORTED")
            self.assertEqual(result["risk_candidate_eligibility"]["status"], "ELIGIBLE")
            self.assertEqual(result["attribution_certainty"]["status"], "UNKNOWN")
            p["features"][self.field(rid, "system_http_agent")] = v2.FULL_UA
            self.assertEqual(self.assess(rid, p)["relation_applicability"]["status"], "NOT_APPLICABLE")

    def test_gpu_family_and_backend_marker_have_distinct_risk_roles(self):
        p = self.payload("NW-005")
        p["features"][self.field("NW-005", "webgl_renderer")] = "Mali-G78"
        result = self.assess("NW-005", p)
        self.assertEqual(result["relation_result"]["outcome"], "COUNTEREXAMPLE")
        self.assertEqual(result["risk_candidate_eligibility"]["status"], "ELIGIBLE")
        p = self.payload("OFFDER-GPU-001")
        p["features"][self.field("OFFDER-GPU-001", "webgl_renderer")] = "ANGLE (NVIDIA Direct3D11)"
        result = self.assess("OFFDER-GPU-001", p)
        self.assertEqual(result["relation_applicability"]["status"], "SUPPORTED")
        self.assertEqual(result["relation_result"]["outcome"], "COUNTEREXAMPLE")
        self.assertEqual(result["risk_candidate_eligibility"]["status"], "NOT_ELIGIBLE")
        self.assertEqual(result["attribution_certainty"]["status"], "UNKNOWN")

    def test_gpu_software_masking_and_ambiguity_cannot_become_hardware_evidence(self):
        for renderer in ("SwiftShader", "llvmpipe", "softpipe", "swrast", "lavapipe", "swangle"):
            p = self.payload("NW-005")
            p["features"][self.field("NW-005", "webgl_renderer")] = renderer
            self.assertEqual(self.assess("NW-005", p)["relation_applicability"]["status"], "NOT_APPLICABLE")
        for renderer in ("ANGLE", "Adreno and Mali", "masked Adreno", "unknown"):
            p = self.payload("NW-005")
            p["features"][self.field("NW-005", "webgl_renderer")] = renderer
            self.assertEqual(self.assess("NW-005", p)["relation_applicability"]["status"], "UNKNOWN")

    def test_context_collector_deployment_and_unreviewed_observations_never_vote(self):
        for rid, row in self.roles.items():
            if row["decision_role"] != "alert_candidate":
                result = self.assess(rid, self.payload(rid))
                self.assertEqual(result["risk_candidate_eligibility"]["status"], "NOT_ELIGIBLE", rid)
        self.assertTrue(all(r["decision_role"] != "alert_candidate" for r in self.roles.values() if r["provenance_group"] in {"H", "C"}))
        p = self.payload("NW-007")
        p["features"][self.field("NW-007", "max_touch_points")] = 0
        self.assertEqual(self.assess("NW-007", p)["relation_applicability"]["status"], "SUPPORTED")
        p = self.payload("P3-SENSOR-TYPE-ORDER")
        self.assertEqual(self.assess("P3-SENSOR-TYPE-ORDER", p)["relation_applicability"]["status"], "SUPPORTED")

    def test_labels_tools_stages_logs_future_and_scope_claims_cannot_affect_results(self):
        for rid, row in self.roles.items():
            if not row["reviewed_candidate"]:
                continue
            p = self.payload(rid)
            expected = self.assess(rid, p)
            for mark in ("clean", "attack"):
                polluted = copy.deepcopy(p)
                for name in ("label", "tool", "phase", "config", "session", "install", "group", "path", "receipt", "logs", "future_post", "research_scope", "authorized_override"):
                    polluted[name] = {"declared": mark, "unmodified_origin": True}
                polluted["features"]["fake.default_origin_confirmed"] = True
                self.assertEqual(self.assess(rid, polluted), expected)

    def test_masked_fields_and_quality_are_required_without_reading_undeclared_values(self):
        rid = "NW-002"; p = self.payload(rid)
        allowed = set(self.scopes[rid]["relation_required_fields"] + self.scopes[rid]["additional_risk_required_fields"])
        class Guarded(dict):
            def get(self, name, default=None):
                if name not in allowed:
                    raise AssertionError("Read undeclared evidence field: " + name)
                return super().get(name, default)
        guarded = {key: Guarded(value) for key, value in p.items()}
        self.assertEqual(self.assess(rid, guarded)["risk_candidate_eligibility"]["status"], "ELIGIBLE")
        target = self.field(rid, "user_agent")
        for key, value in (("field_status", "masked"), ("field_quality", "source_unavailable")):
            masked = copy.deepcopy(p); masked[key][target] = value
            self.assertEqual(self.assess(rid, masked)["relation_applicability"]["status"], "UNKNOWN")

    def test_old_unknown_preconditions_are_individually_classified_not_all_softened(self):
        base = v2._read_jsonl(v1.STUDY_CONFIG / "source_registry.jsonl")
        expected = {(r["rule_id"], c) for r in base for c in r["unobservable_alert_preconditions"]}
        actual = {(r["rule_id"], r["old_condition"]) for r in self.registry["precondition_reclassifications"]}
        self.assertEqual(actual, expected)
        screen = self.assess("P3-X-DPR", self.payload("P3-X-DPR"))
        self.assertEqual(screen["relation_applicability"]["status"], "UNKNOWN")
        self.assertEqual(self.assess("P3-UA-REDUCED-BROWSER", {"features": {}, "field_status": {}, "field_quality": {}})["relation_applicability"]["status"], "UNKNOWN")

    def test_both_explicit_destinations_required_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/"out"
            for generator in (v1.generate, v2.generate):
                with self.assertRaises(ValueError):
                    generator(output=out)
                with self.assertRaises(ValueError):
                    generator(config_dir=Path(tmp)/"config")
                self.assertFalse(out.exists())
            for module in (v1.__name__, v2.__name__):
                result = subprocess.run([sys.executable, "-m", module, "--output", str(out)], capture_output=True,
                                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("--config-dir", result.stderr)
                self.assertFalse(out.exists())

    def test_existing_protected_nested_or_symlink_destinations_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); out = root/"out"; cfg = root/"config"
            cfg.mkdir(); (cfg/"keep.txt").write_text("existing")
            for generator in (v1.generate, v2.generate):
                with self.assertRaises(ValueError): generator(output=out, config_dir=cfg)
                self.assertFalse(out.exists())
                with self.assertRaises(ValueError): generator(output=out, config_dir=v1.STUDY_CONFIG)
            alias = root/"alias"; alias.symlink_to(v1.STUDY_CONFIG, target_is_directory=True)
            for a,b in ((out,alias),(v1.OUTPUT,root/"new"),(out,out),(out,out/"nested")):
                with self.assertRaises(ValueError): validate_destinations(a,b)
            self.assertEqual((cfg/"keep.txt").read_text(), "existing")

    def test_isolated_v2_generation_keeps_v1_files_and_records_both_paths(self):
        protected = {p:p.read_bytes() for p in v1.STUDY_CONFIG.iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/"out"; cfg = Path(tmp)/"config"
            report = v2.generate(output=out, config_dir=cfg)
            self.assertTrue(report["all_candidate_paths_reachable"])
            generation = json.loads((out/"GENERATION.json").read_text())
            self.assertEqual(generation["output"], str(out.resolve()))
            self.assertEqual(generation["config_dir"], str(cfg.resolve()))
            self.assertEqual((out/"decision_roles.json").read_bytes(), (cfg/"decision_roles.json").read_bytes())
            with self.assertRaises(ValueError): v2.generate(output=out, config_dir=cfg)
        self.assertTrue(all(p.read_bytes()==value for p,value in protected.items()))


if __name__ == "__main__":
    unittest.main()
