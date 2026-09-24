"""S05-R packaging-only revision: inherit accepted bytes, never rebuild data."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import ast
import hashlib
from pathlib import Path
import platform
import sys

from hybridguard_agent.research.manipulation_eval import freeze as f
from hybridguard_agent.research.manipulation_eval.runtime_resources import (
    MANIFEST, SOURCE_FILES, preflight, resource_manifest, resource_paths, resource_specs,
)

BASELINE = "595d30d690713f6ee800a7825cfe8199cee97565"
REVISION = "formal-manipulation-freeze-r1"
PACKAGING_SOURCES = (
    "hybridguard_agent/research/manipulation_eval/freeze.py",
    "hybridguard_agent/research/manipulation_eval/freeze_revision.py",
    "hybridguard_agent/research/manipulation_eval/runtime_resources.py",
    "hybridguard_agent/research/manipulation_eval/runner.py",
    "hybridguard_agent/research/manipulation_eval/snapshot_smoke.py",
    "hybridguard_agent/scripts/freeze_formal_manipulation_protocol.py",
    "hybridguard_agent/scripts/run_formal_manipulation_eval.py",
    "hybridguard_agent/tests/test_formal_manipulation_snapshot_resources.py",
)
PROTOCOL_ADDITIONS = {"freeze_revision", "parent_snapshot", "packaging_revision"}


def verify_manifest(directory, config_dir=None):
    directory = Path(directory).resolve()
    manifest, protocol = f.read(directory / "FREEZE_MANIFEST.json"), f.read(directory / "protocol.json")
    entries = manifest["bound_files"]
    f.require(len(entries) == len({e["path"] for e in entries}), "Duplicate bound path")
    f.require(entries == sorted(entries, key=lambda e: e["path"]), "Manifest order")
    for entry in entries:
        path = (directory / entry["path"]).resolve()
        f.require(directory in path.parents, "Manifest path escape")
        data = path.read_bytes()
        f.require(len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"], "Bound bytes changed: " + entry["path"])
    digest = hashlib.sha256(f.encoded(entries)).hexdigest()
    f.require(digest == manifest["protocol_digest"] == protocol["protocol_digest"], "Protocol digest conflict")
    f.require(hashlib.sha256((directory / "protocol.json").read_bytes()).hexdigest() == manifest["protocol_sha256"], "Protocol bytes changed")
    if config_dir is not None:
        f.require((Path(config_dir) / "protocol.json").read_bytes() == (directory / "protocol.json").read_bytes(), "Protocol config copy conflict")
    return manifest, protocol


def function_ast(path, name):
    tree = ast.parse(Path(path).read_text())
    return ast.dump(next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name), include_attributes=False)


def invariance(parent, output, protocol):
    """Exact inheritance except the explicit packaging source allowlist."""
    parent, output = Path(parent), Path(output)
    old = f.read(parent / "protocol.json")
    stripped = {k: v for k, v in protocol.items() if k not in PROTOCOL_ADDITIONS | {"protocol_digest"}}
    f.require(stripped == {k: v for k, v in old.items() if k != "protocol_digest"}, "Experimental protocol semantics changed")
    allowed = {"frozen_sources/" + p for p in PACKAGING_SOURCES}
    unchanged, changed = [], []
    for entry in f.read(parent / "FREEZE_MANIFEST.json")["bound_files"]:
        name = entry["path"]
        f.require((output / name).is_file(), "Inherited file omitted: " + name)
        if (parent / name).read_bytes() == (output / name).read_bytes():
            unchanged.append(name)
        else:
            f.require(name in allowed, "Non-packaging bytes changed: " + name)
            changed.append(name)
    runner = "frozen_sources/hybridguard_agent/research/manipulation_eval/runner.py"
    for fn in ("worker", "validate_protocol"):
        f.require(function_ast(parent / runner, fn) == function_ast(output / runner, fn), "Original worker/job contract changed: " + fn)
    return {"status": "PASS", "comparison": "Byte equality of every parent-bound file except named packaging sources; protocol equality after removing only revision metadata and digest",
            "unchanged_parent_files": unchanged, "changed_packaging_sources": changed,
            "parent_file_count": len(unchanged) + len(changed), "unchanged_parent_file_count": len(unchanged),
            "original_worker_and_job_validator_AST_unchanged": True,
            "preserved": ["S01 labels/eligibility/environment groups", "S02 input bytes and stage links",
                          "57 ACTIVE / 7 candidates / 5 families", "v2 gates / family OR / threshold 1",
                          "sources/methods/views/samples/all expected units", "denominators/metrics/figures/exposure history",
                          "all original predicates, original Verifier, risk policy and risk Verifier"],
            "real_predictions": 0, "upstream_rebuilds": 0}


def read_audit():
    return {"scope": "Finite selected final_v3_v2 and legacy19_v2 worker chain, including both Verifiers and import-time field mapping",
            "resources": resource_specs(),
            "selected_call_chain": ["contract.load_contract", "runner.worker", "adapter.project_payload / mapping_contract",
                "evidence.paired244.build_paired_evidence / field_contract", "rules.paired244.load_catalog / execute_paired_rules",
                "baselines.legacy19_catalog", "retrieval.paired244.build_paired_context", "adapters.paired244_catalog.runtime_cards",
                "verification.paired244.verify_paired_output", "policy.build_events / decide", "verification.verify_policy_output"],
            "omission_cause": "AST follows Python imports, not runtime JSON reads. Previous explicit resource list omitted all three runtime_cards source documents; manifest validation only covered listed files.",
            "new_required_resources": list(SOURCE_FILES),
            "no_other_selected_chain_resource_omission_found": True,
            "excluded_unselected_readers": [
                {"reader": "adapter.generate / admission readers", "reason": "Upstream processing, not selected worker; retained input bytes copied from S05"},
                {"reader": "provenance / provenance_revision generators", "reason": "Not invoked; only constants and gate functions selected"},
                {"reader": "official_kb_adapter.load_official_cards / exact_retriever.load_retrieval_policy", "reason": "Generic retrieval not selected: paired244 retrieval uses runtime_cards"},
                {"reader": "rules.executor.load_predicates / official_semantics.evaluator.load_catalog", "reason": "Standalone default loaders are not selected by the paired adapters; their deterministic/official JSON definitions are already explicitly bound and supplied by legacy19_catalog"},
                {"reader": "paired244 catalog v2", "reason": "Neither frozen method selects v2 catalog; v1 and v3 are bound"}],
            "caller_inputs": "Blind sample/job IO is caller supplied; synthetic smoke opens no S01/S02 input, label, evaluation or real prediction file",
            "check_limit": "Read-site review plus guarded synthetic execution is not an exhaustive whole-repository audit or proof of performance"}


def revise(*, parent, output, config_dir, freeze_revision, root=f.ROOT):
    root, parent = Path(root).resolve(), Path(parent).resolve()
    out, cfg = f.destinations(root, output, config_dir)
    f.require(freeze_revision == REVISION, "Unsupported packaging revision")
    f.require(f.git(root, "rev-parse", "HEAD") == BASELINE, "S05-R review baseline differs")
    old_manifest, old_protocol = verify_manifest(parent)
    f.require(f.read(parent / "VALIDATION.json")["status"] == "PASS", "Parent S05 acceptance is not PASS")
    f.require("freeze_revision" not in old_protocol, "This revision expects the original S05 parent")
    f.require(old_protocol["protocol_version"] == f.VERSION and old_protocol["contract_version"] == f.CONTRACT and
              old_protocol["policy_version"] == f.POLICY, "Parent semantic version conflict")
    f.require(not old_protocol["execution_authorization"]["formal_execution_authorized"], "Parent unexpectedly authorizes execution")
    for source in SOURCE_FILES:
        # These three documents are baseline resources, not newly authored sources.
        f.require(not f.git(root, "diff", "HEAD", "--", source), "Required baseline resource changed: " + source)
    old_resources = {Path(e["path"]).relative_to("frozen_sources") for e in old_manifest["bound_files"] if e["category"] == "RUNTIME_CONFIG"}
    f.require(set(resource_paths()) == old_resources | {Path(p) for p in SOURCE_FILES}, "Unexpected resource-list scope change")
    f.require(all((root / p).is_file() for p in PACKAGING_SOURCES), "Missing packaging implementation")
    # Reject accidental workspace semantic edits instead of silently bundling them.
    for entry in old_manifest["bound_files"]:
        if entry["category"] == "PARTICIPATING_SOURCE":
            rel = str(Path(entry["path"]).relative_to("frozen_sources"))
            if rel not in PACKAGING_SOURCES:
                f.require((root / rel).read_bytes() == (parent / entry["path"]).read_bytes(), "Workspace semantic source drift: " + rel)
    out.mkdir(parents=True)
    cfg.mkdir(parents=True)
    entries = {}

    def put(name, data, category, source=None):
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        entries[str(name)] = {"path": str(name), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                              "category": category, "source": str(source) if source else None}

    for entry in old_manifest["bound_files"]:
        put(entry["path"], (parent / entry["path"]).read_bytes(), entry["category"], entry["source"])
    for rel in PACKAGING_SOURCES:
        put("frozen_sources/" + rel, (root / rel).read_bytes(), "PARTICIPATING_SOURCE", rel)
    for rel in SOURCE_FILES:
        put("frozen_sources/" + rel, (root / rel).read_bytes(), "RUNTIME_CONFIG", rel)
    frozen_root = out / "frozen_sources"
    closure = f.source_closure(frozen_root, [Path(p) for p in PACKAGING_SOURCES])
    f.require(all("frozen_sources/" + str(p) in entries for p in closure), "Unbound Python import")
    put("frozen_sources/" + MANIFEST, f.encoded(resource_manifest(frozen_root, freeze_revision=freeze_revision)), "RUNTIME_RESOURCE_MANIFEST")
    revision = {"freeze_revision": freeze_revision, "kind": "PACKAGING_ONLY_NO_EXPERIMENT_SEMANTIC_CHANGE",
                "created_at": datetime.now(timezone.utc).isoformat(), "review_baseline": BASELINE,
                "parent_snapshot": {"path": str(parent), "protocol_digest": old_protocol["protocol_digest"]},
                "source_allowlist": list(PACKAGING_SOURCES), "added_runtime_resources": list(SOURCE_FILES),
                "resource_manifest_ref": "frozen_sources/" + MANIFEST, "resource_preflight": "Before contract loading, sample reads, output creation and unit execution in CLI; also enforced by prediction API",
                "validation_output_policy": "Independent SYNTHETIC directory, never formal predictions or S06 units",
                "authorization": "S05-R synthetic packaging checks only; S06 remains pending"}
    protocol = deepcopy(old_protocol)
    protocol.update(freeze_revision=freeze_revision, parent_snapshot=revision["parent_snapshot"], packaging_revision=revision)
    unchanged = invariance(parent, out, protocol)
    put("SEMANTIC_INVARIANCE.json", f.encoded(unchanged), "PACKAGING_VALIDATION")
    put("RESOURCE_READ_AUDIT.json", f.encoded(read_audit()), "PACKAGING_VALIDATION")
    put("PACKAGING_REVISION.json", f.encoded(revision), "PACKAGING_REVISION")
    for name in ("protocol.json", "FREEZE_MANIFEST.json", "STATIC_VALIDATION.json", "VALIDATION.json", "STEP_REPORT.md", "FOCUSED_TESTS.txt"):
        put("inherited_acceptance/S05/" + name, (parent / name).read_bytes(), "PARENT_HISTORICAL_ACCEPTANCE", str(parent / name))
    put("packaging_environment.json", f.encoded({"HEAD": f.git(root, "rev-parse", "HEAD"), "python": sys.version,
        "OS": platform.platform(), "branch": f.git(root, "branch", "--show-current"),
        "participating_git_status": f.git(root, "status", "--porcelain=v1", "--untracked-files=all", "--", *PACKAGING_SOURCES).splitlines(),
        "historical_source_environment": "source_environment.json is the unchanged original S05 timepoint",
        "uncommitted_packaging_sources": "Exact revised source bytes bound here; no commit or push by S05-R"}), "PACKAGING_ENVIRONMENT")
    put("packaging_worktree.diff", (f.git(root, "diff", "HEAD", "--", *PACKAGING_SOURCES) + "\n").encode(), "PACKAGING_DIFF_ONLY")
    ordered = sorted(entries.values(), key=lambda e: e["path"])
    digest = hashlib.sha256(f.encoded(ordered)).hexdigest()
    protocol["protocol_digest"] = digest
    protocol_bytes = f.encoded(protocol)
    (out / "protocol.json").write_bytes(protocol_bytes)
    (cfg / "protocol.json").write_bytes(protocol_bytes)
    counts = Counter(e["category"] for e in ordered)
    manifest = {"manifest_version": old_manifest["manifest_version"], "freeze_revision": freeze_revision,
                "parent_protocol_digest": old_protocol["protocol_digest"], "protocol_digest": digest,
                "digest_definition": old_manifest["digest_definition"], "bound_files": ordered,
                "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(), "config_copy": str(cfg / "protocol.json"),
                "copied_source_count": counts["PARTICIPATING_SOURCE"], "runtime_resource_count": counts["RUNTIME_CONFIG"],
                "bound_file_count": len(ordered), "category_counts": dict(counts),
                "hash_scope": "Finite snapshot and explicit resource bindings only. Later acceptance logs excluded to avoid self-reference."}
    (out / "FREEZE_MANIFEST.json").write_bytes(f.encoded(manifest))
    result = validate_revision(out, config_dir=cfg, parent=parent)
    (out / "STATIC_VALIDATION.json").write_bytes(f.encoded(result))
    return result


def validate_revision(output, *, config_dir, parent=None):
    out = Path(output).resolve()
    manifest, protocol = verify_manifest(out, config_dir)
    f.require(protocol["freeze_revision"] == manifest["freeze_revision"] == REVISION, "Revision mismatch")
    parent = Path(parent or protocol["parent_snapshot"]["path"])
    parent_protocol = f.read(parent / "protocol.json")
    f.require(parent_protocol["protocol_digest"] == protocol["parent_snapshot"]["protocol_digest"] == manifest["parent_protocol_digest"], "Parent inheritance conflict")
    comparison = invariance(parent, out, protocol)
    f.require(comparison == f.read(out / "SEMANTIC_INVARIANCE.json"), "Saved invariance record differs")
    resources = preflight(root=out / "frozen_sources", require_manifest=True)
    f.require(f.read(out / "frozen_sources" / MANIFEST)["freeze_revision"] == REVISION, "Resource revision conflict")
    counts = Counter(e["category"] for e in manifest["bound_files"])
    f.require(manifest["bound_file_count"] == len(manifest["bound_files"]) and manifest["copied_source_count"] == counts["PARTICIPATING_SOURCE"] and
              manifest["runtime_resource_count"] == resources["resource_count"] == counts["RUNTIME_CONFIG"], "Derived file counts differ")
    f.require(not list(out.rglob("predictions.jsonl")) and not list(out.rglob("rule_events.jsonl")), "Predictions mixed into freeze")
    return {"status": "PASS", "scope": "S05-R_STATIC_PACKAGING_AND_BYTE_INHERITANCE", "output": str(out), "config_dir": str(Path(config_dir).resolve()),
            "freeze_revision": REVISION, "protocol_digest": protocol["protocol_digest"], "parent_protocol_digest": parent_protocol["protocol_digest"],
            "bound_file_count": len(manifest["bound_files"]), "source_count": counts["PARTICIPATING_SOURCE"], "resource_count": resources["resource_count"],
            "semantic_invariance": comparison["status"], "startup_resource_preflight": resources["status"],
            "upstream_rebuilds": 0, "real_predictions": 0, "detector_calls": 0, "LLM_calls": 0}
