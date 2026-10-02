#!/usr/bin/env python3
"""Fixed 12-stage MTC constrained reselection, followed by separate evaluation.

Only new output directories are writable. Original observations/models/results
are references. Evaluation is gated on all planned fits closing, including
negative EMPTY_MODEL/FAILED outcomes. No automatic reruns or model selection.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
SCHEMES = ("A", "B")
STAGES = ("GREEDY", "RETENTION")


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def stamp():
    return datetime.now(timezone.utc).isoformat()


def jsonl(path):
    with Path(path).open() as stream:
        for line in stream:
            yield json.loads(line)


def settings(out):
    target = out / "SETTINGS.json"
    if not target.exists():
        write(target, read(HERE / "SETTINGS.json"))
    value = read(target)
    if value != read(HERE / "SETTINGS.json"):
        raise ValueError("FIXED_EXPERIMENT_SETTINGS_DIFFER_FROM_REGISTERED_RUN")
    return value


def registry(config):
    rows = list(jsonl(ROOT / config["mtc_p2_registry"]))
    index = {r["sample_id"]: r for r in rows}
    if len(index) != len(rows):
        raise ValueError("DUPLICATE_P2_MEMBER")
    for split, ids in config["mtc_primary_ids"].items():
        actual = [r["sample_id"] for r in rows if r["analysis_role"] == "primary_representative" and r["split"] == split]
        if actual != ids:
            raise ValueError("FROZEN_P2_MEMBERSHIP_CHANGED")
    return index


def normal_evidence(config):
    # Reuse last round's assessment only. No score or label is passed to fit.
    result = {}
    for row in jsonl(ROOT / config["baseline_mtc_predictions"]):
        sid = row["sample_id"]
        if sid in result and result[sid] != row["normal_basis"]:
            raise ValueError("INCONSISTENT_SAVED_NORMAL_BASIS")
        result[sid] = row["normal_basis"]
    return result


def load_selected_mtc(index, ids, snapshot, *, allowed_ids):
    """Parse only selected P2 rows; unselected evaluation rows are not decoded."""
    if len(ids) != len(set(ids)) or not set(ids) <= set(allowed_ids):
        raise PermissionError("MTC_MEMBER_OUTSIDE_CURRENT_STAGE")
    wanted = defaultdict(dict)
    for sid in ids:
        item = index[sid]
        if item["source_line"] in wanted[item["source_view"]]:
            raise ValueError("DUPLICATE_MTC_SOURCE_REFERENCE")
        wanted[item["source_view"]][item["source_line"]] = sid
    observations, issues = {}, {}
    for view, lines in wanted.items():
        path = Path(snapshot) / (view + ".jsonl")
        try:
            with path.open() as stream:
                for number, line in enumerate(stream, 1):
                    if number not in lines:
                        continue
                    sid = lines[number]
                    try:
                        row = json.loads(line)
                        if row["sample_id"] != sid or row["dataset_view"] != view:
                            raise ValueError("P2_SOURCE_BINDING_MISMATCH")
                        observations[sid] = row
                    except (ValueError, KeyError, TypeError) as exc:
                        issues[sid] = f"{path}:{number}: {type(exc).__name__}: {exc}"
        except OSError as exc:
            issues.update({sid: f"{path}: {type(exc).__name__}: {exc}" for sid in lines.values()})
    for sid in ids:
        if sid not in observations and sid not in issues:
            issues[sid] = "PLANNED_MTC_SOURCE_ROW_MISSING"
    return observations, issues


def controlled_rows(source, ids, allowed_ids):
    if len(ids) != len(set(ids)) or not set(ids) <= set(allowed_ids):
        raise PermissionError("CONTROLLED_MEMBER_OUTSIDE_CURRENT_STAGE")
    rows = {sid: read(source / "inputs" / (sid + ".json")) for sid in ids}
    for sid, row in rows.items():
        if row["opaque_id"] != sid or row["observation_mode"] != "raw_observation_v1":
            raise ValueError("CONTROLLED_INPUT_ID_OR_MODE_MISMATCH")
    return rows


def controlled_metadata(source, ids):
    result = {}
    for sid in ids:
        row = read(source / "evaluation" / (sid + ".json"))
        if row["opaque_id"] != sid or row.get("proposed_supervised_member") is not True:
            raise ValueError("CONTROLLED_LABEL_MEMBER_MISMATCH")
        result[sid] = dict(row, supervised_label=row["proposed_supervised_label"])
    return result


def train(out):
    from hybridguard_agent.research import mtc_reselection_candidates as adapter
    from hybridguard_agent.research import mtc_constrained_reselection as engine

    config = settings(out)
    if (out / "FIT_CALLS.jsonl").exists() or (out / "models.json").exists():
        raise FileExistsError("Use a fresh output directory; no automatic refit")
    source = ROOT / config["controlled_source"]
    index, basis, defs = registry(config), normal_evidence(config), adapter.definitions()
    mtc_ids = config["mtc_normal_train_ids"]
    if any(index[sid]["split"] != "discovery" or index[sid]["analysis_role"] != "primary_representative"
           or not basis[sid]["supported"] for sid in mtc_ids):
        raise PermissionError("ONLY_FIXED_NORMAL_DISCOVERY_REPRESENTATIVES_CAN_TRAIN")
    eval_ids = config["mtc_primary_ids"]["development"] + config["mtc_primary_ids"]["reserved_validation"]
    groups = {index[sid]["group_id"] for sid in mtc_ids}
    if groups & {index[sid]["group_id"] for sid in eval_ids}:
        raise PermissionError("MTC_GROUP_CROSSES_TRAIN_AND_EVALUATION")
    original, issues = load_selected_mtc(index, mtc_ids, ROOT / config["mtc_snapshot"], allowed_ids=mtc_ids)
    if issues:
        write(out / "INPUT_ERRORS.json", issues)
        raise ValueError("Training source failure recorded; no missing member silently dropped")
    mtc_adapted = {sid: adapter.adapt_mtc(original[sid], defs) for sid in mtc_ids}
    mtc_raw = {sid: r["raw"] for sid, r in mtc_adapted.items()}
    mtc_meta = {sid: {"split": "discovery", "normal_basis": True, "group_id": index[sid]["group_id"]} for sid in mtc_ids}
    entries, attempts = [], []
    start = time.monotonic()
    with (out / "FIT_CALLS.jsonl").open("x") as log:
        for fold in config["folds"]:
            inputs = controlled_rows(source, fold["train_ids"], fold["train_ids"])
            raw = {sid: adapter.adapt_controlled(row, defs)["raw"] for sid, row in inputs.items()}
            metadata = controlled_metadata(source, fold["train_ids"])
            prepared = engine.prepare_fold(fold, raw, metadata, defs, mtc_raw, mtc_meta,
                mtc_train_ids=mtc_ids, mtc_evaluation_ids=eval_ids)
            write(out / "folds" / fold["fold_id"] / "encoder.json", prepared.encoder)
            write(out / "folds" / fold["fold_id"] / "atoms.json", [asdict(a) for a in prepared.atoms])
            for scheme in SCHEMES:
                initial, initial_training = None, None
                for stage in STAGES:
                    job_id = scheme + "__" + fold["fold_id"] + "__" + stage
                    dest = out / "trials" / job_id
                    event = {"job_id": job_id, "scheme": scheme, "fold_id": fold["fold_id"],
                             "stage": stage, "started_at": stamp(), "attempt": 1}
                    log.write(json.dumps(event) + "\n"); log.flush()
                    before = time.monotonic()
                    model, detail = (engine.fit_sparse(prepared, scheme=scheme) if stage == "GREEDY" else
                        engine.fit_retention(prepared, scheme=scheme, initial_model=initial, initial_training=initial_training))
                    dest.mkdir(parents=True, exist_ok=False)
                    engine.save_model(model, dest / "model.json")
                    write(dest / "training.json", detail)
                    restored = engine.load_model(dest / "model.json")
                    if restored.model_id != model.model_id or restored.encoder != prepared.encoder:
                        raise ValueError("SAVED_MODEL_OR_SHARED_ENCODER_MISMATCH")
                    entry = {"scheme": scheme, "fold_id": fold["fold_id"], "stage": stage,
                             "model_id": restored.model_id, "status": restored.status,
                             "path": str((dest / "model.json").relative_to(out)),
                             "training_path": str((dest / "training.json").relative_to(out)),
                             "selected_clauses": [asdict(c) for c in restored.clauses],
                             "rule_count": len(restored.clauses), "train_score": restored.fit.get("training_result"),
                             "closed_at": stamp()}
                    entries.append(entry)
                    attempts.append({**event, "model_id": restored.model_id, "status": restored.status,
                                     "elapsed_seconds": time.monotonic() - before, "closed_at": entry["closed_at"]})
                    if stage == "GREEDY":
                        initial, initial_training = restored, detail
                    print(json.dumps({"job": job_id, "status": restored.status, "rules": len(restored.clauses)}, ensure_ascii=False), flush=True)
    if len(attempts) != config["planned_fit_calls"]:
        raise ValueError("INCOMPLETE_FIT_SCHEDULE")
    write(out / "models.json", {"models": entries})
    write(out / "EXECUTION.json", {"experiment_id": config["experiment_id"], "all_fits_closed": True,
        "input_adapter_version": adapter.VERSION,
        "planned_fit_calls": 12, "actual_fit_calls": len(attempts), "fits": attempts,
        "encoder_fit_calls": len(config["folds"]), "encoder_source": "controlled_train_only_shared_per_fold",
        "all_models_frozen_at": stamp(), "elapsed_seconds": time.monotonic() - start,
        "mtc_train_ids": mtc_ids, "mtc_evaluation_ids_used_for_fit": [],
        "new_evaluation_opened_during_training": False, "engineering_corrections": []})


def require_evaluation_ready(out):
    execution = read(out / "EXECUTION.json")
    manifest = read(out / "models.json")
    calls = list(jsonl(out / "FIT_CALLS.jsonl"))
    expected = {(s, f["fold_id"], stage) for s in SCHEMES for f in read(out / "SETTINGS.json")["folds"] for stage in STAGES}
    actual = {(m["scheme"], m["fold_id"], m["stage"]) for m in manifest["models"]}
    if (execution.get("all_fits_closed") is not True or execution.get("actual_fit_calls") != 12
            or len(calls) != 12 or len(manifest["models"]) != 12 or actual != expected):
        raise PermissionError("ALL_TWELVE_FIXED_FITS_MUST_CLOSE_BEFORE_EVALUATION")
    return manifest


def candidate_info(adapted, atom):
    aid = atom.atom_id
    key = "UNFITTED_CONTROL:" + atom.provenance["field"] if atom.orientation == "CONTROL_LE" else aid
    info = adapted.get("candidate_inputs", {}).get(key, {})
    if isinstance(info, list):
        return info
    return info.get("fields", [])


def rule_rows(model, prediction, adapted):
    atoms = {a.atom_id: a for a in model.atoms}
    ae = {x["atom_id"]: x for x in prediction.get("atom_explanations", [])}
    ce = {x["clause_id"]: x for x in prediction.get("clause_explanations", [])}
    result = []
    for c in model.clauses:
        literal = c.literals[0]
        a, clause = ae.get(literal.atom_id, {}), ce.get(c.id, {})
        result.append({"clause_id": c.id, "atom_id": literal.atom_id, "polarity": literal.polarity,
                       "state": clause.get("state") or "FAILED", "atom_state": a.get("state") or "FAILED",
                       "reason": a.get("reason"), "fields": candidate_info(adapted, atoms[literal.atom_id]),
                       "triggered": clause.get("state") == "T"})
    return result


def emit_prediction(stream, *, scheme, fold, model, prediction, rules, sid, dataset, subset, metadata):
    row = {"scheme": scheme, "fold_id": fold, "model_id": model.model_id,
           "sample_id": sid, "dataset": dataset, "subset": subset,
           "decision": prediction["decision"], "logical_state": prediction.get("logical_state"),
           "model_status": model.status, "failure_reason": prediction.get("failure_reason"),
           "rules": rules, "triggered_rules": [r["clause_id"] for r in rules if r["triggered"]], **metadata}
    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")


def evaluate(out):
    manifest = require_evaluation_ready(out)
    from hybridguard_agent.research import mtc_constrained_reselection as engine
    from hybridguard_agent.research import mtc_reselection_candidates as adapter
    from hybridguard_agent.research.rule_semantics_webgl1_cap8 import load_model as load_baseline
    from hybridguard_agent.research.rule_learning.baselines import transform_numeric
    from hybridguard_agent.research.rule_learning.models import Clause, Literal
    from hybridguard_agent.research.rule_learning.predictor import clause_state

    if any((out / name).exists() for name in ("predictions.jsonl", "predictions.jsonl.gz")):
        raise FileExistsError("Saved predictions already exist; use summarize or a new experiment output")
    config = settings(out)
    opened_at = stamp()
    defs, index, basis = adapter.definitions(), registry(config), normal_evidence(config)
    source = ROOT / config["controlled_source"]
    subsets = {**config["mtc_primary_ids"], **config["supplementary_ids"]}
    mtc_ids = [sid for ids in subsets.values() for sid in ids]
    if len(mtc_ids) != len(set(mtc_ids)):
        raise ValueError("MTC_EVALUATION_SUBSETS_OVERLAP_RECORD_IDS")
    originals, mtc_errors = load_selected_mtc(index, mtc_ids, ROOT / config["mtc_snapshot"], allowed_ids=mtc_ids)
    mtc_adapted = {sid: adapter.adapt_mtc(row, defs) for sid, row in originals.items()}
    subset_of = {sid: subset for subset, ids in subsets.items() for sid in ids}
    old_mtc = {(r["model_id"], r["sample_id"]): r for r in jsonl(ROOT / config["baseline_mtc_predictions"]) if r["sample_id"] in subset_of}
    predictions_count, diagnostics_count = 0, 0
    overlaps = []
    with gzip.open(out / "predictions.jsonl.gz", "xt", encoding="utf-8") as stream, (out / "EVAL_CANDIDATE_DIAGNOSTICS.jsonl").open("x") as diagnostic_stream:
        for fold in config["folds"]:
            fid = fold["fold_id"]
            current = controlled_rows(source, fold["outer_test_ids"], fold["outer_test_ids"])
            adapted = {sid: adapter.adapt_controlled(r, defs) for sid, r in current.items()}
            # Sidecar labels are joined after the model is frozen, never supplied to predict.
            metadata = controlled_metadata(source, fold["outer_test_ids"])
            baseline_entry = next(m for m in config["baseline_models"] if m["fold_id"] == fid)
            baseline = load_baseline(ROOT / baseline_entry["path"])
            old_controlled = {r["opaque_id"]: r for r in jsonl(ROOT / Path(baseline_entry["path"]).parent / "predictions.jsonl")}
            if set(old_controlled) != set(fold["outer_test_ids"]):
                raise ValueError("SAVED_CONTROLLED_BASELINE_MEMBERS_DO_NOT_ALIGN")
            for scheme in ("BASELINE", *SCHEMES):
                selected = None if scheme == "BASELINE" else next(m for m in manifest["models"] if m["scheme"] == scheme and m["fold_id"] == fid and m["stage"] == "RETENTION")
                model = baseline if scheme == "BASELINE" else engine.load_model(out / selected["path"])
                for sid in fold["outer_test_ids"]:
                    pred = old_controlled[sid] if scheme == "BASELINE" else engine.predict_current(model, sid, adapted[sid]["raw"])
                    meta = metadata[sid]
                    emit_prediction(stream, scheme=scheme, fold=fid, model=model, prediction=pred,
                        rules=rule_rows(model, pred, adapted[sid]), sid=sid, dataset="controlled", subset="heldout",
                        metadata={"stage": meta["phase"], "configuration_id": meta["config_id"],
                                  "environment_group_id": meta["environment_group_id"], "triplet_id": meta["triplet_id"],
                                  "source_observation_mode": "raw_observation_v1", "source_ref": meta.get("source_ref"),
                                  "normal_basis": {"supported": meta["phase"] != "attack", "kind": "controlled_collection"},
                                  "saved_baseline_reused": scheme == "BASELINE"})
                    predictions_count += 1
                for sid in mtc_ids:
                    if scheme == "BASELINE":
                        pred = old_mtc[model.model_id, sid]
                        rules = pred["rules"]
                    elif sid in mtc_errors:
                        pred, rules = {"decision": "FAILED", "failure_reason": mtc_errors[sid]}, []
                    else:
                        pred = engine.predict_current(model, sid, mtc_adapted[sid]["raw"])
                        rules = rule_rows(model, pred, mtc_adapted[sid])
                    obs = originals.get(sid, {})
                    emit_prediction(stream, scheme=scheme, fold=fid, model=model, prediction=pred, rules=rules,
                        sid=sid, dataset="mtc", subset=subset_of[sid], metadata={"normal_basis": basis[sid],
                            "profile": index[sid]["profile"], "group_id": index[sid]["group_id"],
                            "source_refs": obs.get("source_refs", {}), "source_view": index[sid]["source_view"],
                            "source_line": index[sid]["source_line"], "historical_split": index[sid]["split"],
                            "collector_version_code": obs.get("app", {}).get("collector_version_code"),
                            "source_observation_mode": "legacy_projection_v1", "saved_baseline_reused": scheme == "BASELINE"})
                    predictions_count += 1
                if scheme == "BASELINE":
                    continue
                encoded = {sid: transform_numeric(r["raw"], model.encoder) for sid, r in adapted.items()}
                atoms = read(out / "folds" / fid / "atoms.json")
                for atom in atoms:
                    for polarity in ("POSITIVE", "NEGATIVE"):
                        clause = Clause((Literal(atom["atom_id"], polarity),))
                        by_config = defaultdict(Counter)
                        for sid, row in encoded.items():
                            if metadata[sid]["phase"] != "attack":
                                continue
                            try:
                                state = clause_state(clause, row)
                            except (KeyError, ValueError, TypeError):
                                state = "FAILED"
                            by_config[metadata[sid]["config_id"]][state] += 1
                        for cfg, counts in by_config.items():
                            diagnostic_stream.write(json.dumps({"scheme": scheme, "fold_id": fid, "configuration_id": cfg,
                                "clause_id": clause.id, "heldout_attack_T": counts["T"], "heldout_attack_n": sum(counts.values()),
                                "F": counts["F"], "U": counts["U"], "FAILED": counts["FAILED"]}) + "\n")
                            diagnostics_count += 1
            # Illustrative actual exposed-value overlap, never used to admit a candidate.
            for field in ("app.web_data.navigator_layer.device_memory", "app.web_data.screen_layer.device_pixel_ratio", "app.web_data.execution_layer.timezone_offset"):
                key = "UNFITTED_CONTROL:" + field
                example = None
                for sid in fold["outer_test_ids"]:
                    value = adapted[sid]["raw"][key]
                    if metadata[sid]["phase"] != "attack" or not value.get("available"):
                        continue
                    base_rule = next((r for r in old_controlled[sid]["atom_explanations"] if r.get("provenance", {}).get("field") == field), None)
                    if not base_rule or base_rule["state"] != "F":
                        continue
                    for normal in config["mtc_normal_train_ids"]:
                        observed = mtc_adapted[normal]["raw"][key]
                        if observed.get("available") and type(value["value"]) in (int, float) and observed["value"] == value["value"]:
                            example = {"fold_id": fid, "field": field, "value": value["value"],
                                "attack_sample_id": sid, "configuration_id": metadata[sid]["config_id"],
                                "normal_sample_id": normal, "normal_profile": index[normal]["profile"],
                                "normal_source_line": index[normal]["source_line"],
                                "note": "same reported field value, not evidence of equal physical hardware"}
                            break
                    if example:
                        break
                if example:
                    overlaps.append(example)
    write(out / "OVERLAP_EXAMPLES.json", {"examples": overlaps})
    write(out / "EVALUATION.json", {"opened_at": opened_at, "closed_at": stamp(),
        "input_adapter_version": adapter.VERSION,
        "after_all_models_frozen_at": read(out / "EXECUTION.json")["all_models_frozen_at"],
        "predictions_saved": predictions_count, "candidate_diagnostic_rows": diagnostics_count,
        "mtc_source_errors": mtc_errors, "baseline_new_predictions": 0,
        "baseline_saved_rows_reused": 3 * (126 + len(mtc_ids)),
        "new_retention_prediction_calls": 6 * (126 + len(mtc_ids)),
        "selection_from_evaluation": False, "extra_fit_calls": 0})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("train", "evaluate", "run", "summarize"))
    p.add_argument("--output-dir", type=Path, default=HERE)
    args = p.parse_args()
    out = args.output_dir.resolve(); out.mkdir(parents=True, exist_ok=True)
    if args.command in ("train", "run"):
        train(out)
    if args.command in ("evaluate", "run"):
        evaluate(out)
    if args.command in ("summarize", "run", "evaluate"):
        from summarize import summarize
        summarize(out)


if __name__ == "__main__":
    main()
