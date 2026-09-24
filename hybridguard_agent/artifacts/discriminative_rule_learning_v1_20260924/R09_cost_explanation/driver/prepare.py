"""Seal R09 timing specifications before real inference; read only old resources."""
from pathlib import Path
import hashlib
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from benchmark import read, lines, write, sha, require, NOW, VERSION


def main(out):
    study=out.parent
    freeze=study/"R04_freeze_r1"
    frozen_study=freeze/"snapshot/hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924"
    binding=read(frozen_study/"R01_protocol/PROTOCOL_BINDING.json")
    candidates=lines(frozen_study/"R01_protocol/CANDIDATE_LEDGER.jsonl")
    configs={Path(ref).stem:read(freeze/"snapshot"/ref) for ref in binding["config_refs"]}
    computed=hashlib.sha256(json.dumps({"configs":configs,"candidates":candidates},sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
    require(computed==binding["protocol_digest"]=="4ab418434ea79085746c2761a1314751b7c83a538813ae3872b3d9721a2823d4","PROTOCOL_DIGEST")
    require(read(out/"synthetic_validation.json")["status"]=="PASS","SYNTHETIC_GATE")
    require(read(out/"checks/frozen_verify_stdout.json")["verified_file_n"]==3298,"FROZEN_STARTUP_VERIFICATION")
    index=read(freeze/"DATA_INDEX.json")
    jobs=[j for j in lines(freeze/"expected_model_units.jsonl") if j["experiment_id"]=="R05_PRIMARY" and j["method_id"]=="GREEDY_OR" and j["operating_point"]=="OP05"]
    require(len(jobs)==3,"EXACT_PRIMARY_JOBS")
    models=[]
    resources=set()
    def bind(path):
        path=Path(path).resolve();resources.add(path)
        return {"path":str(path),"sha256":sha(path),"bytes":path.stat().st_size}
    for job in sorted(jobs,key=lambda j:j["fold_id"]):
        folder=study/"R05_primary/dispatch/jobs"/job["model_unit_id"]
        model=read(folder/"model.json")
        predictions=lines(folder/"predictions.jsonl")
        receipt=read(folder/"MODEL_FREEZE_RECEIPT.json")
        require(model["model_id"]==receipt["model_id"] and sha(folder/"model.json")==receipt["sha256"],"MODEL_RECEIPT_BYTES")
        require({r["opaque_id"] for r in predictions}==set(job["outer_test_ids"]) and len(predictions)==len(job["outer_test_ids"]),"INPUT_MEMBERSHIP")
        require(model["fit"]["train_ids"]==job["train_ids"] and not set(job["train_ids"])&set(job["outer_test_ids"]),"TRAIN_BINDING")
        model_binding=bind(folder/"model.json")
        prediction_binding=bind(folder/"predictions.jsonl")
        bind(folder/"MODEL_FREEZE_RECEIPT.json")
        models.append({"fold_id":job["fold_id"],"model_unit_id":job["model_unit_id"],"model_id":model["model_id"],
            "model_path":model_binding["path"],"model_sha256":model_binding["sha256"],
            "predictions_path":prediction_binding["path"],"predictions_sha256":prediction_binding["sha256"],
            "binding":model["binding"],"train_ids":job["train_ids"],"outer_test_ids":sorted(job["outer_test_ids"]),
            "model_freeze_time":model["fit"]["freeze_time"],"source_created_at":receipt["saved_and_loaded_at"],
            "inputs":[dict(opaque_id=oid,**bind(freeze/index[oid]["features"])) for oid in sorted(job["outer_test_ids"])]})
    budget_path=study/"REAL_RESEARCH_BUDGET/ledger.json"
    spec=next(e for e in configs["experiment_matrix"]["experiments"] if e["id"]=="R09_COST")
    explanation=next(e for e in configs["experiment_matrix"]["experiments"] if e["id"]=="R09_EXPLANATION")
    protocol={"schema_version":VERSION,"sealed_at":NOW(),"protocol_digest_recomputed":computed,
        "freeze_root":str(freeze),"freeze_manifest_digest":sha(freeze/"FREEZE_MANIFEST.json"),
        "resource_manifest_digest":sha(freeze/"RESOURCE_MANIFEST.json"),"cost_spec":spec,"explanation_spec":explanation,
        "new_fit_jobs":0,"record_role":"BENCHMARK_ONLY","model_scope":"THREE_R05_GREEDY_OR_OP05_LOEO_PRIMARY_MODELS",
        "comparison_scope":"No other online comparator specified; ALL_SAVED_FITS is offline training-cost scope",
        "input_order":"GLOBAL_ASCENDING_OPAQUE_ID_ACROSS_ALL_THREE_FOLDS_EVERY_PASS",
        "process_order":[e["fold_id"] for e in models],"cold_passes":1,"warmup_passes":1,"timed_passes":5,
        "clock":"MONOTONIC_PERF_COUNTER_NS","clock_info":__import__('time').get_clock_info("perf_counter").__dict__,
        "cold_definition":"3 fresh sequentially launched workers, one per fixed model; cold pass includes launch/module/model loads and all 162 samples; OS page cache NOT cleared",
        "worker_lifetime":"same 3 workers remain alive for warmup and all 5 timed passes; no concurrent prediction requests",
        "boundaries":{
            "cold_pass_inclusive_ns":"parent before launching first worker through last cold sample audit fsync",
            "parent_process_launch_through_ready_ns":"Popen to ready receipt, includes interpreter/driver/module/model/resource loading",
            "module_load_ns":"frozen module imports and no-learning guard installation",
            "model_load_including_validation_ns":"frozen load_model including JSON read/parse, structure, model ID and complexity validation",
            "cached_input_read_parse_ns":"read/parse exactly one R02 cached row on every call",
            "fixed_feature_conversion_ns":"unmodified project_core on complete SRC-111 candidate metadata and one cached row, including alias/polarity/availability",
            "predict_including_explanation_and_model_integrity_ns":"unmodified predict plus two dispatcher metadata fields; includes model content serialization/hash, Boolean logic and explanation construction",
            "boolean_only_ns":"NOT_RECORDED: interleaved frozen predictor, null; no profiling/subtraction estimate",
            "explanation_only_ns":"NOT_RECORDED: interleaved frozen predictor, null; no profiling/subtraction estimate",
            "semantic_verification_ns":"full dictionary equality to saved closed prediction, all fields",
            "prediction_serialization_ns":"JSON encoding full prediction for audit digest",
            "sample_inclusive_ns":"worker cached input read through semantic digest/result fields, before timing-envelope JSON/IPC",
            "ipc_request_response_inclusive_ns":"parent request encoding/write/flush through worker response parse; includes sample and IPC",
            "audit_serialization_write_flush_ns":"per-pass sum of directly measured parent timing-record JSON/write/flush",
            "audit_fsync_ns":"one fsync per pass measured directly",
            "elapsed_inclusive_ns":"parent wall time for complete pass, cold includes startup, warm/timed includes IPC/audit"},
        "primary_summary":"all five timed passes; per-pass plus pooled count/median/p95 (nearest-rank)/mean; no best-pass selection",
        "unmeasured":["original fingerprint collection","relation extraction","Boolean-only time","explanation-only time","old detector runtime"],
        "failure_policy":"one attempt only; stop on first worker/semantic error or budget expiry; retain failed/raw rows and mark every missing expected row NOT_RUN with null times; no retries",
        "shared_budget_ledger":str(budget_path),"budget_link":"TIMING_BUDGET_LEDGER.json",
        "benchmark_wall_cap_seconds":300,"budget_fit_increment":0,"budget_expansion":False,
        "runtime":read(freeze/"RESOURCE_MANIFEST.json")["runtime"],"resource_preflight_outside_pass_timers":True,
        "scientific_predictions_overwritten":False,"new_independent_samples":0}
    write(out/"benchmark_protocol.json",protocol)
    write(out/"model_input_manifest.json",{"models":models,"unique_test_ids":162,"shared_budget_ledger_sha256":sha(budget_path)})
    ordered=sorted((oid,m["fold_id"],m["model_id"]) for m in models for oid in m["outer_test_ids"])
    expected=[]
    for phase,count in (("COLD",1),("WARMUP",1),("TIMED",5)):
        for repeat in range(1,count+1):
            for oid,fold,model_id in ordered:
                expected.append(dict(sequence=len(expected)+1,phase=phase,pass_number=repeat,fold_id=fold,model_id=model_id,opaque_id=oid,record_role="BENCHMARK_ONLY"))
    require(len(expected)==1134 and len({x[0] for x in ordered})==162,"EXPECTED_REPEATS")
    with (out/"expected_repeats.jsonl").open("x") as f:
        for row in expected:f.write(json.dumps(row)+"\n")
    saved=[]
    for stage in ("R05_primary","R06_sources","R07_representation","R08_validation"):
        for p in (study/stage).rglob('*'):
            if p.is_file() and (p.name in {"model.json","training.json","predictions.jsonl","REUSE_RECEIPT.json","MODEL_FREEZE_RECEIPT.json","PREDICTION_CLOSURE.json","model_receipts.json","access_log.json"} or p.name.startswith('expected_')):
                saved.append({"path":str(p),"bytes":p.stat().st_size,"sha256":sha(p)})
    write(out/"SAVED_ARTIFACT_MANIFEST.json",{"files":saved,"purpose":"cost/explanation provenance; includes repeated linked records, not independent evidence"})
    for p in (out/"driver").glob('*.py'):bind(p)
    for p in (freeze/"snapshot/hybridguard_agent/research/rule_learning").glob('*.py'):bind(p)
    for ref in binding["config_refs"]:bind(freeze/"snapshot"/ref)
    for p in [freeze/"FREEZE_MANIFEST.json",freeze/"RESOURCE_MANIFEST.json",freeze/"protocol.json",freeze/"DATA_INDEX.json",
              freeze/"dependencies/python/bin/python3.12",freeze/"expected_model_units.jsonl",budget_path,
              frozen_study/"R01_protocol/CANDIDATE_LEDGER.jsonl",frozen_study/"R01_protocol/PROTOCOL_BINDING.json",
              out/"benchmark_protocol.json",out/"model_input_manifest.json",out/"expected_repeats.jsonl",out/"synthetic_validation.json",
              out/"SAVED_ARTIFACT_MANIFEST.json",out/"R09_AUTHORIZATION.json"]:bind(p)
    write(out/"DRIVER_RESOURCE_MANIFEST.json",{"version":VERSION,"sealed_at":NOW(),"files":[{"path":str(p),"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(resources)],
        "learning_snapshot_manifest_reference":str(freeze/"RESOURCE_MANIFEST.json"),"all_snapshot_resources_verified_by_original_entry":3298,
        "learning_snapshot_modified":False,"driver_is_separate_from_learning_snapshot":True})
    print(json.dumps({"protocol_recomputed":computed,"models":3,"stages":162,"expected_repeats":len(expected),"bound_resources":len(resources)}))


if __name__=="__main__":main(Path(sys.argv[1]).resolve())
