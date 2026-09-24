"""R04-R1 engineering revision: reuse frozen data/resources; synthetic fits only."""
import ast
import copy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from .baselines import single_surface_definitions
from .contracts import CONFIG, ROOT, STUDY, binding, cell, read_json, read_jsonl
from .freeze import copy_file, raw_definitions
from .job_manifest import job, prediction_units
from .job_runtime import file_digest, write_json
from .models import Atom
from .runner import dump_lines
from .synthetic import export_fixture

BASELINE = "51726c0af36f9bcb1fda7647788be2f945c4f44d"
SURFACES = ("native84", "app_web67", "host26")
CODE = "hybridguard_agent/research/rule_learning/"
CHANGED = [CODE + n for n in ("evaluation.py", "oof.py", "runner.py", "baselines.py",
    "job_runtime.py", "freeze.py", "freeze_acceptance.py", "freeze_revision.py")] + [
    "hybridguard_agent/tests/test_rule_learning_r04.py",
    "hybridguard_agent/tests/test_rule_learning_r04_r1.py",
    "hybridguard_agent/scripts/prepare_rule_learning_r04_r1.py"]


def replace_json(path, value):
    # Only newly created revision files may be replaced by this builder.
    path.unlink(missing_ok=True)
    write_json(path, value)


def surface_toys(out, definitions):
    """Real frozen column metadata plus programmatic toy values/labels only."""
    fixture = export_fixture("complementary")
    index = read_json(out / "synthetic/DATA_INDEX.json")
    splits = read_json(out / "synthetic/SPLITS.json")
    jobs, evidence = [], {}
    for surface in SURFACES:
        tag = "r1-single-" + surface
        defs = copy.deepcopy(definitions)
        extra = [Atom("CAT:R1-AUDIT-" + surface, "TOY_AUDIT", (surface,), ("TOY_ONLY",), (),
                      "NO_BOOLEAN_SUMMARY", {"synthetic_only": True}),
                 Atom("UNFITTED_CONTROL:R1_UNDECLARED_" + surface, "TOY_AUDIT_NUMERIC", (surface,),
                      ("TOY_ONLY",), (), "UNFITTED_NUMERIC_MEASUREMENT", {"synthetic_only": True})]
        defs["atoms"].extend(asdict(a) for a in extra)
        ref = "synthetic/definitions/" + tag + ".json"
        write_json(out / ref, defs)
        allowed = set(defs["single_surface_allowlists"][surface])
        members = {p: ["fixture-" + tag + "-" + oid for oid in fixture["membership"][p]]
                   for p in ("train", "outer_test", "descriptive_train_side", "descriptive_test_side")}
        members.update(split_id="SYNTHETIC-R04-R1", fold_id="SYNTHETIC-" + tag)
        splits[tag] = members
        for n, (oid, meta) in enumerate(fixture["evaluation_sidecar"].items()):
            new_id = "fixture-" + tag + "-" + oid
            features = {}
            for a in defs["atoms"]:
                name = a["atom_id"]
                if name not in allowed:
                    # An accidental encoder/selector read must fail, even for
                    # a same-surface deployment marker or numeric audit input.
                    features[name] = {"value": {"TOY_POISON": True}, "available": True,
                                      "evaluation_status": "OK", "reason": "EXCLUDED_TOY_AUDIT"}
                elif name.startswith("UNFITTED_CONTROL:"):
                    features[name] = {"value": n + 1, "available": True,
                                      "evaluation_status": "OK", "reason": "PROGRAMMATIC_TOY_NUMBER"}
                else:
                    features[name] = cell("T" if meta["phase"] == "attack" else "F", "PROGRAMMATIC_TOY_BOOL")
            refs = {"features": "synthetic/current/" + new_id + ".json",
                    "evaluation": "synthetic/evaluation/" + new_id + ".json"}
            write_json(out / refs["features"], {"opaque_id": new_id, "features": features, "origin": "BUILTIN_SYNTHETIC"})
            write_json(out / refs["evaluation"], dict(meta, opaque_id=new_id,
                bundle_id=tag + ":" + meta["bundle_id"], triplet_id=tag + ":" + meta["triplet_id"]))
            index[new_id] = refs
        j = job("SYNTHETIC_R1_SINGLE_" + surface, members, "GREEDY_OR", "OP05", "SRC-111", surface, origin="BUILTIN_SYNTHETIC")
        j.update(fixture_id=tag, authorization_stage="SYNTHETIC_R04", definitions_ref=ref)
        jobs.append(j)
        evidence[surface] = {"allowed_ids": sorted(allowed), "raw_atom_n": len(defs["atoms"]),
            "excluded_same_surface_ids": sorted(a["atom_id"] for a in defs["atoms"]
                if tuple(a["surfaces"]) == (surface,) and a["atom_id"] not in allowed),
            "measurement_values": "PROGRAMMATIC_SYNTHETIC_ONLY", "real_values_read_for_fixture": False}
    replace_json(out / "synthetic/DATA_INDEX.json", index)
    replace_json(out / "synthetic/SPLITS.json", splits)
    write_json(out / "synthetic/R1_SURFACE_FIXTURES.json", evidence)
    return jobs


def build_revision(source, out):
    source, out = Path(source).resolve(), Path(out).resolve()
    if out.exists() or out == source or out.is_relative_to(source):
        raise FileExistsError("R04_R1_REQUIRES_NEW_SEPARATE_DIRECTORY")
    subprocess.run(["git", "merge-base", "--is-ancestor", BASELINE, "HEAD"], cwd=ROOT, check=True)
    old_freeze = read_json(source / "FREEZE_MANIFEST.json")
    old_resources = read_json(source / "RESOURCE_MANIFEST.json")
    for name, expected in old_freeze["manifest_digests"].items():
        if file_digest(source / name) != expected:
            raise ValueError("BASELINE_FREEZE_MISMATCH:" + name)
    out.mkdir(parents=True)
    for e in old_resources["files"]:
        p = source / e["path"]
        if p.stat().st_size != e["bytes"] or file_digest(p) != e["sha256"]:
            raise ValueError("BASELINE_RESOURCE_MISMATCH:" + e["path"])
        copy_file(p, out / e["path"])
    for ref in CHANGED:
        copy_file(ROOT / ref, out / "snapshot" / ref)
    definitions = raw_definitions()  # R01/R02 column metadata only.
    old_definitions = read_json(source / "data/definitions.json")
    if any(definitions[k] != old_definitions[k] for k in ("atoms", "view")):
        # Normalize tuple/list JSON representation, not semantic content.
        from .job_manifest import digest
        if any(digest(definitions[k]) != digest(old_definitions[k]) for k in ("atoms", "view")):
            raise ValueError("FULL_AUDIT_CATALOG_CHANGED")
    replace_json(out / "data/definitions.json", definitions)
    # Preserve all original toy definitions; add only their frozen allowlists.
    for p in (out / "synthetic/definitions").glob('*.json'):
        d = read_json(p)
        d["single_surface_allowlists"] = {s: [a["atom_id"] for a in d["atoms"] if tuple(a["surfaces"]) == (s,)] for s in SURFACES}
        replace_json(p, d)
    toys = read_jsonl(out / "synthetic/expected_model_units.jsonl")
    added = surface_toys(out, definitions)
    for name, records in (("expected_model_units.jsonl", toys + added),
                          ("expected_prediction_units.jsonl", prediction_units(toys + added))):
        p = out / "synthetic" / name
        p.unlink()
        dump_lines(p, records)
    protocol = read_json(source / "protocol.json")
    protocol.update(engineering_revision="R04-R1", engineering_reviewed_commit=BASELINE)
    protocol["synthetic_suites"]["r1_single_surfaces"] = {"job_ids": [j["job_id"] for j in added], "budget": protocol["budget"]}
    protocol["synthetic_suites"]["r1_worker_failure"] = {"job_ids": protocol["synthetic_suites"]["budget_count"]["job_ids"], "budget": protocol["budget"]}
    replace_json(out / "protocol.json", protocol)
    auth = read_json(source / "AUTHORIZATION.json")
    auth.update(engineering_revision="R04-R1", synthetic_job_ids=[j["job_id"] for j in toys + added])
    replace_json(out / "AUTHORIZATION.json", auth)
    unchanged = ['selector.py', 'solver.py', 'models.py', 'contracts.py', 'matrix.py', 'fold_data.py', 'synthetic.py', 'predictor.py', 'access.py', 'job_manifest.py']
    checks = {n: (source / "snapshot" / CODE / n).read_bytes() == (ROOT / CODE / n).read_bytes() for n in unchanged}
    symbols = {"baselines.py": ["sources", "single_surface_definitions", "project_core", "core_view", "fixed_model", "transform_numeric", "historical_seven_contract", "adapt_historical_seven"],
               "runner.py": ["execute_job", "BudgetLedger", "reuse_result", "run", "worker"]}
    functions = {}
    for name, names in symbols.items():
        texts = [(source / 'snapshot' / CODE / name).read_text(), (ROOT / CODE / name).read_text()]
        trees = [{n.name: ast.get_source_segment(t, n) for n in ast.parse(t).body if hasattr(n, 'name')} for t in texts]
        functions.update({name + ':' + n: trees[0][n] == trees[1][n] for n in names})
    if not all(checks.values()) or not all(functions.values()):
        raise ValueError("CHANGE_OUTSIDE_R04_R1_SCOPE")
    replace_json(out / "ALGORITHM_INVARIANCE.json", {"baseline": BASELINE, "whole_files_byte_identical": checks,
        "function_source_byte_identical": functions, "R01_protocol_digest_unchanged": binding()["protocol_digest"] == old_freeze["protocol_digest"],
        "changes": ["OOF unknown expected cell counts including strata", "single-surface whitelist before encoding/support", "targeted synthetic regression and revision packaging"]})
    plans = ['expected_fit_jobs.jsonl', 'expected_model_units.jsonl', 'expected_prediction_units.jsonl', 'SPLIT_MANIFEST.json']
    plan_checks = {n: (source / n).read_bytes() == (out / n).read_bytes() for n in plans}
    assert all(plan_checks.values())
    config_checks = {str(p.relative_to(CONFIG)): p.read_bytes() == (source / 'snapshot' / p.relative_to(ROOT)).read_bytes()
                     for p in CONFIG.rglob('*') if p.is_file()}
    assert all(config_checks.values())
    replace_json(out / 'BINDING_REVIEW.json', {'revision': 'R04-R1', 'baseline': BASELINE,
        'real_job_manifests_byte_identical': plan_checks, 'R01_config_bytes_unchanged': config_checks,
        'real_fit_jobs': 72, 'real_model_units': 115, 'real_prediction_units': 4374,
        'original_complete_synthetic_jobs': len(toys), 'added_synthetic_whitelist_jobs': len(added),
        'R01_R02_rebuilt': False, 'real_values_decoded_for_training_or_fixture': False})
    write_json(out / 'R04_R1_REVISION.json', {'step': 'R04-R1', 'baseline_commit': BASELINE,
        'baseline_directory': str(source.relative_to(ROOT)), 'baseline_freeze_digest': file_digest(source / 'FREEZE_MANIFEST.json'),
        'baseline_saved_failure': 'isolated_validation/budget_count/OOF.json',
        'authority': 'User authorized only incomplete coverage and single-surface whitelist fixes with synthetic regressions.',
        'old_reports_logs_and_failures_preserved': True, 'real_fit_authorized': False, 'R05_authorized': False})
    # Byte preservation must also survive Git checkout of vendored resources.
    (out / '.gitattributes').write_text('* -text\n')
    resources = [{"path": str(p.relative_to(out)), "bytes": p.stat().st_size, "sha256": file_digest(p)}
                 for p in sorted(out.rglob('*')) if p.is_file()]
    write_json(out / 'RESOURCE_MANIFEST.json', {**old_resources, 'files': resources, 'engineering_revision': 'R04-R1'})
    names = list(old_freeze['manifest_digests']) + ['R04_R1_REVISION.json']
    write_json(out / 'FREEZE_MANIFEST.json', {**old_freeze, 'engineering_revision': 'R04-R1',
        'engineering_reviewed_commit': BASELINE, 'created_at': datetime.now(timezone.utc).isoformat(),
        'manifest_digests': {n: file_digest(out / n) for n in names}, 'user_acceptance': 'PENDING'})
    return protocol
