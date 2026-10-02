from copy import deepcopy
import math
import unittest

from hybridguard_agent.research import screen_geometry_relations as relation
from hybridguard_agent.research import screen_geometry_sources as sources
from hybridguard_agent.research.rule_learning.contracts import logic, negate, state


def geometry():
    host = {"read_status":"observed", "thread":"android_main", "clock":{"elapsed_realtime_ms":1000},
            "sequence":{"document":2,"layout":4,"scale":0},"width_px":1080,"height_px":1800,
            "padding_left_px":0,"padding_right_px":0,"padding_top_px":0,"padding_bottom_px":0,
            "content_width_px":1080,"content_height_px":1800,
            "content_region_definition":"view_bounds_minus_padding_no_inset_subtraction",
            "view_scale_x":1,"view_scale_y":1,"rotation_degrees":0,"is_attached_to_window":True,
            "is_shown":True,"density":2.5,"scale":{"status":"not_observed","callback_value":None},
            "diagnostic_get_scale":{"value":2.5}}
    binding={"session_id":"s","webview_instance_id":"v","document_generation":2,"observation_id":"o","attempt_id":1}
    web={"schema_version":sources.WEB_SCHEMA,"read_status":"observed","binding":binding,"document_id":"doc",
         "clock":{"epoch_start_ms":1,"epoch_end_ms":2,"performance_start_ms":1,"performance_end_ms":2},
         "fields":{k:{"status":"observed","value":v} for k,v in {
             "visual_viewport_width":432,"visual_viewport_height":720,"device_pixel_ratio":2.5,
             "visual_viewport_scale":1}.items()}}
    after=deepcopy(host);after["clock"]["elapsed_realtime_ms"]=1010
    attempt={**binding,"host_before":host,"host_after":after,"web":web,"binding_valid":True,"host_stable":True}
    return {"schema_version":sources.GEOMETRY_SCHEMA,"collector_version":"featureapp-geometry-v1","read_status":"observed","session_id":"s",
            "webview_instance_id":"v","document_generation":2,"document_id":"doc",
            "selected_observation_id":"o","started_elapsed_realtime_ms":999,"finished_elapsed_realtime_ms":1011,
            "attempts":[attempt],"host_before":host,"host_after":after,"web":web,"binding_valid":True,"host_stable":True}


def bound(g=None):
    g=geometry() if g is None else g
    return {"status":"OK","geometry":g,"geometry_evidence":sources.geometry_evidence(g,"s")}


def condition(record): return relation.evaluate(record)[relation.ATOM_ID]


class GeometryRelationTests(unittest.TestCase):
    def test_baseline_and_rotation(self):
        b=bound();self.assertEqual(state(condition(b)),"F")
        for h in (b["geometry"]["host_before"],b["geometry"]["host_after"]):
            h.update(width_px=1800,height_px=1080,content_width_px=1800,content_height_px=1080)
        b["geometry"]["web"]["fields"]["visual_viewport_width"]["value"]=720
        b["geometry"]["web"]["fields"]["visual_viewport_height"]["value"]=432
        self.assertEqual(state(condition(b)),"F")

    def test_real_visual_zoom_and_dpr_not_density(self):
        b=bound();f=b["geometry"]["web"]["fields"]
        f["visual_viewport_scale"]["value"]=1.25
        for axis in ("width","height"):f["visual_viewport_"+axis]["value"]/=1.25
        b["geometry"]["host_before"]["density"]=100
        self.assertEqual(state(condition(b)),"F")

    def test_no_insets_subtraction_and_nonzero_padding_unestablished(self):
        b=bound();g=b["geometry"]
        for h in (g["host_before"],g["host_after"]):
            h["root_window_insets"]={"system_window_top_px":100,"system_window_bottom_px":100}
        self.assertEqual(state(condition(b)),"F")
        for h in (g["host_before"],g["host_after"]):
            h.update(padding_left_px=10,padding_right_px=10,content_width_px=1060,
                     root_window_insets={"system_window_top_px":100,"system_window_bottom_px":100})
        g["web"]["fields"]["visual_viewport_width"]["value"]=424
        self.assertEqual(state(condition(b)),"U")

    def test_stable_contradiction_remains_true(self):
        g=geometry();g["web"]["fields"]["visual_viewport_height"]["value"]=851
        self.assertTrue(sources.geometry_evidence(g,"s")["usable_window"])
        self.assertEqual(state(condition(bound(g))),"T")

    def test_missing_axis_or_logic(self):
        g=geometry();f=g["web"]["fields"];f["visual_viewport_width"]["value"]=None
        self.assertEqual(state(condition(bound(g))),"U")
        f["visual_viewport_height"]["value"]=851
        self.assertEqual(state(condition(bound(g))),"T")
        self.assertEqual(negate("U"),"U");self.assertEqual(logic(["T","U"],"OR"),"T")

    def test_missing_wrong_zero_negative_nonfinite_scale(self):
        for value in (None,0,-1,"1",True,float("nan"),float("inf")):
            with self.subTest(value=value):
                g=geometry();g["web"]["fields"]["visual_viewport_scale"]["value"]=value
                self.assertEqual(state(condition(bound(g))),"U")

    def test_host_callback_missing_or_stale_is_not_filled_or_used(self):
        g=geometry();g["host_before"]["scale"]={"status":"observed","callback_value":999,"document_generation":1}
        g["host_before"]["diagnostic_get_scale"]["value"]=999
        self.assertEqual(state(condition(bound(g))),"F")
        g["web"]["fields"]["visual_viewport_scale"]["value"]=None
        self.assertEqual(state(condition(bound(g))),"U")

    def test_labels_scenario_target_do_not_predict(self):
        a=bound();b=deepcopy(a);b.update(phase="attack",label=1,process_type="A",environment="special",target=999)
        self.assertEqual(condition(a),condition(b))

    def test_not_equality_smaller_viewport_is_valid(self):
        g=geometry();g["web"]["fields"]["visual_viewport_height"]["value"]=400
        self.assertEqual(state(condition(bound(g))),"F")

    def test_fixed_tolerance_boundary(self):
        g=geometry();g["web"]["fields"]["visual_viewport_height"]["value"]=(1802)/2.5
        self.assertEqual(state(condition(bound(g))),"F")
        g["web"]["fields"]["visual_viewport_height"]["value"]=(1803)/2.5
        self.assertEqual(state(condition(bound(g))),"T")

    def test_host_transform_domain(self):
        g=geometry();g["host_before"]["view_scale_x"]=2
        self.assertEqual(state(condition(bound(g))),"U")


class GeometrySourceTests(unittest.TestCase):
    def test_current_window_bound(self): self.assertTrue(sources.geometry_evidence(geometry(),"s")["usable_window"])

    def test_cross_session_or_document_or_observation_is_failed(self):
        for key,value in (("session_id","foreign"),("document_generation",99),("observation_id","old")):
            g=geometry();g["web"]["binding"][key]=value
            self.assertEqual(sources.geometry_evidence(g,"s")["evaluation_status"],"FAILED")

    def test_missing_not_failed_but_runtime_error_failed(self):
        self.assertEqual(sources.geometry_evidence(None,"s")["evaluation_status"],"OK")
        g=geometry();g.update(read_status="runtime_error",reason="parse_error")
        self.assertEqual(sources.geometry_evidence(g,"s")["evaluation_status"],"FAILED")

    def test_duplicate_or_stale_selection_failed(self):
        g=geometry();g["attempts"].append(deepcopy(g["attempts"][0]))
        self.assertEqual(sources.geometry_evidence(g,"s")["evaluation_status"],"FAILED")

    def test_host_change_not_contradiction_triggers_u(self):
        g=geometry();g["host_after"]["sequence"]["layout"]+=1
        self.assertFalse(sources.geometry_evidence(g,"s")["usable_window"])
        self.assertEqual(state(condition(bound(g))),"U")

    def test_clocks_not_subtracted_across_domains(self):
        g=geometry();g["web"]["clock"].update(epoch_start_ms=1e12,epoch_end_ms=1e12+1,performance_start_ms=4,performance_end_ms=5)
        self.assertTrue(sources.geometry_evidence(g,"s")["usable_window"])
        g["host_after"]["clock"]["elapsed_realtime_ms"]=2801;g["finished_elapsed_realtime_ms"]=2802
        self.assertFalse(sources.geometry_evidence(g,"s")["usable_window"])

    def test_legacy_v14_rejected_new_binding_without_modifying_old_entry(self):
        raw={"raw_payload_archive_schema_version":"expanded-raw-payload-v1","session_id":"s",
             "canonical_received_payload":{"session_id":"s","schema_version":"expanded-v2.2-status",
                 "collector_app":"featureapp","collection_manifest":{"collector_version_code":14}}}
        b=sources.bind_current(raw,session_id="s",source_reference="fixture")
        self.assertEqual(b["status"],"FAILED")
        raw["canonical_received_payload"]["collection_manifest"]["collector_version_code"]=15
        raw["canonical_received_payload"]["collection_manifest"]["collector_version_name"]="1.6.8-expanded-v2.2-geometry"
        b=sources.bind_current(raw,session_id="s",source_reference="fixture")
        self.assertEqual(b["status"],"OK");self.assertEqual(state(condition(b)),"U")

    def test_malformed_collection_status_is_failed_not_exception(self):
        for value in (None, [], "observed"):
            raw={"raw_payload_archive_schema_version":"expanded-raw-payload-v1","session_id":"s",
                 "canonical_received_payload":{"session_id":"s","schema_version":"expanded-v2.2-status",
                     "collector_app":"featureapp","collection_manifest":{"collector_version_code":15,"collector_version_name":"1.6.8-expanded-v2.2-geometry"},
                     "collection_status":value}}
            b=sources.bind_current(raw,session_id="s",source_reference="fixture")
            self.assertEqual(b["status"],"FAILED")

    def test_malformed_web_fields_is_unknown_not_exception(self):
        g=geometry();g["web"]["fields"]=None
        self.assertEqual(state(condition(bound(g))),"U")

    def test_nested_malformed_geometry_is_retained_as_failure_or_unknown(self):
        for section,key,value in (("host_before","clock",None),("host_before","sequence",[1]),
                                  ("web","clock",None),("web","binding",[])):
            g=geometry();g[section][key]=value
            e=sources.geometry_evidence(g,"s")
            self.assertFalse(e["usable_window"])
        g=geometry();g["attempts"][0]["observation_id"]=["invalid"]
        self.assertEqual(sources.geometry_evidence(g,"s")["evaluation_status"],"FAILED")

    def test_v16_explicit_error_fix_identity_and_wrong_pair_rejected(self):
        raw={"raw_payload_archive_schema_version":"expanded-raw-payload-v1","session_id":"s",
             "canonical_received_payload":{"session_id":"s","schema_version":"expanded-v2.2-status",
                 "collector_app":"featureapp","collection_manifest":{"collector_version_code":16,
                     "collector_version_name":"1.6.9-expanded-v2.2-geometry"},
                 "collection_observations":{"webview_geometry":geometry()}}}
        b=sources.bind_current(raw,session_id="s",source_reference="fixture")
        self.assertEqual(b["status"],"OK");self.assertEqual(b["geometry_evidence"]["evaluation_status"],"FAILED")
        raw["canonical_received_payload"]["collection_observations"]["webview_geometry"]["collector_version"]="featureapp-geometry-v1.1"
        b=sources.bind_current(raw,session_id="s",source_reference="fixture")
        self.assertTrue(b["geometry_evidence"]["usable_window"])
        raw["canonical_received_payload"]["collection_manifest"]["collector_version_code"]=17
        self.assertEqual(sources.bind_current(raw,session_id="s",source_reference="fixture")["status"],"FAILED")

    def test_destroy_before_dispatch_keeps_unavailable_and_manifest_identity(self):
        payload={"session_id":"s","schema_version":"expanded-v2.2-status","collector_app":"featureapp",
                 "collection_manifest":{"collector_version_code":16,"collector_version_name":"1.6.9-expanded-v2.2-geometry",
                                        "geometry_observer_version":"featureapp-geometry-v1.1"},
                 "collection_observations":{"webview_geometry":{"schema_version":sources.GEOMETRY_SCHEMA,
                     "session_id":"s","read_status":"unavailable","reason":"activity_destroyed_before_geometry_dispatch"}}}
        raw={"session_id":"s","raw_payload_archive_schema_version":"expanded-raw-payload-v1",
             "canonical_received_payload":payload}
        b=sources.bind_current(raw,session_id="s",source_reference="fixture")
        self.assertEqual(state(condition(b)),"U")
        self.assertIn("activity_destroyed_before_geometry_dispatch",b["geometry_evidence"]["issues"][0])
        self.assertNotIn("collector_version",b["geometry"])
        payload["collection_manifest"]["geometry_observer_version"]="unknown-version"
        b=sources.bind_current(raw,session_id="s",source_reference="fixture")
        self.assertEqual(condition(b)["evaluation_status"],"FAILED")


if __name__ == "__main__": unittest.main()
