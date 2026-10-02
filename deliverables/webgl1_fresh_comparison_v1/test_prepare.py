"""Focused admission, exact membership and unavailable-input boundary tests."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fresh_prepare", HERE / "prepare.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def payload(values):
    return {"web_data": {"fixture_layer": values}, "collection_status": {
        "fields": {"web_data.fixture_layer." + k: "observed" for k in values}}}


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        registry = json.loads((HERE / "CONFIGURATIONS.json").read_text())
        self.config = next(c for c in registry if c["id"] == "stealth_webgl_pair_v1")
        self.sids = ["pre", "attack", "post"]
        normal = {"webgl_vendor": "normal vendor", "webgl_renderer": "normal renderer"}
        active = {prepare.PROFILE_FIELDS[k]: v for k, v in self.config["profile"].items()}
        self.payloads = [payload(normal), payload(active), payload(copy.deepcopy(normal))]
        self.receipt = {"status": "MEASURED", "configId": self.config["configId"],
                        "configurationId": self.config["id"], "measuredSessionIds": ["attack"],
                        "injected": self.config["profile"], "declaredObservableFields": self.config["observableFields"],
                        "declaredStealthEvasions": self.config["stealthEvasions"]}

    def audit(self):
        return prepare.audit_triplet(self.config, self.payloads, self.receipt, self.sids)

    def test_effect_labels_do_not_use_new_candidate_or_observation(self):
        first = self.audit()
        self.assertEqual(first["status"], "PASS")
        for i, row in enumerate(self.payloads):
            row["collection_observations"] = {"webgl_parameter": {"state": ("T", "U", "F")[i],
                                                                      "read_status": "runtime_error"}}
            row["supervised_label"] = 1 - int(i == 1)
        with patch.object(prepare.webgl, "compile_payload", side_effect=AssertionError("candidate must not label")):
            self.assertEqual(self.audit(), first)

    def test_no_effect_is_not_attack_evidence_even_with_matching_profile(self):
        self.payloads[0] = copy.deepcopy(self.payloads[1])
        self.payloads[2] = copy.deepcopy(self.payloads[1])
        result = self.audit()
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertFalse(result["declared_effect_present"])

    def test_every_declared_field_must_restore_and_be_observed(self):
        self.payloads[2]["web_data"]["fixture_layer"]["webgl_renderer"] = "still changed"
        self.assertFalse(self.audit()["declared_fields_restored"])
        self.payloads[2] = copy.deepcopy(self.payloads[0])
        self.payloads[1]["collection_status"]["fields"]["web_data.fixture_layer.webgl_vendor"] = "runtime_error"
        self.assertEqual(self.audit()["status"], "REVIEW_REQUIRED")
        self.assertFalse(self.audit()["declared_fields_observed"])

    def test_session_bound_execution_and_actual_profile_required(self):
        self.receipt["measuredSessionIds"] = ["unrelated"]
        self.assertFalse(self.audit()["execution_receipt_valid"])
        self.receipt["measuredSessionIds"] = ["attack"]
        self.payloads[1]["web_data"]["fixture_layer"]["webgl_vendor"] = "different spoof"
        self.assertFalse(self.audit()["active_profile_observed"])

    def test_typed_values_screen_tolerance_and_missing_triplet(self):
        self.assertFalse(prepare.same(True, 1))
        self.assertFalse(prepare.same(False, 0))
        self.assertFalse(prepare.same(None, None))
        self.assertFalse(prepare.same(float("nan"), float("nan")))
        self.assertTrue(prepare.same(393.1, 393, 1))
        self.assertFalse(prepare.same(395, 393, 1))
        self.payloads[2] = None
        self.assertEqual(self.audit()["status"], "INCOMPLETE")

    def test_cdp_rollback_needs_both_receipt_and_paired_raw_restoration(self):
        registry = json.loads((HERE / "CONFIGURATIONS.json").read_text())
        cfg = next(c for c in registry if c["id"] == "cdp_timezone_only_v1")
        normal = {"timezone_id": "UTC", "timezone_offset": 0}
        active = {prepare.PROFILE_FIELDS[k]: v for k, v in cfg["profile"].items()}
        rows = [payload(normal), payload(active), payload(copy.deepcopy(normal))]
        receipt = {"status": "MEASURED", "configId": cfg["configId"], "configurationId": cfg["id"],
                   "measuredSessionIds": ["attack"], "injected": cfg["profile"],
                   "declaredObservableFields": cfg["observableFields"], "declaredCdpEmulation": cfg["cdpEmulation"],
                   "cdpEmulation": {"rollback": {"rollback_verified": False}}}
        self.assertFalse(prepare.audit_triplet(cfg, rows, receipt, self.sids)["execution_receipt_valid"])
        receipt["cdpEmulation"]["rollback"]["rollback_verified"] = True
        self.assertEqual(prepare.audit_triplet(cfg, rows, receipt, self.sids)["status"], "PASS")
        rows[2] = payload(active)
        self.assertEqual(prepare.audit_triplet(cfg, rows, receipt, self.sids)["status"], "REVIEW_REQUIRED")


class CompilationTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads((prepare.ROOT / "hybridguard_agent/tests/fixtures/webgl_parameter_equivalence_v1/observer_examples.json").read_text())
        observation = copy.deepcopy(next(c["observation"] for c in fixture["cases"] if c["id"] == "normal"))
        observation["realm_binding"] = "featureapp:receipt-owned:main-frame"
        self.raw = {"session_id": "receipt-owned", "schema_version": "expanded-v2.2-status", "collector_app": "featureapp",
                    "collection_manifest": {"collector_version_code": 14,
                        "collector_version_name": prepare.webgl.COLLECTOR_VERSION_NAME, "web_probe_revision": "expanded-web-67-v2"},
                    "collection_observations": {"observation_schema_version": "app-web-observations-v1",
                        "webgl_parameter": {"collection_revision": prepare.webgl.COLLECTION_REVISION,
                            "read_status": "observed", "reason": None, "observation": observation}}}

    def compile(self, expected="receipt-owned"):
        return prepare.compile_record(self.raw, expected_session_id=expected,
            source_reference="new-protocol-fixture", measurement_contract={})

    def test_missing_and_mismatched_bindings_stay_unknown_without_row_drop(self):
        result = self.compile()
        self.assertEqual(result["candidate_cells"][prepare.webgl.CANDIDATE_ID]["state"], "F")
        self.assertEqual(self.compile("external-other")["candidate_cells"][prepare.webgl.CANDIDATE_ID]["state"], "U")
        del self.raw["collection_observations"]["webgl_parameter"]
        result = self.compile()
        self.assertEqual(result["candidate_cells"][prepare.webgl.CANDIDATE_ID]["state"], "U")
        self.assertEqual(set(result["candidate_cells"]), {prepare.LANG_ID, prepare.WD_ID, prepare.webgl.CANDIDATE_ID})

    def test_bad_base_record_retains_all_failed_cells_and_raw_mode_lineage(self):
        result = self.compile()
        self.assertEqual(set(result["features"]), set(prepare.W0_ATOM_IDS))
        self.assertEqual({prepare.cell_state(c) for c in result["features"].values()}, {"FAILED"})
        self.assertTrue(result["compilation_errors"])
        self.assertEqual(result["candidate_cells"][prepare.WD_ID]["diagnostics"]["mode"], "raw_observation_v1")
        self.assertNotIn("proposed_supervised_label", result)

    def test_collection_association_checks_external_receipt_and_new_install(self):
        raw = copy.deepcopy(self.raw)
        raw["collection_manifest"].update(collector_install_id="new-install", android_api=29, runtime_context="fresh:step")
        step = {"step_id": "step", "phase": "attack", "runtime_context": "fresh:step"}
        saved = {**step, "accepted": True, "observation": {"session_id": "receipt-owned"}}
        attempt = {**step, "status": "ACCEPTED", "session_id": "receipt-owned"}
        archived = {"session_id": "receipt-owned", "receipt_id": "receipt", "collection_batch_id": "batch",
                    "canonical_received_payload": raw}
        receipt = {"session_id": "receipt-owned", "receipt_id": "receipt", "collection_batch_id": "batch",
                   "validation_status": "accepted", "raw_payload_archived": True}
        registration = {"identity": {"collector_install_id": "new-install", "android_api": 29}}
        args = (step, saved, attempt, archived, receipt, raw, registration, 29)
        self.assertEqual(prepare._association_issues(*args), [])
        receipt["session_id"] = "another-receipt-session"
        self.assertIn("SESSION_ASSOCIATION", prepare._association_issues(*args))
        receipt["session_id"] = "receipt-owned"
        raw["collection_manifest"]["collector_install_id"] = "historical-install"
        self.assertIn("FRESH_REGISTERED_INSTALL", prepare._association_issues(*args))
        raw["collection_manifest"]["collector_version_code"] = 13
        self.assertIn("V14_SOURCE", prepare._association_issues(*args))


class FoldTests(unittest.TestCase):
    def setUp(self):
        self.rows = {}
        for env in ("a", "b", "c"):
            for cfg in range(14):
                for number in range(3):
                    for phase in prepare.PHASES:
                        oid = f"{env}-{cfg}-{number}-{phase}"
                        self.rows[oid] = {"opaque_id": oid, "environment_group_id": env, "config_id": str(cfg),
                            "bundle_id": f"{env}:{cfg}", "triplet_id": f"{env}:{cfg}:{number}", "phase": phase}

    def test_exact_balanced_folds_and_whole_triplets(self):
        folds = prepare.make_folds(self.rows)
        self.assertEqual(len(folds), 3)
        self.assertEqual({len(f["train_ids"]) for f in folds}, {252})
        self.assertEqual({len(f["outer_test_ids"]) for f in folds}, {126})
        self.assertEqual(set(i for f in folds for i in f["outer_test_ids"]), set(self.rows))

    def test_missing_or_repeated_position_cannot_silently_change_denominator(self):
        missing = copy.deepcopy(self.rows)
        missing.pop(next(iter(missing)))
        with self.assertRaisesRegex(ValueError, "EXACT_378"):
            prepare.make_folds(missing)
        first, second = list(self.rows)[:2]
        self.rows[second] = copy.deepcopy(self.rows[first])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_TRIPLET_PHASE"):
            prepare.make_folds(self.rows)

    def test_bundle_cannot_cross_environment_fold(self):
        self.rows["b-0-0-clean_pre"]["bundle_id"] = "a:0"
        with self.assertRaisesRegex(ValueError, "BUNDLE_LEAKAGE"):
            prepare.make_folds(self.rows)


if __name__ == "__main__":
    unittest.main()
