"""Effect, normal evidence and all-planned denominators stay outside prediction."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest
from hybridguard_agent.tests.test_screen_geometry_relations import geometry

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("geometry_evaluation", ROOT/"deliverables/screen_geometry_observation_v1/evaluate.py")
evaluation=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluation)


def trio(kind="L2",changed=True):
    result=[]
    for phase,sid,value in (("clean_pre","a",100),("change","b",120 if changed else 100),("clean_post","c",100)):
        active=kind=="A" and phase=="change"
        result.append({"row":{"sample_id":sid,"environment":"unit","process_type":kind,"round":1,"phase":phase,
            "operation":{"status":"COLLECTED"},"host_before":None,"major_non_target_fields":{"user_agent":"same"},
            "conditions":{k:{"state":"U" if k=="R_HOST_GEOMETRY" else "F"} for k in evaluation.CONDITIONS}},
            "observation":{"valid":True,"session_id":sid,"values":dict.fromkeys(evaluation.LEGACY_NORMAL_FIELDS,value),
                           "source_reference":"raw:"+sid,"reasons":[]},
            "workflow":{"verified":True,"session_id":sid,"operation_id":"op-"+sid,"noop":not active,
                        "fresh_process_verified":True,"process_removed_verified":True,"system_operation_verified":True,
                        "cdp_rollback_verified":True,"evidence_refs":["receipt:"+sid]}})
    return result


class EvaluationTests(unittest.TestCase):
    def test_geometry_missing_normal_kept_and_unknown_counted(self):
        members=trio();effect=evaluation.adjudicate_trio(members)
        self.assertEqual(effect["normal_supported"],[True,True,True])
        stats=evaluation.statistics([m["row"] for m in members])
        self.assertEqual(stats["n"],3)
        self.assertEqual(stats["conditions"]["R_HOST_GEOMETRY"]["U"],3)
        self.assertEqual(stats["conditions"]["R_HOST_GEOMETRY"]["explicit_coverage"],{"numerator":0,"denominator":3})

    def test_real_target_change_does_not_require_detector_alarm(self):
        members=trio("A");effect=evaluation.adjudicate_trio(members)
        self.assertTrue(effect["observable_intervention"])
        self.assertEqual(effect["normal_supported"],[True,False,True])
        self.assertEqual(effect["recovery"],"RESTORED")

    def test_no_effect_not_detection_success_even_if_alarm(self):
        members=trio("A",changed=False)
        for c in members[1]["row"]["conditions"].values():c["state"]="T"
        effect=evaluation.adjudicate_trio(members)
        self.assertEqual(effect["effect"],"NO_OBSERVABLE_EFFECT")
        self.assertFalse(effect["observable_intervention"])

    def test_post_phase_without_recovery_not_normal(self):
        members=trio();members[1]["workflow"]["cdp_rollback_verified"]=False
        effect=evaluation.adjudicate_trio(members)
        self.assertEqual(effect["recovery"],"RECOVERY_NOT_VERIFIED")
        self.assertFalse(members[2]["row"]["normal_basis"]["supported"])

    def test_post_missing_cannot_erase_current_effect(self):
        members=trio("A");members[2]["observation"].update(valid=False, values={}, reasons=["POST_MISSING"])
        effect=evaluation.adjudicate_trio(members)
        self.assertTrue(effect["observable_intervention"])
        self.assertEqual(effect["effect"],"OBSERVABLE_CHANGE")
        self.assertEqual(effect["recovery"],"MISSING_OBSERVATION")
        self.assertFalse(members[2]["row"]["normal_basis"]["supported"])

    def test_rollback_failure_cannot_erase_current_effect(self):
        members=trio("A")
        members[1]["workflow"].update(current_execution_verified=True, complete_workflow_verified=False,
                                      cdp_rollback_verified=False)
        effect=evaluation.adjudicate_trio(members)
        self.assertEqual(effect["execution"],"EXECUTED");self.assertTrue(effect["observable_intervention"])
        self.assertEqual(effect["recovery"],"RECOVERY_NOT_VERIFIED")

    def test_failed_execution_or_missing_observation_not_positive(self):
        members=trio("A");members[1]["workflow"]["verified"]=False
        effect=evaluation.adjudicate_trio(members)
        self.assertEqual(effect["execution"],"OPERATION_FAILED");self.assertFalse(effect["observable_intervention"])
        members=trio("A");members[1]["observation"]["valid"]=False
        effect=evaluation.adjudicate_trio(members)
        self.assertEqual(effect["effect"],"MISSING_OBSERVATION");self.assertFalse(effect["observable_intervention"])

    def test_model_results_do_not_change_label_or_recovery(self):
        members=trio("L3");other=deepcopy(members)
        for m in other:
            for condition in m["row"]["conditions"].values():condition["state"]="T"
        self.assertEqual(evaluation.adjudicate_trio(members),evaluation.adjudicate_trio(other))

    def test_actual_non_target_differences_are_preserved(self):
        members=trio("A");members[1]["row"]["major_non_target_fields"]["user_agent"]="changed"
        effect=evaluation.adjudicate_trio(members)
        self.assertTrue(effect["confounded"]);self.assertIn("user_agent",effect["non_target_differences"])

    def test_report_malformed_geometry_does_not_drop_position(self):
        variations=[None, ["bad"]]
        for key in ("host_before", "attempts"):
            g=geometry();g[key]=None;variations.append(g)
        g=geometry();g["web"]["fields"]=None;variations.append(g)
        for value in variations:
            with self.subTest(value_type=type(value).__name__):
                raw={"raw_payload_archive_schema_version":"expanded-raw-payload-v1","session_id":"s",
                     "canonical_received_payload":{"session_id":"s","schema_version":"expanded-v2.2-status","collector_app":"featureapp",
                         "collection_manifest":{"collector_version_code":15,"collector_version_name":"1.6.8-expanded-v2.2-geometry", "device_manifest_id":"screen-geometry-unit"},
                         "collection_observations":{"webview_geometry":value}}}
                operation={"session_id":"s","step_id":"unit","process_type":"L1","phase":"clean_pre","round":1}
                row,_,_=evaluation.current_row(raw,operation,"raw:1","unit")
                self.assertEqual(row["step_id"],"unit")
                self.assertIn(row["conditions"]["R_HOST_GEOMETRY"]["state"],("U","FAILED"))

    def test_actual_current_flow_survives_failed_driver_rollback(self):
        context="screen-geometry:unit:op"
        iso=lambda second:f"2026-10-02T00:00:0{second}+00:00"
        bound={"status":"OK","source_binding":{"raw_reference":"raw:1"},"geometry":{"host_before":None}}
        raw={"server_received_at":iso(3),"canonical_received_payload":{"collection_manifest":{"runtime_context":context,"collector_install_id":"i"}}}
        operation={"step_id":"op","session_id":"s","collector_install_id":"i","process_type":"A","phase":"change",
                   "status":"FAILED","cdp_status":"FAILED","started_at":iso(1),"finished_at":iso(5),"owned_app_process_absent_after":True}
        operation.update({k:{"user_rotation":"0","accelerometer_rotation":"0","input_orientation":["0"]} for k in ("system_before","system_after")})
        params={"fixed":"settings"}
        settings={"screen_configuration":{"cdpEmulation":{"applyCommands":[{"params":params}]}}}
        receipt={"version":"screen-only-cdp-v1","status":"FAILED","active_screen_override":True,"started_at":iso(2),"finished_at":iso(4),
                 "raw_receipt":{"session_id":"s","received_before_rollback":True},"rollback_status":"FAILED",
                 "commands":[{"method":"Page.enable","result":{}},{"method":"Emulation.setDeviceMetricsOverride","params":params,"result":{}},
                    {"method":"Page.navigate","params":{"url":"file:///android_asset/expanded_probe.html"},"result":{}},
                    {"method":"Runtime.evaluate","result":{}},{"method":"Emulation.clearDeviceMetricsOverride","error":{"message":"failed"}}]}
        launch=["am","start",context,"p.GEOMETRY_HIDE_HEADER","false","p.GEOMETRY_ENABLE_ZOOM","false","p.GEOMETRY_ZOOM_FACTOR","1.0"]
        commands=[{"argv":["am","force-stop","p"],"returncode":0},{"argv":["pidof","p"],"returncode":1},
                  {"argv":["settings","put","system","accelerometer_rotation","0"],"returncode":0},
                  {"argv":["settings","put","system","user_rotation","0"],"returncode":0},
                  {"argv":launch,"returncode":0},{"argv":["node","/run/op.cdp.json"],"returncode":1},
                  {"argv":["am","force-stop","p"],"returncode":0},{"argv":["pidof","p"],"returncode":1}]
        proof=evaluation.workflow_proof(bound,raw,operation,receipt,commands,environment="unit",run=Path("run"),settings=settings)
        self.assertTrue(proof["current_execution_verified"],proof["reasons"])
        self.assertFalse(proof["complete_workflow_verified"])
        self.assertFalse(proof["cdp_rollback_verified"])
        # dumpsys SurfaceOrientation is absent on some APIs and geometry may
        # be missing. The known normal request remains separately verifiable.
        operation["system_after"]["input_orientation"]=[]
        proof=evaluation.workflow_proof(bound,raw,operation,receipt,commands,environment="unit",run=Path("run"),settings=settings)
        self.assertTrue(proof["current_execution_verified"],proof["reasons"])
        self.assertIsNone(proof["requested_orientation_achieved"])


if __name__ == "__main__": unittest.main()
