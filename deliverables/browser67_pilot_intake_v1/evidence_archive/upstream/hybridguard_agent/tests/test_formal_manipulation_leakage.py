"""S04 synthetic metadata, masking, process-input and saved-output isolation."""
import copy
import inspect
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.evidence.paired244 import legacy_payload
from hybridguard_agent.research.manipulation_eval.adapter import adapt_payload
from hybridguard_agent.research.manipulation_eval.persistence import new_output
from hybridguard_agent.research.manipulation_eval.runner import worker
from hybridguard_agent.research.manipulation_eval.schemas import validate_record
from hybridguard_agent.research.manipulation_eval.schemas import RISK, validate_schema
from hybridguard_agent.research.manipulation_eval.synthetic import consistent_payload, put, MAP
from hybridguard_agent.tests.test_formal_manipulation_policy import load


class LeakageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load()

    def run_payload(self, payload, **kwargs):
        result = worker(payload, contract=self.contract, condition_id="SRC-111", **kwargs)
        result.pop("timings_ms")
        return result

    def raw(self):
        raw = legacy_payload(consistent_payload())
        raw["collection_status"].update(status_schema_version="field-status-v1", fixed_signal_count=177)
        return raw

    def test_label_phase_tool_config_paths_and_logs_do_not_change_projection_or_prediction(self):
        raw = self.raw(); first = adapt_payload(raw)
        raw.update(label={"attack": True}, phase="attack", tool="secret-tool", config={"expected": "wrong"},
                   session_id="secret-session", install="secret-install", group="secret-group", raw_path="/secret/path",
                   receipt={"success": True}, execution_log="secret-log", expected_mutations=["os_version"],
                   collection_manifest={"user_agent": "metadata-collision", "runtime_context": {"capture_attack": True, "control_mid": False}})
        raw["web_data"]["capture_attack"] = True
        second = adapt_payload(raw)
        self.assertEqual(first, second)
        self.assertEqual(self.run_payload(first), self.run_payload(second))
        self.assertNotIn("secret", json.dumps(self.run_payload(second)))

    def test_future_post_changes_leave_pre_and_active_unchanged(self):
        pre = self.raw(); active = self.raw()
        before = [self.run_payload(adapt_payload(r)) for r in (pre, active)]
        for raw in (pre, active):
            raw["future_post"] = {"os_version": "999", "label": "different", "roll_back": False}
            raw["clean_post"] = {"user_agent": "different"}
        after = [self.run_payload(adapt_payload(r)) for r in (pre, active)]
        self.assertEqual(before, after)

    def test_view_mask_removes_values_states_quality_and_derived_facts_before_use(self):
        p = consistent_payload(); original = self.run_payload(p, input_view="Native84")
        for section in ("features", "field_status", "field_quality"):
            for f in p[section]:
                if not f.startswith("app.android_native_data."):
                    p[section][f] = {"poison": "MASKED_LAYER_SHOULD_NEVER_APPEAR"}
        masked = self.run_payload(p, input_view="Native84")
        self.assertEqual(original, masked)
        bundle = masked["original_runtime"]["evidence_bundle"]
        self.assertTrue(all(f.startswith("app.android_native_data.") for f in bundle["fields"]))
        self.assertTrue(all(set(f["source_fields"]) <= set(bundle["fields"]) for f in bundle["derived_facts"].values()))
        self.assertNotIn("MASKED_LAYER_SHOULD_NEVER_APPEAR", json.dumps(masked))

    def test_worker_rejects_metadata_envelope_browser_unknown_fields_and_supplied_facts(self):
        for attack in ("label", "future_post", "derived_facts", "opaque_id", "browser", "unknown_feature"):
            p = consistent_payload()
            if attack == "unknown_feature": p["features"]["capture_attack"] = True
            else: p[attack] = "EXTRA_PRIVATE_METADATA"
            result = self.run_payload(p)
            self.assertEqual(result["risk"]["decision"], "FAILED")
            self.assertNotIn("EXTRA_PRIVATE_METADATA", json.dumps(result))
        self.assertNotIn("opaque_id", inspect.signature(worker).parameters)

    def test_saved_schema_rejects_metadata_and_risk_probability_promotion(self):
        risk = self.run_payload(consistent_payload())["risk"]
        validate_schema(risk, RISK)
        for key, value in (("label", "attack"), ("future_post", {}), ("calibrated_attack_probability", 0.9)):
            bad = copy.deepcopy(risk); bad[key] = value
            with self.assertRaises(ValueError): validate_schema(bad, RISK)

    def test_facts_and_logs_deliberately_unreadable_worker_still_predicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); (root / "facts.json").write_text('"secret"'); (root / "execution.log").write_text("secret")
            original_open = io.open
            def guarded(path, *args, **kwargs):
                if not isinstance(path, int) and Path(path).resolve().is_relative_to(root):
                    raise PermissionError("Synthetic facts/logs access denied")
                return original_open(path, *args, **kwargs)
            with patch("io.open", side_effect=guarded), patch("builtins.open", side_effect=guarded):
                with self.assertRaises(PermissionError): (root / "facts.json").read_text()
                result = self.run_payload(consistent_payload())
            self.assertEqual(result["risk"]["decision"], "NO_ALERT")

    def test_false_zero_empty_list_and_observed_UA_content_are_not_metadata(self):
        p = consistent_payload()
        for alias, value in {"webview_data.is_debuggable": False, "web_data.max_touch_points": 0,
                             "android_native_data.sensor_type_list": []}.items(): put(p, alias, value)
        put(p, "web_data.user_agent", p["features"][MAP["web_data.user_agent"]].replace("Chrome", "HeadlessChrome"))
        result = self.run_payload(p)
        self.assertEqual(result["execution_status"], "COMPLETED")
        projection = result["original_runtime"]["evidence_bundle"]["projection"]
        self.assertIs(projection["features"][MAP["webview_data.is_debuggable"]], False)
        self.assertEqual(projection["features"][MAP["web_data.max_touch_points"]], 0)
        self.assertEqual(projection["features"][MAP["android_native_data.sensor_type_list"]], [])
        self.assertIn("Headless", projection["features"][MAP["web_data.user_agent"]])

    def test_output_paths_cannot_cover_frozen_artifacts_inputs_or_existing_runs(self):
        for name in ("hybridguard_agent/config/formal_manipulation_role_gate_v2", "hybridguard_agent/artifacts/formal_manipulation_v1_20260923/03_registry",
                     "hybridguard_agent/artifacts/formal_manipulation_v1_20260923/03r_role_gate_v2"):
            with self.assertRaises(ValueError): new_output(name)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp); (path / "old.txt").write_text("retained")
            with self.assertRaises(ValueError): new_output(path)
            with self.assertRaises(ValueError): new_output(path / "nested", inputs=[path])
            link = path / "config-link"; link.symlink_to(Path("hybridguard_agent/config/formal_manipulation_role_gate_v2").resolve())
            with self.assertRaises(ValueError): new_output(link / "nested")


if __name__ == "__main__":
    unittest.main()
