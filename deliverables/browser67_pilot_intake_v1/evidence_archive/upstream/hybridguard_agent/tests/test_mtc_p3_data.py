"""Synthetic-only tests for the P3 reader's split and inference boundaries."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from hybridguard_agent.research.mtc_p3_data import inference_record, load_split_records


FIELD = "app.web_data.navigator_layer.hardware_concurrency"


class MtcP3DataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan = self.root / "plan"
        self.plan.mkdir()
        self.snapshot = self.root / "snapshot"
        self.snapshot.mkdir()
        self.source = self.snapshot / "paired_244.jsonl"
        self.summary = {"p2_status": "COMPLETE", "source_snapshot": str(self.snapshot)}
        self.lock = {"status": "LOCKED"}
        self.registry = []
        self.source_rows = []
        for number, (split, role) in enumerate([
            ("discovery", "primary_representative"),
            ("reserved_validation", "primary_representative"),
            ("development", "primary_representative"),
            ("discovery", "primary_representative"),
            ("discovery", "paired_repeat_observation"),
        ], 1):
            profile = {"manufacturer": "fixture", "model": f"model-{number}",
                       "android_release": "13", "android_api": 33,
                       "collector_install_id": f"install-{number}"}
            sid = f"sample-{number}"
            fields = {FIELD: 8, **{f"app.fixture.field_{n}": n for n in range(243)}}
            self.source_rows.append({
                "sample_id": sid, "record_schema_version": "hybridguard-mtc-observation-v2",
                "dataset_view": "paired_244", "feature_count": 244, "profile": profile,
                "features": fields,
                "field_status": {key: "observed" for key in fields},
                "field_quality": {key: "observed_value" for key in fields},
                "app": {"payload_sha256": f"app-binding-{number}"},
                "browser": {"payload_sha256": f"browser-binding-{number}"},
                "qc": {"status": "passed"}, "pair": {"pair_status": "completed"},
                "label_status": "unknown", "scenario_phase": "CONTROL_ONLY",
            })
            self.registry.append({
                "sample_id": sid, "source_view": "paired_244", "source_line": number,
                "split": split, "analysis_role": role, "profile": profile,
                "group_id": f"group-{number}", "app_payload_sha256": f"app-binding-{number}",
                "browser_payload_sha256": f"browser-binding-{number}",
                "label_status": "unknown", "manipulation_present": None,
            })
        # Reverse source order: output must follow the frozen input projection.
        self.inputs = {"discovery": [self.ref(4), self.ref(1)], "development": [self.ref(3)]}
        self.write_fixture()

    def ref(self, line):
        meta = self.registry[line - 1]
        return {"sample_id": meta["sample_id"], "source_file": str(self.source),
                **{key: meta[key] for key in ("source_line", "app_payload_sha256", "browser_payload_sha256")}}

    def write_fixture(self):
        for name, payload in [("summary.json", self.summary), ("reserved_validation_LOCK.json", self.lock)]:
            (self.plan / name).write_text(json.dumps(payload), encoding="utf-8")
        self.write_jsonl(self.plan / "sample_registry.jsonl", self.registry)
        for split, rows in self.inputs.items():
            self.write_jsonl(self.plan / f"{split}_inputs.jsonl", rows)
        self.write_jsonl(self.source, self.source_rows)

    @staticmethod
    def write_jsonl(path, rows):
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def assert_rejected(self, message):
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, message):
            load_split_records(self.plan, "discovery")

    def test_allowed_splits_read_only_selected_lines_in_projection_order(self):
        lines = self.source.read_text(encoding="utf-8").splitlines()
        lines[1] = "THIS RESERVED FEATURE LINE IS DELIBERATELY NOT JSON"
        lines[4] = "THIS NONREPRESENTATIVE FEATURE LINE IS ALSO NOT JSON"
        self.source.write_text("\n".join(lines) + "\n", encoding="utf-8")
        discovery = load_split_records(self.plan, "discovery")
        development = load_split_records(self.plan, "development")
        self.assertEqual([row["sample_id"] for row in discovery], ["sample-4", "sample-1"])
        self.assertEqual([row["sample_id"] for row in development], ["sample-3"])
        self.assertEqual(discovery[0]["_p2"], {key: self.registry[3][key] for key in
                         ("group_id", "split", "profile", "analysis_role", "source_line")})

    def test_reserved_or_unknown_split_is_rejected_before_any_file_read(self):
        for split in ("reserved_validation", "reserved_rule_validation", "all", "DISCOVERY"):
            with self.subTest(split=split), self.assertRaisesRegex(ValueError, "reserved validation is locked"):
                load_split_records(self.root / "does-not-exist", split)

    def test_completed_plan_and_active_reserved_lock_are_required(self):
        for target, key, invalid in ((self.summary, "p2_status", "INCOMPLETE"),
                                     (self.lock, "status", "UNLOCKED")):
            with self.subTest(key=key):
                original = target[key]
                target[key] = invalid
                self.assert_rejected("completed P2 with locked")
                target[key] = original

    def test_omitted_or_duplicate_representative_is_rejected(self):
        original = copy.deepcopy(self.inputs["discovery"])
        self.inputs["discovery"] = original[:1]
        self.assert_rejected("omits admitted")
        self.inputs["discovery"] = original + [original[0]]
        self.assert_rejected("unique admitted")

    def test_other_split_and_repeat_cannot_enter_discovery_projection(self):
        original = copy.deepcopy(self.inputs["discovery"])
        for line in (2, 3, 5):
            with self.subTest(line=line):
                self.inputs["discovery"] = original + [self.ref(line)]
                self.assert_rejected("unique admitted")

    def test_registry_duplicate_and_duplicate_source_line_are_rejected(self):
        self.registry.append(copy.deepcopy(self.registry[0]))
        self.assert_rejected("Duplicate P2 registry")
        self.registry.pop()
        self.registry[3]["source_line"] = 1
        self.inputs["discovery"][0]["source_line"] = 1
        self.assert_rejected("Invalid or duplicate source line")

    def test_source_path_and_every_projection_binding_must_match(self):
        original = copy.deepcopy(self.inputs["discovery"][0])
        cases = [("source_file", str(self.snapshot / "other.jsonl"), "source differs"),
                 ("source_line", 3, "binding mismatch: source_line"),
                 ("app_payload_sha256", "wrong", "binding mismatch: app_payload_sha256"),
                 ("browser_payload_sha256", "wrong", "binding mismatch: browser_payload_sha256")]
        for key, value, message in cases:
            with self.subTest(key=key):
                self.inputs["discovery"][0] = {**original, key: value}
                self.assert_rejected(message)

    def test_projection_cannot_carry_control_fields(self):
        self.inputs["discovery"][0]["scenario_phase"] = "attack_active"
        self.assert_rejected("unsupported/control fields")

    def test_selected_source_identity_schema_view_count_and_bindings_are_checked(self):
        original = copy.deepcopy(self.source_rows[3])
        cases = [("sample_id", "other", "identity/version mismatch"),
                 ("record_schema_version", "v1", "identity/version mismatch"),
                 ("dataset_view", "partial", "full paired244"),
                 ("feature_count", 177, "full paired244"),
                 ("app", {"payload_sha256": "wrong"}, "payload binding mismatch"),
                 ("browser", {"payload_sha256": "wrong"}, "payload binding mismatch"),
                 ("profile", {**original["profile"], "model": "other"}, "Profile differs")]
        for key, value, message in cases:
            with self.subTest(key=key):
                self.source_rows[3] = {**original, key: value}
                self.assert_rejected(message)

    def test_missing_selected_line_is_rejected(self):
        self.source_rows = self.source_rows[:3]
        self.assert_rejected("Missing selected source rows")

    def test_inference_projection_contains_only_original_values_and_field_states(self):
        row = load_split_records(self.plan, "discovery")[0]
        row.update({"metric_eligible": True, "label_status": "verified",
                    "manipulation_present": True, "scenario_id": "secret-control", "group_id": "secret-group"})
        # Valid source false/zero/empty/null values must not be imputed or removed here.
        row["features"].update({"app.fixture.zero": 0, "app.fixture.false": False,
                                "app.fixture.empty": "", "app.fixture.null": None})
        before = copy.deepcopy(row)
        projected = inference_record(row)
        self.assertEqual(set(projected), {"features", "field_status", "field_quality"})
        self.assertEqual(projected, {key: before[key] for key in projected})
        self.assertEqual(row, before)


if __name__ == "__main__":
    unittest.main()
