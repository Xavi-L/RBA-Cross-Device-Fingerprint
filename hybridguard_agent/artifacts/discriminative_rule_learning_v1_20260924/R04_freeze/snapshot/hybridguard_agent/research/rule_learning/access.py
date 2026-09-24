"""R03 fit capabilities. No user-supplied synthetic flag or ID-name admission.

Public issuance reads only named, programmatically constructed toy fixtures.
Formal issuance is an explicit future entry point and is CLOSED in R03.
This is a trusted-code workflow boundary, not a sandbox against Python reflection.
"""
import copy
import json
import weakref
from dataclasses import dataclass

from .contracts import PHASES, binding
from .fold_data import FoldBatch, FoldData, FIT_OPERATIONS

_ISSUER = object()
_ISSUED = weakref.WeakKeyDictionary()


class FitAuthorizationError(PermissionError):
    """Not a solver/algorithm failure. Propagates before selection starts."""


@dataclass(frozen=True)
class FormalFitRequest:
    stage: str
    authorization_record_ref: str
    freeze_manifest_ref: str
    resource_manifest_ref: str
    expected_fit_job_ref: str
    protocol_digest: str
    split_id: str
    fold_id: str
    method_id: str
    operating_point: str
    source_condition: str
    input_view: str
    train_membership_ref: str


def open_formal_fit(request, *, context=None):
    if not isinstance(request, FormalFitRequest):
        raise FitAuthorizationError("FORMAL_JOB_REQUIRES_EXPLICIT_BOUND_REQUEST")
    if not all(isinstance(v, str) and v for v in vars(request).values()):
        raise FitAuthorizationError("INCOMPLETE_FORMAL_FIT_REQUEST")
    if request.protocol_digest != binding()["protocol_digest"]:
        raise FitAuthorizationError("FORMAL_PROTOCOL_BINDING_MISMATCH")
    if context is None:
        raise FitAuthorizationError("R03_REAL_DATA_FIT_NOT_AUTHORIZED: a verified R04 job context is required")
    # The context checks every request field before opening any train resource.
    from .job_runtime import formal_access
    return formal_access(request, context)


class TrainingAccess:
    def __init__(self, issuer, membership, features, evaluation, atoms, view, fixture_name, encoder=None):
        if issuer is not _ISSUER:
            raise FitAuthorizationError("NO_PUBLIC_DATA_OR_SYNTHETIC_FLAG_ISSUER")
        self._data = FoldData(membership, features, evaluation, synthetic=True)
        self._atoms = tuple(atoms)
        self._view = copy.deepcopy(view)
        declared = {a.atom_id for a in atoms}
        if any(set(row) != declared for row in features.values()):
            raise ValueError("VIEW_FEATURE_COLUMNS_MUST_MATCH_DECLARED_ATOMS")
        self._view["input_atom_ids"] = sorted(declared)
        self._encoder = copy.deepcopy(encoder or {})
        self.fixture_name = fixture_name
        self.operations = []
        self._check_groups()
        _ISSUED[self] = self._snapshot()

    def _snapshot(self):
        return json.dumps({"features": self._data._features, "sidecar": self._data._evaluation,
                           "parts": self._data.parts, "view": self._view, "encoder": self._encoder,
                           "atoms": [vars(a) for a in self._atoms], "fold": self.fold_id,
                           "fixture_name": self.fixture_name}, sort_keys=True)

    def _check_groups(self):
        groups = {}
        for part, ids in self._data.parts.items():
            for oid in ids:
                meta = self._data._evaluation[oid]
                if meta["supervised_label"] is not None:
                    if meta["phase"] not in PHASES:
                        raise ValueError("INVALID_ADMITTED_PHASE")
                    groups.setdefault(meta["bundle_id"], set()).add(part)
        if any(len(parts) != 1 for parts in groups.values()):
            raise ValueError("BUNDLE_SPLIT_ACROSS_PARTITIONS")

    @property
    def fold_id(self):
        return self._data.fold_id

    @property
    def atoms(self):
        return copy.deepcopy(self._atoms)

    @property
    def view(self):
        return copy.deepcopy(self._view)

    @property
    def encoder(self):
        return copy.deepcopy(self._encoder)

    def batch(self, partition):
        return self._data.batch(partition)

    def assert_fit(self, batch, operation):
        if self not in _ISSUED or self._snapshot() != _ISSUED[self]:
            raise FitAuthorizationError("FIT_CAPABILITY_CONTENT_CHANGED")
        try:
            self._data.assert_fit(batch, operation)
        except PermissionError as exc:
            raise FitAuthorizationError(str(exc)) from exc
        self.operations.append({"operation": operation, "partition": "train", "ids": list(batch.ids)})

    def assert_transform(self, batch, fitted_fold):
        self._data.assert_transform(batch, fitted_fold)

    def training_metadata(self, batch):
        self.assert_fit(batch, "support")
        return {oid: copy.deepcopy(self._data._evaluation[oid]) for oid in batch.ids}

    def evaluation_metadata(self, partition):
        return {oid: copy.deepcopy(self._data._evaluation[oid]) for oid in self._data.parts[partition]}

    def model_binding(self, operating_point):
        b = binding()
        return {k: b[k] for k in ("study_version", "protocol_digest", "candidate_version")} | {
            "fold_id": self.fold_id, "split_id": "SYNTHETIC", "operating_point": operating_point,
            "protocol_input_manifest_ref": b["input_manifest_ref"],
            "input_manifest_ref": "hybridguard_agent/research/rule_learning/synthetic.py#" + self.fixture_name,
            "data_origin": "BUILTIN_SYNTHETIC"}

    def fit_context(self):
        return {"fit_scope": "SYNTHETIC_ONLY", "fixture_name": self.fixture_name}

    def assert_method(self, method, operating_point):
        # R03 named toys may exercise every registered method/point.
        pass


def authorize(access, batch, operation):
    if type(access) not in (TrainingAccess, JobTrainingAccess) or access not in _ISSUED:
        # In particular FoldData(synthetic=True) is NOT an R03 fit capability.
        raise FitAuthorizationError("R03_FIT_REQUIRES_ISSUED_CAPABILITY_NOT_SYNTHETIC_FLAG_OR_RENAMED_IDS")
    access.assert_fit(batch, operation)


def synthetic_fixture(name):
    from .synthetic import make_fixture
    membership, features, sidecar, atoms, view = make_fixture(name)
    return TrainingAccess(_ISSUER, membership, features, sidecar, atoms, view, name)


def _derived(access, features, atoms, view, encoder=None):
    """Only fixed projection/authorized encoder modules call this internal issuer."""
    authorize(access, access.batch("train"), "support")
    if type(access) is JobTrainingAccess:
        return JobTrainingAccess(_ISSUER, access._job, features, access._data._evaluation,
                                 atoms, view, access._lineage, encoder)
    membership = dict(access._data.parts, fold_id=access.fold_id)
    return TrainingAccess(_ISSUER, membership, features, access._data._evaluation, atoms,
                          view, access.fixture_name, encoder)


class _TrainOnlyData:
    """An issued job contains train rows only; no test/description store exists."""
    def __init__(self, job, features, evaluation):
        self.fold_id = job["fold_id"]
        self.parts = {"train": tuple(job["train_ids"])}
        if set(features) != set(self.parts["train"]) or set(evaluation) != set(features):
            raise FitAuthorizationError("JOB_TRAIN_MEMBERSHIP_MISMATCH")
        if any(type(r["supervised_label"]) is not int or r["supervised_label"] not in (0, 1)
               for r in evaluation.values()):
            raise FitAuthorizationError("DESCRIPTIVE_OR_UNADMITTED_TRAIN_ROW")
        self._features, self._evaluation = copy.deepcopy(features), copy.deepcopy(evaluation)

    def batch(self, partition):
        if partition != "train":
            raise FitAuthorizationError("TEST_OR_DESCRIPTION_NOT_OPEN_IN_TRAIN_CAPABILITY")
        return FoldBatch(self.fold_id, "train", self.parts["train"],
                         tuple(copy.deepcopy(self._features[i]) for i in self.parts["train"]))

    def assert_fit(self, batch, operation):
        if operation not in FIT_OPERATIONS or batch != self.batch("train"):
            raise FitAuthorizationError("FIT_REQUIRES_EXACT_JOB_TRAIN_BATCH")

    def assert_transform(self, batch, fitted_fold):
        if fitted_fold != self.fold_id or batch != self.batch("train"):
            raise FitAuthorizationError("TRAIN_TRANSFORM_MEMBERSHIP_OR_FOLD_MISMATCH")


class JobTrainingAccess(TrainingAccess):
    """Private issuance by a verified orchestration context, never a data flag."""
    def __init__(self, issuer, job, features, evaluation, atoms, view, lineage, encoder=None):
        if issuer is not _ISSUER:
            raise FitAuthorizationError("JOB_ACCESS_REQUIRES_VERIFIED_ISSUER")
        self._job, self._lineage = copy.deepcopy(job), copy.deepcopy(lineage)
        self._data = _TrainOnlyData(job, features, evaluation)
        self._atoms, self._view = tuple(atoms), copy.deepcopy(view)
        if view["kind"] == "CANONICAL_DEVIATION" and (job["input_view"] != "core" or view.get("source_condition") != job["source_condition"]):
            raise FitAuthorizationError("PROJECTED_SOURCE_VIEW_DIFFERS_FROM_EXACT_JOB")
        if view["kind"] == "SINGLE_SURFACE" and view.get("surface") != job["input_view"]:
            raise FitAuthorizationError("ENCODER_SURFACE_DIFFERS_FROM_EXACT_JOB")
        declared = {a.atom_id for a in atoms}
        if any(set(row) != declared for row in features.values()):
            raise ValueError("VIEW_FEATURE_COLUMNS_MUST_MATCH_DECLARED_ATOMS")
        self._view["input_atom_ids"] = sorted(declared)
        self._encoder, self.fixture_name, self.operations = copy.deepcopy(encoder or {}), job.get("fixture_id"), []
        self._check_groups()
        _ISSUED[self] = self._snapshot()

    def _snapshot(self):
        return super()._snapshot() + json.dumps([self._job, self._lineage], sort_keys=True)

    def model_binding(self, operating_point):
        if operating_point != self._job["operating_point"]:
            raise FitAuthorizationError("JOB_OPERATING_POINT_MISMATCH")
        return copy.deepcopy(self._lineage)

    def fit_context(self):
        return {"fit_scope": "SYNTHETIC_ONLY" if self._job["data_origin"] == "BUILTIN_SYNTHETIC"
                else "EXACT_AUTHORIZED_JOB_TRAIN_ONLY", "fixture_name": self.fixture_name,
                "fit_job_id": self._job["fit_job_id"]}

    def assert_method(self, method, operating_point):
        if (method, operating_point) != (self._job["method_id"], self._job["operating_point"]):
            raise FitAuthorizationError("FIT_METHOD_OR_POINT_DIFFERS_FROM_EXACT_JOB")
