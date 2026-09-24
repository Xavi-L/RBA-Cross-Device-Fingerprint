"""Focused final-study parsing, applicability, grouping and selection boundaries."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.evidence.paired244 import build_paired_evidence
from hybridguard_agent.research.mtc_closed_resource import candidates, evaluate, model_token, describe
from hybridguard_agent.tests.test_paired244_runtime import fixture


class ClosedResourceStudyTests(unittest.TestCase):
    def setUp(self):
        self.specs = {c["rule_id"]: c for c in candidates()}

    def check(self, rid, values):
        c = self.specs[rid]
        projection = {"features": dict(zip(c["dependencies"], values)),
                      "field_status": {p: "observed" for p in c["dependencies"]},
                      "field_quality": {p: "observed_value" for p in c["dependencies"]}}
        return evaluate(c, projection)

    def test_explicit_model_exact_match_not_substring_or_alias(self):
        ua = "Mozilla/5.0 (Linux; Android 13; MODEL-X Build/TQ1A; wv) Chrome/110.0"
        self.assertEqual(self.check("NW-001", ["model-x", ua])["outcome"], "MATCH")
        self.assertEqual(self.check("NW-001", ["MODEL", ua])["outcome"], "COUNTEREXAMPLE")
        self.assertEqual(self.check("NW-001", ["Marketing Name", ua])["outcome"], "COUNTEREXAMPLE")

    def test_missing_reduced_or_ambiguous_model_is_not_match(self):
        for ua, expected in [("Mozilla/5.0 (Linux; Android 10; K) Chrome/120.0", "NOT_APPLICABLE"),
                              ("Dalvik/2.1 (Linux; U; Android 13 Build/X)", "NOT_APPLICABLE"),
                              ("Android 13; vendor; MODEL-X Build/X", "UNKNOWN"),
                              ("unknown", "UNKNOWN")]:
            self.assertEqual(self.check("NW-001", ["MODEL-X", ua])["outcome"], expected)

    def test_explicit_locale_and_dalvik_scope(self):
        self.assertEqual(model_token("Android 8; en-US; MODEL-X Build/X")[0], "model-x")
        dalvik = "Dalvik/2.1.0 (Linux; U; Android 13; MODEL-X Build/TQ1A)"
        self.assertEqual(self.check("NVW-001", ["MODEL-X", dalvik])["outcome"], "MATCH")
        self.assertEqual(self.check("NVW-001", ["MODEL-X", dalvik.replace("Dalvik", "Browser")])["outcome"], "NOT_APPLICABLE")

    def test_gpu_wrapper_unknown_and_software_are_distinct(self):
        for native, web, outcome in [("Adreno (TM) 650", "ANGLE (Qualcomm, Adreno (TM) 650, OpenGL ES)", "MATCH"),
                                     ("Mali-G78", "Adreno (TM) 650", "COUNTEREXAMPLE"),
                                     ("WebKit WebGL", "WebKit WebGL", "UNKNOWN"),
                                     ("Adreno", "SwiftShader", "NOT_APPLICABLE"),
                                     ("Mali", "Mali and Adreno", "UNKNOWN")]:
            self.assertEqual(self.check("NW-005", [native, web])["outcome"], outcome)

    def test_two_dimensional_screen_fixed_tolerance_orientation_and_invalid(self):
        self.assertEqual(self.check("NW-003", ["2400x1080", "360x800", 3])["outcome"], "MATCH")
        self.assertEqual(self.check("NW-003", ["1080x2400", "360x801", 3])["outcome"], "MATCH")
        self.assertEqual(self.check("NW-003", ["1080x2400", "360x802", 3])["outcome"], "COUNTEREXAMPLE")
        for values in (["1080x2400", "360x800", 0], ["0x2400", "360x800", 3], ["1080x2400", "360x800", True]):
            self.assertEqual(self.check("NW-003", values)["outcome"], "UNKNOWN")

    def test_missing_status_nonfinite_and_quality_cannot_produce_support(self):
        for spec in self.specs.values():
            row=fixture(); projection={k:row[k] for k in ("features","field_status","field_quality")}
            for status in ("timeout", "permission_denied"):
                test=copy.deepcopy(projection);test["field_status"][spec["dependencies"][0]]=status
                self.assertEqual(evaluate(spec,test)["outcome"],"UNKNOWN")
        self.assertEqual(self.check("NW-003",["1080x2400","360x800",float("nan")])["outcome"],"UNKNOWN")

    def test_control_plane_and_non_dependency_fields_never_affect_predicate(self):
        row=fixture(); projection={k:row[k] for k in ("features","field_status","field_quality")}
        for spec in self.specs.values():
            before=evaluate(spec,projection)
            changed=copy.deepcopy(projection);changed.update(label="attack",group_id="hidden",profile={"model":"poison"})
            for p in changed["features"]:
                if p not in spec["dependencies"]:changed["features"][p]={"poison":True}
            self.assertEqual(before,evaluate(spec,changed))

    def test_unknown_groups_and_duplicate_groups_are_not_extra_support(self):
        from hybridguard_agent.scripts.run_mtc_p3_discovery import aggregate
        row={"_p2":{"group_id":"g","profile":{"manufacturer":"fixture","android_api":34}}}
        values=[{"outcome":"MATCH","reason":"fixture"},{"outcome":"UNKNOWN","reason":"missing"}]
        summary=aggregate(self.specs["NW-001"],[row,row],values)
        self.assertEqual(summary["applicable_groups"],0)
        self.assertEqual(summary["group_outcomes"],{"UNKNOWN":1})

    def test_descriptions_keep_memory_missing_and_plugin_fallback_ambiguous(self):
        from hybridguard_agent.evidence.paired244 import legacy_field_map
        row=fixture(); paths=legacy_field_map()
        row["features"][paths["web_data.device_memory"]]=0
        row["features"][paths["web_data.plugins_count"]]=0
        row["features"][paths["web_data.mime_types_count"]]=0
        result=describe(build_paired_evidence(row))
        self.assertIsNone(result["memory"])
        self.assertEqual(result["plugins"]["state"],"zero_or_api_fallback")
        self.assertEqual(result["attack_label"],"UNKNOWN")

    def test_discovery_rejection_cannot_be_rescued_by_development(self):
        from hybridguard_agent.scripts.run_mtc_closed_resource_study import execute, CONFIG
        protocol=json.loads((CONFIG/"mtc_closed_resource_protocol.v1.json").read_text())
        calls=[]
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);plan=root/"plan";plan.mkdir();out=root/"out"
            (plan/"protocol.json").write_text(json.dumps({"candidate_support_floor":protocol["candidate_support_floor"]}))
            def mocked(plan,output,split,declared,protocol):
                calls.append(split)
                if split=="development":
                    frozen=json.loads((out/"discovery_selection_FREEZE.json").read_text())
                    self.assertNotIn("NW-001",frozen["candidate_ids"])
                return {c["candidate_id"]:{"screen_decision":"INSUFFICIENT_APPLICABLE_SUPPORT" if split=="discovery" and c["candidate_id"]=="NW-001" else "PASS_RESEARCH_SCREEN"} for c in declared}
            with patch("hybridguard_agent.scripts.run_mtc_closed_resource_study.evaluate_split",side_effect=mocked):
                result=execute(plan,out)
            self.assertEqual(calls,["discovery","development"])
            self.assertNotIn("NW-001",result["admitted_rule_ids"])


class ClosedResourceRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from hybridguard_agent.rules.paired244 import load_catalog
        cls.catalog=load_catalog()

    def record(self):
        from hybridguard_agent.tests.test_legacy_rule_backlog import record, FIELDS
        row=record()
        values={"android_native_data.device_model":"MODEL-X",
                "web_data.user_agent":"Mozilla/5.0 (Linux; Android 13; MODEL-X Build/TQ1A; wv) Chrome/110.0",
                "webview_data.system_http_agent":"Dalvik/2.1.0 (Linux; U; Android 13; MODEL-X Build/TQ1A)",
                "android_native_data.native_gpu_renderer":"Adreno (TM) 650",
                "web_data.webgl_renderer":"ANGLE (Qualcomm, Adreno (TM) 650, OpenGL ES)"}
        row["features"].update({FIELDS[k]:v for k,v in values.items()})
        return row

    def run_record(self,row,view="Full244"):
        from hybridguard_agent.runtime.paired244 import analyze_paired244_record
        return analyze_paired244_record(row,input_view=view,catalog=self.catalog)

    def test_final_catalog_accounts_for_every_item_and_preserves_54_contracts(self):
        from collections import Counter
        from hybridguard_agent.rules.paired244 import load_catalog,V2_CATALOG
        from hybridguard_agent.scripts.build_paired244_catalog_v3 import build_catalog_v3
        self.assertEqual(build_catalog_v3()[0],self.catalog)
        self.assertEqual(Counter(r["status"] for r in self.catalog["rules"]),
                         {"ACTIVE":57,"DESCRIPTIVE_ONLY":11,"CLOSED_UNVERIFIABLE":11,"RETIRED":4,"MERGED":4})
        new={r["rule_id"]:r for r in self.catalog["rules"]}
        for r in load_catalog(V2_CATALOG)["rules"]:
            if r["status"]=="ACTIVE":self.assertEqual(r,new[r["rule_id"]])

    def test_three_new_checks_reach_execution_retrieval_verifier_trace(self):
        from hybridguard_agent.tests.test_paired244_runtime import by_rule
        from hybridguard_agent.tests.test_legacy_rule_backlog import FIELDS
        before=self.run_record(self.record())
        for rid in ("NW-001","NVW-001","NW-005"):
            self.assertEqual(by_rule(before)[rid]["outcome"],"MATCH")
        for alias, value, rid in [("web_data.user_agent","Android 13; OTHER Build/TQ1A","NW-001"),
                                  ("webview_data.system_http_agent","Dalvik/2.1 (Linux; U; Android 13; OTHER Build/TQ1A)","NVW-001"),
                                  ("web_data.webgl_renderer","Mali-G78","NW-005")]:
            row=self.record();row["features"][FIELDS[alias]]=value
            output=self.run_record(row)
            self.assertEqual(by_rule(output)[rid]["outcome"],"COUNTEREXAMPLE")
            self.assertIn(rid,output["decision"]["relation_deviation_rule_ids"])
            self.assertIn(FIELDS[alias],output["context_pack"]["query_fields"])
            self.assertTrue(output["decision_trace"]["verification"]["valid"])
            self.assertEqual(output["decision"]["attack_classification"],"NOT_EVALUATED")

    def test_inactive_final_dispositions_are_not_success_or_pending_or_citations(self):
        from hybridguard_agent.tests.test_paired244_runtime import by_rule
        output=self.run_record(self.record());rules=by_rule(output);decision=output["decision"]
        self.assertEqual(rules["NW-003"]["outcome"],"DESCRIPTIVE_ONLY")
        self.assertEqual(rules["OFFDER-KEY-001"]["outcome"],"CLOSED_UNVERIFIABLE")
        self.assertFalse(decision["pending_data_rule_ids"] or decision["pending_research_rule_ids"])
        self.assertFalse(decision["collection_requested"] or decision["research_backlog_open"])
        self.assertFalse(decision["catalog_fully_assessed"])
        self.assertTrue(decision["catalog_dispositions_complete"])
        self.assertEqual(len(output["context_pack"]["cards"]),57)
        self.assertNotIn("OFFDER-KEY-001",output["decision_trace"]["citations"]["rule_ids"])
        self.assertNotIn("next_action",rules["TOL-002"])

    def test_missing_source_and_reduced_ua_remain_unassessed(self):
        from hybridguard_agent.tests.test_paired244_runtime import by_rule
        from hybridguard_agent.tests.test_legacy_rule_backlog import FIELDS
        row=self.record();row["field_status"][FIELDS["android_native_data.native_gpu_renderer"]]="timeout"
        output=self.run_record(row)
        self.assertEqual(by_rule(output)["NW-005"]["outcome"],"NOT_EVALUATED")
        self.assertEqual(by_rule(output)["NW-005"]["used_fields"],[])
        row=self.record();row["features"][FIELDS["web_data.user_agent"]]="Mozilla/5.0 (Linux; Android 10; K) Chrome/120"
        self.assertEqual(by_rule(self.run_record(row))["NW-001"]["outcome"],"NOT_APPLICABLE")

    def test_browser_only_cannot_read_new_app_predicates(self):
        from hybridguard_agent.tests.test_paired244_runtime import by_rule
        output=self.run_record(self.record(),"Browser67")
        for rid in ("NW-001","NVW-001","NW-005"):
            self.assertEqual(by_rule(output)[rid]["outcome"],"NOT_EVALUATED")
            self.assertEqual(by_rule(output)[rid]["used_fields"],[])

    def test_runtime_driver_rejects_reserved_before_reading(self):
        from hybridguard_agent.scripts.run_mtc_closed_resource_runtime import execute
        with tempfile.TemporaryDirectory() as name:
            p=Path(name)
            with self.assertRaisesRegex(ValueError,"reserved stays locked"):
                execute(p/"missing",p/"missing",p/"out",("reserved_validation",))
            self.assertFalse((p/"out").exists())

    def test_runtime_failure_remains_in_results_and_summary(self):
        from hybridguard_agent.scripts.run_mtc_closed_resource_runtime import execute
        with tempfile.TemporaryDirectory() as name:
            p=Path(name);study=p/"study";study.mkdir();plan=p/"plan"
            (study/"summary.json").write_text(json.dumps({"status":"COMPLETE","plan_dir":str(plan),"admitted_rule_ids":["NW-001","NVW-001","NW-005"]}))
            (study/"discovery_results.jsonl").write_text("")
            with patch("hybridguard_agent.scripts.run_mtc_closed_resource_runtime.load_split_records",return_value=[{"sample_id":"bad","record_schema_version":"invalid"}]):
                with self.assertRaisesRegex(RuntimeError,"failures persisted"):
                    execute(plan,study,p/"out",("discovery",))
            result=json.loads((p/"out/summary.json").read_text())
            self.assertEqual(result["status"],"FAILED")
            self.assertEqual(len(result["failures"]),2)
            self.assertEqual(result["views"],[])


if __name__ == "__main__":
    unittest.main()
