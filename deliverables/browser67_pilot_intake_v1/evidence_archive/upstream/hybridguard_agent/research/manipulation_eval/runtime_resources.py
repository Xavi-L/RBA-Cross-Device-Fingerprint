"""Finite resources for the frozen final-v3/legacy19 chain, before any samples.

This is a packaging preflight, not a predicate, gate or risk-policy change.
The required set lives in code as well as the manifest: deleting a manifest row
cannot hide a required resource. No search paths or workspace fallback exist.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = "RUNTIME_RESOURCES.json"
VERSION = "formal-runtime-resources-v1"
CONFIG = "hybridguard_agent/config/"
ROLE = CONFIG + "formal_manipulation_role_gate_v2/"
POLICY = CONFIG + "formal_manipulation_policy_v2/"
SOURCE_FILES = (
    CONFIG + "mtc_p3_semantic_sources.v1.json",
    CONFIG + "paired244_review_sources.v1.json",
    CONFIG + "mtc_closed_resource_sources.v1.json",
)


def resource_specs():
    rows = []

    def add(paths, reader, scope):
        rows.extend({"path": p, "reader": reader, "scope": scope} for p in paths)

    add(["android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv"],
        "evidence/paired244.py::field_contract", "Both methods, including import-time field mapping")
    add(["scoring/rule_knowledge_base.json"], "adapters/rule_kb_adapter.py::assert_pinned_rule_kb", "Both load_catalog paths")
    add([CONFIG + "paired244_rule_catalog.v1.json", CONFIG + "paired244_rule_catalog.v3.json",
         CONFIG + "paired244_browser_relations.v1.json", CONFIG + "paired244_browser_relations.v3.json"],
        "rules/paired244.py::load_catalog", "Exact v1 and v3 used by legacy19/final; v2 catalog is not selected")
    add([CONFIG + "deterministic_rule_predicates.v1.json", CONFIG + "official_semantic_relations.v1.json"],
        "manipulation_eval/baselines.py::legacy19_catalog", "Original 10+9 compiled predicates")
    add([SOURCE_FILES[0]], "adapters/paired244_catalog.py::runtime_cards", "Both v1 and v3, including Verifier replay")
    add([SOURCE_FILES[1], SOURCE_FILES[2]], "adapters/paired244_catalog.py::runtime_cards", "v3 only, including Verifier replay")
    add([ROLE + n + ".json" for n in ("applicability_policy", "decision_roles", "research_scope", "source_conditions", "family_bindings", "precondition_classification")] + [ROLE + "source_bindings.jsonl"],
        "manipulation_eval/contract.py::load_contract", "Complete explicit S03-R v2 documents")
    add([POLICY + "decision_policy.json"], "manipulation_eval/contract.py::load_contract", "Fixed v2 risk policy")
    add([POLICY + n + ".json" for n in ("evaluation_contract", "figure_spec", "metric_spec", "variant_plan")],
        "Frozen protocol/evaluation consumers", "Inherited companion specs; retained without semantic changes")
    add(["hybridguard_agent/schemas/expanded_v2.schema.json"], "manipulation_eval/adapter.py::mapping_contract", "Both payload projection paths")
    add(["hybridguard_agent/schemas/" + n for n in ("field_registry.json", "formal_manipulation_job_v2.schema.json",
         "formal_manipulation_long_tables_v2.schema.json", "manipulation_decision_v2.schema.json")],
        "Frozen schema companions", "Inherited schema resources; field registry helper is not the paired runtime retrieval")
    return sorted(rows, key=lambda r: r["path"])


class ResourcePreflightError(ValueError):
    def __init__(self, code, paths):
        self.code, self.paths = code, sorted(map(str, paths))
        super().__init__(code + ": " + ", ".join(self.paths))


def resource_paths():
    return [Path(r["path"]) for r in resource_specs()]


def _checked_paths(root):
    root = Path(root).resolve()
    missing, outside = [], []
    for rel in resource_paths():
        path = root / rel
        if root not in path.resolve().parents:
            outside.append(rel)
        elif not path.is_file():
            missing.append(rel)
    if outside:
        raise ResourcePreflightError("RUNTIME_RESOURCE_OUTSIDE_SNAPSHOT", outside)
    if missing:
        raise ResourcePreflightError("MISSING_RUNTIME_RESOURCE", missing)
    return root


def resource_manifest(root, *, freeze_revision):
    root = _checked_paths(root)
    rows = []
    for spec in resource_specs():
        data = (root / spec["path"]).read_bytes()
        rows.append({**spec, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return {"resource_manifest_version": VERSION, "freeze_revision": freeze_revision,
            "path_base": "This file's parent, never the main workspace", "resources": rows,
            "resource_count": len(rows), "methods": ["final_v3_v2", "legacy19_v2"],
            "boundary": "Finite selected-chain resources and inherited schema/spec companions; not a whole-repository audit"}


def preflight(*, root=ROOT, require_manifest=False, config_dir=None, policy_path=None):
    root = _checked_paths(root)  # Independent of manifest membership.
    path = root / MANIFEST
    if require_manifest and not path.is_file():
        raise ResourcePreflightError("MISSING_RUNTIME_RESOURCE_MANIFEST", [MANIFEST])
    checked = []
    if path.is_file():
        doc = json.loads(path.read_text())
        rows = doc.get("resources", [])
        names = [r["path"] for r in rows]
        expected = [str(p) for p in resource_paths()]
        if (doc.get("resource_manifest_version") != VERSION or len(names) != len(set(names))
                or sorted(names) != expected or doc.get("resource_count") != len(rows)):
            raise ResourcePreflightError("RUNTIME_RESOURCE_MANIFEST_SET_MISMATCH", sorted(set(expected) ^ set(names)) or [MANIFEST])
        for row in rows:
            data = (root / row["path"]).read_bytes()
            if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ResourcePreflightError("RUNTIME_RESOURCE_DIGEST_MISMATCH", [row["path"]])
            checked.append(str(root / row["path"]))
        for supplied, expected_path in ((config_dir, root / ROLE), (policy_path, root / POLICY / "decision_policy.json")):
            if supplied is not None and Path(supplied).resolve() != expected_path:
                raise ResourcePreflightError("RUNTIME_CONFIG_OUTSIDE_FROZEN_BINDING", [supplied])
    return {"status": "PASS", "root": str(root), "manifest": str(path) if path.is_file() else None,
            "resource_count": len(resource_paths()), "digest_checked_paths": checked,
            "sample_files_read": False, "output_created": False}
