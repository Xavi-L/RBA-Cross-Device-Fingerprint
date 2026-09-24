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


def open_formal_fit(request):
    if not isinstance(request, FormalFitRequest):
        raise FitAuthorizationError("FORMAL_JOB_REQUIRES_EXPLICIT_BOUND_REQUEST")
    if not all(isinstance(v, str) and v for v in vars(request).values()):
        raise FitAuthorizationError("INCOMPLETE_FORMAL_FIT_REQUEST")
    if request.protocol_digest != binding()["protocol_digest"]:
        raise FitAuthorizationError("FORMAL_PROTOCOL_BINDING_MISMATCH")
    # R04 must close resources; R05/R06/R07/R08 must separately authorize jobs.
    # Neither a FREEZE label nor caller-supplied strings grant execution rights.
    raise FitAuthorizationError("R03_REAL_DATA_FIT_NOT_AUTHORIZED: R04 resource binding and later job authorization required")


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


def authorize(access, batch, operation):
    if type(access) is not TrainingAccess or access not in _ISSUED:
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
    membership = dict(access._data.parts, fold_id=access.fold_id)
    return TrainingAccess(_ISSUER, membership, features, access._data._evaluation, atoms,
                          view, access.fixture_name, encoder)
