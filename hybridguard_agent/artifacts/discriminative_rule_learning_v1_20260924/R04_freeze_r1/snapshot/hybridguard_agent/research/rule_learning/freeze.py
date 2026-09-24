"""R04 resource closure and metadata-only planning. No real learning/prediction."""
from collections import Counter
import copy
import ast
from dataclasses import asdict
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from .acceptance import review_inputs
from .baselines import historical_seven_contract, single_surface_definitions
from .contracts import CONFIG, ROOT, STUDY, binding, ledger, read_json, read_jsonl
from .job_manifest import digest, job, plan_real_jobs, prediction_units
from .job_runtime import file_digest, write_json
from .models import Atom
from .runner import dump_lines
from .synthetic import export_fixture

REVIEW_COMMIT = "a1d8695b832850f1807d2af6a1dd1ea1bc99f63c"
OLD = Path("hybridguard_agent/artifacts/formal_manipulation_v1_20260923")


def copy_file(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def copy_tree(source, dest):
    for p in sorted(Path(source).rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith(('.pyc', '.pyo')):
            copy_file(p, dest / p.relative_to(source))


def raw_definitions():
    atoms = [Atom(c["atom_id"], c["decision_family"], tuple(c["observation_surfaces"]),
                  (c["provenance_group"],), (c["rule_id"],), "CATALOG_CONDITION",
                  {"field_refs": c["dependencies"], "condition": c["measurement"]["condition"]}) for c in ledger()]
    for surface in ("native84", "app_web67", "host26"):
        atoms.extend(a for a in single_surface_definitions(surface) if not a.atom_id.startswith("CAT:"))
    assert len({a.atom_id for a in atoms}) == len(atoms)
    return {"atoms": [asdict(a) for a in atoms], "view": {"view_id": "RAW_CORE", "kind": "RAW_CORE", "source_condition": "SRC-111"},
            "single_surface_allowlists": {s: [a.atom_id for a in single_surface_definitions(s)]
                                          for s in ("native84", "app_web67", "host26")}}


def cache_rows(out):
    """Repackage fixed R02 cells into individual files; no extraction or fit.

    Both catalog polarity and availability/reasons are copied exactly. Views
    and canonical source projection are formed later on an opened partition.
    """
    base = STUDY / "R02_matrix"
    columns = read_json(base / "COLUMN_MANIFEST.json")
    values = {r["opaque_id"]: r for r in read_jsonl(base / "candidate_matrix.jsonl")}
    av = {r["opaque_id"]: r for r in read_jsonl(base / "availability_matrix.jsonl")}
    fixed = {r["opaque_id"]: r for r in read_jsonl(base / "fixed_control_matrix.jsonl")}
    control = {r["opaque_id"]: r for r in read_jsonl(base / "control_inputs.jsonl")}
    sidecar = {r["opaque_id"]: r for r in read_jsonl(base / "evaluation_index.jsonl")}
    index = {}
    for oid in sorted(values):
        features = {}
        for names, val, status in ((columns["candidate_columns"], values[oid], av[oid]),
                                    (columns["fixed_control_columns"], fixed[oid], fixed[oid])):
            for i, name in enumerate(names):
                features[name] = {"value": val["values"][i], "available": status["available"][i],
                                  "evaluation_status": status["evaluation_status"][i], "reason": status["reasons"][i]}
        for i, col in enumerate(columns["control_columns"]):
            if "TRAIN_QUANTILE" in col["encoder"]:
                features["UNFITTED_CONTROL:" + col["field"]] = {
                    "value": control[oid]["values"][i], "available": control[oid]["available"][i],
                    "evaluation_status": control[oid]["evaluation_status"][i], "reason": control[oid]["reasons"][i]}
        refs = {"features": f"data/current/{oid}.json", "evaluation": f"data/evaluation/{oid}.json"}
        write_json(out / refs["features"], {"opaque_id": oid, "features": features,
            "origin": "R02_FIXED_CACHE", "cache_lineage_ref": "snapshot/" + str((base / "CACHE_LINEAGE.json").relative_to(ROOT))})
        write_json(out / refs["evaluation"], sidecar[oid])
        index[oid] = refs
    write_json(out / "DATA_INDEX.json", index)
    write_json(out / "data/definitions.json", raw_definitions())
    return index


def history_inputs(out):
    inputs = {r["opaque_id"]: r["payload"] for r in read_jsonl(ROOT / OLD / "02_inputs/inference_inputs.jsonl")}
    frozen = {r["opaque_id"]: r["payload"] for r in read_jsonl(ROOT / OLD / "05_freeze_r1/blind/inputs.jsonl")}
    input_manifest = {r["opaque_id"]: r for r in read_jsonl(ROOT / OLD / "02_inputs/input_manifest.jsonl")}
    spec = historical_seven_contract()
    saved = {r["opaque_id"]: r for r in read_jsonl(ROOT / OLD / "06_e1/prediction/predictions.jsonl") if r["method"] == "final_v3_v2"}
    proof = {}
    for oid, payload in sorted(inputs.items()):
        r, manifest = saved.get(oid), input_manifest[oid]
        same = oid in frozen and payload == frozen[oid]
        method = r is not None and all(r.get(k) == v for k, v in spec.items() if k != "rule_ids")
        good = same and method and manifest["adapter_version"] == spec["adapter_version"] and manifest["status"] == "ADAPTED"
        proof[oid] = {"status": "EXACT_INPUT_AND_METHOD_MATCH" if good else "UNAVAILABLE_OR_CONTRACT_MISMATCH",
            "S02_ref": str(OLD / "02_inputs/inference_inputs.jsonl") + "#" + oid,
            "S06_frozen_ref": str(OLD / "05_freeze_r1/blind/inputs.jsonl") + "#" + oid,
            "S06_prediction_ref": str(OLD / "06_e1/prediction/predictions.jsonl") + "#" + oid,
            "S02_payload_digest": digest(payload), "S06_payload_digest": digest(frozen[oid]) if oid in frozen else None,
            "input_bytes_semantically_equal": same, "method_contract_equal": method}
    write_json(out / "HISTORICAL_INPUT_PROOF.json", proof)
    write_json(out / "data/historical_predictions.json", saved)
    return Counter(p["status"] for p in proof.values())


def synthetic_resources(out):
    specifications = [("complementary", "GREEDY_OR", "SRC-111", "core", f) for f in (1, 2)]
    specifications += [("complementary_test_labels", "GREEDY_OR", "SRC-111", "core", 1)]
    specifications += [("and_required", m, "SRC-111", "core", 1) for m in ("GREEDY_OR", "FINITE_IP_OR", "FINITE_IP_DNF2")]
    specifications += [("aliases", "GREEDY_OR", s, "core", 1) for s in ("SRC-000", "SRC-001", "SRC-010", "SRC-111")]
    specifications += [("aliases", m, "SRC-111", "core", 1) for m in ("DIRECT_CORE_OR", "HISTORICAL_SEVEN", "ALWAYS_NO_ALERT", "ALWAYS_ABSTAIN")]
    specifications += [(n, "GREEDY_OR", "SRC-111", "native84", 1) for n in ("numeric", "numeric_test_extreme")]
    specifications += [("negative", "GREEDY_OR", "SRC-111", "core", 1),
                       ("infeasible", "FINITE_IP_OR", "SRC-111", "core", 1),
                       ("cap_overflow", "FINITE_IP_DNF2", "SRC-111", "core", 1)]
    jobs, index, exported = [], {}, {}
    for name, method, source, view, fold_number in specifications:
        tag = name + "-" + str(fold_number)
        if tag not in exported:
            fixture = export_fixture("complementary" if name == "complementary_test_labels" else name)
            mapping = {i: "fixture-r04-" + tag + "-" + i for i in fixture["features"]}
            members = {p: [mapping[i] for i in fixture["membership"][p]] for p in (
                "train", "outer_test", "descriptive_train_side", "descriptive_test_side")}
            members.update(split_id="SYNTHETIC-R04", fold_id="SYNTHETIC-" + tag)
            definitions = {"atoms": fixture["atoms"], "view": fixture["view"],
                "single_surface_allowlists": {s: [a["atom_id"] for a in fixture["atoms"] if a["surfaces"] == (s,)]
                                              for s in ("native84", "app_web67", "host26")}}
            write_json(out / f"synthetic/definitions/{tag}.json", definitions)
            for oid, new_id in mapping.items():
                refs = {"features": f"synthetic/current/{new_id}.json", "evaluation": f"synthetic/evaluation/{new_id}.json"}
                write_json(out / refs["features"], {"opaque_id": new_id, "features": fixture["features"][oid], "origin": "BUILTIN_SYNTHETIC"})
                label = dict(fixture["evaluation_sidecar"][oid], opaque_id=new_id,
                             bundle_id=tag + ":" + fixture["evaluation_sidecar"][oid]["bundle_id"],
                             triplet_id=tag + ":" + fixture["evaluation_sidecar"][oid]["triplet_id"])
                if name == "complementary_test_labels" and oid in fixture["membership"]["outer_test"]:
                    label["phase"] = {"attack": "clean_pre", "clean_pre": "attack", "clean_post": "clean_post"}[label["phase"]]
                    label["supervised_label"] = int(label["phase"] == "attack")
                write_json(out / refs["evaluation"], label)
                index[new_id] = refs
            exported[tag] = members
        j = job("SYNTHETIC_" + name, exported[tag], method,
                "OP05" if method in ("GREEDY_OR", "FINITE_IP_OR", "FINITE_IP_DNF2") else "NOT_APPLICABLE",
                source, view, origin="BUILTIN_SYNTHETIC")
        j.update(fixture_id=name, authorization_stage="SYNTHETIC_R04", definitions_ref=f"synthetic/definitions/{tag}.json")
        if method == "HISTORICAL_SEVEN":
            historical = {oid: dict(historical_seven_contract(), opaque_id=oid, execution_status="COMPLETED",
                risk={"decision": "NO_ALERT", "family_coverage": .8}) for oid in j["outer_test_ids"]}
            proof = {oid: {"status": "EXACT_INPUT_AND_METHOD_MATCH", "origin": "BUILTIN_SYNTHETIC_HISTORY_FIXTURE"} for oid in historical}
            j.update(history_ref="synthetic/history.json", history_proof_ref="synthetic/history_proof.json")
            write_json(out / j["history_ref"], historical)
            write_json(out / j["history_proof_ref"], proof)
        jobs.append(j)
    reused = copy.deepcopy(jobs[0])
    reused.update(job_id="SYNTHETIC_REUSE__" + jobs[0]["job_id"], model_unit_id="SYNTHETIC_REUSE__" + jobs[0]["model_unit_id"],
                  experiment_id="SYNTHETIC_REUSE", fixture_id="reuse_complementary", priority=6,
                  reuse_model_unit_id=jobs[0]["model_unit_id"])
    jobs.append(reused)
    write_json(out / "synthetic/DATA_INDEX.json", index)
    dump_lines(out / "synthetic/expected_model_units.jsonl", jobs)
    dump_lines(out / "synthetic/expected_prediction_units.jsonl", prediction_units(jobs))
    write_json(out / "synthetic/SPLITS.json", exported)
    return jobs


def dependencies(out):
    target = out / "dependencies"
    base = Path(sys.base_prefix)
    copy_file(Path(sys._base_executable), target / "python/bin/python3.12")
    stdlib = base / "lib/python3.12"
    for p in stdlib.rglob('*'):
        if p.is_file() and not any(x in p.parts for x in ('site-packages', '__pycache__')):
            copy_file(p, target / "python/lib/python3.12" / p.relative_to(stdlib))
    for p in (base / "lib").glob('*.dylib'):
        copy_file(p, target / "python/lib" / p.name)
    packages = {}
    for name in ('numpy', 'highspy'):
        distribution = importlib.metadata.distribution(name)
        packages[name] = distribution.version
        for ref in distribution.files:
            path = Path(distribution.locate_file(ref))
            if path.is_file() and '..' not in ref.parts and '__pycache__' not in ref.parts:
                copy_file(path, target / "site-packages" / ref)
    return {"python": platform.python_version(), "numpy": packages["numpy"], "highspy": packages["highspy"],
            "platform": platform.platform(), "machine": platform.machine(), "python_copy": "dependencies/python/bin/python3.12",
            "original_python_ref": str(sys._base_executable), "external_python_files": [],
            "OS_dependency_policy": "same macOS/platform; system frameworks and /usr/lib remain OS resources; no workspace or site-package fallback"}


LAUNCH = '''"""Isolated launcher: -I -S ignores cwd, PYTHONPATH and user site packages."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path[:0] = [str(root / "snapshot"), str(root / "dependencies/site-packages")]
from hybridguard_agent.research.rule_learning.runner import main
main()
'''


def build(out):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError("R04_FREEZE_MUST_BE_NEW_NO_HISTORICAL_OVERWRITE")
    review = review_inputs()
    subprocess.run(["git", "merge-base", "--is-ancestor", REVIEW_COMMIT, "HEAD"], cwd=ROOT, check=True)
    review.update(R03_reviewed_commit=REVIEW_COMMIT, R03_source_changes="R04 job authorization, partition access, provenance and history adapter admission only")
    fits, models, predictions = plan_real_jobs()
    out.mkdir(parents=True)
    for j in models + fits:
        j.update(definitions_ref="data/definitions.json", history_ref="data/historical_predictions.json",
                 history_proof_ref="HISTORICAL_INPUT_PROOF.json")
    for name, records in (("expected_fit_jobs.jsonl", fits), ("expected_model_units.jsonl", models), ("expected_prediction_units.jsonl", predictions)):
        dump_lines(out / name, records)
    write_json(out / "SPLIT_MANIFEST.json", {"folds": read_json(STUDY / "R02_matrix/FOLD_INPUT_MANIFEST.json")["folds"],
        "final_development_members": next(j["train_ids"] for j in models if j["experiment_id"] == "FINAL_DEVELOPMENT_REFIT"),
        "supervised_n": 162, "descriptive_n": 100, "partition_changed": False})
    # Source copies include runtime imports and builder/test entry points. They
    # do not include unrelated Android worktree files or historical executables.
    for p in (ROOT / "hybridguard_agent").rglob('*.py'):
        if not any(s in p.relative_to(ROOT).parts for s in ('artifacts', '__pycache__', '.venv')):
            copy_file(p, out / "snapshot" / p.relative_to(ROOT))
    copy_tree(CONFIG, out / "snapshot" / CONFIG.relative_to(ROOT))
    for step in ('R01_protocol', 'R02_matrix', 'R03_implementation'):
        copy_tree(STUDY / step, out / "snapshot" / (STUDY / step).relative_to(ROOT))
    for ref in [OLD / "02_inputs/input_manifest.jsonl", OLD / "02_inputs/inference_inputs.jsonl",
                OLD / "05_freeze_r1/blind/inputs.jsonl", OLD / "06_e1/prediction/predictions.jsonl",
                Path("hybridguard_agent/config/formal_manipulation_role_gate_v2/decision_roles.json"),
                Path("RESEARCH_MAINLINE.md"), Path("deliverables/formal_experiment_execution_plan/EXECUTION_PLAN.md")]:
        copy_file(ROOT / ref, out / "snapshot" / ref)
    real_index = cache_rows(out)
    history_counts = history_inputs(out)
    toys = synthetic_resources(out)
    runtime = dependencies(out)
    (out / "launch.py").write_text(LAUNCH)
    budget = read_json(CONFIG / "learning_search_space.json")["total_budget"]
    count_jobs = [j["job_id"] for j in toys if j["fixture_id"] == "complementary"]
    protocol = {"schema_version": "r04-job-freeze-v1", "protocol_digest": binding()["protocol_digest"],
        "reviewed_commit": REVIEW_COMMIT, "real_execution_authorized": False,
        "data_indices": {"R02_FIXED_CACHE": "DATA_INDEX.json", "BUILTIN_SYNTHETIC": "synthetic/DATA_INDEX.json"},
        "budget": budget, "priority_tie_break": "priority then lexicographic exact job_id; no result adaptation",
        "global_budget_ledger": "one persistent exclusive ledger per freeze across all later stages; no automatic retries",
        "io_overhead_seconds_per_job_cap": 30,
        "synthetic_suites": {
            "complete": {"job_ids": [j["job_id"] for j in toys], "budget": budget},
            "budget_count": {"job_ids": count_jobs, "budget": dict(budget, max_fit_jobs=1)},
            "budget_time": {"job_ids": count_jobs, "budget": dict(budget, wall_clock_seconds=0)}},
        "unimplemented_later_experiment_interfaces": ["R06_POSTFIT_DELETE", "R07_FIXED_MODEL_MASK", "R09_COST_TIMING_DRIVER"],
        "reserved_nonfit_units": {"R06_POSTFIT_DELETE": {"base_models": [j['model_unit_id'] for j in models if j['experiment_id'] == 'R05_PRIMARY' and j['method_id'] == 'GREEDY_OR' and j['operating_point'] == 'OP05'],
            "source_removals": ['E', 'O_u', 'H'], "state": 'NOT_RUN_INTERFACE_RESERVED_FOR_R06'},
            "R07_FIXED_MODEL_MASK": {"base_models": [j['model_unit_id'] for j in models if j['experiment_id'] == 'R05_PRIMARY' and j['method_id'] == 'GREEDY_OR' and j['operating_point'] == 'OP05'],
            "removed_surfaces": ['native84', 'app_web67', 'host26'], "state": 'NOT_RUN_INTERFACE_RESERVED_FOR_R07'},
            "R09_COST": {"spec_ref": 'snapshot/' + str((CONFIG / 'experiment_matrix.json').relative_to(ROOT)) + '#R09_COST',
                           "state": 'NOT_RUN_TIMING_DRIVER_RESERVED_FOR_R09'}},
        "separately_closed_branches": {"R08_MECHANISM": "NOT_EVALUABLE_UNVERIFIED_MECHANISM_PARTITION", "R08_PROSPECTIVE": "NOT_AVAILABLE"},
        "real_data_rows": len(real_index), "history_proof_counts": dict(history_counts),
        "fit_slots_before_SRC111_reuse": 75, "unique_fit_jobs": len(fits), "model_units": len(models),
        "prediction_units": len(predictions), "R05_counts": {"fits": sum(j["experiment_id"] == "R05_PRIMARY" for j in fits),
            "models": sum(j["experiment_id"] == "R05_PRIMARY" for j in models),
            "predictions": sum(j["experiment_id"] == "R05_PRIMARY" for j in predictions)}}
    write_json(out / "protocol.json", protocol)
    write_json(out / "AUTHORIZATION.json", {"step": "R04", "real_fit_grants": [], "synthetic_scope": "BUILTIN_RESOURCES_ONLY",
        "synthetic_job_ids": [j["job_id"] for j in toys], "future_grants": "separate explicit stage/job approval required"})
    write_json(out / "BINDING_REVIEW.json", review)
    unchanged_files = ['solver.py', 'models.py', 'contracts.py', 'matrix.py', 'fold_data.py', 'evaluation.py', 'synthetic.py']
    code_base = 'hybridguard_agent/research/rule_learning/'
    file_checks = {}
    for name in unchanged_files:
        old = subprocess.check_output(['git', 'show', REVIEW_COMMIT + ':' + code_base + name], cwd=ROOT)
        file_checks[name] = old == (ROOT / code_base / name).read_bytes()
    functions = {'selector.py': ['compatible', 'TrainProblem', 'better', 'json_score', 'greedy', 'selection_rows'],
                 'baselines.py': ['sources', 'single_surface_definitions', 'project_core', 'core_view', 'transform_numeric',
                                  'single_surface_view', 'historical_seven_contract', 'adapt_historical_seven'],
                 'predictor.py': ['clause_state', 'predict_batch', 'predict_single_surface']}
    function_checks = {}
    for name, symbols in functions.items():
        old = subprocess.check_output(['git', 'show', REVIEW_COMMIT + ':' + code_base + name], cwd=ROOT, text=True)
        current = (ROOT / code_base / name).read_text()
        old_nodes = {n.name: ast.get_source_segment(old, n) for n in ast.parse(old).body if hasattr(n, 'name')}
        new_nodes = {n.name: ast.get_source_segment(current, n) for n in ast.parse(current).body if hasattr(n, 'name')}
        for symbol in symbols:
            function_checks[name + ':' + symbol] = old_nodes[symbol] == new_nodes[symbol]
    if not all(file_checks.values()) or not all(function_checks.values()):
        raise ValueError('UNAUTHORIZED_ALGORITHM_BYTE_CHANGE')
    write_json(out / 'ALGORITHM_INVARIANCE.json', {'reviewed_commit': REVIEW_COMMIT,
        'whole_files_byte_identical': file_checks, 'function_source_byte_identical': function_checks,
        'changed_functions': {'selector.fit': 'replace synthetic provenance construction with verified access binding; selection body unchanged',
            'baselines.fixed_model': 'verified provenance, scope and actual creation time',
            'predictor.predict': 'reject historical placeholder inference without the saved-output/input-proof adapter',
            'access': 'separate train-only job capability and exact formal request validation'},
        'R01_math_configs_changed': False, 'real_algorithm_selection': False})
    write_json(out / "R03_EXTERNAL_ACCEPTANCE.json", {"reviewed_commit": REVIEW_COMMIT, "authority": "User: R03 外部验收通过。执行 R04。",
        "recorded_at": datetime.now(timezone.utc).isoformat(), "original_R03_report_and_VALIDATION_overwritten": False})
    resources = [{"path": str(p.relative_to(out)), "bytes": p.stat().st_size, "sha256": file_digest(p)}
                 for p in sorted(out.rglob('*')) if p.is_file()]
    write_json(out / "RESOURCE_MANIFEST.json", {"schema_version": "r04-resource-manifest-v1", "runtime": runtime,
        "files": resources, "scope": "source, configs, fixed caches, provenance, sidecars, exact jobs, historical input proof, Python stdlib and copied NumPy/HiGHS distributions"})
    names = ['RESOURCE_MANIFEST.json', 'protocol.json', 'AUTHORIZATION.json', 'SPLIT_MANIFEST.json',
             'expected_fit_jobs.jsonl', 'expected_model_units.jsonl', 'expected_prediction_units.jsonl',
             'synthetic/expected_model_units.jsonl']
    write_json(out / "FREEZE_MANIFEST.json", {"schema_version": "r04-freeze-manifest-v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_commit": REVIEW_COMMIT, "protocol_digest": binding()["protocol_digest"],
        "manifest_digests": {n: file_digest(out / n) for n in names}, "real_execution_authorized": False,
        "synthetic_fit_permission": "exact built-in suite through dispatcher only", "user_acceptance": "PENDING"})
    return protocol
