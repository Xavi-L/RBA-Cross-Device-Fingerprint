#!/usr/bin/env python3
"""Build a label-safe experiment plan for one latest paired244 snapshot.

This builder never edits the snapshot, invents labels, trains a model, or
computes performance metrics.  With no fact sidecar it still produces a useful
blocked readiness report.  With verified external facts it assigns whole
trusted groups to deterministic train/development/test splits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hybridguard_agent.runtime import snapshot_loader  # noqa: E402


DEFAULT_PROTOCOL_PATH = (
    REPO_ROOT / "hybridguard_agent/config/latest_experiment_protocol.v1.json"
)
DEFAULT_SCHEMA_PATH = (
    REPO_ROOT / "hybridguard_agent/schemas/latest_experiment_fact_v1.schema.json"
)

PLAN_VERSION = "latest-experiment-plan-v1"
REGISTRY_VERSION = "latest-experiment-registry-v1"
SPLIT_MANIFEST_VERSION = "latest-experiment-split-manifest-v1"
READINESS_VERSION = "latest-experiment-readiness-v1"
INPUT_MANIFEST_VERSION = "latest-experiment-input-manifest-v1"
LATEST_MANIFEST_VERSION = "latest-featureapp-paired244-snapshot-v1"
LATEST_INDEX_VERSION = "latest-paired244-sample-index-v1"
PRIMARY_TASK = "paired244_fingerprint_effect"
HEX64 = frozenset("0123456789abcdef")

FACT_KEYS = {
    "experiment_fact_version",
    "app_session_id",
    "app_payload_sha256",
    "label_status",
    "manipulation_present",
    "evaluation_task",
    "execution_status",
    "field_effect_status",
    "stable_group_key_hash",
    "identity_scope",
    "identity_stability",
    "scenario_group_id",
    "scenario_phase",
    "scenario_repetition",
    "attack_family",
    "evidence_refs",
}
LABEL_STATUSES = {"verified", "candidate", "rejected"}
TASKS = {PRIMARY_TASK, "transport_path_effect", "collection_reference"}
EXECUTION_STATUSES = {"succeeded", "failed", "not_applicable", "unknown"}
EFFECT_STATUSES = {
    "observed",
    "no_configured_change",
    "not_observed",
    "not_applicable",
    "unknown",
}
IDENTITY_SCOPES = {
    "physical_device",
    "device_profile",
    "provider_device_profile",
    "collector_install_profile_not_physical_device",
    "run_profile",
    "unknown",
}
IDENTITY_STABILITIES = {
    "cross_run_verified",
    "provider_verified",
    "run_scoped_unverified",
    "unknown",
}
SCENARIO_PHASES = {"clean_pre", "attack_active", "clean_post", None}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--facts",
        type=Path,
        help="Optional latest-experiment-fact-v1 JSONL supplied outside the snapshot.",
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    return parser.parse_args()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def jsonl_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    return "".join(canonical_json(row) + "\n" for row in rows).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def is_hex64(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX64


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected an object in {path}:{line_number}")
            rows.append(value)
    return rows


def direct_child(directory: Path, relative: Any, *, field: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"Snapshot manifest has no {field}")
    path = (directory / relative).resolve()
    if path.parent != directory or not path.is_file():
        raise ValueError(f"Snapshot {field} must name an existing direct child")
    return path


def load_protocol(path: Path) -> dict[str, Any]:
    protocol = read_json(path)
    if protocol.get("protocol_version") != "latest-experiment-protocol-v1":
        raise ValueError("Unsupported latest experiment protocol")
    source = protocol.get("source_contract")
    eligibility = protocol.get("eligibility")
    split = protocol.get("group_split")
    readiness = protocol.get("readiness")
    if not all(isinstance(value, dict) for value in (source, eligibility, split, readiness)):
        raise ValueError("Latest experiment protocol is incomplete")
    if (
        source.get("dataset_manifest_version") != LATEST_MANIFEST_VERSION
        or source.get("sample_index_version") != LATEST_INDEX_VERSION
        or source.get("experiment_fact_version") != "latest-experiment-fact-v1"
        or source.get("fact_join_key") != "app_session_id"
        or eligibility.get("primary_evaluation_task") != PRIMARY_TASK
    ):
        raise ValueError("Latest experiment protocol source contract is invalid")
    if (
        eligibility.get("required_label_status") != "verified"
        or not isinstance(eligibility.get("required_evidence_reference_count"), int)
        or eligibility["required_evidence_reference_count"] < 1
        or not set(eligibility.get("trusted_identity_scopes", ())) <= IDENTITY_SCOPES
        or not eligibility.get("trusted_identity_scopes")
        or not set(eligibility.get("trusted_identity_stabilities", ()))
        <= IDENTITY_STABILITIES
        or not eligibility.get("trusted_identity_stabilities")
    ):
        raise ValueError("Latest experiment eligibility contract is invalid")
    modulus = split.get("bucket_modulus")
    thresholds = split.get("thresholds")
    if (
        not isinstance(modulus, int)
        or modulus < 2
        or not isinstance(thresholds, list)
        or not isinstance(split.get("seed"), str)
        or not split["seed"]
        or split.get("hash_input_prefix") != "latest-split-v1"
        or split.get("hash_input_separator") != "\0"
        or not isinstance(split.get("digest_hex_prefix_length"), int)
        or not 1 <= split["digest_hex_prefix_length"] <= 64
    ):
        raise ValueError("Latest experiment split contract is invalid")
    expected_start = 0
    names: list[str] = []
    for item in thresholds:
        if not isinstance(item, dict) or item.get("start_inclusive") != expected_start:
            raise ValueError("Latest experiment split thresholds are not contiguous")
        end = item.get("end_exclusive")
        name = item.get("split")
        if not isinstance(end, int) or end <= expected_start or not isinstance(name, str):
            raise ValueError("Latest experiment split threshold is invalid")
        names.append(name)
        expected_start = end
    if expected_start != modulus or names != ["train", "development", "test"]:
        raise ValueError("Latest experiment split thresholds must cover train/development/test")
    structural = readiness.get("structural")
    grouped_data = readiness.get("grouped_data")
    if (
        not isinstance(structural, dict)
        or not isinstance(grouped_data, dict)
        or not isinstance(structural.get("minimum_independent_groups_per_split"), int)
        or structural["minimum_independent_groups_per_split"] < 1
        or structural.get("require_both_manipulation_classes_per_split") is not True
        or not isinstance(grouped_data.get("minimum_independent_groups_per_split"), int)
        or grouped_data["minimum_independent_groups_per_split"] < 1
        or not isinstance(
            grouped_data.get("minimum_groups_per_manipulation_class_per_split"), int
        )
        or grouped_data["minimum_groups_per_manipulation_class_per_split"] < 1
        or grouped_data.get("necessary_not_sufficient") is not True
    ):
        raise ValueError("Latest experiment readiness contract is invalid")
    return protocol


def load_snapshot_index(
    snapshot_dir: Path,
    protocol: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Path]]:
    snapshot_loader.validate_latest_snapshot_views(snapshot_dir)
    manifest_path = snapshot_dir / "dataset_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing latest dataset manifest: {manifest_path}")
    manifest = read_json(manifest_path)
    if manifest.get("dataset_manifest_version") != LATEST_MANIFEST_VERSION:
        raise ValueError("Unsupported latest paired244 snapshot")
    if manifest.get("dataset_role") != "development_qc_only" or manifest.get("label_status") != "unlabeled":
        raise ValueError("Latest snapshot must remain development-only and unlabeled")
    views = manifest.get("views")
    if not isinstance(views, dict):
        raise ValueError("Latest snapshot has no views")
    view_ids: dict[str, set[str]] = {}
    source_paths = {"dataset_manifest": manifest_path}
    for view in ("paired_244", "app_only_177"):
        metadata = views.get(view)
        if not isinstance(metadata, dict):
            raise ValueError(f"Latest snapshot has no {view} view")
        view_path = direct_child(snapshot_dir, metadata.get("path"), field=f"views.{view}.path")
        source_paths[view] = view_path
        ids: set[str] = set()
        for row in read_jsonl(view_path):
            sample_id = row.get("sample_id")
            if not isinstance(sample_id, str) or not sample_id or sample_id in ids:
                raise ValueError(f"Duplicate or missing sample_id in {view}")
            if row.get("dataset_view") != view:
                raise ValueError(f"Sample is stored in the wrong latest view: {sample_id}")
            ids.add(sample_id)
        if metadata.get("count") != len(ids):
            raise ValueError(f"Latest snapshot count mismatch for {view}")
        view_ids[view] = ids
    if view_ids["paired_244"] & view_ids["app_only_177"]:
        raise ValueError("Latest sample appears in both data views")

    index_path = direct_child(snapshot_dir, manifest.get("sample_index_path"), field="sample_index_path")
    catalog_path = direct_child(
        snapshot_dir,
        manifest.get("feature_catalog_path"),
        field="feature_catalog_path",
    )
    source_paths["sample_index"] = index_path
    source_paths["feature_catalog"] = catalog_path
    rows = read_jsonl(index_path)
    by_sample: dict[str, dict[str, Any]] = {}
    by_session: dict[str, str] = {}
    for row in rows:
        sample_id = row.get("sample_id")
        session_id = row.get("app_session_id")
        view = row.get("dataset_view")
        if row.get("sample_index_version") != protocol["source_contract"]["sample_index_version"]:
            raise ValueError("Unsupported latest sample index row")
        if not isinstance(sample_id, str) or not sample_id or sample_id in by_sample:
            raise ValueError("Duplicate or missing sample_id in latest sample index")
        if not isinstance(session_id, str) or not session_id or session_id in by_session:
            raise ValueError("Duplicate or missing app_session_id in latest sample index")
        if view not in view_ids or sample_id not in view_ids[view]:
            raise ValueError(f"Latest sample index/view mismatch: {sample_id}")
        if row.get("dataset_role") != "development_qc_only" or row.get("label_status") != "unlabeled":
            raise ValueError(f"Latest sample index crosses the label boundary: {sample_id}")
        if not is_hex64(row.get("app_payload_sha256")):
            raise ValueError(f"Latest sample index has no payload binding: {sample_id}")
        by_sample[sample_id] = row
        by_session[session_id] = sample_id
    if set(by_sample) != view_ids["paired_244"] | view_ids["app_only_177"]:
        raise ValueError("Latest sample index does not cover both views exactly")
    return manifest, [by_sample[key] for key in sorted(by_sample)], source_paths


def validate_fact(fact: dict[str, Any], *, line_number: int) -> None:
    prefix = f"E_SIDECAR_ROW_INVALID line {line_number}:"
    if set(fact) != FACT_KEYS:
        raise ValueError(f"{prefix} unexpected or missing keys")
    if fact.get("experiment_fact_version") != "latest-experiment-fact-v1":
        raise ValueError(f"{prefix} unsupported fact version")
    if not isinstance(fact.get("app_session_id"), str) or not fact["app_session_id"]:
        raise ValueError(f"{prefix} app_session_id is required")
    if not is_hex64(fact.get("app_payload_sha256")):
        raise ValueError(f"{prefix} app_payload_sha256 must be lowercase SHA-256")
    if fact.get("label_status") not in LABEL_STATUSES or fact.get("evaluation_task") not in TASKS:
        raise ValueError(f"{prefix} label/task enum is invalid")
    if fact.get("execution_status") not in EXECUTION_STATUSES or fact.get("field_effect_status") not in EFFECT_STATUSES:
        raise ValueError(f"{prefix} execution/effect enum is invalid")
    label = fact.get("manipulation_present")
    if label is not None and not isinstance(label, bool):
        raise ValueError(f"{prefix} manipulation_present must be boolean or null")
    group_hash = fact.get("stable_group_key_hash")
    if group_hash is not None and not is_hex64(group_hash):
        raise ValueError(f"{prefix} stable_group_key_hash is invalid")
    if fact.get("identity_scope") not in IDENTITY_SCOPES or fact.get("identity_stability") not in IDENTITY_STABILITIES:
        raise ValueError(f"{prefix} identity enum is invalid")
    scenario = fact.get("scenario_group_id")
    if scenario is not None and (not isinstance(scenario, str) or not scenario):
        raise ValueError(f"{prefix} scenario_group_id is invalid")
    if fact.get("scenario_phase") not in SCENARIO_PHASES:
        raise ValueError(f"{prefix} scenario_phase is invalid")
    repetition = fact.get("scenario_repetition")
    if repetition is not None and (not isinstance(repetition, int) or isinstance(repetition, bool) or repetition < 1):
        raise ValueError(f"{prefix} scenario_repetition is invalid")
    family = fact.get("attack_family")
    if family is not None and (not isinstance(family, str) or not family):
        raise ValueError(f"{prefix} attack_family is invalid")
    refs = fact.get("evidence_refs")
    if not isinstance(refs, list) or any(not isinstance(item, str) or not item for item in refs) or len(refs) != len(set(refs)):
        raise ValueError(f"{prefix} evidence_refs must be unique non-empty strings")
    if fact["label_status"] == "verified" and (not isinstance(label, bool) or not refs):
        raise ValueError("E_VERIFIED_EVIDENCE_INVALID: verified facts require a boolean label and evidence")
    if fact["label_status"] == "verified" and fact["evaluation_task"] == PRIMARY_TASK:
        if label is True and not (
            fact["execution_status"] == "succeeded"
            and fact["field_effect_status"] == "observed"
            and scenario
            and fact["scenario_phase"] == "attack_active"
            and family
        ):
            raise ValueError("E_TASK_LABEL_CONTRACT: verified fingerprint positive lacks execution/field-effect facts")
        if label is False and not (
            fact["execution_status"] == "not_applicable"
            and fact["field_effect_status"] == "no_configured_change"
            and fact["scenario_phase"] in {"clean_pre", "clean_post", None}
        ):
            raise ValueError("E_TASK_LABEL_CONTRACT: verified fingerprint negative lacks clean baseline facts")


def load_facts(path: Path | None, index_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    index_by_session = {row["app_session_id"]: row for row in index_rows}
    facts: dict[str, dict[str, Any]] = {}
    for line_number, fact in enumerate(read_jsonl(path), start=1):
        validate_fact(fact, line_number=line_number)
        session_id = fact["app_session_id"]
        if session_id in facts:
            raise ValueError(f"E_SIDECAR_ROW_INVALID: duplicate app_session_id {session_id}")
        sample = index_by_session.get(session_id)
        if sample is None or sample["app_payload_sha256"] != fact["app_payload_sha256"]:
            raise ValueError(f"E_SIDECAR_JOIN_MISMATCH: {session_id}")
        facts[session_id] = fact
    scenario_groups: dict[str, set[tuple[str, str]]] = defaultdict(set)
    stable_contracts: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for fact in facts.values():
        group_hash = fact["stable_group_key_hash"]
        if group_hash:
            contract = (fact["identity_scope"], fact["identity_stability"])
            stable_contracts[group_hash].add(contract)
            if fact["scenario_group_id"]:
                scenario_groups[fact["scenario_group_id"]].add((group_hash, fact["identity_scope"]))
    if any(len(values) > 1 for values in stable_contracts.values()):
        raise ValueError("E_STABLE_GROUP_CONTRACT: one group hash has conflicting identity contracts")
    if any(len(values) > 1 for values in scenario_groups.values()):
        raise ValueError("E_SCENARIO_GROUP_MISMATCH: one scenario spans multiple stable groups")
    return facts


def assign_split(protocol: dict[str, Any], *, scope: str, group_hash: str) -> str:
    split = protocol["group_split"]
    separator = split["hash_input_separator"]
    value = separator.join((split["hash_input_prefix"], split["seed"], scope, group_hash))
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    bucket = int(digest[: split["digest_hex_prefix_length"]], 16) % split["bucket_modulus"]
    for threshold in split["thresholds"]:
        if threshold["start_inclusive"] <= bucket < threshold["end_exclusive"]:
            return threshold["split"]
    raise AssertionError("Validated split thresholds did not cover the hash bucket")


def scenario_hash(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(("scenario\0" + value).encode("utf-8")).hexdigest()


def build_plan(
    snapshot_dir: Path,
    output_dir: Path,
    *,
    facts_path: Path | None = None,
    protocol_path: Path = DEFAULT_PROTOCOL_PATH,
) -> dict[str, Any]:
    snapshot_dir = snapshot_dir.resolve()
    output_dir = output_dir.resolve()
    protocol_path = protocol_path.resolve()
    facts_path = facts_path.resolve() if facts_path is not None else None
    if output_dir == snapshot_dir or output_dir.is_relative_to(snapshot_dir):
        raise ValueError("Experiment-plan output must be outside the immutable source snapshot")
    if output_dir.exists():
        raise FileExistsError(f"Experiment-plan output already exists: {output_dir}")
    protocol = load_protocol(protocol_path)
    manifest, index_rows, source_paths = load_snapshot_index(snapshot_dir, protocol)
    facts = load_facts(facts_path, index_rows)

    eligibility = protocol["eligibility"]
    trusted_scopes = set(eligibility["trusted_identity_scopes"])
    trusted_stabilities = set(eligibility["trusted_identity_stabilities"])
    inventory: list[dict[str, Any]] = []
    splits: list[dict[str, Any]] = []
    verified_primary = 0
    trusted_groups: set[str] = set()

    for sample in index_rows:
        fact = facts.get(sample["app_session_id"])
        reasons: list[str] = []
        if sample["dataset_view"] != "paired_244":
            reasons.append("X_APP_ONLY_RESERVE")
        elif fact is None:
            reasons.append("X_FACT_MISSING")
        else:
            if fact["evaluation_task"] != eligibility["primary_evaluation_task"]:
                reasons.append("X_TASK_NOT_PRIMARY")
            if fact["label_status"] != eligibility["required_label_status"]:
                reasons.append("X_LABEL_NOT_VERIFIED")
            else:
                verified_primary += fact["evaluation_task"] == PRIMARY_TASK
            if not isinstance(fact["manipulation_present"], bool):
                reasons.append("X_LABEL_MISSING")
            if not fact["stable_group_key_hash"]:
                reasons.append("X_STABLE_GROUP_MISSING")
            if fact["identity_scope"] not in trusted_scopes:
                reasons.append("X_IDENTITY_SCOPE_UNTRUSTED")
            if fact["identity_stability"] not in trusted_stabilities:
                reasons.append("X_IDENTITY_STABILITY_UNTRUSTED")
            if len(fact["evidence_refs"]) < eligibility["required_evidence_reference_count"]:
                reasons.append("X_EVIDENCE_MISSING")
            if not reasons and fact["stable_group_key_hash"]:
                trusted_groups.add(fact["stable_group_key_hash"])

        eligible = not reasons
        split_name = None
        if eligible and fact is not None:
            split_name = assign_split(
                protocol,
                scope=fact["identity_scope"],
                group_hash=fact["stable_group_key_hash"],
            )
            splits.append(
                {
                    "split_manifest_version": SPLIT_MANIFEST_VERSION,
                    "sample_id": sample["sample_id"],
                    "split": split_name,
                    "stable_group_key_hash": fact["stable_group_key_hash"],
                    "identity_scope": fact["identity_scope"],
                    "scenario_group_key_hash": scenario_hash(fact["scenario_group_id"]),
                    "manipulation_present": fact["manipulation_present"],
                    "attack_family": fact["attack_family"],
                    "evaluation_task": fact["evaluation_task"],
                }
            )
        inventory.append(
            {
                "experiment_registry_version": REGISTRY_VERSION,
                "sample_id": sample["sample_id"],
                "dataset_view": sample["dataset_view"],
                "experiment_lane": (
                    "paired244_primary_candidate"
                    if sample["dataset_view"] == "paired_244"
                    else "app177_reserve"
                ),
                "fact_status": fact["label_status"] if fact else "missing",
                "evaluation_task": fact["evaluation_task"] if fact else None,
                "grouped_input_eligible": eligible,
                "exclusion_reasons": reasons,
                "stable_group_key_hash": fact["stable_group_key_hash"] if fact else None,
                "scenario_group_key_hash": scenario_hash(fact["scenario_group_id"]) if fact else None,
                "manipulation_present": fact["manipulation_present"] if fact else None,
                "split": split_name,
            }
        )

    inventory.sort(key=lambda row: row["sample_id"])
    splits.sort(key=lambda row: row["sample_id"])
    split_names = [item["split"] for item in protocol["group_split"]["thresholds"]]
    split_samples: Counter[str] = Counter(row["split"] for row in splits)
    split_groups: dict[str, set[str]] = defaultdict(set)
    split_class_groups: dict[str, dict[bool, set[str]]] = defaultdict(lambda: defaultdict(set))
    split_class_samples: Counter[tuple[str, bool]] = Counter()
    group_splits: dict[str, set[str]] = defaultdict(set)
    scenario_splits: dict[str, set[str]] = defaultdict(set)
    for row in splits:
        split_groups[row["split"]].add(row["stable_group_key_hash"])
        split_class_groups[row["split"]][row["manipulation_present"]].add(row["stable_group_key_hash"])
        split_class_samples[(row["split"], row["manipulation_present"])] += 1
        group_splits[row["stable_group_key_hash"]].add(row["split"])
        if row["scenario_group_key_hash"]:
            scenario_splits[row["scenario_group_key_hash"]].add(row["split"])
    if any(len(values) > 1 for values in group_splits.values()) or any(
        len(values) > 1 for values in scenario_splits.values()
    ):
        raise AssertionError("E_SPLIT_GROUP_LEAKAGE: group/scenario crossed deterministic splits")

    structural_rules = protocol["readiness"]["structural"]
    grouped_data_rules = protocol["readiness"]["grouped_data"]
    structural_blockers: list[str] = []
    if facts_path is None:
        structural_blockers.append("B_SIDECAR_NOT_PROVIDED")
    if verified_primary == 0:
        structural_blockers.append("B_NO_VERIFIED_LABELS")
    if not trusted_groups:
        structural_blockers.append("B_STABLE_GROUP_FACTS_INCOMPLETE")
    if not splits:
        structural_blockers.append("B_NO_FORMAL_PAIRED244")
    minimum_groups = structural_rules["minimum_independent_groups_per_split"]
    if any(len(split_groups[name]) < minimum_groups for name in split_names):
        structural_blockers.append("B_SPLIT_GROUP_MISSING")
    if structural_rules["require_both_manipulation_classes_per_split"] and any(
        not split_class_groups[name][False] or not split_class_groups[name][True]
        for name in split_names
    ):
        structural_blockers.append("B_SPLIT_CLASS_MISSING")
    structural_ready = not structural_blockers

    grouped_data_blockers = list(structural_blockers)
    grouped_min_groups = grouped_data_rules["minimum_independent_groups_per_split"]
    grouped_min_class = grouped_data_rules["minimum_groups_per_manipulation_class_per_split"]
    if any(len(split_groups[name]) < grouped_min_groups for name in split_names) or any(
        len(split_class_groups[name][label]) < grouped_min_class
        for name in split_names
        for label in (False, True)
    ):
        grouped_data_blockers.append("B_GROUP_COVERAGE_THRESHOLD_NOT_MET")
    grouped_data_blockers = list(dict.fromkeys(grouped_data_blockers))
    grouped_data_prerequisites_met = not grouped_data_blockers

    counts = {
        "indexed_sample_count": len(index_rows),
        "paired244_primary_count": sum(row["dataset_view"] == "paired_244" for row in index_rows),
        "app177_reserve_count": sum(row["dataset_view"] == "app_only_177" for row in index_rows),
        "fact_row_count": len(facts),
        "verified_primary_label_count": verified_primary,
        "trusted_stable_group_count": len(trusted_groups),
        "grouped_input_eligible_count": len(splits),
        "split_assigned_count": len(splits),
        "split_sample_counts": {name: split_samples[name] for name in split_names},
        "split_group_counts": {name: len(split_groups[name]) for name in split_names},
        "split_class_sample_counts": {
            name: {
                "manipulation_absent": split_class_samples[(name, False)],
                "manipulation_present": split_class_samples[(name, True)],
            }
            for name in split_names
        },
        "split_class_group_counts": {
            name: {
                "manipulation_absent": len(split_class_groups[name][False]),
                "manipulation_present": len(split_class_groups[name][True]),
            }
            for name in split_names
        },
    }
    readiness = {
        "experiment_readiness_version": READINESS_VERSION,
        "plan_version": PLAN_VERSION,
        "build_status": "passed",
        "primary_task": PRIMARY_TASK,
        "counts": counts,
        "structural_ready": structural_ready,
        "grouped_data_prerequisites_met": grouped_data_prerequisites_met,
        "structural_blockers": structural_blockers,
        "grouped_data_blockers": grouped_data_blockers,
        "downstream_permissions": {
            "collection_qc": True,
            "paired_browser_observation": counts["paired244_primary_count"] > 0,
            "build_grouped_experiment_inputs": grouped_data_prerequisites_met,
            "train_or_tune_model": False,
            "report_performance_metrics": False,
            "final_test_evaluation": False,
        },
        "claim_boundary": (
            "Readiness is a necessary control-plane gate, not proof of sample-size adequacy, "
            "performance, calibration, or cross-device generalization."
        ),
    }

    registry_data = jsonl_bytes(inventory)
    split_data = jsonl_bytes(splits)
    readiness_data = json_bytes(readiness)
    schema_hash = sha256_file(DEFAULT_SCHEMA_PATH)
    source_hashes = {
        name: sha256_file(path)
        for name, path in sorted(source_paths.items())
    }
    protocol_hash = sha256_file(protocol_path)
    canonical_fact_data = jsonl_bytes(
        facts[key] for key in sorted(facts)
    ) if facts_path is not None else None
    facts_hash = sha256_bytes(canonical_fact_data) if canonical_fact_data is not None else None
    run_material = "\0".join(
        (canonical_json(source_hashes), protocol_hash, facts_hash or "no-facts")
    )
    input_manifest = {
        "experiment_input_manifest_version": INPUT_MANIFEST_VERSION,
        "run_id": "latest-experiment-" + hashlib.sha256(run_material.encode("utf-8")).hexdigest()[:20],
        "source": {
            "source_run_id": manifest.get("run_id"),
            "file_sha256": source_hashes,
        },
        "protocol": {
            "protocol_version": protocol["protocol_version"],
            "protocol_sha256": protocol_hash,
            "fact_schema_sha256": schema_hash,
        },
        "fact_registry": {
            "provided": facts_path is not None,
            "row_count": len(facts),
            "canonical_sha256": facts_hash,
        },
        "outputs": {
            "experiment_registry.jsonl": {"row_count": len(inventory), "sha256": sha256_bytes(registry_data)},
            "split_manifest.jsonl": {"row_count": len(splits), "sha256": sha256_bytes(split_data)},
            "experiment_readiness.json": {"sha256": sha256_bytes(readiness_data)},
        },
        "control_boundary": "Labels, tasks, groups, evidence references, and splits remain outside model features and runtime EvidenceBundle inputs.",
    }
    manifest_data = json_bytes(input_manifest)

    output_dir.mkdir(parents=True)
    (output_dir / "experiment_registry.jsonl").write_bytes(registry_data)
    (output_dir / "split_manifest.jsonl").write_bytes(split_data)
    (output_dir / "experiment_readiness.json").write_bytes(readiness_data)
    (output_dir / "experiment_input_manifest.json").write_bytes(manifest_data)
    return readiness


def main() -> None:
    args = parse_args()
    readiness = build_plan(
        args.snapshot_dir,
        args.output_dir,
        facts_path=args.facts,
        protocol_path=args.protocol,
    )
    counts = readiness["counts"]
    print(
        "Latest experiment plan complete: "
        f"{counts['paired244_primary_count']} paired candidates, "
        f"{counts['app177_reserve_count']} App-only reserve, "
        f"{counts['grouped_input_eligible_count']} split-assigned; "
        f"structural_ready={str(readiness['structural_ready']).lower()}, "
        "grouped_data_prerequisites_met="
        f"{str(readiness['grouped_data_prerequisites_met']).lower()} -> {args.output_dir}"
    )


if __name__ == "__main__":
    main()
