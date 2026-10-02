"""Eligibility must follow same-session workflow evidence, never clean labels."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from hybridguard_agent.research import normal_collection_evidence as normal


def observation(sid, value=0):
    return {"valid": True, "session_id": sid, "source_reference": "raw.jsonl:" + sid,
            "values": {"web_offset": value}, "reasons": []}


def workflow(sid, *, noop=True):
    return {"verified": True, "noop": noop, "session_id": sid, "operation_id": "op-" + sid,
            "evidence_refs": ["receipt-" + sid]}


def rollback():
    return {"verified": True, "from_operation_id": "op-active", "from_session_id": "active",
            "to_session_id": "post", "evidence_refs": ["process-exit", "new-process"]}


class NormalEvidenceTests(unittest.TestCase):
    def test_pre_requires_observation_and_matching_noop_workflow(self):
        obs, flow = observation("pre"), workflow("pre")
        self.assertTrue(normal.normal_pre(obs, flow)["supported"])
        for invalid in ({**flow, "noop": False}, {**flow, "verified": False},
                        {**flow, "session_id": "other"}, {**flow, "evidence_refs": []}):
            self.assertFalse(normal.normal_pre(obs, invalid)["supported"])
        obs["valid"] = False
        obs.update(phase="clean_pre", label="normal")
        self.assertFalse(normal.normal_pre(obs, flow)["supported"])

    def test_post_requires_operation_and_rollback_and_values(self):
        pre = normal.normal_pre(observation("pre"), workflow("pre"))
        args = [pre, observation("post"), workflow("post"), workflow("active", noop=False), rollback()]
        self.assertTrue(normal.normal_post(*args)["supported"])
        for idx, key, value in ((0, "supported", False), (3, "verified", False),
                                (4, "verified", False), (4, "from_session_id", "other"),
                                (4, "from_operation_id", "other"), (4, "to_session_id", "other"),
                                (1, "values", {"web_offset": -60})):
            changed = deepcopy(args); changed[idx][key] = value
            self.assertFalse(normal.normal_post(*changed)["supported"], (idx, key))

    def test_one_session_cannot_pose_as_three_phases(self):
        pre = normal.normal_pre(observation("pre"), workflow("pre"))
        roll = rollback(); roll["to_session_id"] = "pre"
        self.assertFalse(normal.normal_post(pre, observation("pre"), workflow("pre"),
                                           workflow("active", noop=False), roll)["supported"])

    def test_labels_and_detector_alarms_never_determine_normal(self):
        obs, flow = observation("pre"), workflow("pre")
        expected = normal.normal_pre(obs, flow)
        for state in ("MANIPULATION_ALERT", "NO_ALERT", "U", "FAILED"):
            obs.update(prediction=state, phase="attack", target="Los_Angeles", label="attack")
            flow.update(prediction=state, phase="attack", label="attack")
            self.assertEqual(normal.normal_pre(obs, flow), expected)

    def test_legitimate_system_change_needs_actual_expected_values(self):
        pre = normal.normal_pre(observation("pre"), workflow("pre"))
        proof = {"verified": True, "from_session_id": "pre", "to_session_id": "mid",
                 "expected_values": {"web_offset": 420}, "evidence_refs": ["verified-system-settings"]}
        self.assertTrue(normal.normal_system_change(pre, observation("mid", 420), workflow("mid"), proof)["supported"])
        self.assertFalse(normal.normal_system_change(pre, observation("mid", 0), workflow("mid"), proof)["supported"])
        proof["verified"] = False
        self.assertFalse(normal.normal_system_change(pre, observation("mid", 420), workflow("mid"), proof)["supported"])

    def test_zero_negative_and_minus_one_are_valid_observed_offsets(self):
        for offset in (0, -1, -480, 420):
            bound = {"status": "OK", "source_binding": {"binding_valid": True, "same_app_record": True,
                     "app_session_id": "session", "raw_reference": "raw:1"},
                     "features": {"offset": offset}, "field_status": {"offset": "observed"},
                     "field_quality": {"offset": "observed_value"}}
            self.assertTrue(normal.observation_evidence(bound, ["offset"])["valid"])
        for invalid in (None, float("nan"), float("inf")):
            bound["features"]["offset"] = invalid
            self.assertFalse(normal.observation_evidence(bound, ["offset"])["valid"])
        bound["features"]["offset"] = 0
        bound["field_quality"]["offset"] = "ambiguous_sentinel"
        self.assertFalse(normal.observation_evidence(bound, ["offset"])["valid"])


class SavedMemoryEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.base = cls.root / "deliverables/memory_relation_validation_v1"
        run = cls.base / "runs/api29_swiftshader"
        cls.operation = json.loads((run / "operations.jsonl").read_text().splitlines()[0])
        cls.raw = json.loads((run / "backend/raw_expanded_payloads.jsonl").read_text().splitlines()[0])
        cls.receipt = json.loads((run / "memory-2-r1-clean_pre.cdp.json").read_text())
        cls.commands = json.loads((run / "environment.json").read_text())["commands"]
        cls.ref = "deliverables/memory_relation_validation_v1/runs/api29_swiftshader/backend/raw_expanded_payloads.jsonl:1"

    def verify(self, *, operation=None, raw=None, receipt=None, commands=None):
        return normal.verify_memory_position(self.root, "api29_swiftshader", "memory-2-r1-clean_pre",
            operation or self.operation, raw or self.raw, self.ref, receipt or self.receipt,
            commands or self.commands)

    def test_saved_current_receipt_raw_values_and_lifecycle(self):
        obs, flow = self.verify()
        self.assertTrue(obs["valid"])
        self.assertTrue(flow["verified"])
        self.assertTrue(flow["fresh_process_verified"])
        self.assertTrue(flow["process_removed_verified"])
        self.assertTrue(normal.normal_pre(obs, flow)["supported"])

    def test_completed_flags_cannot_hide_raw_or_cdp_mismatch(self):
        altered = deepcopy(self.raw)
        altered["canonical_received_payload"]["collection_manifest"]["runtime_context"] = "other-session"
        self.assertFalse(self.verify(raw=altered)[1]["verified"])
        altered = deepcopy(self.receipt)
        altered["current_runtime_observation"]["deviceMemory"] = 16
        self.assertFalse(self.verify(receipt=altered)[1]["verified"])
        altered = deepcopy(self.receipt)
        altered["commands"][2]["error"] = {"message": "navigate failed"}
        self.assertFalse(self.verify(receipt=altered)[1]["verified"])

    def test_exit_claim_needs_recorded_process_command(self):
        altered = deepcopy(self.commands)
        i = next(i for i, c in enumerate(altered)
                 if any(str(a).endswith("/memory-2-r1-clean_pre.cdp.json") for a in c["argv"]))
        altered[i + 2]["returncode"] = 0  # pidof still finds the process
        self.assertFalse(self.verify(commands=altered)[1]["process_removed_verified"])

    def test_all_planned_memory_positions_retained_and_old_counts_unchanged(self):
        before = (self.base / "summary.json").read_bytes()
        result = normal.review_memory_batch(self.root)
        self.assertEqual((result["planned_records"], result["reviewed_records"], len(result["records"])), (72, 72, 72))
        self.assertEqual((result["groups_n"], result["verified_rollback_groups_n"]), (24, 24))
        self.assertEqual((result["confirmed_normal_n"], result["normal_without_support_n"]), (48, 0))
        self.assertEqual(result["conditions_on_confirmed_normal"], {"R_REL": {"F": 48}, "R_WEB8": {"F": 48}})
        self.assertTrue(all(c == {"NO_ALERT": 48} for c in result["models_on_confirmed_normal"].values()))
        self.assertEqual((self.base / "summary.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
