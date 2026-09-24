"""R09 saved-cost and explanation audit. No predict(), selector or encoder fit."""
import csv
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark import read, lines, write, sha, require, frozen_api, NOW

STAGES = ("R05_primary", "R06_sources", "R07_representation", "R08_validation")


def table(path, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open("x", newline="") as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, tuple))
                             else "null" if v is None else v for k, v in row.items()})


def audit_one(model, row, cells, contracts):
    """Check recorded states with truth tables; do not generate a new prediction."""
    require(row["model_id"] == model.model_id, "MODEL_ID")
    if model.status in ("EMPTY_MODEL", "FAILED"):
        require(row["decision"] == model.status and row.get("logical_state") is None, "EMPTY_FAILED_SEPARATION")
        require(not row.get("atom_explanations") and not row.get("clause_explanations"), "UNUSED_RULE_EXPLANATION")
        require(row["selected_atoms_expected"] == 0 and row["clauses_expected"] == 0, "EMPTY_DENOMINATOR")
        return {"triggered_clause_ids": [], "status": "PASS_NONEXECUTABLE_STATE", "field_n": 0}
    if model.constant:
        require(row["decision"] == model.constant, "CONSTANT_DECISION")
        require(row["logical_state"] == ("F" if model.constant=="NO_ALERT" else "U"), "CONSTANT_LOGIC")
        require(not row["atom_explanations"] and not row["clause_explanations"], "CONSTANT_UNUSED_RULE")
        return {"triggered_clause_ids": [], "status": "PASS_CONSTANT", "field_n": 0}
    atom_rows = row["atom_explanations"]
    clause_rows = row["clause_explanations"]
    require(len(atom_rows)==len(model.atoms) and {a["atom_id"] for a in atom_rows} == {a.atom_id for a in model.atoms}, "ATOM_MEMBERSHIP")
    require(len(clause_rows)==len(model.clauses) and {c["clause_id"] for c in clause_rows} == {c.id for c in model.clauses}, "CLAUSE_MEMBERSHIP")
    indexed = {a["atom_id"]: a for a in atom_rows}
    states, fields = {}, set()
    for atom in model.atoms:
        saved = indexed[atom.atom_id]
        expected_metadata = dict(orientation=atom.orientation, aliases=list(atom.aliases), source_groups=list(atom.sources),
                                 surfaces=list(atom.surfaces), provenance=atom.provenance)
        require(all(saved[k] == v for k,v in expected_metadata.items()), "ATOM_METADATA_ALIAS_FIELDS_ORIENTATION")
        try:
            state = contracts.state(cells[atom.atom_id])
        except (ValueError, KeyError):
            state = None
        states[atom.atom_id] = state
        require(saved["state"] == state, "ATOM_CURRENT_CACHE_STATE")
        if state is not None:
            require(saved["reason"] == cells[atom.atom_id].get("reason"), "ATOM_REASON")
        provenance = atom.provenance
        fields.update(provenance.get("field_refs", []))
        if "field" in provenance: fields.add(provenance["field"])
        for alias in provenance.get("contributing_aliases", []): fields.update(alias["field_refs"])
        require(set(saved) == {"atom_id","state","reason","orientation","aliases","source_groups","surfaces","provenance"}, "UNEXPECTED_NARRATIVE_OR_INTENT_FIELD")
    clause_states = []
    triggered = []
    by_clause = {c["clause_id"]:c for c in clause_rows}
    for clause in model.clauses:
        saved = by_clause[clause.id]
        require(saved["literals"] == [{"atom_id": l.atom_id,"polarity": l.polarity} for l in clause.literals], "LITERAL_POLARITY")
        literals = [states[l.atom_id] if l.polarity=="POSITIVE" or states[l.atom_id] is None
                    else contracts.negate(states[l.atom_id]) for l in clause.literals]
        expected = None if None in literals else contracts.logic(literals,"AND")
        require(saved["state"] == expected, "CLAUSE_TRIVALENT_STATE")
        clause_states.append(expected)
        if expected=="T": triggered.append(clause.id)
    require(row["selected_atoms_available"]==sum(s in ("T","F") for s in states.values()), "ATOM_AVAILABILITY")
    require(row["selected_atoms_expected"]==len(model.atoms) and row["clauses_expected"]==len(model.clauses), "COVERAGE_EXPECTATIONS")
    require(row["clauses_defined"]==sum(s in ("T","F") for s in clause_states), "CLAUSE_AVAILABILITY")
    if None in states.values():
        require(row["decision"]=="FAILED" and row["logical_state"] is None, "FAILURE_NOT_UNKNOWN")
    else:
        state = contracts.logic(clause_states,"OR")
        require(row["logical_state"]==state and row["decision"]=={"T":"MANIPULATION_ALERT","F":"NO_ALERT","U":"INSUFFICIENT_EVIDENCE"}[state], "RECORDED_DECISION_LOGIC")
        require(row["failure_reason"] is None, "SUCCESS_WITH_FAILURE_REASON")
    return {"triggered_clause_ids":triggered,"status":"PASS_LITERAL_AND_CURRENT_CACHE_CONSISTENCY","field_n":len(fields)}


def main(out):
    study = out.parent
    freeze = study / "R04_freeze_r1"
    models, predictor, baselines, contracts, modules, rejected = frozen_api(freeze)
    budget = read(study / "REAL_RESEARCH_BUDGET/ledger.json")
    candidates = contracts.ledger()
    candidate_by_id = {c["atom_id"]:c for c in candidates}
    index = read(freeze / "DATA_INDEX.json")
    historical = read(freeze / "data/historical_predictions.json")
    proofs = read(freeze / "HISTORICAL_INPUT_PROOF.json")
    fits, model_rows, audits, lineage, access_inventory = [], [], [], [], []
    unique_models, stage_counts = set(), {}
    for stage in STAGES:
        directory = study / stage
        jobs = lines(directory / "expected_model_units.jsonl")
        receipts = read(directory / "dispatch/model_receipts.json")
        stage_count = 0
        for job in jobs:
            uid = job["model_unit_id"]
            folder = directory / "dispatch/jobs" / uid
            source_uid = job.get("reuse_model_unit_id") or uid
            source = Path(budget["jobs"][source_uid]["artifact_directory"])
            path = source / "model.json"
            model = models.load_model(path)
            raw_model = read(path)
            unique_models.add(model.model_id)
            require(receipts[uid]["model_id"]==model.model_id, "RECEIPT_MODEL_ID")
            freeze_receipt = read(source / "MODEL_FREEZE_RECEIPT.json")
            require(sha(path)==freeze_receipt["sha256"], "SAVED_MODEL_CHANGED")
            predictions = lines(folder / "predictions.jsonl")
            require(len(predictions)==len(job["outer_test_ids"]) and {p["opaque_id"] for p in predictions}==set(job["outer_test_ids"]), "SAVED_OOF_MEMBERSHIP")
            if source_uid != uid:
                reuse = read(folder / "REUSE_RECEIPT.json")
                require(reuse["model_id"]==model.model_id and reuse["new_fit"] is False and reuse["model_bytes_rewritten"] is False, "REUSE_RECEIPT")
            metadata = {k:job[k] for k in ("experiment_id","split_id","fold_id","method_id","operating_point","source_condition","input_view","train_membership_digest")}
            metadata.update(model_unit_id=uid, source_model_unit_id=source_uid, model_id=model.model_id,
                model_status=model.status, model_path=str(path), model_sha256=sha(path),
                is_exact_reuse=uid!=source_uid, model_freeze_time=model.fit.get("freeze_time"),
                train_ids=model.fit["train_ids"], outer_test_ids=job["outer_test_ids"])
            model_rows.append(dict(metadata, complexity=raw_model["complexity"],
                process_job_elapsed_seconds=budget["jobs"][uid].get("elapsed_seconds"),
                cost_kind="EXACT_REUSE_NO_NEW_FIT" if uid!=source_uid else "SAVED_FIT" if job["fit_job_id"] else "FIXED_BASELINE_NO_FIT"))
            if job["fit_job_id"] and uid==source_uid:
                training=read(folder / "training.json")
                fits.append(dict(metadata, fit_job_id=job["fit_job_id"],
                    candidate_support_selection_validation_combined_seconds=model.fit.get("elapsed_seconds"),
                    combined_timer_status="RECORDED" if model.fit.get("elapsed_seconds") is not None else "NOT_RECORDED",
                    transform_only_seconds=None, transform_only_status="NOT_RECORDED",
                    candidate_support_only_seconds=None, candidate_support_only_status="NOT_RECORDED",
                    selection_solver_only_seconds=None, selection_solver_only_status="NOT_RECORDED",
                    audit_only_seconds=None, audit_only_status="NOT_RECORDED",
                    process_job_elapsed_seconds=budget["jobs"][uid].get("elapsed_seconds"),
                    candidate_pool_size=model.fit.get("candidate_pool_size"), registered_clause_count=model.fit.get("registered_clause_count"),
                    saved_candidate_manifest_n=len(training["candidate_manifest"]), saved_support_n=len(training["support"]),
                    input_atom_count=len(model.view["input_atom_ids"]), complexity=raw_model["complexity"],
                    solver_status=model.fit["status"], solver=model.fit.get("solver"), gap=model.fit.get("gap"),
                    best_bound=model.fit.get("best_bound"), infeasibility_proved=model.fit.get("infeasibility_proved"),
                    gap_status="RECORDED" if model.fit.get("gap") is not None else "NOT_APPLICABLE_OR_NOT_RECORDED",
                    clean_denominator=model.fit.get("clean_denominator"), clean_budget_count=model.fit.get("clean_budget_count"),
                    recorded_training_feasible=model.fit.get("training_result",{}).get("feasible"),
                    cg_pricing_seconds=None, cg_status="NOT_IMPLEMENTED_FINITE_IP_IS_NOT_CG"))
            # Cache-only transforms for checking explanations, never new predictions.
            if model.method_id != "HISTORICAL_SEVEN" and model.status=="FITTED" or (model.method_id=="DIRECT_CORE_OR"):
                raw = {oid: read(freeze/index[oid]["features"])["features"] for oid in job["outer_test_ids"]}
                if job["input_view"]=="core":
                    cells, canonical_atoms = baselines.project_core(raw, candidates, job["source_condition"])
                    by_id = {a.atom_id:a for a in canonical_atoms}
                    require(all(a==by_id[a.atom_id] for a in model.atoms), "MODEL_CANONICAL_PROVENANCE_NOT_FROZEN_METADATA")
                else:
                    cells = {oid:baselines.transform_numeric(r, model.encoder) for oid,r in raw.items()}
                    definitions = {a.atom_id:a for a in baselines.single_surface_definitions(job["input_view"])}
                    require(model.encoder["fold_id"]==job["fold_id"] and model.encoder["train_ids"]==job["train_ids"], "ENCODER_FOLD_TRAIN_MEMBERSHIP")
                    for a in model.atoms:
                        if a.orientation=="CONTROL_LE":
                            spec=model.encoder["numeric"]["UNFITTED_CONTROL:"+a.provenance["field"]]
                            require(a.atom_id in spec["atom_ids"] and a.provenance["threshold"]==spec["thresholds"][spec["atom_ids"].index(a.atom_id)], "ENCODER_FROZEN_THRESHOLD")
                        else: require(a==definitions[a.atom_id], "SINGLE_METADATA_WHITELIST")
            else: cells={oid:{} for oid in job["outer_test_ids"]}
            for p in predictions:
                oid=p["opaque_id"]
                info={**{k:metadata[k] for k in ("experiment_id","split_id","fold_id","method_id","operating_point","source_condition","input_view","model_unit_id","source_model_unit_id","model_id","is_exact_reuse")},
                    "opaque_id":oid,"decision":p["decision"],"logical_state":p.get("logical_state"),
                    "model_status":model.status,"manual_semantic_review":"NOT_REVIEWED",
                    "current_field_semantics":"NOT_REVIEWED_ORIGINAL_MEASUREMENT_MANUAL_CHECK",
                    "scientific_independent_stage_key":oid,"model_stage_link_key":model.model_id+":"+oid,
                    "prediction_ref":str(folder/"predictions.jsonl"),"input_cache_ref":str(freeze/index[oid]["features"])}
                try:
                    for k in ("fold_id","method_id","source_condition","operating_point","input_view","model_unit_id"):
                        require(p[k]==job[k], "ROW_JOB_BINDING:"+k)
                    if model.method_id=="HISTORICAL_SEVEN":
                        require(proofs[oid]["status"]=="EXACT_INPUT_AND_METHOD_MATCH", "HISTORY_INPUT_PROOF")
                        require(p["decision"]==historical[oid]["risk"]["decision"], "HISTORY_SAVED_DECISION")
                        require(p["historical_contract"]==baselines.historical_seven_contract(), "HISTORY_CONTRACT")
                        require(not p.get("atom_explanations") and not p.get("clause_explanations"), "HISTORY_ADAPTER_INVENTED_EXPLANATION")
                        info.update(status="PASS_SAVED_HISTORY_ADAPTER_ONLY", literal_explanation_status="NOT_EVALUABLE_SAVED_ADAPTER", triggered_clause_ids=None, field_n=None)
                    else:
                        info.update(audit_one(model,p,cells[oid],contracts), literal_explanation_status="PROGRAMMATICALLY_CHECKED")
                    info["error"]=None
                except (ValueError, KeyError, TypeError) as exc:
                    info.update(status="FAILED_AUDIT",error=type(exc).__name__+":"+str(exc))
                audits.append(info)
                stage_count+=1
            lineage.append(dict(model_unit_id=uid,source_model_unit_id=source_uid,model_id=model.model_id,
                predictions_sha256=sha(folder/"predictions.jsonl"),model_sha256=sha(path),
                n=len(predictions),reuse=uid!=source_uid))
            if source_uid==uid:
                events=read(source/"access_log.json")
                access_inventory.append(dict(model_unit_id=uid, events=Counter(e["event"] for e in events),
                    source_ref=str(source/"access_log.json"), timing_derivation="NO_EVENT_DIFFERENCE_USED_AS_SUBSTAGE_TIMER"))
        stage_counts[stage]=stage_count
    require(len(fits)==71 and len(model_rows)==114 and len(unique_models)==111 and len(audits)==4374, "EXPECTED_RECONCILIATION")
    require(len({f["fit_job_id"] for f in fits})==71, "DUPLICATE_FIT")
    table(out/"existing_training_costs.csv",fits)
    table(out/"model_complexity_solver.csv",model_rows)
    table(out/"explanation_audit.csv",audits)
    write(out/"model_source_lineage.json",lineage)
    write(out/"saved_access_event_inventory.json",access_inventory)
    failures=[a for a in audits if a["status"]=="FAILED_AUDIT"]
    write(out/"explanation_audit_summary.json",dict(status="PASS" if not failures else "FAILED",utc=NOW(),
        expected_records=4374,audited_records=len(audits),unique_supervised_stages=len({a["opaque_id"] for a in audits}),
        unique_model_stage_links=len({a["model_stage_link_key"] for a in audits}),
        stage_counts=stage_counts,status_counts=Counter(a["status"] for a in audits),
        failure_n=len(failures),failures=failures,manual_review="NOT_REVIEWED",manual_record_n=len(audits),
        original_fingerprint_semantics="NOT_REVIEWED_CACHE_AND_FROZEN_FIELD_REFERENCE_CHECK_ONLY",
        no_intent_attribution="STRUCTURED_EXPLANATION_SCHEMA_HAS_NO_INTENT_CLAIM_FIELD_NOT_A_MANUAL_SEMANTIC_JUDGMENT",
        new_fit_jobs=0,new_scientific_predictions=0,existing_fit_n=len(fits),model_units=len(model_rows),
        distinct_models=len(unique_models),fit_statuses=Counter(f["model_status"] for f in fits),
        solver_statuses=Counter(f["solver_status"] for f in fits),module_paths=modules,forbidden_call_attempts=rejected))
    write(out/"NOT_RECORDED_NOT_REVIEWED.json",{
        "training_substages":{"transform_only":"NOT_RECORDED","candidate_support_only":"NOT_RECORDED",
            "selection_solver_only":"NOT_RECORDED","audit_only":"NOT_RECORDED","cg_pricing":"NOT_IMPLEMENTED"},
        "inference_substages":{"boolean_only":"NOT_RECORDED_INTERLEAVED_FROZEN_PREDICTOR",
            "explanation_only":"NOT_RECORDED_INTERLEAVED_FROZEN_PREDICTOR","raw_capture":"NOT_MEASURED",
            "relation_extraction":"NOT_MEASURED","historical_detector":"NOT_EVALUABLE_SAVED_LOOKUP_NOT_RUNTIME"},
        "manual_semantics":"NOT_REVIEWED","manual_labels_modified":False,"labels_used_to_choose_models":False})
    print(json.dumps({"fits":len(fits),"models":len(model_rows),"records":len(audits),"audit_failures":len(failures)}))


if __name__=="__main__":
    main(Path(sys.argv[1]).resolve())
