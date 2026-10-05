"""Static S04 variant/figure definitions; no dataset or experiment execution."""
from hybridguard_agent.research.manipulation_eval.baselines import legacy19_catalog
from hybridguard_agent.research.manipulation_eval.contract import VERSION, CONFIG_REF

VIEWS = ("App177", "Native84", "Host26", "AppWeb67", "NativeAppWeb151")


def variant_plan(contract):
    legacy = legacy19_catalog()
    variants = []
    for method in ("final_v3_v2", "legacy19_v2"):
        catalog = contract["catalog"] if method == "final_v3_v2" else legacy
        active = {r["rule_id"] for r in catalog["rules"] if r["status"] == "ACTIVE"}
        for view in VIEWS:
            for cid, condition in contract["conditions"].items():
                ids = sorted(active & set(condition["rule_ids"]))
                candidates = [rid for rid in ids if contract["roles"][rid]["decision_role"] == "alert_candidate"]
                variants.append({"variant_id": f"{method}:{view}:{cid}", "method": method, "input_view": view,
                    "condition_id": cid, "selected_rule_ids": ids, "candidate_rule_ids": candidates,
                    "candidate_family_ids": sorted({contract["roles"][rid]["decision_family"] for rid in candidates}),
                    "contract_version": VERSION, "common_gate_ids": condition["common_gate_ids"], "threshold": 1})
    return {"variant_plan_version": "formal-variant-plan-v2", "contract_version": VERSION,
            "role_gate_config_ref": CONFIG_REF, "variants": variants,
            "matrix_definition": "2 risk methods x 5 App views x 8 source conditions = 80 structural definitions, not 80 executed experiments",
            "four_source_mapping": contract["documents"]["source_conditions"]["four_source_mapping"],
            "methods": {
                "final_v3_v2": {"runtime": "Complete original v3 chain: 87 dispositions / 57 ACTIVE", "all_rule_events_retained": True},
                "legacy19_v2": {"rule_ids": [r["rule_id"] for r in legacy["rules"]],
                    "candidate_rule_ids": ["NW-002", "NVW-002", "OFFDER-OS-001", "OFFDER-OS-002"],
                    "retired_diagnostic": "OFFDER-WEBVIEW-001 never receives a risk role",
                    "short_circuit": False, "definition": "Original 10+9 predicates, external v2 gates/families; not the paired-v1 whole catalog."},
                "current_v3_relation_role_projection": {"execution_alias": "final_v3_v2", "risk_view_alias": "final_v3_v2",
                    "type": "RELATION_DIAGNOSTIC_NOT_RISK_PREDICTION",
                    "reason": "All risk predictions obey v2. Removing gates is a mechanism diagnostic, not a third independent valid risk baseline."}},
            "diagnostics": [
                {"id": "D1_REMOVE_UA_REDUCTION", "scope": "Only reduction gate; remaining parsing and typed identity requirements retained", "status": "SPECIFIED_FOR_S09_NO_REAL_RUN"},
                {"id": "D2_UNKNOWN_AS_COMPARABLE", "scope": "Explicit synthetic assumption, never a formal risk classification", "status": "SPECIFIED_FOR_S09_NO_REAL_RUN"},
                {"id": "D3_DUPLICATE_VOTES", "scope": "Count qualifying rules; binary effect at threshold 1 structurally zero", "status": "SAVED_EVENT_DERIVATION_ONLY"},
                {"id": "D4_RAW_UNCONDITIONAL_EQUALITY", "scope": "Synthetic raw equality, not original runtime behavior", "status": "SPECIFIED_FOR_S09_NO_REAL_RUN"}],
            "no_browser_attack_view": True, "source_group_ablation_not_official_knowledge_removal": True,
            "real_performance": "NOT_EVALUATED"}


def figure_spec():
    scopes = [("method and inference/evaluation boundary", ["schemas", "policy"]),
              ("all configurations triplet trajectories", ["triplet_results", "evaluation_joined"]),
              ("fixed denominator rates and coverage", ["metrics"]),
              ("positive and verified-negative source overlaps", ["source_overlap", "metrics"]),
              ("App view and P6 coverage-only comparison", ["metrics", "P6_SAVED_OUTPUT"]),
              ("boundary, missingness, costs and fidelity", ["metrics", "timings_ms", "verification"])]
    return {"figure_spec_version": "formal-figure-spec-v2", "contract_version": VERSION,
            "primary_formats": ["svg", "pdf"], "source_formats": ["csv", "json"], "preview_format": "png",
            "font": "DejaVu Sans / Noto Sans CJK SC when available", "single_column_width_mm": 85,
            "double_column_width_mm": 178, "minimum_font_pt": 8,
            "palette": ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"],
            "line_styles": ["solid", "dashed", "dotted"],
            "interval_units": "Rates 0..1; differences in percentage points; no population CI for related groups",
            "status_markers": {"NO_ELIGIBLE_LABELS": "NA", "FAILED": "x", "INSUFFICIENT_EVIDENCE": "open triangle", "ZERO_OBSERVED": "0/n"},
            "figures": [{"id": f"Fig.{i}", "scope": s, "required_sources": src,
                         "status": "NOT_EVALUATED_UNTIL_AUTHORIZED_SAVED_RESULTS"} for i, (s, src) in enumerate(scopes, 1)],
            "manifest_required": ["source_tables", "source_prediction_rows", "filters", "run_id", "protocol_digest", "execution_scope"],
            "synthetic_policy": "S04 tables validate interfaces; no paper figures or real sample metrics."}
