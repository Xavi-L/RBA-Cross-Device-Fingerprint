"""Fold access boundary and synthetic-only train-quantile contract for R02.

Fixed per-sample relations may be cached on every row. Every data-dependent
operation must first obtain an exact train batch from this boundary. R02 has
no authority to fit real records, even records on a fold's train side.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import json
import math
from pathlib import Path

FIT_OPERATIONS = frozenset({"numeric_thresholds", "support", "ranking", "polarity_selection",
                            "combination_selection", "pruning"})


@dataclass(frozen=True)
class FoldBatch:
    fold_id: str
    partition: str
    ids: tuple[str, ...]
    records: tuple[dict, ...]


class FoldData:
    def __init__(self, membership, features, evaluation_index, *, synthetic=False):
        self.fold_id = membership["fold_id"]
        self.parts = {p: tuple(membership[p]) for p in (
            "train", "outer_test", "descriptive_train_side", "descriptive_test_side")}
        flat = [i for ids in self.parts.values() for i in ids]
        if len(set(flat)) != len(flat) or set(flat) != set(features) or set(flat) != set(evaluation_index):
            raise ValueError("FOLD_ROW_DUPLICATE_OR_MEMBERSHIP_MISMATCH")
        for p, ids in self.parts.items():
            for i in ids:
                label = evaluation_index[i]["supervised_label"]
                if p in {"train", "outer_test"}:
                    if type(label) is not int or label not in {0, 1}:
                        raise ValueError("SUPERVISED_PARTITION_REQUIRES_ADMITTED_LABEL")
                elif label is not None:
                    raise ValueError("DESCRIPTIVE_LABEL_PROMOTION")
        self._features = copy.deepcopy(features)
        self._evaluation = copy.deepcopy(evaluation_index)
        self.synthetic = synthetic
        if synthetic and any(not i.startswith("fixture-") for i in flat):
            raise PermissionError("REAL_SAMPLE_CANNOT_BE_MARKED_SYNTHETIC")

    def batch(self, partition):
        ids = self.parts[partition]
        # Sidecar labels/phase/config/paths never enter transform records.
        return FoldBatch(self.fold_id, partition, ids, tuple(copy.deepcopy(self._features[i]) for i in ids))

    def assert_fit(self, batch, operation):
        if operation not in FIT_OPERATIONS:
            raise PermissionError("UNREGISTERED_DATA_DEPENDENT_OPERATION")
        if (batch.fold_id != self.fold_id or batch.partition != "train"
                or batch.ids != self.parts["train"]
                or batch.records != tuple(self._features[i] for i in batch.ids)):
            raise PermissionError("FIT_REQUIRES_EXACT_OWN_TRAIN_BATCH")
        if not self.synthetic:
            raise PermissionError("R02_REAL_DATA_FIT_NOT_AUTHORIZED")

    def assert_transform(self, batch, fitted_fold):
        if fitted_fold != self.fold_id or batch.fold_id != self.fold_id:
            raise PermissionError("TRANSFORM_MODEL_FROM_ANOTHER_FOLD")
        if batch.partition not in self.parts or batch.ids != self.parts[batch.partition]:
            raise PermissionError("TRANSFORM_MEMBERSHIP_MISMATCH")
        if batch.records != tuple(self._features[i] for i in batch.ids):
            raise PermissionError("TRANSFORM_BATCH_CONTENT_MISMATCH")


class TrainQuantiles:
    """Focused fit/transform implementation tested only on synthetic inputs.

The 0.25/0.5/0.75 choices and linear interpolation are frozen in R01. This
component does not rank/select rules or choose a polarity. Real use requires
a later authorized implementation of the fit gate, not a flag in this CLI.
"""
    def __init__(self, field):
        self.field = field
        self.thresholds = None
        self.fold_id = None
        self.train_ids = None

    def fit(self, access, batch):
        access.assert_fit(batch, "numeric_thresholds")
        if self.thresholds is not None:
            raise PermissionError("FITTED_TRANSFORM_IS_IMMUTABLE")
        values = []
        for record in batch.records:
            cell = record[self.field]
            if cell["evaluation_status"] == "FAILED":
                raise ValueError("FAILED_TRAIN_MEASUREMENT")
            if cell["available"]:
                v = cell["value"]
                if type(v) not in (int, float) or not math.isfinite(v):
                    raise ValueError("NONNUMERIC_QUANTILE_INPUT")
                values.append(v)
        values.sort()
        thresholds = []
        for q in (.25, .5, .75):
            if values:
                x = (len(values) - 1) * q
                lo, hi = math.floor(x), math.ceil(x)
                thresholds.append(values[lo] + (values[hi] - values[lo]) * (x - lo))
        self.thresholds = tuple(sorted(set(thresholds)))
        self.fold_id, self.train_ids = access.fold_id, batch.ids
        return self

    def transform(self, access, batch):
        if self.thresholds is None:
            raise PermissionError("TRANSFORM_REQUIRES_FROZEN_TRAIN_FIT")
        access.assert_transform(batch, self.fold_id)
        rows = []
        for record in batch.records:
            c = record[self.field]
            if c["evaluation_status"] == "FAILED":
                rows.append({"states": [None] * len(self.thresholds), "evaluation_status": "FAILED"})
            elif not c["available"]:
                rows.append({"states": ["U"] * len(self.thresholds), "evaluation_status": "OK"})
            else:
                rows.append({"states": ["T" if c["value"] <= t else "F" for t in self.thresholds],
                             "evaluation_status": "OK"})
        return rows


def load_fold(directory, fold_id, view="core"):
    """Read only approved matrix columns; all evaluation metadata stays aside.

Single-surface views include same-surface catalog atoms, fixed control atoms
and unfitted numeric control measurements. R03 must fit thresholds on train
before those numeric measurements can become candidate literals.
"""
    directory = Path(directory)

    def load(name):
        with (directory / name).open() as f:
            return [json.loads(line) for line in f if line.strip()]

    columns = json.loads((directory / "COLUMN_MANIFEST.json").read_text())
    membership = next(f for f in json.loads((directory / "FOLD_INPUT_MANIFEST.json").read_text())["folds"] if f["fold_id"] == fold_id)
    evaluation = {r["opaque_id"]: r for r in load("evaluation_index.jsonl")}
    features = {i: {} for i in evaluation}

    def add(matrix, names, selected, availability=None):
        seen = set()
        for r in matrix:
            oid = r["opaque_id"]
            if oid in seen or oid not in features or len(r["values"]) != len(names):
                raise ValueError("MATRIX_ROW_OR_COLUMN_MISMATCH")
            seen.add(oid)
            av = availability[oid] if availability is not None else r
            if any(len(av[k]) != len(names) for k in ("available", "evaluation_status")):
                raise ValueError("AVAILABILITY_COLUMN_MISMATCH")
            for j in selected:
                features[oid][names[j]] = {"value": r["values"][j], "available": av["available"][j],
                                          "evaluation_status": av["evaluation_status"][j]}
        if seen != set(features):
            raise ValueError("MISSING_MATRIX_ROWS")

    if view == "core":
        add(load("core_matrix.jsonl"), columns["core_columns"], range(len(columns["core_columns"])))
    elif view in {"native84", "host26", "app_web67"}:
        names = columns["candidate_columns"]
        av = {r["opaque_id"]: r for r in load("availability_matrix.jsonl")}
        add(load("candidate_matrix.jsonl"), names, [names.index(n) for n in columns["single_surface_catalog_columns"][view]], av)
        fixed = load("fixed_control_manifest.jsonl")
        add(load("fixed_control_matrix.jsonl"), columns["fixed_control_columns"], [j for j,c in enumerate(fixed) if c["surface"] == view])
        raw = columns["control_columns"]
        add(load("control_inputs.jsonl"), ["UNFITTED_CONTROL:"+c["field"] for c in raw],
            [j for j,c in enumerate(raw) if c["surface"] == view and "TRAIN_QUANTILE" in c["encoder"]])
    else:
        raise ValueError("UNREGISTERED_INPUT_VIEW")
    return FoldData(membership, features, evaluation)
