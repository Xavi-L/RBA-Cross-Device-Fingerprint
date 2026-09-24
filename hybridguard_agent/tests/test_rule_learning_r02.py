"""Focused R02 semantic and leakage checks. All values here are synthetic."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from hybridguard_agent.research.rule_learning import matrix as m
from hybridguard_agent.research.rule_learning.build_matrix import contracts, ROOT, SOURCE_FILES
from hybridguard_agent.research.rule_learning.fold_data import FoldData, FoldBatch, TrainQuantiles, FIT_OPERATIONS

UA = "Mozilla/5.0 (Linux; Android 14; ModelX Build/UP1A; wv) AppleWebKit/537.36 Chrome/120.0 Mobile"
SYSTEM = "Dalvik/2.1.0 (Linux; U; Android 14; ModelX Build/UP1A)"


def fixture(candidates):
    specs = {s["field"]: s for c in candidates for s in c["dependency_schema"]}
    special = {"os_version": "14", "device_model": "ModelX", "user_agent": UA,
               "system_http_agent": SYSTEM, "default_ua_native": UA, "settings_user_agent": UA,
               "platform": "Linux aarch64", "native_gpu_renderer": "Adreno 660", "egl_renderer": "Adreno 660",
               "webgl_renderer": "Adreno 660", "webgl_vendor": "Qualcomm", "screen_resolution_physical": "1080x1920",
               "screen_resolution_logical": "540x960", "device_pixel_ratio": 2,
               "sensor_type_list": list(range(1, 21)), "sensor_total_count": 20,
               "sensor_name_count": 20, "sensor_vendor_count": 20,
               "webview_provider_version": "120.0.1.2", "webview_provider_major": 120,
               "app_package_name": "com.example.hybridguard.featureapp", "app_version_code": 9,
               "app_version_name": "1.6.2-expanded-v2.2-mtc", "installer_package": "manual",
               "battery_level_pct": 99, "timezone_offset": 0,
               "build_fingerprint": "test-keys", "build_tags": "test-keys", "build_type": "userdebug"}
    values = {p: special.get(p.rsplit(".", 1)[1], {"number": 4, "boolean": True, "string": "known", "array": []}[s["type"]]) for p,s in specs.items()}
    return {"record_schema_version": "hybridguard-mtc-observation-v2", "adapter_version": "app177-triplet-adapter-v1",
            "features": values, "field_status": {p: "observed" for p in values}, "field_quality": {p: "observed_value" for p in values}}


class MatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.candidates, _, _, _ = contracts()
        cls.cby = {c["rule_id"]: c for c in cls.candidates}
        cls.catalog = {r["rule_id"]: r for r in json.loads((ROOT / SOURCE_FILES[-2]).read_text())["rules"]}

    def setUp(self):
        self.payload = fixture(self.candidates)

    def set_value(self, leaf, value):
        for p in self.payload["features"]:
            if p.rsplit(".",1)[1] == leaf:
                self.payload["features"][p] = value

    def atom(self, rid, **kw):
        return m.extract_atom(self.cby[rid], self.catalog[rid], self.payload, **kw)

    def cache(self, rid):
        c = self.cby[rid]
        raw = m.original_relation(self.catalog[rid], self.payload)
        event = {"rule_id": rid, "method": "final_v3_v2", "verification_valid": True,
                 "original_result": {**raw, "predicate": c["predicate"], "rule_version": c["predicate_version"], "required_fields": c["dependencies"]},
                 "field_states": {s["field"]: m.field_state(self.payload,s) for s in c["dependency_schema"]},
                 "risk_candidate_eligibility": {"status": "NOT_ELIGIBLE"}, "relation_applicability": {"status": "UNKNOWN"}}
        return event, {"input": True, "catalog_parameters": True, "implementation_version": True}

    def test_hand_expected_all_defined_conditions_and_original_predicate_agreement(self):
        false = {"NW-002", "NVW-002", "NW-006", "NW-007", "WVWEB-004"}
        for c in self.candidates:
            with self.subTest(rule=c["rule_id"]):
                cell = self.atom(c["rule_id"])
                if not c["measurement"]["defined"]:
                    self.assertEqual(cell["evaluation_status"], "NOT_REQUESTED")
                    self.assertIsNone(cell["state"])
                else:
                    expected = "F" if c["rule_id"] in false else "T"
                    self.assertEqual(cell["state"], expected, cell)
                    raw = m.original_relation(self.catalog[c["rule_id"]], self.payload)
                    self.assertEqual(m.mapped_state(c, raw["outcome"]), expected)

    def test_os_opposite_conditions_canonical_same_deviation(self):
        self.set_value("os_version", "13")
        for a,b in [("NW-002","OFFDER-OS-001"),("NVW-002","OFFDER-OS-002")]:
            self.assertEqual(self.atom(a)["state"], "T")
            self.assertEqual(self.atom(b)["state"], "F")
        cells={c["atom_id"]:self.atom(c["rule_id"]) for c in self.candidates}
        merged=m.canonical_core(self.candidates,cells)
        pair=[c for c in merged if c["aliases"]==["NW-002","OFFDER-OS-001"]][0]
        self.assertEqual(pair["state"],"T")
        self.assertEqual(pair["source_groups"],["E","O_u"])

    def test_alias_source_subset_keeps_condition_and_only_allowed_alias(self):
        cells={c["atom_id"]:self.atom(c["rule_id"]) for c in self.candidates}
        pair=[c for c in m.canonical_core(self.candidates,cells,{"O_u"}) if c["atom_id"]=="DEVIATION:NW-002"][0]
        self.assertEqual(pair["aliases"],["OFFDER-OS-001"])
        self.assertEqual(pair["state"],"F")

    def test_alias_domain_conflict_is_failed_not_preferred_value(self):
        cells={c["atom_id"]:self.atom(c["rule_id"]) for c in self.candidates}
        cells["CAT:OFFDER-OS-001"].update(state="U",available=False,reason="different-domain")
        pair=[c for c in m.canonical_core(self.candidates,cells) if c["atom_id"]=="DEVIATION:NW-002"][0]
        self.assertEqual(pair["evaluation_status"],"FAILED")
        self.assertIsNone(pair["state"])

    def test_negation_unknown_and_failure_distinct(self):
        self.assertEqual([m.negate(s) for s in ("T","F","U")],["F","T","U"])
        with self.assertRaises(ValueError):m.negate(None)

    def test_reuse_ignores_old_attribution_and_risk_vetoes(self):
        e,p=self.cache("NW-002")
        with patch.object(m,"original_relation",side_effect=AssertionError("must reuse")):
            c=self.atom("NW-002",cached=e,cache_proof=p)
        self.assertTrue(c["cache_lineage"]["reuse"])
        self.assertEqual(c["state"],"F")

    def test_cache_input_parameter_source_version_mismatch_reextracts(self):
        for k in ("input","catalog_parameters","implementation_version"):
            e,p=self.cache("NW-002");p[k]=False
            c=self.atom("NW-002",cached=e,cache_proof=p)
            self.assertFalse(c["cache_lineage"]["reuse"])
            self.assertEqual(c["cache_lineage"]["status"],"CONTRACT_MISMATCH")
            self.assertEqual(c["state"],"F")
        e,p=self.cache("NW-002");e["original_result"]["rule_version"]="wrong"
        self.assertEqual(self.atom("NW-002",cached=e,cache_proof=p)["cache_lineage"]["status"],"CONTRACT_MISMATCH")

    def test_missing_cache_and_unexecuted_are_not_U(self):
        c=self.atom("NW-002",execute_missing=False)
        self.assertIsNone(c["state"]);self.assertEqual(c["evaluation_status"],"NOT_REQUESTED")
        e,p=self.cache("NW-002");e["original_result"]["outcome"]="NOT_EVALUATED"
        c=self.atom("NW-002",cached=e,cache_proof=p,execute_missing=False)
        self.assertEqual(c["evaluation_status"],"NOT_REQUESTED")
        self.assertEqual(c["cache_lineage"]["status"],"UNEXECUTED_WITH_AVAILABLE_OPERANDS")
        c=self.atom("NW-002",cached=e,cache_proof=p)
        self.assertEqual(c["state"],"F")
        self.assertEqual(c["original_outcome"],"NOT_EVALUATED")

    def test_cached_unknown_outcome_is_failed(self):
        e,p=self.cache("NW-002");e["original_result"]["outcome"]="INVENTED"
        c=self.atom("NW-002",cached=e,cache_proof=p)
        self.assertEqual(c["evaluation_status"],"FAILED");self.assertIsNone(c["state"])

    def test_reduced_ua_rejects_old_true_or_false(self):
        e,p=self.cache("NW-002")
        self.set_value("user_agent","Mozilla/5.0 (Linux; Android 10; K) Chrome/120.0 Mobile")
        for rid in ("NW-002","OFFDER-OS-001"):
            c=self.atom(rid,cached=e,cache_proof=p)
            self.assertEqual(c["state"],"U");self.assertFalse(c["cache_lineage"]["reuse"])

    def test_no_android_token_is_unknown_not_version_conflict(self):
        self.set_value("user_agent","Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0")
        self.assertEqual(self.atom("NW-002")["state"],"U")
        self.assertEqual(self.atom("OFFDER-UA-001")["state"],"F")

    def test_parser_ambiguity_nonpositive_and_dalvik_scope(self):
        for v in ("0","preview-14","14 or 13","140"):
            self.set_value("os_version",v)
            self.assertEqual(self.atom("NW-002")["state"],"U")
        self.set_value("os_version","14")
        self.set_value("user_agent","Android 14 Android 13")
        self.assertEqual(self.atom("NW-002")["state"],"U")
        self.set_value("system_http_agent",UA)
        self.assertEqual(self.atom("NVW-002")["state"],"U")

    def test_model_tokens_and_software_gpu_unavailable(self):
        for ua in ("Mozilla (Linux; Android 10; K)","Mozilla (Linux; Android 14; X; Y Build/ZZ)"):
            self.set_value("user_agent",ua)
            self.assertEqual(self.atom("NW-001")["state"],"U")
        self.set_value("webgl_renderer","SwiftShader")
        self.assertEqual(self.atom("NW-005")["state"],"U")
        self.set_value("webgl_renderer","Adreno Mali")
        self.assertEqual(self.atom("NW-005")["state"],"U")

    def test_screen_snapshot_deviation_does_not_require_capture_or_window_proof(self):
        self.set_value("screen_resolution_logical","600x1000")
        c=self.atom("P3-SCREEN-APP")
        self.assertEqual(c["state"],"F")
        self.set_value("device_pixel_ratio",0)
        self.assertEqual(self.atom("P3-SCREEN-APP")["state"],"U")

    def test_ua_literal_trimmed_vs_exact_not_aliases(self):
        self.set_value("default_ua_native"," "+UA+" ")
        self.assertEqual(self.atom("OFFDER-UA-002")["state"],"T")
        self.assertEqual(self.atom("P3-UA-DEFAULT")["state"],"F")

    def test_missing_browser_never_imputed(self):
        self.payload=m.mask(self.payload,["native84","host26","app_web67"])
        for c in self.candidates:
            if "browser67" in c["observation_surfaces"]:
                result=self.atom(c["rule_id"])
                self.assertEqual(result["state"],"U");self.assertEqual(result["reason"],"MISSING_SURFACE")

    def test_invalid_measurement_vs_invalid_envelope_vs_execution_exception(self):
        self.set_value("max_touch_points",True)
        self.assertEqual(self.atom("NW-007")["state"],"U")
        self.payload["phase"]="attack"
        self.assertEqual(self.atom("NW-002")["evaluation_status"],"FAILED")
        del self.payload["phase"]
        with patch.object(m,"original_relation",side_effect=RuntimeError("synthetic")):
            c=self.atom("NW-002")
        self.assertEqual(c["evaluation_status"],"FAILED");self.assertIsNone(c["state"])

    def test_field_states_quality_placeholders_and_false_zero(self):
        p=self.cby["CORE-002"]["dependencies"][0]
        self.payload["features"][p]=False
        self.assertEqual(self.atom("CORE-002")["state"],"F")
        self.payload["field_status"][p]="runtime_error"
        self.assertEqual(self.atom("CORE-002")["state"],"U")
        self.set_value("max_touch_points",0)
        self.assertEqual(self.atom("NW-007")["state"],"T")
        self.set_value("user_agent","unknown")
        self.assertEqual(self.atom("NW-002")["state"],"U")

    def test_sensor_false_antecedent_empty_list_and_wrong_element(self):
        self.set_value("has_accelerometer",False)
        self.assertEqual(self.atom("P3-SENSOR-ACCELEROMETER")["state"],"U")
        self.set_value("sensor_type_list",[])
        self.assertEqual(self.atom("P3-SENSOR-TYPE-ORDER")["state"],"T")
        self.set_value("has_accelerometer",True)
        self.assertEqual(self.atom("P3-SENSOR-ACCELEROMETER")["state"],"F")
        self.set_value("sensor_type_list",[True,2])
        self.assertEqual(self.atom("P3-SENSOR-TYPE-ORDER")["state"],"U")

    def test_side_labels_and_non_dependency_changes_cannot_affect_transform(self):
        side={"phase":"attack","label":1,"tool":"A","config":"x","triplet":"future"}
        before=self.atom("NW-002")
        side.update(phase="clean_post",label=0,tool="B",config="y",triplet="past")
        self.set_value("is_adb_enabled",False)
        self.assertEqual(before,self.atom("NW-002"))

    def test_control_single_surface_mask_and_numeric_unfitted(self):
        spec={"field":self.cby["NW-007"]["dependencies"][0],"type":"number","surface":"app_web67","encoder":"TRAIN_QUANTILE_LE"}
        before=m.control_input(m.mask(self.payload,["app_web67"]),spec)
        self.set_value("os_version","12")
        self.assertEqual(before,m.control_input(m.mask(self.payload,["app_web67"]),spec))
        self.assertEqual(before["value"],4)
        p="app.web_data.navigator_layer.hardware_concurrency"
        self.payload["features"][p]=0;self.payload["field_status"][p]="observed";self.payload["field_quality"][p]="observed_value"
        self.assertFalse(m.control_input(self.payload,{**spec,"field":p})["available"])


class FoldTests(unittest.TestCase):
    def access(self, test_value=100, *, synthetic=True):
        ids=["fixture-"+str(i) for i in range(6)]
        membership={"fold_id":"synthetic-fold", "train":ids[:4],"outer_test":ids[4:5],"descriptive_train_side":ids[5:],"descriptive_test_side":[]}
        features={i:{"x":{"value":v,"available":True,"evaluation_status":"OK"}} for i,v in zip(ids,[0,10,20,30,test_value,9999])}
        evaluation={i:{"supervised_label":None if i==ids[5] else n%2} for n,i in enumerate(ids)}
        return FoldData(membership,features,evaluation,synthetic=synthetic)

    def test_test_and_descriptive_fit_denied_for_all_operations(self):
        a=self.access()
        for op in FIT_OPERATIONS:
            for part in ("outer_test","descriptive_train_side","descriptive_test_side"):
                with self.assertRaises(PermissionError):a.assert_fit(a.batch(part),op)

    def test_real_train_fit_denied_by_R02_authorization(self):
        a=self.access(synthetic=False)
        with self.assertRaises(PermissionError):TrainQuantiles("x").fit(a,a.batch("train"))

    def test_identical_content_distinct_stage_ids_not_deduplicated(self):
        a=self.access()
        first,second=a.parts['train'][:2]
        a._features[second]=copy.deepcopy(a._features[first])
        batch=a.batch('train')
        self.assertEqual(len(batch.ids),4)
        self.assertEqual(batch.records[0],batch.records[1])
        self.assertNotEqual(batch.ids[0],batch.ids[1])

    def test_exact_train_membership_required_and_copy_does_not_mutate_source(self):
        a=self.access(); b=a.batch("train")
        forged=FoldBatch(a.fold_id,"train",b.ids[:2],b.records[:2])
        with self.assertRaises(PermissionError):a.assert_fit(forged,"support")
        b.records[0]["x"]["value"]=999
        with self.assertRaises(PermissionError):a.assert_fit(b,"numeric_thresholds")

    def test_hand_quantiles_and_test_extremes_do_not_change_fit(self):
        a=self.access();t=TrainQuantiles("x").fit(a,a.batch("train"))
        self.assertEqual(t.thresholds,(7.5,15.0,22.5))
        b=self.access(-10000);u=TrainQuantiles("x").fit(b,b.batch("train"))
        self.assertEqual(t.thresholds,u.thresholds)
        self.assertEqual(t.transform(a,a.batch("outer_test"))[0]["states"],["F"]*3)
        self.assertEqual(u.transform(b,b.batch("outer_test"))[0]["states"],["T"]*3)

    def test_transform_requires_own_frozen_fit(self):
        a=self.access();t=TrainQuantiles("x")
        with self.assertRaises(PermissionError):t.transform(a,a.batch("outer_test"))
        t.fit(a,a.batch("train"))
        with self.assertRaises(PermissionError):t.fit(a,a.batch("train"))
        b=self.access();b.fold_id="other"
        with self.assertRaises(PermissionError):t.transform(b,b.batch("outer_test"))

    def test_label_permutation_leaves_feature_batches_and_fixed_transform_unchanged(self):
        a=self.access(); b=self.access()
        for record in b._evaluation.values():
            if record['supervised_label'] is not None:
                record['supervised_label']=1-record['supervised_label']
        self.assertEqual(a.batch('train'),b.batch('train'))
        ta=TrainQuantiles('x').fit(a,a.batch('train'))
        tb=TrainQuantiles('x').fit(b,b.batch('train'))
        self.assertEqual(ta.thresholds,tb.thresholds)
        self.assertEqual(ta.transform(a,a.batch('outer_test')),tb.transform(b,b.batch('outer_test')))

    def test_transform_keeps_unavailable_and_failure_separate(self):
        a=self.access();t=TrainQuantiles('x').fit(a,a.batch('train'))
        oid=a.parts['outer_test'][0]
        a._features[oid]['x'].update(value=None,available=False)
        self.assertEqual(t.transform(a,a.batch('outer_test'))[0],{'states':['U']*3,'evaluation_status':'OK'})
        a._features[oid]['x']['evaluation_status']='FAILED'
        self.assertEqual(t.transform(a,a.batch('outer_test'))[0],{'states':[None]*3,'evaluation_status':'FAILED'})


if __name__ == "__main__":
    unittest.main()
