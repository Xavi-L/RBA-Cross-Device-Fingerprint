"""Fixed-cohort input/rule/source comparisons; no fitting or attack labels."""
from __future__ import annotations

from collections import Counter, defaultdict
import copy
import json
import random
from pathlib import Path
from statistics import mean, median

from hybridguard_agent.evidence.paired244 import VIEWS, surface_of
from hybridguard_agent.rules.paired244 import load_catalog, CONFIG

SPLITS = ("discovery", "development", "reserved_validation")
V3 = "paired244-runtime-catalog-v3"
ASSESSED = {"MATCH", "COUNTEREXAMPLE", "CONTEXT_OBSERVED", "POLICY_MISMATCH"}
METRICS = ("applicable_checks", "unassessed_checks", "not_applicable_checks",
           "relation_deviation_checks", "collector_issue_checks", "policy_mismatch_checks",
           "relation_deviation_present", "uncertain_present", "used_fields")
PRIORITY = ("FAILED", "COUNTEREXAMPLE", "POLICY_MISMATCH", "UNKNOWN", "NOT_EVALUATED",
            "CONTEXT_OBSERVED", "MATCH", "NOT_APPLICABLE")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_lines(path):
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def definitions():
    rows = [{"id": view, "view": view, "catalog": "v3", "selection": "all_active"}
            for view in ("Native84", "Host26", "AppWeb67", "Browser67", "NativeAppWeb151",
                         "AppWebBrowser134", "App177", "Full244")]
    rows += [{"id": "Full244_no_cross", "view": "Full244", "catalog": "v3", "selection": "no_app_browser_relation"}]
    rows += [{"id": f"App177_{v}", "view": "App177", "catalog": v, "selection": "all_active"}
             for v in ("v1", "v2")]
    rows += [{"id": "Full244_" + suffix, "view": "Full244", "catalog": "v3", "selection": suffix}
             for suffix in ("empirical", "official", "empirical_official", "support")]
    return rows


def is_cross(rule):
    refs = rule["dependencies"]
    return any(p.startswith("browser.") for p in refs) and any(p.startswith("app.") for p in refs)


def select_rules(catalog, selection):
    active = [r for r in catalog["rules"] if r["status"] == "ACTIVE"]
    lanes = {"empirical": {"device_mined_rule"}, "official": {"official_derived_semantic_rule"},
             "empirical_official": {"device_mined_rule", "official_derived_semantic_rule"},
             "support": {"collector_context", "collector_derived_consistency", "project_deployment_policy"}}
    if selection == "all_active":
        return active
    if selection == "no_app_browser_relation":
        return [r for r in active if not is_cross(r)]
    if selection not in lanes:
        raise ValueError("Unknown frozen source selection")
    return [r for r in active if r["source_lane"] in lanes[selection]]


def variants(specs=None):
    result = {}
    for spec in specs or definitions():
        base = load_catalog(CONFIG / f"paired244_rule_catalog.{spec['catalog']}.json")
        selected = select_rules(base, spec["selection"])
        ids = {r["rule_id"] for r in selected}
        catalog = copy.deepcopy(base)
        catalog["rules"] = [r for r in catalog["rules"] if r["status"] != "ACTIVE" or r["rule_id"] in ids]
        # Predicate/threshold/source objects themselves are never changed.
        catalog["evaluation_selection"] = {"variant_id": spec["id"], "base_catalog": base["catalog_version"],
                                            "active_rule_ids": sorted(ids), "predicate_changes": False}
        result[spec["id"]] = {**spec, "catalog_object": catalog, "active_rule_ids": sorted(ids),
                              "active_count": len(ids), "source_lanes": dict(Counter(r["source_lane"] for r in selected)),
                              "cross_rule_ids": [r["rule_id"] for r in selected if is_cross(r)],
                              "evidence_families": sorted({r["evidence_family"] for r in selected}),
                              "empirically_screened_official_ids": [r["rule_id"] for r in selected
                                  if r["source_lane"] == "official_derived_semantic_rule" and r.get("empirical_selection_applied")]}
    return result


def load_p6_rows(plan, snapshot, split, role, release):
    """P6-only release: leave P2 lock and P3 reader unchanged."""
    if split not in SPLITS or role not in {"primary_representative", "paired_repeat_observation"}:
        raise ValueError("Unregistered P6 cohort")
    guard = read_json(release)
    if (guard.get("status") != "FROZEN_FOR_FIXED_EVALUATION" or not guard.get("protocol_frozen")
            or not guard.get("rules_frozen") or not guard.get("exposure_disclosed")
            or Path(guard["plan_dir"]).resolve() != Path(plan).resolve()
            or Path(guard["snapshot_dir"]).resolve() != Path(snapshot).resolve()):
        raise ValueError("P6 release requires frozen rules/protocol and exposure disclosure")
    if read_json(Path(plan) / "reserved_validation_LOCK.json")["status"] != "LOCKED":
        raise ValueError("Historical P2 lock must remain unchanged")
    metadata = list(read_lines(Path(plan) / "sample_registry.jsonl"))
    if len({r["sample_id"] for r in metadata}) != len(metadata):
        raise ValueError("Duplicate P2 sample ID")
    groups = defaultdict(set)
    for row in metadata:
        groups[row["group_id"]].add(row["split"])
    if any(len(s) != 1 for s in groups.values()):
        raise ValueError("P2 cross-split group conflict")
    selected = {r["source_line"]: r for r in metadata if r["source_view"] == "paired_244"
                and r["split"] == split and r["analysis_role"] == role}
    expected = [r for r in metadata if r["source_view"] == "paired_244"
                and r["split"] == split and r["analysis_role"] == role]
    if len(selected) != len(expected) or any(type(n) is not int or n < 1 for n in selected):
        raise ValueError("Invalid/duplicate P2 source line")
    rows = []
    with (Path(snapshot) / "paired_244.jsonl").open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            meta = selected.get(line_no)
            if meta is None:
                continue
            row = json.loads(line)
            if (row.get("record_schema_version") != "hybridguard-mtc-observation-v2"
                    or row.get("dataset_view") != "paired_244" or row.get("feature_count") != 244
                    or row.get("sample_id") != meta["sample_id"] or row.get("profile") != meta["profile"]
                    or row.get("app", {}).get("payload_sha256") != meta["app_payload_sha256"]
                    or row.get("browser", {}).get("payload_sha256") != meta["browser_payload_sha256"]):
                raise ValueError("P1/P2 frozen input binding mismatch")
            row["_p2"] = {k: meta[k] for k in ("group_id", "split", "analysis_role", "source_line")}
            rows.append(row)
    if len(rows) != len(expected):
        raise ValueError("P2 selected rows absent from P1")
    return rows


def pack_result(output, spec):
    ids = set(spec["active_rule_ids"])
    rules = [r for r in output["rule_execution"]["rule_results"] if r["rule_id"] in ids]
    if {r["rule_id"] for r in rules} != ids:
        raise ValueError("Frozen rule selection mismatch")
    for rule in rules:
        if not set(rule["used_fields"]) <= set(output["evidence_bundle"]["fields"]):
            raise ValueError("Ablated field reached predicate")
        if any(surface_of(p) not in VIEWS[spec["view"]] for p in rule["used_fields"]):
            raise ValueError("Ablated surface reached predicate")
    counts = Counter(r["outcome"] for r in rules)
    deviations = [r for r in rules if r["outcome"] == "COUNTEREXAMPLE"
                  and r["source_lane"] != "collector_derived_consistency"]
    collectors = [r for r in rules if r["outcome"] == "COUNTEREXAMPLE"
                  and r["source_lane"] == "collector_derived_consistency"]
    metrics = {"applicable_checks": sum(counts[s] for s in ASSESSED),
               "unassessed_checks": counts["UNKNOWN"] + counts["NOT_EVALUATED"],
               "not_applicable_checks": counts["NOT_APPLICABLE"],
               "relation_deviation_checks": len(deviations), "collector_issue_checks": len(collectors),
               "policy_mismatch_checks": counts["POLICY_MISMATCH"],
               "relation_deviation_present": int(bool(deviations)),
               "uncertain_present": int(bool(counts["UNKNOWN"] + counts["NOT_EVALUATED"])),
               "used_fields": len({p for r in rules for p in r["used_fields"]})}
    return {"status": "COMPLETE", "active_checks": len(ids), "outcome_counts": dict(counts), "metrics": metrics,
            "rule_outcomes": {r["rule_id"]: r["outcome"] for r in rules},
            "decision_status": output["decision"]["decision_status"],
            "relation_evidence_families": sorted({r["evidence_family"] for r in deviations}),
            "verification_valid": output["decision_trace"]["verification"]["valid"],
            "attack_classification": output["decision"]["attack_classification"]}, rules


def group_outcome(outcomes):
    return next(state for state in PRIORITY if state in outcomes)


def percentile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    pos = (len(values) - 1) * fraction
    low = int(pos)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (pos - low)


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["group_id"]].append(row)
    failures = sum(r["status"] != "COMPLETE" for r in rows)
    means = None if failures else {m: mean(mean(r["metrics"][m] for r in members)
                                    for members in groups.values()) for m in METRICS}
    times = [r["elapsed_ms"] for r in rows if r["status"] == "COMPLETE"]
    return {"records": len(rows), "groups": len(groups), "failed_records": failures,
            "groups_with_failure": sum(any(r["status"] != "COMPLETE" for r in rs) for rs in groups.values()),
            "group_weighted_means": means,
            "decision_counts": dict(Counter(r.get("decision_status", "FAILED") for r in rows)),
            "record_outcome_counts": dict(sum((Counter(r.get("outcome_counts", {})) for r in rows), Counter())),
            "timing_ms": {"n": len(times), "median": median(times) if times else None,
                          "p95": percentile(times, .95)},
            "metric_boundary": "Unlabelled fixed-rule observations; failures never converted to negative/pass."}


def paired_comparison(before, after, *, bootstrap_replicates=2000, seed=620260923, interval=False):
    left, right = ({r["sample_id"]: r for r in rows} for rows in (before, after))
    if len(left) != len(before) or len(right) != len(after) or set(left) != set(right):
        raise ValueError("Comparison must preserve exactly the same cohort")
    groups = defaultdict(list)
    transitions = Counter()
    failures = 0
    for sid, b in left.items():
        a = right[sid]
        if b["group_id"] != a["group_id"]:
            raise ValueError("Paired comparison group mismatch")
        transitions[(b.get("decision_status", "FAILED"), a.get("decision_status", "FAILED"))] += 1
        if b["status"] != "COMPLETE" or a["status"] != "COMPLETE":
            failures += 1
            continue
        groups[b["group_id"]].append({m: a["metrics"][m] - b["metrics"][m] for m in METRICS})
    result = {"records": len(left), "failed_pairs": failures,
              "transitions": [{"before": b, "after": a, "records": n} for (b, a), n in transitions.items()],
              "group_weighted_delta": None, "conditional_95_percent_bootstrap": None}
    if failures or not groups:
        return result
    values = [{m: mean(r[m] for r in rs) for m in METRICS} for rs in groups.values()]
    result.update(groups=len(values), group_weighted_delta={m: mean(r[m] for r in values) for m in METRICS})
    if interval:
        rng = random.Random(seed)
        metrics = ("applicable_checks", "relation_deviation_present", "unassessed_checks")
        estimates = defaultdict(list)
        for _ in range(bootstrap_replicates):
            draw = [values[rng.randrange(len(values))] for _ in values]
            for m in metrics:
                estimates[m].append(sum(v[m] for v in draw) / len(draw))
        result["conditional_95_percent_bootstrap"] = {m: [percentile(v, .025), percentile(v, .975)]
                                                       for m, v in estimates.items()}
    return result
