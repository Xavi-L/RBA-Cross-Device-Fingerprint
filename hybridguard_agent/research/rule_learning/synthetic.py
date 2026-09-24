"""Named toy recipes only. This module reads no real feature or label matrix.

Calling synthetic_fixture takes a recipe name, never caller-provided rows.
The exported JSON fixtures in R03 are outputs for independent inspection.
"""
import copy
from .contracts import PHASES, cell, ledger
from .models import Atom

FIXTURES = ("union_budget", "complementary", "redundant", "negative", "and_required",
            "infeasible", "all_unknown", "low_coverage", "coverage_boundary", "failed_atom",
            "empty_pool", "label_sensitive", "train_labels_changed", "macro_weights",
            "aliases", "aliases_conflict", "numeric", "numeric_test_extreme", "numeric_masked_failure",
            "two_available", "one_true_attack", "cap_overflow", "invalid_split", "pruning", "coverage_tie")


def toy_atom(name, family=None, surface=None):
    return Atom(name, family or name, (surface,) if surface else ("native84", "app_web67"),
                ("E",), (name,), provenance={"fixture_only": True})


def make_fixture(name):
    if name not in FIXTURES:
        raise ValueError("UNKNOWN_BUILTIN_SYNTHETIC_RECIPE")
    n = 12 if name in ("union_budget", "pruning") else 5 if name == "coverage_boundary" else 6
    base = "numeric" if name.startswith("numeric") else "aliases" if name.startswith("aliases") else "label_sensitive" if name == "train_labels_changed" else name
    members = {p: [] for p in ("train", "outer_test", "descriptive_train_side", "descriptive_test_side")}
    features, sidecar = {}, {}
    atoms = (toy_atom("A"), toy_atom("B"))
    if name == "pruning":
        atoms += (toy_atom("C"),)
    single = name.startswith("numeric")
    raw_core = name.startswith("aliases")
    if name in ("negative", "infeasible", "all_unknown", "low_coverage", "coverage_boundary", "failed_atom"):
        atoms = (toy_atom("A"),)
    if name == "empty_pool":
        atoms = ()
    if name == "cap_overflow":
        atoms = tuple(toy_atom(f"ATOM-{i:02d}") for i in range(48))
    if name in ("two_available", "one_true_attack"):
        atoms = (toy_atom("A"),)
    candidates = ledger() if raw_core else []
    if raw_core:
        candidates = [c for c in candidates if c["candidate_use"]["core"] and c["candidate_use"]["selectable_on_App177"]]
        atoms = tuple(Atom(c["atom_id"], c["decision_family"], tuple(c["observation_surfaces"]),
                           (c["provenance_group"],), (c["rule_id"],), "CATALOG_CONDITION") for c in candidates)
    if single:
        atoms = (toy_atom("UNFITTED_CONTROL:native.number", "number", "native84"),
                 toy_atom("CONTROL:native.flag", "flag", "native84"),
                 toy_atom("UNFITTED_CONTROL:web.number", "webnumber", "app_web67"))
    for partition, count in (("train", n), ("outer_test", 3), ("descriptive_test_side", 1)):
        for j in range(count):
            bundle = f"fixture-{base}-{partition}-bundle"
            for phase in PHASES:
                oid = f"fixture-{base}-{partition}-{j}-{phase}"
                members[partition].append(oid)
                label = None if partition.startswith("descriptive") else int(phase == "attack")
                m = {"opaque_id": oid, "supervised_label": label, "phase": phase,
                     "bundle_id": bundle, "triplet_id": f"{bundle}-{j}",
                     "config_id": "C1" if name == "macro_weights" and j >= 4 else "C0",
                     "environment_group_id": "E0" if partition == "train" else "E1",
                     "data_role": "DESCRIPTIVE_ONLY" if label is None else "SYNTHETIC_ADMITTED",
                     "source_rows": [oid]}
                sidecar[oid] = m
                attack = phase == "attack"
                row = {a.atom_id: cell("F") for a in atoms}
                if name in ("union_budget", "complementary", "macro_weights"):
                    cut = 4 if name == "macro_weights" else n // 2
                    row["A"] = cell("T" if attack and j < cut or name == "union_budget" and phase == "clean_pre" and j == 0 else "F")
                    row["B"] = cell("T" if attack and j >= cut or name == "union_budget" and phase == "clean_pre" and j == 1 else "F")
                elif name == "two_available":
                    row["A"] = cell("U" if j >= 2 else "T" if attack else "F")
                elif name == "one_true_attack":
                    row["A"] = cell("T" if attack and j == 0 else "F")
                elif name == "pruning":
                    for atom, hits in (("A", {0, 1, 2, 3, 4, 5}), ("B", {0, 1, 2, 6, 7}), ("C", {3, 4, 5, 8, 9})):
                        row[atom] = cell("T" if attack and j in hits else "F")
                elif name == "coverage_tie":
                    row["A"] = cell("U" if phase == "clean_pre" and j == 5 else "T" if attack and j < 3 else "F")
                    row["B"] = cell("T" if attack and j < 3 else "F")
                elif name in ("redundant", "failed_atom"):
                    row = {a.atom_id: cell("T" if attack else "F") for a in atoms}
                    if name == "failed_atom" and j == 0 and phase == "clean_pre":
                        row["A"] = cell("FAILED")
                elif name == "negative":
                    row["A"] = cell("F" if attack else "T")
                elif name == "and_required":
                    row["A"] = cell("T" if attack or phase == "clean_pre" else "F")
                    row["B"] = cell("T" if attack or phase == "clean_post" else "F")
                elif name == "infeasible":
                    row["A"] = cell("T")
                elif name in ("all_unknown", "low_coverage", "coverage_boundary"):
                    available = 0 if name == "all_unknown" else 3 if name == "low_coverage" else 4
                    row["A"] = cell("U" if j >= available else "T" if attack else "F")
                elif name in ("label_sensitive", "train_labels_changed"):
                    row["A"], row["B"] = cell("T" if attack else "F"), cell("T" if phase == "clean_pre" else "F")
                    if name == "train_labels_changed" and partition == "train":
                        # Coherent alternative admission: swap attack/pre roles and labels,
                        # with exactly the same feature values and opaque IDs.
                        m["phase"] = {"attack": "clean_pre", "clean_pre": "attack", "clean_post": "clean_post"}[phase]
                        m["supervised_label"] = int(m["phase"] == "attack")
                elif raw_core:
                    for c in candidates:
                        s = "T" if attack else "F"
                        if c["direct_OR_deviation_polarity"] == "NEGATIVE":
                            s = "F" if s == "T" else "T"
                        row[c["atom_id"]] = cell(s)
                    if name == "aliases_conflict":
                        row["CAT:OFFDER-OS-001"] = cell("U", "SYNTHETIC_DIFFERENT_DOMAIN")
                elif single:
                    value = j * 3 + PHASES.index(phase)
                    if partition == "outer_test" and name == "numeric_test_extreme":
                        value = 10**9
                    row["UNFITTED_CONTROL:native.number"] = {"value": value, "available": True, "evaluation_status": "OK"}
                    row["CONTROL:native.flag"] = cell("T" if attack else "F")
                    row["UNFITTED_CONTROL:web.number"] = {"value": -value, "available": True, "evaluation_status": "OK"}
                    if name == "numeric_masked_failure":
                        row["UNFITTED_CONTROL:web.number"] = cell("FAILED")
                features[oid] = row
    members["fold_id"] = "fixture-fold-1"
    if name == "invalid_split":
        sidecar[members["outer_test"][0]]["bundle_id"] = sidecar[members["train"][0]]["bundle_id"]
    view = {"view_id": "RAW_CORE" if raw_core else "RAW_SINGLE" if single else "SYNTHETIC_CORE",
            "kind": "RAW_CORE" if raw_core else "RAW_SINGLE_SURFACE" if single else "CANONICAL_DEVIATION",
            "source_condition": "SRC-111"}
    return members, features, sidecar, atoms, view


def export_fixture(name):
    from dataclasses import asdict
    members, rows, labels, atoms, view = make_fixture(name)
    return {"fixture_id": name, "origin": "PROGRAMMATIC_TOY_RECIPE_NO_REAL_SAMPLES", "membership": members,
            "features": rows, "evaluation_sidecar": labels, "atoms": [asdict(a) for a in atoms], "view": view}
