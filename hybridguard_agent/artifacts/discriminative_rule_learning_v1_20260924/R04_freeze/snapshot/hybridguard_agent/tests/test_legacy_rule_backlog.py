"""Focused contracts for reviewed legacy observations, not attack effectiveness."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.evidence.paired244 import legacy_field_map
from hybridguard_agent.rules.paired244 import CONFIG, LEGACY_CATALOG, V2_CATALOG, load_catalog
from hybridguard_agent.runtime.paired244 import analyze_paired244_record, paired_runtime_readiness
from hybridguard_agent.runtime.service import analyze_payload
from hybridguard_agent.tests.test_paired244_runtime import fixture, by_rule
from hybridguard_agent.verification.paired244 import verify_paired_output

FIELDS = legacy_field_map()
NEW_IDS = {"NVW-003", "NVW-004", "WVWEB-002", "TOL-001", "OFFDER-PACKAGE-001", "OFFDER-NET-001"}


def record():
    row = fixture()
    for alias, value in {
        "webview_data.app_package_name": "com.example.hybridguard.featureapp",
        "webview_data.app_version_code": 11,
        "webview_data.app_version_name": "1.6.4-expanded-v2.2-mtc-https",
        "webview_data.installer_package": "manual",
        "android_native_data.os_api_level": 34,
        "android_native_data.active_network_present": True,
        "android_native_data.active_transport_types": ["wifi"],
        "android_native_data.has_wifi_transport": True,
    }.items():
        row["features"][FIELDS[alias]] = value
    return row


class LegacyBacklogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(V2_CATALOG)

    def run_record(self, row, view="Full244"):
        return analyze_paired244_record(row, input_view=view, catalog=self.catalog)

    def test_complete_accounting_reproducible_build_and_original_contracts_unchanged(self):
        from hybridguard_agent.scripts.build_paired244_catalog_v2 import build_catalog_v2
        built, browser = build_catalog_v2()
        self.assertEqual(built, self.catalog)
        self.assertEqual(browser, json.loads((CONFIG / "paired244_browser_relations.v2.json").read_text()))
        ready = paired_runtime_readiness(catalog=self.catalog)
        self.assertEqual(ready["entry_status_counts"], {"NEEDS_RESEARCH": 17, "ACTIVE": 54, "RETIRED": 4, "MERGED": 4, "NEEDS_DATA": 8})
        current = {r["rule_id"]: r for r in self.catalog["rules"]}
        for old in load_catalog(LEGACY_CATALOG)["rules"]:
            if old["status"] == "ACTIVE":
                self.assertEqual(old, current[old["rule_id"]])
        review = json.loads((CONFIG / "paired244_legacy_review.v1.json").read_text())
        self.assertEqual(len(review["entries"]), 37)
        self.assertEqual({r["rule_id"] for r in review["entries"] if r["status"] == "ACTIVE"}, NEW_IDS)

    def test_exact_package_policy_not_prefix_or_attestation(self):
        for package, expected in [("com.example.hybridguard.featureapp", "MATCH"),
                                   ("com.example.hybridguard.featureapp.evil", "POLICY_MISMATCH"),
                                   ("com.example.hybridguard.other", "POLICY_MISMATCH"),
                                   ("", "UNKNOWN")]:
            row = record(); row["features"][FIELDS["webview_data.app_package_name"]] = package
            output = self.run_record(row)
            self.assertEqual(by_rule(output)["NVW-003"]["outcome"], expected)
            self.assertEqual(output["decision"]["attack_classification"], "NOT_EVALUATED")
            self.assertNotIn("NVW-003", output["decision"]["relation_deviation_rule_ids"])
            if expected == "POLICY_MISMATCH":
                self.assertIn("NVW-003", output["decision"]["deployment_policy_mismatch_rule_ids"])
                self.assertEqual(output["decision"]["deployment_policy_evidence_families"], ["deployment_identity"])

    def test_release_code_and_name_pairing_and_numeric_edges(self):
        cases = [(9, "1.6.2-expanded-v2.2-mtc", "MATCH"),
                 (11.0, "1.6.4-expanded-v2.2-mtc-https", "MATCH"),
                 (9, "1.6.4-expanded-v2.2-mtc-https", "POLICY_MISMATCH"),
                 (12, "future-release", "POLICY_MISMATCH"),
                 (0, "unknown", "UNKNOWN"), (11.5, "future-release", "UNKNOWN"),
                 (True, "1.6.4-expanded-v2.2-mtc-https", "NOT_EVALUATED")]
        for code, name, expected in cases:
            with self.subTest(code=code, name=name):
                row=record(); row["features"][FIELDS["webview_data.app_version_code"]]=code
                row["features"][FIELDS["webview_data.app_version_name"]]=name
                self.assertEqual(by_rule(self.run_record(row))["OFFDER-PACKAGE-001"]["outcome"], expected)

    def test_installer_null_fallback_and_error_never_trust_or_attack(self):
        for value, outcome, reason in [("manual", "CONTEXT_OBSERVED", "null_fallback"),
                                       ("com.android.vending", "CONTEXT_OBSERVED", "not_proof_of_trust"),
                                       ("unknown", "UNKNOWN", "collector_error"),
                                       ("", "UNKNOWN", "collector_error")]:
            row=record(); row["features"][FIELDS["webview_data.installer_package"]]=value
            result=by_rule(self.run_record(row))["NVW-004"]
            self.assertEqual(result["outcome"],outcome); self.assertIn(reason,result["reason"])

    def test_ua_tokens_are_context_including_absence_and_custom_ua(self):
        for value, marker in [("Mozilla/5.0 (Linux; Android 14; X; wv) Version/4.0", "both"),
                              ("custom client", "none"), ("Something; wv)", "wv"),
                              ("Version/4.0", "version"), ("Version/4.01", "none")]:
            row=record(); row["features"][FIELDS["web_data.user_agent"]]=value
            result=by_rule(self.run_record(row))["WVWEB-002"]
            self.assertEqual(result["outcome"], "CONTEXT_OBSERVED")
            self.assertIn("ua_markers_"+marker+"_", result["reason"])

    def test_development_flags_are_context_and_false_is_not_missing(self):
        row=record()
        first=by_rule(self.run_record(row))["TOL-001"]
        self.assertEqual(first["outcome"],"CONTEXT_OBSERVED")
        self.assertIn("flags_none_",first["reason"])
        row["features"][FIELDS["android_native_data.is_adb_enabled"]]=True
        second=by_rule(self.run_record(row))["TOL-001"]
        self.assertIn("flags_adb_",second["reason"])
        self.assertEqual(second["outcome"],"CONTEXT_OBSERVED")

    def test_network_api_gate_vpn_disconnected_and_malformed_array(self):
        row=record(); row["features"][FIELDS["android_native_data.os_api_level"]]=22
        self.assertEqual(by_rule(self.run_record(row))["OFFDER-NET-001"]["outcome"], "NOT_APPLICABLE")
        row=record(); row["features"][FIELDS["android_native_data.has_vpn_transport"]]=True
        result=by_rule(self.run_record(row))["OFFDER-NET-001"]
        self.assertEqual(result["outcome"],"CONTEXT_OBSERVED"); self.assertIn("vpn_transport_observed",result["reason"])
        row["features"][FIELDS["android_native_data.active_network_present"]]=False
        self.assertIn("not_proof_of_no_vpn",by_rule(self.run_record(row))["OFFDER-NET-001"]["reason"])
        row["features"][FIELDS["android_native_data.active_transport_types"]]=[{}]
        self.assertEqual(by_rule(self.run_record(row))["OFFDER-NET-001"]["outcome"],"UNKNOWN")

    def test_missing_or_bad_status_blocks_each_new_check_and_references(self):
        for rule in self.catalog["rules"]:
            if rule["rule_id"] not in NEW_IDS:continue
            for status in ("timeout", "permission_denied", "unsupported_by_os"):
                row=record(); row["field_status"][rule["dependencies"][0]]=status
                result=by_rule(self.run_record(row))[rule["rule_id"]]
                self.assertEqual(result["outcome"],"NOT_EVALUATED")
                self.assertEqual(result["used_fields"],[])

    def test_browser_only_cannot_read_app_and_app_masks_hidden_browser(self):
        row=record(); browser=self.run_record(row,"Browser67")
        for rid in NEW_IDS:self.assertEqual(by_rule(browser)[rid]["outcome"],"NOT_EVALUATED")
        before=self.run_record(row,"App177")
        for section in ("features","field_status","field_quality"):
            for p in row[section]:
                if p.startswith("browser."):row[section][p]={"hidden":"poison"}
        row["pair"]={}; row["browser"]={}
        self.assertEqual(before,self.run_record(row,"App177"))

    def test_pending_merged_retired_are_never_retrieved_or_counted_pass(self):
        output=self.run_record(record()); results=by_rule(output)
        self.assertEqual(results["TOL-004"]["outcome"],"DISABLED")
        self.assertEqual(results["SCENE-004"]["outcome"],"DISABLED")
        self.assertEqual(results["TOL-002"]["outcome"],"MERGED")
        self.assertEqual(results["NW-003"]["outcome"],"PENDING_RESEARCH")
        self.assertEqual(results["OFFDER-KEY-001"]["outcome"],"PENDING_DATA")
        self.assertEqual(len(output["context_pack"]["cards"]),54)
        inactive={r["rule_id"] for r in self.catalog["rules"] if r["status"]!="ACTIVE"}
        self.assertFalse(inactive & set(output["decision_trace"]["citations"]["rule_ids"]))
        self.assertFalse(output["decision"]["catalog_fully_assessed"])

    def test_policy_parameters_are_in_cards_and_forgery_is_rejected(self):
        original=self.run_record(record())
        for change in ("outcome","card"):
            output=copy.deepcopy(original)
            if change=="outcome":by_rule(output)["NVW-003"]["outcome"]="POLICY_MISMATCH"
            else:
                card=next(c for c in output["context_pack"]["cards"] if c["rule_id"]=="NVW-003")
                self.assertEqual(card["parameters"]["allowed_packages"],["com.example.hybridguard.featureapp"])
                card["parameters"]["allowed_packages"]=["forged"]
            verified=verify_paired_output(output["evidence_bundle"],output["rule_execution"],output["context_pack"],output["decision"],self.catalog)
            self.assertFalse(verified["valid"])

    def test_default_service_uses_latest_without_control_plane_metadata(self):
        row=record(); before=analyze_payload(row)
        self.assertEqual(before["rule_execution"]["catalog_version"],load_catalog()["catalog_version"])
        row.update(sample_id="hidden",label="attack",profile={"model":"hidden"},_p2={"split":"reserved_validation"})
        self.assertEqual(before,analyze_payload(row))

    def test_driver_rejects_reserved_and_duplicates_before_creating_output(self):
        from hybridguard_agent.scripts.run_mtc_rule_backlog import execute
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            for splits in (("reserved_validation",),("discovery","discovery")):
                with self.assertRaisesRegex(ValueError,"reserved stays locked"):
                    execute(root/"missing",root/"out",splits)
                self.assertFalse((root/"out").exists())

    def test_driver_persists_failures_instead_of_success(self):
        from hybridguard_agent.scripts.run_mtc_rule_backlog import execute
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            with patch("hybridguard_agent.scripts.run_mtc_rule_backlog.load_split_records",
                       return_value=[{"sample_id":"bad-fixture","record_schema_version":"unsupported"}]):
                with self.assertRaisesRegex(RuntimeError,"failures persisted"):
                    execute(root/"plan",root/"out",("discovery",))
            summary=json.loads((root/"out/summary.json").read_text())
            self.assertEqual(summary["status"],"FAILED")
            self.assertEqual(len(summary["runtime_failures"]),2)
            self.assertEqual(summary["views"],[])


if __name__ == "__main__":
    unittest.main()
