"""Focused synthetic S01 boundaries. No real detector or attack execution."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from hybridguard_agent.research.manipulation_eval import admission as a


FIELD = "web_data.navigator_layer.platform"


def make_bundle(root, name="fixture", install="install", alias="device", control=False):
    directory = root / "execution_log/evidence" / name
    directory.mkdir(parents=True)
    kind = "control" if control else "attack"
    run_name = "no_attack_temporal_control_run.json" if control else "paired_triplet_run.json"
    raw_ref = str((directory / "raw_payloads.jsonl").relative_to(root))
    receipt_ref = str((directory / "receipt.json").relative_to(root))
    run = {"run_id": name, "attack_run_id": name, "status": "verified_measured", "method": "fixture",
           "device": {"device_manifest_id": alias}, "tool": {"tool_name": "fixture", "tool_version": "v1",
           "config_id": "configuration", "expected_mutations": [FIELD]}, "sessions": []}
    raws, manifests = [], []
    for index, role in enumerate(("clean_pre", "control_mid" if control else "attack", "clean_post")):
        sid = f"{name}-{index}"
        value = "changed" if role == "attack" else "base"
        cm = {"collector_install_id": install, "device_manifest_id": alias, "runtime_context": f"context-{sid}"}
        raw = {"session_id": sid, "schema_version": "expanded-v2.2-status", "collection_manifest": cm,
               "web_data": {"navigator_layer": {"platform": value}},
               "collection_status": {"status_schema_version": "field-status-v1", "fixed_signal_count": 177,
                                     "fields": {FIELD: "observed", **{f"unused-{i}": "not_applicable" for i in range(176)}}}}
        phase = {"sequence_index": index, "triplet_id" if control else "pair_id": name + "-triplet",
                 "control_role" if control else "pair_role": role}
        session = {"session_id": sid, "round": 1, "runtime_context": cm["runtime_context"], **phase,
                   "execution_status": "verified_success" if role == "attack" else "not_run",
                   "verification": {"state_observable_injection": {
                       "result": "observed" if role == "attack" else "absence_verified", "observed": {"platform": value}}},
                   "active_runner_evidence": {"status": "MEASURED", "receiptPath": receipt_ref} if role == "attack" else None}
        manifest = {"session_id": sid, "raw_payload_reference": raw_ref + f"#session_id={sid}",
                    "collection_manifest_reference": raw_ref + f"#session_id={sid}", "triplet" if control else "pair": phase,
                    "device": {"anonymous_device_instance_id": alias}, "integrity": {"receiver_row_sha256": a.sha256_value(raw)}}
        if control:
            session["manipulation_present"] = False
            manifest["control"] = {"manipulation_present": False, "control_only": True, "active_tooling": []}
        else:
            manifest["label"] = {"manipulation_present": role == "attack", "label_status": "attack_positive_candidate" if role == "attack" else "verified_control"}
            manifest["attack"] = {"attack_run_id": name, **run["tool"], "execution_status": session["execution_status"],
                                  "success_evidence": [receipt_ref] if role == "attack" else [],
                                  "observed_mutations": [{"field_path": FIELD, "clean_pre_value": "base", "attack_value": "changed"}] if role == "attack" else []}
        raws.append(raw)
        manifests.append(manifest)
        run["sessions"].append(session)
    receipt = {"receipt_schema_version": "controlled-runner-receipt-v1", "run_id": name, "attack_run_id": name,
               "session_id": f"{name}-1", "runtime_context": f"context-{name}-1", "round": 1, "method": "fixture", **run["tool"]}
    a.write_json(directory / "receipt.json", receipt)
    a.write_json(directory / run_name, run)
    a.write_jsonl(directory / "raw_payloads.jsonl", raws)
    a.write_jsonl(directory / f"{kind}_sample_manifest_v1.jsonl", manifests)
    return a.load_bundle(root, directory, kind)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bundle = make_bundle(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def decisions(self, bundle=None, status="passed"):
        return a.adjudicate_bundle(bundle or self.bundle, {"result": {"status": status}})

    def test_supported_execution_effect_and_scoped_controls(self):
        rows, triplets = self.decisions()
        self.assertTrue(rows[1]["eligible_detection"])
        self.assertTrue(rows[0]["eligible_pre_control"])
        self.assertTrue(rows[2]["eligible_post_control"])
        self.assertTrue(triplets[0]["eligible_triplet"])
        self.assertFalse(rows[1]["independent_attestation"])

    def test_missing_reference_cannot_be_saved_by_validator_pass(self):
        self.bundle["manifests"][1]["value"]["raw_payload_reference"] = "missing.jsonl#session_id=fixture-1"
        rows, _ = self.decisions()
        self.assertFalse(rows[1]["eligible_detection"])
        self.assertEqual(rows[1]["payload_binding"]["status"], "REJECTED")

    def test_missing_execution_receipt_preserves_effect_but_not_attribution(self):
        (self.bundle["directory"] / "receipt.json").unlink()
        rows, _ = self.decisions()
        self.assertEqual(rows[1]["observable_effect"]["status"], "SUPPORTED")
        self.assertEqual(rows[1]["execution"]["status"], "UNKNOWN")
        self.assertFalse(rows[1]["eligible_detection"])

    def test_receipt_for_other_session_is_conflict_even_when_validator_passes(self):
        path = self.bundle["directory"] / "receipt.json"
        receipt = json.loads(path.read_text())
        receipt["session_id"] = "other-session"
        a.write_json(path, receipt)
        rows, _ = self.decisions()
        self.assertFalse(rows[1]["eligible_detection"])
        self.assertEqual(rows[1]["execution"]["evidence_grade"], "CONFLICT")

    def test_duplicate_session_is_rejected_without_silently_losing_raw_rows(self):
        duplicate = copy.deepcopy(self.bundle["raw"][1])
        duplicate["line"] = 4
        self.bundle["raw"].append(duplicate)
        rows, _ = self.decisions()
        self.assertIn("raw_session_count=2", rows[1]["payload_binding"]["reasons"])
        self.assertFalse(rows[1]["eligible_detection"])

    def test_wrong_payload_with_same_session_rejects_binding(self):
        self.bundle["raw"][1]["value"]["web_data"]["navigator_layer"]["platform"] = "wrong"
        rows, _ = self.decisions()
        self.assertIn("manifest_payload_digest_mismatch", rows[1]["payload_binding"]["reasons"])
        self.assertFalse(rows[1]["eligible_detection"])

    def test_restoration_failure_does_not_select_away_detection_or_triplet(self):
        post = self.bundle["raw"][2]["value"]
        post["web_data"]["navigator_layer"]["platform"] = "changed"
        self.bundle["manifests"][2]["value"]["integrity"]["receiver_row_sha256"] = a.sha256_value(post)
        self.bundle["run"]["sessions"][2]["verification"]["state_observable_injection"]["observed"]["platform"] = "changed"
        rows, triplets = self.decisions(status="failed")
        self.assertTrue(rows[1]["eligible_detection"])
        self.assertTrue(triplets[0]["eligible_triplet"])
        self.assertEqual(rows[2]["rollback"]["status"], "REFUTED")
        self.assertFalse(rows[2]["eligible_post_control"])

    def test_missing_post_does_not_remove_supported_active_fact(self):
        self.bundle["manifests"] = self.bundle["manifests"][:2]
        self.bundle["raw"] = self.bundle["raw"][:2]
        self.bundle["run"]["sessions"] = self.bundle["run"]["sessions"][:2]
        rows, triplets = self.decisions(status="failed")
        self.assertTrue(rows[1]["eligible_detection"])
        self.assertFalse(triplets[0]["eligible_triplet"])
        self.assertEqual(rows[1]["rollback"]["status"], "UNKNOWN")

    def test_future_post_label_conflict_is_not_a_veto_on_active_detection(self):
        self.bundle["manifests"][2]["value"]["label"]["manipulation_present"] = True
        rows, triplets = self.decisions(status="failed")
        self.assertTrue(rows[1]["eligible_detection"])
        self.assertTrue(triplets[0]["eligible_triplet"])
        self.assertFalse(rows[2]["eligible_post_control"])
        self.assertEqual(rows[2]["evidence_grade"], "CONFLICT")

    def test_control_positive_annotation_never_creates_a_positive(self):
        control = make_bundle(self.root, "control", control=True)
        control["manifests"][1]["value"]["label"] = {"manipulation_present": True}
        rows, _ = self.decisions(control)
        self.assertFalse(any(r["eligible_detection"] or r["eligible_temporal_control"] for r in rows))
        self.assertTrue(rows[1]["label_conflict"])
        self.assertEqual(rows[1]["no_intervention"]["evidence_grade"], "CONFLICT")

    def test_control_pass_and_stability_are_not_operational_no_intervention_proof(self):
        control = make_bundle(self.root, "control", control=True)
        rows, _ = self.decisions(control)
        self.assertTrue(all(r["payload_binding"]["status"] == "BOUND" for r in rows))
        self.assertTrue(all(r["no_intervention"]["status"] == "UNKNOWN" for r in rows))
        self.assertFalse(any(r["eligible_temporal_control"] for r in rows))

    def test_same_install_across_aliases_and_alias_only_attempt_merge_transitively(self):
        second = make_bundle(self.root, "second", install="install", alias="different-alias")
        third = make_bundle(self.root, "third", install="reinstall", alias="different-alias")
        unrelated = make_bundle(self.root, "unrelated", install="other", alias="other")
        groups = a.environment_groups([self.bundle, second, third, unrelated])["groups"]
        self.assertEqual(sorted(sorted(g["member_bundles"]) for g in groups), [["fixture", "second", "third"], ["unrelated"]])
        self.assertTrue(all(g["physical_identity"] == "UNKNOWN" for g in groups))

    def test_unavailable_field_and_false_zero_are_not_silently_conflated(self):
        self.assertFalse(a.same(False, 0))
        self.assertTrue(a.same([], []))
        self.assertIs(a.field_value({}, FIELD), a.MISSING)
        raw = self.bundle["raw"][1]["value"]
        raw["collection_status"]["fields"][FIELD] = "runtime_error"
        self.bundle["manifests"][1]["value"]["integrity"]["receiver_row_sha256"] = a.sha256_value(raw)
        rows, _ = self.decisions()
        self.assertFalse(rows[1]["eligible_detection"])
        self.assertEqual(rows[1]["observable_effect"]["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
