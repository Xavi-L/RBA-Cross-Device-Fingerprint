"""S05 static freeze. Only stdlib and static specifications; no detector import.

Reads accepted S01/S02 ledgers and S03-R/S04 configuration. Copies bytes and
constructs IDs, sets and denominators, never calls admission, adapter or worker.
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

from hybridguard_agent.research.manipulation_eval.freeze_specs import diagnostic_spec, fixtures, timing_spec

ROOT = Path(__file__).resolve().parents[3]
STUDY = "formal-manipulation-v1"
VERSION = "formal-manipulation-protocol-v2"
CONTRACT = "formal-manipulation-relation-risk-attribution-v2"
POLICY = "formal-manipulation-family-or-v2"
ARTIFACT = Path("hybridguard_agent/artifacts/formal_manipulation_v1_20260923")
ROLE = Path("hybridguard_agent/config/formal_manipulation_role_gate_v2")
POLICY_DIR = Path("hybridguard_agent/config/formal_manipulation_policy_v2")
MAIN_COHORTS = {"admitted_attack_triplet", "temporal_control_unknown"}
BASE = "final_v3_v2:App177:SRC-111"
VIEWS = ("App177", "Native84", "Host26", "AppWeb67", "NativeAppWeb151")
CANDIDATES = {"NW-001", "NW-002", "NW-005", "NVW-001", "NVW-002", "OFFDER-OS-001", "OFFDER-OS-002"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def decode(text):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, "Duplicate JSON key: " + k)
            result[k] = v
        return result

    def bad_constant(value):
        raise ValueError("Nonfinite JSON: " + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad_constant)


def read(path):
    return decode(Path(path).read_text())


def lines(path):
    return [decode(s) for s in Path(path).read_text().splitlines() if s.strip()]


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def encoded_lines(rows):
    return b"".join((json.dumps(r, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode() for r in rows)


def keyed(rows, field):
    result = {r[field]: r for r in rows}
    require(len(result) == len(rows), "Duplicate key: " + field)
    return result


def load_bindings(root):
    """Static binding checks. Does not load runtime modules or run gates."""
    docs = {name: read(root / ROLE / (name + ".json")) for name in
            ("applicability_policy", "decision_roles", "research_scope", "source_conditions", "family_bindings", "precondition_classification")}
    for name, d in docs.items():
        require(d.get("contract_version", d.get("version")) == CONTRACT, "Missing/mixed v2 config: " + name)
    bindings = keyed(lines(root / ROLE / "source_bindings.jsonl"), "rule_id")
    catalog = read(root / "hybridguard_agent/config/paired244_rule_catalog.v3.json")
    require(all(r.get("catalog_version") == catalog["catalog_version"] for r in bindings.values()), "Mixed source catalog bindings")
    active = {r["rule_id"]: r for r in catalog["rules"] if r["status"] == "ACTIVE"}
    roles = keyed(docs["decision_roles"]["roles"], "rule_id")
    scopes = keyed(docs["applicability_policy"]["scopes"], "rule_id")
    require(len(active) == 57 and set(active) == set(roles) == set(scopes) == set(bindings), "Incomplete ACTIVE bindings")
    candidate_ids = {rid for rid, r in roles.items() if r["decision_role"] == "alert_candidate"}
    require(candidate_ids == CANDIDATES, "Unreviewed candidate changes")
    for rid, b in bindings.items():
        for name in ("predicate", "parameters", "dependencies"):
            require(b[name] == active[rid].get(name, {}), "Original predicate drift: " + rid)
        for name in ("provenance_group", "decision_family", "original_evidence_family"):
            require(b[name] == roles[rid][name] == scopes[rid][name], "Binding mismatch: " + rid)
        require(roles[rid]["decision_role"] == scopes[rid]["decision_role"], "Scope role mismatch")
        require(roles[rid]["attribution_certainty"] == "UNKNOWN", "Attribution promotion")
    families = docs["family_bindings"]["families"]
    members = [rid for f in families for rid in f["rule_ids"]]
    require(len(members) == len(set(members)) == 57 and set(members) == set(active), "Family coverage mismatch")
    for f in families:
        require(set(f["candidate_ids"]) == set(f["rule_ids"]) & candidate_ids, "Family candidate mismatch")
        require(all(roles[rid]["decision_family"] == f["decision_family"] for rid in f["rule_ids"]), "Wrong family")
    source = docs["source_conditions"]
    groups = {g: sorted(rid for rid, r in roles.items() if r["provenance_group"] == g) for g in ("E", "O_u", "H", "C")}
    require(source["groups"] == groups, "Source group mismatch")
    conditions = keyed(source["conditions"], "condition_id")
    require(set(conditions) == {f"SRC-{i:03b}" for i in range(8)}, "Eight source IDs required")
    gates = docs["applicability_policy"]["common_gate_ids"]
    for cid, c in conditions.items():
        expected_groups = ["C"] + [g for bit, g in zip(cid[-3:], ("O_u", "H", "E")) if bit == "1"]
        require(c["included_groups"] == expected_groups and c["rule_ids"] == sorted(rid for g in expected_groups for rid in groups[g]), "Source condition mismatch")
        require(c["common_C_ids"] == groups["C"] and c["common_gate_ids"] == gates and c["applicability_policy_version"] == CONTRACT, "Common gate/C drift")
    policy = read(root / POLICY_DIR / "decision_policy.json")
    require(policy["contract_version"] == CONTRACT and policy["policy_version"] == POLICY and
            policy["role_gate_config_ref"] == str(ROLE) and type(policy["threshold"]) is int and policy["threshold"] == 1 and
            policy["aggregation"] == "distinct_family_OR", "Policy version/path/threshold mismatch")
    variants = read(root / POLICY_DIR / "variant_plan.json")
    require(variants["contract_version"] == CONTRACT and len(variants["variants"]) == 80, "S04 variant plan mismatch")
    vmap = keyed(variants["variants"], "variant_id")
    legacy = set(variants["methods"]["legacy19_v2"]["rule_ids"])
    device = set(read(root / "hybridguard_agent/config/deterministic_rule_predicates.v1.json")["compiled_rules"])
    official = {r["relation_id"] for r in read(root / "hybridguard_agent/config/official_semantic_relations.v1.json")["relations"] if r["executable_status"] == "compiled_v1"}
    require(legacy == device | official and len(legacy) == 19, "Legacy19 ID drift")
    for v in vmap.values():
        expected = set(conditions[v["condition_id"]]["rule_ids"])
        if v["method"] == "legacy19_v2":
            expected &= legacy
        require(v["input_view"] in VIEWS and v["method"] in {"legacy19_v2", "final_v3_v2"}, "Unknown variant")
        require(v["selected_rule_ids"] == sorted(expected) and v["candidate_rule_ids"] == sorted(expected & candidate_ids), "Variant ID mismatch")
        require(v["candidate_family_ids"] == sorted({roles[rid]["decision_family"] for rid in expected & candidate_ids}), "Variant family mismatch")
        require(v["common_gate_ids"] == gates and v["threshold"] == 1 and v["contract_version"] == CONTRACT, "Variant contract drift")
    return {"docs": docs, "roles": roles, "scopes": scopes, "bindings": bindings, "catalog": catalog,
            "variants": variants, "vmap": vmap, "policy": policy}


def population(facts, index, inputs, triplets, inventory):
    fact_map, idx, inp = keyed(facts, "candidate_id"), keyed(index, "opaque_id"), keyed(inputs, "opaque_id")
    require(set(idx) == set(inp), "Input/index mismatch")
    require({r["candidate_id"] for r in index} == set(fact_map) and len(index) == len(facts), "Stages not unique/exhaustive")
    for r in index:
        require(r["admission_fact"] == fact_map[r["candidate_id"]], "S01/S02 fact conflict")
        require(r["phase"] == r["admission_fact"]["phase"] and r["environment_group_id"] == r["admission_fact"]["environment_group_id"], "Phase/group conflict")
    require(sum(r["raw_rows"] for r in inventory) == len(facts), "Inventory raw-stage mismatch")
    denoms = {}
    for name, flag, phase in (("positive", "eligible_detection", "attack"), ("clean_pre", "eligible_pre_control", "clean_pre"),
                              ("clean_post", "eligible_post_control", "clean_post"), ("control_mid", "eligible_temporal_control", "control_mid")):
        denoms[name] = sorted(r["opaque_id"] for r in index if r["admission_fact"][flag] and r["phase"] == phase)
    denoms["all_temporal_points"] = sorted(r["opaque_id"] for r in index if r["admission_fact"]["eligible_temporal_control"])
    denoms["all_negative"] = sorted(set(denoms["clean_pre"] + denoms["clean_post"] + denoms["all_temporal_points"]))
    denoms["eligible_triplets"] = sorted([r["bundle_id"], r["triplet_id"]] for r in triplets if r["eligible_triplet"])
    denoms["unknown_truth"] = sorted(set(idx) - set(denoms["positive"]) - set(denoms["all_negative"]))
    main = sorted(r["opaque_id"] for r in index if r["cohort"] in MAIN_COHORTS)
    descriptive = sorted(set(idx) - set(main))
    require(set(denoms["positive"] + denoms["all_negative"]) <= set(main), "Qualified stage outside main matrix")
    return {"denominators": {k: {"n": len(v), "members": v} for k, v in denoms.items()},
            "main_ids": main, "descriptive_ids": descriptive,
            "counts": {"raw_stages": len(facts), "adapted_stages": len(inputs), "rejections": 0,
                       "candidate_bundles": len(inventory), "triplet_registry_rows": len(triplets),
                       "cohorts": dict(Counter(r["cohort"] for r in index)), "phases": dict(Counter(r["phase"] for r in index)),
                       "environment_groups": len({r["environment_group_id"] for r in index}),
                       "independent_physical_devices": None},
            "denominator_policy": "Inherited S01 task eligibility, not raw labels; FAILED/abstention stay in frozen denominators. No detector outcomes used.",
            "performance_branches": {"attack_response_and_010": "FROZEN_PENDING_S06", "clean_pre_post_FPR": "FROZEN_PENDING_S06",
                "temporal_control_FPR": "NOT_EVALUATED_NO_ELIGIBLE_LABELS", "MTC_TPR_FPR": "NOT_EVALUATED_UNLABELED",
                "lower_evidence_detection": "NOT_EVALUATED_DESCRIPTIVE_ONLY"}}


def matrices(pop, inputs, bindings):
    selected = {BASE: "S06", "legacy19_v2:App177:SRC-111": "S06"}
    selected.update({f"final_v3_v2:App177:SRC-{i:03b}": "S07" for i in range(7)})
    selected.update({f"final_v3_v2:{view}:SRC-111": "S08" for view in VIEWS if view != "App177"})
    lookup = {r["opaque_id"]: i for i, r in enumerate(inputs, 1)}
    expected = []
    for vid, step in sorted(selected.items()):
        for oid in pop["main_ids"]:
            expected.append({"opaque_id": oid, "variant_id": vid, "input_line": lookup[oid], "first_execution_step": step})
    for oid in pop["descriptive_ids"]:
        expected.append({"opaque_id": oid, "variant_id": BASE, "input_line": lookup[oid], "first_execution_step": "S10"})
    require(len(expected) == len({(r["opaque_id"], r["variant_id"]) for r in expected}), "Duplicated execution unit")
    registry = deepcopy(bindings["variants"])
    registry.update(variant_registry_version="formal-variant-registry-freeze-v2", selected_execution_variant_ids=sorted(selected),
        planned_risk_variant_count=len(selected), unused_structural_variants="67 S04 combinations defined but excluded from this protocol; adding them requires a versioned amendment before reading their outcomes.",
        common_roles_ref="frozen_sources/" + str(ROLE / "decision_roles.json"),
        common_scopes_ref="frozen_sources/" + str(ROLE / "applicability_policy.json"),
        common_families_ref="frozen_sources/" + str(ROLE / "family_bindings.json"),
        experiments={"S06": {"variant_ids": [BASE, "legacy19_v2:App177:SRC-111"], "cohort": "main216", "current_v3_projection": "saved relation diagnostic alias of final, not a third detector"},
                     "S07": {"variant_ids": [f"final_v3_v2:App177:SRC-{i:03b}" for i in range(8)], "cohort": "main216", "reuse_from_S06": [BASE]},
                     "S08": {"variant_ids": [f"final_v3_v2:{v}:SRC-111" for v in VIEWS], "cohort": "main216", "reuse_from_S06": [BASE]},
                     "S10": {"variant_ids": [BASE], "cohort": "lower_evidence45_and_incomplete1", "evaluation": "DESCRIPTIVE_ONLY"}},
        execution_order="first_execution_step then variant_id lexicographic then opaque_id lexicographic; same semantic unit reused, failed units never silently rerun",
        execution_authorized=False)
    return sorted(expected, key=lambda r: (r["first_execution_step"], r["variant_id"], r["opaque_id"])), registry


def evaluation_index(index, inputs):
    inp = keyed(inputs, "opaque_id")
    signatures = sorted({tuple(sorted((r["admission_fact"].get("original_attack_annotation") or {}).get("expected_mutations", []))) for r in index})
    signature_ids = {s: f"MECH-{i:02d}" for i, s in enumerate(signatures)}
    result = []
    for old in index:
        r = deepcopy(old)
        r["S02_configuration_id"] = r["configuration_id"]
        r["configuration_id"] = r["configuration_id"] or r["config_id"] or "CONTROL:" + r["bundle_id"]
        r["configuration_key_basis"] = "S02 configuration_id else config_id; controls without either use explicit bundle ID"
        sig = tuple(sorted((r["admission_fact"].get("original_attack_annotation") or {}).get("expected_mutations", [])))
        r["mechanism_id"] = signature_ids[sig]
        r["mechanism_definition"] = list(sig)
        r["mechanism_scope"] = "Declared expected field set from S01 annotation, not a detected mechanism or independently verified attack family"
        p = inp[r["opaque_id"]]["payload"]
        api = "app.android_native_data.build_fingerprint_layer.os_api_level"
        r["api_level"] = p["features"].get(api) if p["field_status"].get(api) == "observed" and p["field_quality"].get(api) == "observed_value" else "UNKNOWN"
        r["batch_id"] = r["bundle_id"]
        r["batch_scope"] = "Original material bundle; no cross-bundle joint experimental-batch identity inferred from date/name"
        r["evaluation_index_version"] = "formal-freeze-evaluation-index-v2"
        result.append(r)
    return result


def select_timing(index, main_ids, count=24):
    strata = defaultdict(list)
    for r in index:
        if r["opaque_id"] in set(main_ids):
            strata[(r["environment_group_id"], r["cohort"], r["phase"])].append(r["opaque_id"])
    for ids in strata.values():
        ids.sort()
    selected, round_number = [], 0
    while len(selected) < min(count, len(main_ids)):
        for key in sorted(strata):
            if round_number < len(strata[key]) and len(selected) < min(count, len(main_ids)):
                selected.append(strata[key][round_number])
        round_number += 1
    return sorted(selected), [{"environment_group_id": k[0], "cohort": k[1], "phase": k[2], "selected_ids": sorted(set(v) & set(selected))} for k, v in sorted(strata.items())]


def source_closure(root, seeds):
    """Finite AST import closure; imported code is read as text, not executed."""
    pending, result = list(seeds), set()
    while pending:
        rel = Path(pending.pop())
        if rel in result:
            continue
        require((root / rel).is_file(), "Missing participating source: " + str(rel))
        result.add(rel)
        tree = ast.parse((root / rel).read_text(), filename=str(rel))
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    package = rel.parent.parts
                    require(node.level <= len(package), "Relative import escapes source package")
                    base = package[:len(package) - node.level + 1]
                    module = ".".join((*base, *([module] if module else [])))
                names += [module] + [module + "." + a.name for a in node.names]
        for name in names:
            if not name.startswith("hybridguard_agent"):
                continue
            parts = name.split(".")
            for n in range(1, len(parts) + 1):
                prefix = Path(*parts[:n])
                for candidate in (prefix.with_suffix(".py"), prefix / "__init__.py"):
                    if (root / candidate).is_file() and candidate not in result:
                        pending.append(candidate)
    return sorted(result)


def destinations(root, output, config_dir):
    require(output is not None and config_dir is not None, "Both --output and --config-dir are mandatory")
    out, cfg = Path(output).resolve(), Path(config_dir).resolve()
    require(out != cfg and out not in cfg.parents and cfg not in out.parents, "Overlapping output/config directories")
    protected = [root / ARTIFACT / d for d in ("01_admission", "02_inputs", "03_registry", "03r_role_gate_v2", "04_contract")]
    protected += [root / ROLE, root / POLICY_DIR, root / "hybridguard_agent/config/formal_manipulation_v1"]
    protected += list((root / "hybridguard_agent/artifacts").glob("mtc_*"))
    protected += [root / "deliverables", root / "hybridguard-browser-fingerprint-research"]
    for dest in (out, cfg):
        require(not dest.exists(), "Destination exists; use a new version: " + str(dest))
        require(all(not (dest == p.resolve() or p.resolve() in dest.parents or dest in p.resolve().parents) for p in protected), "Protected/overlapping destination")
    return out, cfg


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def build(root=ROOT):
    root = Path(root)
    a, i, s4 = root / ARTIFACT / "01_admission", root / ARTIFACT / "02_inputs", root / ARTIFACT / "04_contract"
    acceptance = {}
    for step, folder in (("S01", "01_admission"), ("S02", "02_inputs"), ("S03", "03_registry"), ("S03-R", "03r_role_gate_v2"), ("S04", "04_contract")):
        v = read(root / ARTIFACT / folder / "VALIDATION.json")
        require(v["status"] == "PASS", "Unaccepted dependency: " + step)
        acceptance[step] = {"status": v["status"], "ref": str(ARTIFACT / folder / "VALIDATION.json")}
    bindings = load_bindings(root)
    facts, index, inputs = lines(a / "facts_and_eligibility.jsonl"), lines(i / "evaluation_index.jsonl"), lines(i / "inference_inputs.jsonl")
    triplets, inventory = lines(a / "triplet_registry.jsonl"), lines(a / "material_inventory.jsonl")
    require(not lines(i / "adapter_rejections.jsonl"), "New rejection matrix needs explicit protocol review")
    pop = population(facts, index, inputs, triplets, inventory)
    require(pop["counts"]["raw_stages"] == 262, "Accepted population changed")
    require(pop["counts"]["cohorts"] == {"admitted_attack_triplet": 162, "temporal_control_unknown": 54, "lower_evidence_attack": 45, "incomplete_attempt": 1}, "S02 cohort drift")
    require([pop["denominators"][k]["n"] for k in ("positive", "clean_pre", "clean_post", "eligible_triplets", "control_mid")] == [54, 54, 54, 54, 0], "S01 denominator drift")
    require(all(r["admission_fact"]["no_intervention"]["status"] == "UNKNOWN" for r in index if r["cohort"] == "temporal_control_unknown"), "Time control fact promotion")
    mapping = read(i / "field_mapping.json")
    allowed = {r["field"] for r in mapping["fields"]}
    for row in inputs:
        require(set(row) == {"opaque_id", "payload"}, "Leaky input envelope")
        p = row["payload"]
        require(set(p) == {"record_schema_version", "adapter_version", "features", "field_status", "field_quality"}, "Leaky payload")
        require(p["record_schema_version"] == "hybridguard-mtc-observation-v2" and p["adapter_version"] == "app177-triplet-adapter-v1", "Input version mismatch")
        require(len(allowed) == 177 and all(set(p[s]) == allowed for s in ("features", "field_status", "field_quality")), "Field-key drift")
    expected, variants = matrices(pop, inputs, bindings)
    enriched = evaluation_index(index, inputs)
    sample_ids, timing_strata = select_timing(enriched, pop["main_ids"])
    base = next(r["payload"] for r in lines(s4 / "SYNTHETIC_FIXTURES.jsonl") if r["fixture_id"] == "consistent")
    synthetic = fixtures(base, mapping, list(bindings["scopes"].values()))
    require(all(set(r["payload"][s]) == allowed for r in synthetic for s in ("features", "field_status", "field_quality")), "Synthetic field mismatch")
    diagnostics = diagnostic_spec(CANDIDATES)
    diag_units = []
    for d in diagnostics["definitions"]:
        ids = sorted(([r["opaque_id"] for r in synthetic if r["suite"] == "E4"] if "synthetic_semantic" in d["domains"] else []) +
                     (pop["main_ids"] if "main216" in d["domains"] else []))
        diag_units.extend({"opaque_id": oid, "diagnostic_id": d["diagnostic_id"], "step_id": "S09"} for oid in ids)
    synth_units = [{"opaque_id": r["opaque_id"], "variant_id": BASE, "step_id": "S09" if r["suite"] == "E4" else "S10"} for r in synthetic]
    timing = timing_spec(sample_ids)
    timing_units = [{"opaque_id": oid, "method_id": method, "mode_id": mode, "repeat_id": rep, "step_id": "S11"}
                    for oid in sample_ids for method in timing["methods"]
                    for mode, count in (("COLD", 1), ("WARMUP", 3), ("MEASURED", 20)) for rep in range(1, count + 1)]
    matches = [{"attack_key": [r["bundle_id"], r["triplet_id"]], "control_key": None, "matching_status": "UNMATCHED_NO_REGISTERED_JOINT_BATCH",
                "reason": "S01/S02 register bundle and environment but no common attack/control batch key. Names/dates alone do not establish pairing; retain environment/configuration strata.",
                "adds_negative_denominator_units": False} for r in triplets if r["eligible_triplet"]]
    return dict(bindings=bindings, population=pop, expected=expected, variants=variants, enriched=enriched,
                timing=timing, timing_strata=timing_strata, synthetic=synthetic, diagnostics=diagnostics,
                diag_units=diag_units, synth_units=synth_units, timing_units=timing_units, matching=matches,
                acceptance=acceptance, inventory=inventory)


def figure_spec(root, enriched):
    figure = deepcopy(read(root / POLICY_DIR / "figure_spec.json"))
    figure.update(figure_spec_version="formal-figure-spec-freeze-v2", supersedes_for_future_figures="formal-figure-spec-v2",
                  reason="S04 Fig.6 placeholder differs from the execution plan. Freeze Fig.6 as discrete operating points; move missingness/cost/fidelity to Table.2/3 and appendices. No S04 history overwritten.",
                  configuration_order=sorted({r["configuration_id"] for r in enriched}),
                  phase_order=["clean_pre", "attack", "clean_post"], temporal_phase_order=["clean_pre", "control_mid", "clean_post"],
                  result_selection="All configurations in frozen order; no selection by alert, success, effect, or statistical significance.")
    for f in figure["figures"]:
        f["denominator_ref"] = "evaluation/task_denominators.json"
    figure["figures"][-1].update(scope="Discrete predeclared risk operating points: temporal control_mid FPR x eligible attack TPR; coverage and n annotated",
        required_sources=["metrics"], operating_variant_ids=[f"final_v3_v2:App177:SRC-{i:03b}" for i in range(8)],
        status="NOT_EVALUATED_NO_ELIGIBLE_TEMPORAL_CONTROL_LABELS",
        fallback="Do not replace x-axis with clean_pre/post or unlabeled MTC. A separately labeled clean_pre/post table is allowed; no curve/ROC/smoothing/calibration.")
    figure["tables"] = [{"id": "Table.1", "scope": "Candidate/material/admission flow, all cohorts/bundles/groups and unresolved facts"},
                         {"id": "Table.2", "scope": "Fixed-denominator attack/recovery/coverage and separate MTC reuse block; E5 boundaries and E6 cost"},
                         {"id": "Table.3", "scope": "Source structure/overlap, gate and dedup diagnostic results, explanation references; no diagnostic risk TPR/FPR"}]
    return figure


def generate(*, output, config_dir, root=ROOT):
    root = Path(root).resolve()
    out, cfg = destinations(root, output, config_dir)  # Validate BOTH before any write.
    d = build(root)
    required_sources = source_closure(root, [
        "hybridguard_agent/scripts/run_formal_manipulation_eval.py",
        "hybridguard_agent/scripts/plot_formal_manipulation_eval.py",
        "hybridguard_agent/scripts/freeze_formal_manipulation_protocol.py",
        "hybridguard_agent/research/manipulation_eval/synthetic.py",
        "hybridguard_agent/tests/test_formal_manipulation_freeze.py",
    ])
    resources = [Path("hybridguard_agent/config") / f for f in (
        "paired244_rule_catalog.v1.json", "paired244_rule_catalog.v3.json",
        "paired244_browser_relations.v1.json", "paired244_browser_relations.v3.json",
        "deterministic_rule_predicates.v1.json", "official_semantic_relations.v1.json")]
    resources += [Path("hybridguard_agent/schemas") / f for f in ("field_registry.json", "expanded_v2.schema.json",
        "formal_manipulation_job_v2.schema.json", "formal_manipulation_long_tables_v2.schema.json", "manipulation_decision_v2.schema.json")]
    resources += [Path("scoring/rule_knowledge_base.json"), Path("android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv")]
    resources += sorted(p.relative_to(root) for directory in (ROLE, POLICY_DIR) for p in (root / directory).iterdir() if p.is_file())
    copies = [(p, Path("frozen_sources") / p, "PARTICIPATING_SOURCE" if p.suffix == ".py" else "RUNTIME_CONFIG") for p in required_sources + resources]
    a, i, s4 = ARTIFACT / "01_admission", ARTIFACT / "02_inputs", ARTIFACT / "04_contract"
    copies += [(i / "inference_inputs.jsonl", Path("blind/inputs.jsonl"), "BLIND_INPUT")]
    for f in ("facts_and_eligibility.jsonl", "triplet_registry.jsonl", "environment_group_registry.json", "exclusions.jsonl",
              "material_inventory.jsonl", "stage_accounting.jsonl", "missing_materials.jsonl", "manual_fact_queue.json", "history_links.json", "admission_policy.json"):
        copies.append((a / f, Path("evaluation/S01") / f, "EVALUATION_ONLY"))
    for f in ("evaluation_index.jsonl", "input_manifest.jsonl", "phase_associations.json", "adapter_rejections.jsonl", "bundle_history.json", "field_mapping.json"):
        copies.append((i / f, Path("evaluation/S02") / f, "EVALUATION_ONLY"))
    for folder in ("01_admission", "02_inputs", "03_registry", "03r_role_gate_v2", "04_contract"):
        for f in ("VALIDATION.json", "STEP_REPORT.md"):
            copies.append((ARTIFACT / folder / f, Path("evaluation/acceptance") / folder / f, "PRIOR_ACCEPTANCE"))
    for f in ("source_registry.jsonl", "family_registry.json", "primary_source_review.json"):
        copies.append((Path("hybridguard_agent/config/formal_manipulation_v1") / f, Path("evaluation/provenance_v1") / f, "PROVENANCE_ONLY_NOT_V2_ROLE_AUTHORITY"))
    copies.append((ARTIFACT / "03_registry/source_uncertainties.jsonl", Path("evaluation/source_uncertainties.jsonl"), "EVALUATION_ONLY"))
    p6refs = [Path("hybridguard_agent/config/mtc_p6_protocol.v1.json"),
              Path("hybridguard_agent/artifacts/mtc_p6_fixed_20260923/protocol_FREEZE.json")]
    p6refs += [Path("deliverables/mtc_p6_20260923") / f for f in ("RESERVED_ACCESS.json", "RESERVED_RELEASE.json", "RESERVED_FIRST_READ.json")]
    copies += [(p, Path("evaluation/P6_metadata") / p.name, "P6_METADATA_ONLY_NO_OUTCOMES") for p in p6refs]
    for f in ("EXECUTION_PLAN.md", "S03_R_CONTRACT_REVISION_v2.md", "S04_CONTRACT_IMPLEMENTATION_v2.md"):
        copies.append((Path("deliverables/formal_experiment_execution_plan") / f, Path("evaluation/plan_at_freeze") / f, "PRE_FREEZE_PLAN_TIMEPOINT"))
    for f in ("SYNTHETIC_FIXTURES.jsonl", "SOURCE_STRUCTURAL_LIMITS.json"):
        copies.append((s4 / f, Path("synthetic/reference") / f, "S04_SYNTHETIC_OR_STATIC_REFERENCE"))
    require(all((root / src).is_file() for src, _, _ in copies), "Missing freeze dependency file")
    require(len(copies) == len({str(dest) for _, dest, _ in copies}), "Duplicate frozen destination")
    require(not any((root / ARTIFACT / name).exists() for name in ("06_e1", "07_e2", "08_e3", "09_e4", "10_e5", "11_e6")), "Formal output already present; cannot claim a pre-run freeze")
    # Capture only participating-source/config differences, not the noisy Android tree.
    participating = [str(p) for p in required_sources + resources]
    patch = git(root, "diff", "HEAD", "--", *participating)
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all", "--", *participating)
    now = datetime.now(timezone.utc).isoformat()
    head = git(root, "rev-parse", "HEAD")
    p6_access = read(root / "deliverables/mtc_p6_20260923/RESERVED_ACCESS.json")
    require(p6_access["status"] == "CONSUMED_FIXED_EVALUATION", "P6 exposure ledger conflict")
    pop = d["population"]
    dry = {"schema_version": "formal-dry-plan-v2", "status": "PLANNED_NOT_AUTHORIZED", "detector_calls": 0,
           "risk_unique_unit_count": len(d["expected"]), "risk_variant_count": 13,
           "risk_first_execution_counts": dict(Counter(r["first_execution_step"] for r in d["expected"])),
           "diagnostic_unit_count": len(d["diag_units"]), "synthetic_risk_unit_count": len(d["synth_units"]),
           "timing_unit_count": len(d["timing_units"]),
           "unit_files": ["expected_units.jsonl", "diagnostic_expected_units.jsonl", "synthetic_expected_units.jsonl", "timing_expected_units.jsonl"]}
    metrics = deepcopy(read(root / POLICY_DIR / "metric_spec.json"))
    metrics.update(metric_spec_version="formal-metric-spec-freeze-v2", task_denominators_ref="evaluation/task_denominators.json",
        main_cohort_ids_ref="evaluation/population.json#main_ids", descriptive_cohort_ids_ref="evaluation/population.json#descriptive_ids",
        positive_n=54, clean_pre_n=54, clean_post_n=54, verified_control_mid_n=0, all_verified_negative_n=108,
        eligible_triplets_n=54, temporal_control_FPR="NOT_EVALUATED_NO_ELIGIBLE_LABELS",
        paired_difference_in_differences="NOT_EVALUATED_NO_REGISTERED_JOINT_BATCH",
        intervals="NOT_ESTIMABLE_RELATED_GROUPS; no bootstrap in this App protocol; P6 saved intervals keep original P6 scope",
        secondary_precision_F1_accuracy="NOT_EVALUATED_NO_NATURAL_PREVALENCE; not part of this version's claims",
        configuration_key="S02 configuration_id if present, else config_id; null control IDs use CONTROL:<bundle_id>; original S02 fields archived unchanged",
        frozen_zero_denominator="null rate / NO_ELIGIBLE_LABELS, never 0%", retry_policy="No automatic retries or best-run replacement. Preserve FAILED; technical repair uses new run_id with reason, semantic changes require new protocol version.")
    exposure = {"version": VERSION, "App_track": "EXPOSED_MATERIAL_REPLAY_NOT_BLIND_TEST", "S01_S02_materials_previously_read": True,
        "historical_App177_exposure": {"manifests": 23, "paired_records": 69, "two_state_rows": 138,
            "basis": "EXECUTION_PLAN section 2.3 and historical P6 diagnostic access; no detector results reread in S05"},
        "attack_side_prior_evaluations": "Original manifests/annotations and historical attack-side reports were available before this study; do not inherit their effect targets or call the current material held-out",
        "MTC_track": "P6_SAVED_OUTPUT_REUSE_ONLY_NOT_NEW_BLIND_EVALUATION", "P6_reserved_access": p6_access,
        "P6_QC_exposure": "Global QC and discovery/development inspected before reserved fixed evaluation; P2 LOCKED remains historical",
        "S03_R_basis": "Existing official/derived sources, collection code and declared discovery/development review, synthetic boundaries; no formal prediction-based selection",
        "S04_exposure": "Synthetic only; old pre-push/pre-review report wording is a historical timepoint",
        "S05_inputs_read": "Static saved topology, inherited facts/metadata, native API stratum, IDs and byte copying; no rule evaluation",
        "unknowns": "Physical device independence, private logs, authorization/intent and some source versions remain unknown",
        "no_new_splits": True, "no_outcome_based_selection": True}
    access = {"version": "formal-evaluation-access-policy-v2",
        "scheduler_allowed": ["blind/inputs.jsonl", "expected_units.jsonl", "step_execution_plans/*.json", "protocol.json", "frozen_sources/"],
        "worker_arguments": ["current payload only", "fixed v2 contract", "condition_id", "input_view", "method"],
        "worker_forbidden": ["evaluation/", "original raw/manifests/logs/receipts", "S01/S02 fact tables", "labels", "phase", "tool", "sample config", "session/install/environment IDs", "original paths", "expected_mutations", "future post", "formal saved predictions for selection"],
        "evaluation_allowed_after": "All expected prediction/event/runtime/failure/abstention files closed and unique, run manifest PREDICTIONS_CLOSED, exact frozen job binding checked",
        "evaluation_inputs": ["saved closed outputs", "evaluation/evaluation_index.jsonl", "evaluation/S01/triplet_registry.jsonl", "evaluation/task_denominators.json", "evaluation/control_matching.json"],
        "reporting": "Saved evaluation tables and separately authorized P6 saved export only; no detector",
        "S05_allowed": "Exact static ledgers/config/source and input copying; no predicates, runtime, metrics on real data or P6 outcome reads",
        "enforcement_boundary": "Versioned file/interface contract and S04 isolation tests; not a claim of OS process sandbox enforcement",
        "identical_payload_units": "Keep distinct opaque IDs, never content deduplication",
        "formal_jobs": "S05 writes non-runnable plans only. After explicit step authorization materialize the existing S04 job schema with authorized_execution_step; JSON freeze status alone is not permission."}
    p6 = {"mode": "SAVED_EXPORT_ONLY", "steps": ["S08", "S10"], "source_protocol_ref": "evaluation/P6_metadata/protocol_FREEZE.json",
        "view_ids": ["App177", "Full244_no_cross", "Full244"], "primary_expected_by_split": {"discovery": 630, "development": 144, "reserved_validation": 117},
        "repeat_rows": 137, "reserved_repeat_rows": 18, "origin": "P6_SAVED_OUTPUT", "missing_event_details": "NOT_RECORDED_IN_P6",
        "saved_files_for_future_export": ["results.jsonl", "matrix_summary.json", "paired_comparisons.json", "repeat_results.jsonl", "repeat_summary.json", "counterexamples.jsonl"],
        "source_root": "hybridguard_agent/artifacts/mtc_p6_fixed_20260923", "new_detector_runs": 0,
        "performance_metrics": "NOT_EVALUATED_UNLABELED", "natural_missingness": {"App_only": 654, "partial": 11, "same_session_extras": 6,
            "mode": "SAVED_P1_ACCOUNTING_ONLY_NO_NEW_MTC_PREDICTIONS_IN_THIS_PROTOCOL", "reason": "Keep this protocol bounded to accepted App177 replay and P6 saved reuse. A new natural-MTC runtime matrix requires explicit source/unit binding in another amendment before execution."},
        "hash_scope": "Only original P6 protocol and access metadata bound now; large outcome files remain unread. At authorized export record source file identity/size and original frozen provenance, no historical audit script or rewrite."}
    candidate_families = sorted({d["bindings"]["roles"][rid]["decision_family"] for rid in CANDIDATES})
    protocol = {"protocol_version": VERSION, "study_version": STUDY, "contract_version": CONTRACT, "policy_version": POLICY,
        "status": "FROZEN", "frozen_at": now, "code_commit": head, "role_gate_config_ref": str(ROLE), "policy_config_ref": str(POLICY_DIR),
        "frozen_role_gate_config_ref": "frozen_sources/" + str(ROLE), "frozen_policy_ref": "frozen_sources/" + str(POLICY_DIR / "decision_policy.json"),
        "source_snapshot_root": "frozen_sources", "source_binding_scope": "Participating Python import closure and explicit runtime configs/data only; no repository-wide audit",
        "strategy": "Fixed distinct-family OR; threshold 1; no weights, training, calibration, threshold search or LLM",
        "candidate_rule_ids": sorted(CANDIDATES), "candidate_family_ids": candidate_families,
        "candidate_rules": 7, "candidate_families": 5, "attribution": "UNKNOWN_NOT_ATTACK_PROOF", "calibrated_attack_probability": None,
        "input_ref": "blind/inputs.jsonl", "evaluation_index_ref": "evaluation/evaluation_index.jsonl",
        "variant_registry_ref": "variant_registry.json", "denominators_ref": "evaluation/task_denominators.json",
        "metric_spec_ref": "metric_spec.json", "figure_spec_ref": "figure_spec.json", "access_policy_ref": "evaluation_access_policy.json",
        "diagnostic_spec_ref": "diagnostic_spec.json", "synthetic_fixtures_ref": "synthetic/fixtures.jsonl", "timing_spec_ref": "timing_spec.json",
        "expected_unit_files": dry["unit_files"], "expected_unit_counts": {k: v for k, v in dry.items() if k.endswith("count")},
        "prior_acceptance": d["acceptance"], "performance_branches": pop["performance_branches"],
        "execution_authorization": {"S05": "STATIC_FREEZE_ONLY", "S06_S12": "PENDING_SEPARATE_USER_AUTHORIZATION", "formal_execution_authorized": False},
        "mutability": "Immutable snapshot. Changes to source behavior, candidates, gates, threshold, input eligibility, metric definitions or selected units require a new version; never overwrite this freeze.",
        "runtime_binding": "Future execution uses copied frozen_sources with the same internal layout and explicitly passed copied v2 config/policy. Compare resolved module paths and input/job bindings before running. Future S09/S10/S11 wrappers must implement these finite definitions, not alter the risk chain; record wrapper source/version at their authorized implementation.",
        "formal_predictions_created_in_S05": 0, "formal_metrics": "NOT_EVALUATED", "model_calls": 0, "collection_started": False}
    out.mkdir(parents=True)
    cfg.mkdir(parents=True)
    entries = []

    def put(dest, data, category, source=None):
        path = out / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        entries.append({"path": str(dest), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                        "category": category, "source": str(source) if source else None})

    for src, dest, category in copies:
        put(dest, (root / src).read_bytes(), category, src)
    generated = {
        "variant_registry.json": d["variants"], "evaluation/population.json": pop,
        "evaluation/task_denominators.json": pop["denominators"], "evaluation/control_matching.json": {"matches": [], "unmatched": d["matching"], "paired_delta_status": "NOT_EVALUATED_NO_REGISTERED_JOINT_BATCH"},
        "evaluation/timing_strata.json": d["timing_strata"], "diagnostic_spec.json": d["diagnostics"],
        "timing_spec.json": d["timing"], "metric_spec.json": metrics, "figure_spec.json": figure_spec(root, d["enriched"]),
        "exposure_history.json": exposure, "evaluation_access_policy.json": access, "p6_reuse_spec.json": p6, "dry_plan.json": dry,
        "source_environment.json": {"HEAD": head, "branch": git(root, "branch", "--show-current"), "python": sys.version,
            "OS": platform.platform(), "machine": platform.machine(), "processor": platform.processor(),
            "dependency_policy": "Participating runtime is stdlib Python; no dependency install or model runtime. Imported local modules are explicitly copied.",
            "participating_git_status": status.splitlines(), "participating_diff_ref": "participating_worktree.diff",
            "new_untracked_sources": [str(p) for p in required_sources if not git(root, "ls-files", "--", str(p))],
            "unrelated_workspace": "Preserved, excluded from source binding; current APK/build/TLS edits do not rewrite old collection release."},
    }
    for step in ("S06", "S07", "S08", "S10"):
        units = [r for r in d["expected"] if r["first_execution_step"] == step]
        vids = sorted({r["variant_id"] for r in units})
        generated[f"step_execution_plans/{step}.json"] = {"schema_version": "formal-static-step-plan-v2", "status": "PLANNED_NOT_AUTHORIZED", "step_id": step,
            "variants": [{k: d["bindings"]["vmap"][vid][k] for k in ("variant_id", "method", "input_view", "condition_id")} for vid in vids],
            "expected_units": [{k: r[k] for k in ("opaque_id", "variant_id", "input_line")} for r in units],
            "reuse": d["variants"]["experiments"][step].get("reuse_from_S06", []), "not_a_runnable_S04_job": True}
    for name, value in generated.items():
        put(Path(name), encoded(value), "GENERATED_STATIC_SPEC")
    for name, rows in (("expected_units.jsonl", d["expected"]), ("diagnostic_expected_units.jsonl", d["diag_units"]),
                       ("synthetic_expected_units.jsonl", d["synth_units"]), ("timing_expected_units.jsonl", d["timing_units"]),
                       ("evaluation/evaluation_index.jsonl", d["enriched"]), ("synthetic/fixtures.jsonl", d["synthetic"])):
        put(Path(name), encoded_lines(rows), "GENERATED_STATIC_UNITS_OR_INPUTS")
    put(Path("participating_worktree.diff"), (patch + "\n").encode(), "PARTICIPATING_DIFF_ONLY")
    entries.sort(key=lambda e: e["path"])
    digest = hashlib.sha256(encoded(entries)).hexdigest()
    protocol["protocol_digest"] = digest
    protocol_bytes = encoded(protocol)
    (out / "protocol.json").write_bytes(protocol_bytes)
    (cfg / "protocol.json").write_bytes(protocol_bytes)
    manifest = {"manifest_version": "formal-freeze-manifest-v2", "protocol_digest": digest,
        "digest_definition": "sha256(sorted bound_files canonical JSON encoded by freeze.encoded); protocol binds that digest; protocol SHA is outside the digest to avoid self-reference",
        "bound_files": entries, "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
        "config_copy": str(cfg / "protocol.json"), "copied_source_count": len(required_sources), "runtime_resource_count": len(resources),
        "hash_scope": "One finite participating-source/config/input freeze, no whole-repo hashing; acceptance reports and subsequent status/report files excluded from self-reference"}
    (out / "FREEZE_MANIFEST.json").write_bytes(encoded(manifest))
    result = validate(out, config_dir=cfg)
    (out / "STATIC_VALIDATION.json").write_bytes(encoded(result))
    return {"output": str(out), "config_dir": str(cfg), "status": result["status"], "protocol_digest": digest, "counts": dry}


def validate(output, *, config_dir):
    """One bounded manifest/schema/set validation, never import a runtime."""
    out = Path(output)
    manifest, protocol = read(out / "FREEZE_MANIFEST.json"), read(out / "protocol.json")
    entries = manifest["bound_files"]
    require(len(entries) == len({e["path"] for e in entries}), "Duplicate manifest path")
    for entry in entries:
        path = (out / entry["path"]).resolve()
        require(out.resolve() in path.parents, "Manifest path escape")
        data = path.read_bytes()
        require(len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"], "Frozen content mismatch: " + entry["path"])
    digest = hashlib.sha256(encoded(entries)).hexdigest()
    require(digest == manifest["protocol_digest"] == protocol["protocol_digest"], "Protocol binding mismatch")
    require(hashlib.sha256((out / "protocol.json").read_bytes()).hexdigest() == manifest["protocol_sha256"], "Protocol content mismatch")
    require((Path(config_dir) / "protocol.json").read_bytes() == (out / "protocol.json").read_bytes(), "Independent config copy differs")
    require(protocol["protocol_version"] == VERSION and protocol["contract_version"] == CONTRACT and protocol["policy_version"] == POLICY, "Protocol version mismatch")
    require(protocol["execution_authorization"]["formal_execution_authorized"] is False, "Freeze cannot authorize execution")
    inputs = lines(out / "blind/inputs.jsonl")
    units = lines(out / "expected_units.jsonl")
    require(len(units) == len({(r["opaque_id"], r["variant_id"]) for r in units}) == 2854, "Unit uniqueness/count")
    require(all(set(r) == {"opaque_id", "variant_id", "input_line", "first_execution_step"} and inputs[r["input_line"] - 1]["opaque_id"] == r["opaque_id"] for r in units), "Unit schema/input binding")
    require({r["opaque_id"] for r in units} == {r["opaque_id"] for r in inputs} and len(inputs) == 262, "All stages must have a planned destination")
    pop = read(out / "evaluation/population.json")
    for oid in pop["main_ids"]:
        require(sum(r["opaque_id"] == oid for r in units) == 13, "Main matrix incomplete")
    for oid in pop["descriptive_ids"]:
        require([(r["variant_id"], r["first_execution_step"]) for r in units if r["opaque_id"] == oid] == [(BASE, "S10")], "Descriptive matrix leaked into formal evaluation")
    original = lines(out / "evaluation/S02/evaluation_index.jsonl")
    current = lines(out / "evaluation/evaluation_index.jsonl")
    require([r["admission_fact"] for r in original] == [r["admission_fact"] for r in current], "Facts changed")
    rebuilt = population(lines(out / "evaluation/S01/facts_and_eligibility.jsonl"), original, inputs,
                         lines(out / "evaluation/S01/triplet_registry.jsonl"), lines(out / "evaluation/S01/material_inventory.jsonl"))
    require(rebuilt == pop and rebuilt["denominators"] == read(out / "evaluation/task_denominators.json"), "Denominator reconstruction differs")
    runtime_names = ("hybridguard_agent.rules", "hybridguard_agent.runtime", "hybridguard_agent.verification", "hybridguard_agent.official_semantics")
    loaded = sorted(m for m in sys.modules if m.startswith(runtime_names) or m.endswith((".manipulation_eval.runner", ".manipulation_eval.provenance_revision")))
    require(not loaded, "S05 imported forbidden executable chain")
    require(not list(out.rglob("predictions.jsonl")) and not list(out.rglob("rule_events.jsonl")), "Freeze created prediction/event files")
    for name, key in (("diagnostic_expected_units.jsonl", ("opaque_id", "diagnostic_id")),
                      ("synthetic_expected_units.jsonl", ("opaque_id", "variant_id")),
                      ("timing_expected_units.jsonl", ("opaque_id", "method_id", "mode_id", "repeat_id"))):
        rows = lines(out / name)
        require(len(rows) == len({tuple(r[k] for k in key) for r in rows}), "Duplicate auxiliary unit")
    return {"status": "PASS", "scope": "FINITE_MANIFEST_SCHEMA_SET_CHECKS_ONLY", "checks": {
        "finite_manifest_bytes_match": True, "protocol_config_version_and_digest_match": True,
        "unique_2854_risk_units_and_262_stage_destinations": True, "same_main216_denominator_in_13_variants": True,
        "lower46_single_descriptive_condition": True, "S01_denominators_reconstructed": True,
        "S02_facts_unchanged": True, "auxiliary_units_unique": True, "no_runtime_import": True,
        "no_predictions_or_rule_events": True, "execution_not_authorized_by_freeze": True},
        "runtime_modules_loaded": loaded, "real_predictions": 0, "detector_calls": 0, "LLM_calls": 0,
        "bound_file_count": len(entries)}
