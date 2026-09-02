"""Resolve and validate reusable controlled-attack input selections.

An input-set file freezes which attack manifests belong to a validation run,
why each cohort was accepted, and which incomplete/exploratory manifests were
excluded.  It is selection/provenance metadata only: attack labels and tool
names remain forbidden decision inputs for both knowledge lanes.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hybridguard_agent.adapters.official_kb_adapter import sha256_file


REPO_ROOT = Path(__file__).resolve().parents[1]
ATTACK_INPUT_SET_SCHEMA_VERSION = "official-semantic-attack-input-set-v1"


@dataclass
class AttackInputSelection:
    """Resolved manifests plus cohort/provenance metadata."""

    manifests: list[Path]
    metadata_by_manifest: dict[Path, dict[str, str]]
    provenance: dict[str, Any]


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _required_text(container: dict[str, Any], key: str, context: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _current_git_revision(repository: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(
            f"Cannot resolve pinned source repository revision: {repository}"
        ) from exc
    return completed.stdout.strip()


def resolve_attack_inputs(
    *,
    explicit_manifests: list[Path] | None = None,
    input_set_path: Path | None = None,
) -> AttackInputSelection:
    """Resolve either repeated explicit manifests or one frozen input-set file."""

    explicit = [path.resolve() for path in (explicit_manifests or [])]
    if input_set_path is not None and explicit:
        raise ValueError(
            "attack_input_set and explicit attack_manifests are mutually exclusive"
        )

    if input_set_path is None:
        seen: set[Path] = set()
        for manifest in explicit:
            if manifest in seen:
                raise ValueError(f"Duplicate attack manifest: {manifest}")
            seen.add(manifest)
            if not manifest.is_file():
                raise FileNotFoundError(f"Attack manifest does not exist: {manifest}")
        metadata = {
            manifest: {
                "cohort_id": "explicit_inputs",
                "cohort_label": "命令行显式输入",
                "relation_design_exposure": "not_declared",
                "acceptance_reference": "not_declared",
            }
            for manifest in explicit
        }
        return AttackInputSelection(
            manifests=explicit,
            metadata_by_manifest=metadata,
            provenance={
                "selection_mode": "explicit_manifests",
                "selected_manifest_count": len(explicit),
                "cohorts": [
                    {
                        "cohort_id": "explicit_inputs",
                        "label": "命令行显式输入",
                        "relation_design_exposure": "not_declared",
                        "acceptance_reference": "not_declared",
                        "manifest_paths": [_repo_relative(path) for path in explicit],
                    }
                ]
                if explicit
                else [],
                "excluded_manifests": [],
                "expected_counts": {},
            },
        )

    resolved_input_set = input_set_path.resolve()
    if not resolved_input_set.is_file():
        raise FileNotFoundError(
            f"Attack input-set file does not exist: {resolved_input_set}"
        )
    raw = json.loads(resolved_input_set.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Attack input-set root must be an object")
    if raw.get("schema_version") != ATTACK_INPUT_SET_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported attack input-set schema_version: "
            f"{raw.get('schema_version')!r}"
        )
    input_set_id = _required_text(raw, "input_set_id", "attack_input_set")
    cohorts = raw.get("cohorts")
    if not isinstance(cohorts, list) or not cohorts:
        raise ValueError("attack_input_set.cohorts must be a non-empty array")

    manifests: list[Path] = []
    metadata_by_manifest: dict[Path, dict[str, str]] = {}
    normalized_cohorts: list[dict[str, Any]] = []
    seen_cohort_ids: set[str] = set()
    for cohort_index, cohort in enumerate(cohorts):
        context = f"attack_input_set.cohorts[{cohort_index}]"
        if not isinstance(cohort, dict):
            raise ValueError(f"{context} must be an object")
        cohort_id = _required_text(cohort, "cohort_id", context)
        if cohort_id in seen_cohort_ids:
            raise ValueError(f"Duplicate cohort_id: {cohort_id}")
        seen_cohort_ids.add(cohort_id)
        label = _required_text(cohort, "label", context)
        exposure = _required_text(cohort, "relation_design_exposure", context)
        acceptance = _required_text(cohort, "acceptance_reference", context)
        manifest_values = cohort.get("manifests")
        if not isinstance(manifest_values, list) or not manifest_values:
            raise ValueError(f"{context}.manifests must be a non-empty array")
        cohort_paths: list[str] = []
        for manifest_index, value in enumerate(manifest_values):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{context}.manifests[{manifest_index}] must be a non-empty string"
                )
            manifest = _resolve_repo_path(value.strip())
            if manifest in metadata_by_manifest:
                raise ValueError(f"Duplicate attack manifest across cohorts: {manifest}")
            if not manifest.is_file():
                raise FileNotFoundError(f"Attack manifest does not exist: {manifest}")
            metadata_by_manifest[manifest] = {
                "cohort_id": cohort_id,
                "cohort_label": label,
                "relation_design_exposure": exposure,
                "acceptance_reference": acceptance,
            }
            manifests.append(manifest)
            cohort_paths.append(_repo_relative(manifest))
        normalized_cohorts.append(
            {
                "cohort_id": cohort_id,
                "label": label,
                "relation_design_exposure": exposure,
                "acceptance_reference": acceptance,
                "manifest_paths": cohort_paths,
                "selected_manifest_count": len(cohort_paths),
            }
        )

    expected_counts = raw.get("expected_counts", {})
    if not isinstance(expected_counts, dict):
        raise ValueError("attack_input_set.expected_counts must be an object")
    expected_manifest_count = expected_counts.get("selected_manifest_count")
    if expected_manifest_count is not None and expected_manifest_count != len(manifests):
        raise ValueError(
            "Attack input-set selected_manifest_count mismatch: "
            f"expected {expected_manifest_count}, observed {len(manifests)}"
        )

    source_repository = raw.get("source_repository")
    normalized_source: dict[str, Any] | None = None
    if source_repository is not None:
        if not isinstance(source_repository, dict):
            raise ValueError("attack_input_set.source_repository must be an object")
        source_path_text = _required_text(
            source_repository, "path", "attack_input_set.source_repository"
        )
        expected_revision = _required_text(
            source_repository, "revision", "attack_input_set.source_repository"
        )
        source_path = _resolve_repo_path(source_path_text)
        if not source_path.is_dir():
            raise FileNotFoundError(
                f"Pinned source repository does not exist: {source_path}"
            )
        actual_revision = _current_git_revision(source_path)
        if actual_revision != expected_revision:
            raise ValueError(
                "Pinned source repository revision mismatch: "
                f"expected {expected_revision}, observed {actual_revision}"
            )
        normalized_source = {
            "path": _repo_relative(source_path),
            "expected_revision": expected_revision,
            "observed_revision": actual_revision,
        }

    excluded = raw.get("excluded_new_manifests", [])
    if not isinstance(excluded, list):
        raise ValueError("attack_input_set.excluded_new_manifests must be an array")
    normalized_excluded: list[dict[str, str]] = []
    selected_set = set(manifests)
    for index, row in enumerate(excluded):
        context = f"attack_input_set.excluded_new_manifests[{index}]"
        if not isinstance(row, dict):
            raise ValueError(f"{context} must be an object")
        excluded_path_text = _required_text(row, "path", context)
        reason = _required_text(row, "reason", context)
        excluded_path = _resolve_repo_path(excluded_path_text)
        if excluded_path in selected_set:
            raise ValueError(
                f"Manifest cannot be both selected and excluded: {excluded_path}"
            )
        normalized_excluded.append(
            {"path": _repo_relative(excluded_path), "reason": reason}
        )

    provenance = {
        "selection_mode": "frozen_input_set",
        "input_set_id": input_set_id,
        "input_set_schema_version": ATTACK_INPUT_SET_SCHEMA_VERSION,
        "input_set_path": _repo_relative(resolved_input_set),
        "input_set_sha256": sha256_file(resolved_input_set),
        "description": raw.get("description"),
        "source_repository": normalized_source,
        "protocol": raw.get("protocol"),
        "selection_policy": raw.get("selection_policy"),
        "selected_manifest_count": len(manifests),
        "cohorts": normalized_cohorts,
        "excluded_manifests": normalized_excluded,
        "expected_counts": expected_counts,
    }
    return AttackInputSelection(
        manifests=manifests,
        metadata_by_manifest=metadata_by_manifest,
        provenance=provenance,
    )


def attach_and_validate_observed_counts(
    selection: AttackInputSelection,
    attack_pairs: list[dict[str, Any]],
) -> dict[str, int]:
    """Validate frozen expected counts after pair parsing and retain observations."""

    eligible = [pair for pair in attack_pairs if pair["eligible_for_two_state_validation"]]
    legacy_pairs = 0
    new_pairs = 0
    tools: set[str] = set()
    configs: set[str] = set()
    for pair in attack_pairs:
        manifest_path = pair.get("manifest_path")
        if isinstance(manifest_path, Path):
            exposure = selection.metadata_by_manifest[manifest_path.resolve()][
                "relation_design_exposure"
            ]
        else:
            exposure = pair.get("relation_design_exposure")
        if exposure == "inspected_before_semantic_catalog_freeze":
            legacy_pairs += 1
        elif exposure == "not_inspected_before_semantic_catalog_freeze":
            new_pairs += 1
        tool_summary = pair.get("tool")
        if isinstance(tool_summary, dict):
            attack = tool_summary
        else:
            active = pair.get("attack_active")
            manifest = active.get("manifest") if isinstance(active, dict) else None
            attack = manifest.get("attack") if isinstance(manifest, dict) else None
        if isinstance(attack, dict):
            tool = attack.get("tool_name")
            config = attack.get("config_id")
            if isinstance(tool, str) and tool:
                tools.add(tool)
            if isinstance(config, str) and config:
                configs.add(config)

    observed = {
        "selected_manifest_count": len(selection.manifests),
        "legacy_pair_count": legacy_pairs,
        "new_pair_count": new_pairs,
        "total_pair_count": len(attack_pairs),
        "eligible_pair_count": len(eligible),
        "ignored_historical_post_count": sum(
            int(pair["ignored_historical_post_count"]) for pair in attack_pairs
        ),
        "unique_tool_name_count": len(tools),
        "unique_config_id_count": len(configs),
    }
    expected = selection.provenance.get("expected_counts", {})
    mismatches = {
        key: {"expected": expected_value, "observed": observed.get(key)}
        for key, expected_value in expected.items()
        if key in observed and observed[key] != expected_value
    }
    if mismatches:
        raise ValueError(
            "Attack input-set observed count mismatch: "
            + json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
        )
    selection.provenance["observed_counts"] = observed
    return observed
