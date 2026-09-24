"""Verified resources, exact-job capabilities and staged input access.

This is a trusted Python workflow boundary, not an OS sandbox against code
replacement/reflection. R04 ships NO real execution grant. A future approved
grant issuer must be separately delivered; request strings cannot grant rights.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import weakref

from .access import FitAuthorizationError, JobTrainingAccess, _ISSUER
from .contracts import ROOT, binding, read_json, read_jsonl
from .job_manifest import digest, plan_real_jobs
from .models import Atom, load_model

_CONTEXTS = weakref.WeakSet()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x") as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")


class FrozenSnapshot:
    def __init__(self, root):
        self.root = Path(root).resolve()
        if ROOT.resolve() != self.root / "snapshot":
            raise FitAuthorizationError("RUN_FROM_INDEPENDENT_FROZEN_CODE_ONLY_NO_WORKSPACE_FALLBACK")
        self.freeze = read_json(self.root / "FREEZE_MANIFEST.json")
        self.freeze_digest = file_digest(self.root / "FREEZE_MANIFEST.json")
        for name, expected in self.freeze["manifest_digests"].items():
            if file_digest(self.root / name) != expected:
                raise FitAuthorizationError("FREEZE_MANIFEST_MISMATCH:" + name)
        self.resources = read_json(self.root / "RESOURCE_MANIFEST.json")
        self.resource_digest = file_digest(self.root / "RESOURCE_MANIFEST.json")
        self.protocol = read_json(self.root / "protocol.json")
        self.entries = {e["path"]: e for e in self.resources["files"]}
        if len(self.entries) != len(self.resources["files"]):
            raise ValueError("DUPLICATE_RESOURCE")
        # Byte integrity checks do not decode/test/transform rows. Semantic read
        # events are separately logged only through JobContext below.
        for e in self.resources["files"]:
            self.check_resource(e["path"])
        runtime = self.resources["runtime"]
        if Path(sys.executable).resolve() != self.root / runtime["python_copy"]:
            raise ValueError("PYTHON_EXECUTABLE_OUTSIDE_FROZEN_COPY")
        if (platform.python_version() != runtime["python"] or platform.platform() != runtime["platform"]
                or platform.machine() != runtime["machine"]):
            raise ValueError("RUNTIME_PLATFORM_OR_PYTHON_VERSION_CONFLICT")
        for e in runtime["external_python_files"]:
            if not Path(e["path"]).is_file() or file_digest(e["path"]) != e["sha256"]:
                raise ValueError("PYTHON_RUNTIME_RESOURCE_MISMATCH:" + e["path"])
        import highspy
        import numpy
        if highspy.Highs().version() != runtime["highspy"] or numpy.__version__ != runtime["numpy"]:
            raise ValueError("SOLVER_OR_NUMPY_VERSION_CONFLICT_NO_FALLBACK")
        for module in (highspy, numpy):
            if not Path(module.__file__).resolve().is_relative_to(self.root / "dependencies/site-packages"):
                raise ValueError("DEPENDENCY_OUTSIDE_FROZEN_COPY")
        self.models = read_jsonl(self.root / "expected_model_units.jsonl")
        self.synthetic = read_jsonl(self.root / "synthetic/expected_model_units.jsonl")
        self.splits = read_json(self.root / "SPLIT_MANIFEST.json")
        self.auth = read_json(self.root / "AUTHORIZATION.json")
        self._formal_grant = None
        if self.protocol["protocol_digest"] != binding()["protocol_digest"]:
            raise ValueError("PROTOCOL_BINDING_MISMATCH")
        for j in self.models + self.synthetic:
            if j["protocol_digest"] != self.protocol["protocol_digest"]:
                raise ValueError("JOB_PROTOCOL_MISMATCH")
            if digest(j["train_ids"]) != j["train_membership_digest"] or digest(j["outer_test_ids"]) != j["test_membership_digest"]:
                raise ValueError("JOB_MEMBERSHIP_DIGEST_MISMATCH")
            if set(j["train_ids"]) & set(j["outer_test_ids"]):
                raise ValueError("JOB_PARTITION_OVERLAP")
        fits, planned, units = plan_real_jobs()
        for actual, expected in zip(self.models, planned, strict=True):
            if any(actual.get(k) != v for k, v in expected.items()):
                raise ValueError("EXACT_JOB_DIFFERS_FROM_R01_MEMBERS_OR_PLAN")
        expected_fits = read_jsonl(self.root / "expected_fit_jobs.jsonl")
        for actual, expected in zip(expected_fits, fits, strict=True):
            if any(actual.get(k) != v for k, v in expected.items()):
                raise ValueError("EXACT_FIT_PLAN_MISMATCH")
        if read_jsonl(self.root / "expected_prediction_units.jsonl") != units:
            raise ValueError("EXACT_PREDICTION_PLAN_MISMATCH")
        for origin, ref in self.protocol["data_indices"].items():
            index = read_json(self.check_resource(ref))
            for j in self.models + self.synthetic:
                if j["data_origin"] != origin:
                    continue
                if j["definitions_ref"] not in self.entries:
                    raise ValueError("MISSING_DEFINITIONS_RESOURCE")
                for oid in j["train_ids"] + j["outer_test_ids"]:
                    if oid not in index or any(v not in self.entries for v in index[oid].values()):
                        raise ValueError("JOB_MEMBER_RESOURCE_MISSING")
        self.startup_audit = {"verified_file_n": len(self.entries), "integrity_read_scope": "BINARY_ONLY_NO_FEATURE_OR_LABEL_DECODE",
            "module_root": str(ROOT), "highspy_path": highspy.__file__, "numpy_path": numpy.__file__,
            "python_executable": sys.executable, "cwd": str(Path.cwd()), "freeze_digest": self.freeze_digest}
        if any(getattr(m, "__file__", None) and not Path(m.__file__).resolve().is_relative_to(ROOT)
               for n, m in sys.modules.items() if n.startswith("hybridguard_agent")):
            raise ValueError("MODULE_OUTSIDE_FROZEN_SOURCE_TREE")

    def bind_formal_authorization(self, path, expected_approval_digest):
        """Operator entry for a separately approved later stage; never used in R04.

        The approval digest is pinned by the owner at run launch, not inferred
        from a synthetic flag, sample IDs, a FREEZE marker or a solver result.
        This file is a trusted operator approval record, not a digital signature.
        """
        path = Path(path).resolve()
        if file_digest(path) != expected_approval_digest:
            raise FitAuthorizationError("OWNER_PINNED_APPROVAL_DIGEST_MISMATCH")
        grant = read_json(path)
        stage = grant.get("stage")
        if stage not in ("R05", "R06", "R07", "R08", "FINAL_DEVELOPMENT_REFIT_SEPARATE_AUTHORIZATION"):
            raise FitAuthorizationError("R04_CANNOT_GRANT_REAL_EXECUTION")
        jobs = [j for j in self.models if j["authorization_stage"] == stage]
        expected = {"type": "EXPLICIT_USER_STAGE_APPROVAL", "stage": stage,
            "freeze_manifest_digest": self.freeze_digest, "resource_manifest_digest": self.resource_digest,
            "protocol_digest": self.protocol["protocol_digest"], "job_ids": [j["job_id"] for j in jobs],
            "train_membership_digests": {j["job_id"]: j["train_membership_digest"] for j in jobs},
            "budget": self.protocol["budget"]}
        if (any(grant.get(k) != v for k, v in expected.items()) or not grant.get("user_instruction_ref")
                or not isinstance(grant.get("budget_ledger_ref"), str) or not Path(grant["budget_ledger_ref"]).is_absolute()):
            raise FitAuthorizationError("FORMAL_APPROVAL_SCOPE_OR_RESOURCE_MISMATCH")
        if path.is_relative_to(self.root) or self._formal_grant is not None:
            raise FitAuthorizationError("APPROVAL_MUST_BE_SEPARATE_ONCE_BOUND_OWNER_RECORD")
        self._formal_grant = dict(grant, ref=str(path) + "#" + expected_approval_digest,
                                  path=str(path), pinned_digest=expected_approval_digest)

    def check_resource(self, name):
        if name not in self.entries:
            raise ValueError("UNREGISTERED_RESOURCE:" + name)
        e = self.entries[name]
        path = self.root / name
        if path.is_symlink() or not path.resolve().is_relative_to(self.root) or not path.is_file():
            raise ValueError("MISSING_OR_EXTERNAL_RESOURCE:" + name)
        if path.stat().st_size != e["bytes"] or file_digest(path) != e["sha256"]:
            raise ValueError("RESOURCE_DIGEST_MISMATCH:" + name)
        return path

    def context(self, job_id, stage):
        jobs = self.synthetic if stage == "SYNTHETIC_R04" else self.models
        matches = [j for j in jobs if j["job_id"] == job_id]
        if len(matches) != 1:
            raise FitAuthorizationError("UNKNOWN_OR_FORGED_JOB")
        return JobContext(self, matches[0], stage)


class JobContext:
    def __init__(self, snapshot, job, stage):
        self.snapshot, self.job, self.stage = snapshot, copy.deepcopy(job), stage
        self.phase, self.events, self.receipt = "CREATED", [], None
        self._job_digest = digest(self.job)
        _CONTEXTS.add(self)

    def event(self, name, **details):
        self.events.append({"sequence": len(self.events), "event": name, "utc": datetime.now(timezone.utc).isoformat(),
                            "monotonic_ns": time.monotonic_ns(), **details})

    def authorize(self):
        if self not in _CONTEXTS or digest(self.job) != self._job_digest:
            raise FitAuthorizationError("FORGED_OR_CHANGED_JOB_CONTEXT")
        if self.stage != "SYNTHETIC_R04":
            g = self.snapshot._formal_grant
            if (g is None or g["stage"] != self.stage or self.job not in self.snapshot.models
                    or self.job["job_id"] not in g["job_ids"] or self.job["authorization_stage"] != self.stage
                    or file_digest(g["path"]) != g["pinned_digest"]):
                raise FitAuthorizationError("R04_REAL_DATA_FIT_NOT_AUTHORIZED: separate approved stage grant required")
            return
        if (self.job not in self.snapshot.synthetic or self.job["data_origin"] != "BUILTIN_SYNTHETIC"
                or self.snapshot.auth["synthetic_scope"] != "BUILTIN_RESOURCES_ONLY"
                or self.job["job_id"] not in self.snapshot.auth["synthetic_job_ids"]):
            raise FitAuthorizationError("SYNTHETIC_CAPABILITY_CANNOT_AUTHORIZE_REAL_OR_CALLER_DATA")

    def _read(self, ref, event):
        self.event(event, resource=ref)
        return read_json(self.snapshot.check_resource(ref))

    def train(self):
        self.authorize()
        if self.phase != "CREATED":
            raise FitAuthorizationError("TRAIN_ACCESS_NOT_AT_START")
        self.phase = "TRAIN_OPEN"
        index = self.snapshot.protocol["data_indices"][self.job["data_origin"]]
        entries = self._read(index, "OPEN_METADATA_ONLY_DATA_INDEX")
        rows, meta = {}, {}
        for oid in self.job["train_ids"]:
            rows[oid] = self._read(entries[oid]["features"], "OPEN_TRAIN_FEATURE")["features"]
            meta[oid] = self._read(entries[oid]["evaluation"], "OPEN_TRAIN_LABEL")
        definitions = self._read(self.job["definitions_ref"], "OPEN_FIXED_DEFINITIONS")
        atoms = tuple(Atom(**dict(a, surfaces=tuple(a["surfaces"]), sources=tuple(a["sources"]), aliases=tuple(a["aliases"])))
                      for a in definitions["atoms"])
        # A surface job discards every other field before the encoder is fitted.
        if self.job["input_view"] != "core":
            atoms = tuple(a for a in atoms if a.surfaces == (self.job["input_view"],))
        names = {a.atom_id for a in atoms}
        rows = {oid: {k: row[k] for k in names} for oid, row in rows.items()}
        self.event("TRAIN_READY", ids=self.job["train_ids"])
        return JobTrainingAccess(_ISSUER, self.job, rows, meta, atoms, definitions["view"], self.lineage())

    def lineage(self):
        j, b = self.job, binding()
        return {k: b[k] for k in ("study_version", "protocol_digest", "candidate_version")} | {
            **{k: j[k] for k in ("split_id", "fold_id", "method_id", "operating_point", "source_condition", "input_view",
                                "data_origin", "model_unit_id", "fit_job_id", "train_membership_digest")},
            "input_manifest_ref": self.snapshot.protocol["data_indices"][j["data_origin"]],
            "protocol_input_manifest_ref": b["input_manifest_ref"], "freeze_manifest_digest": self.snapshot.freeze_digest,
            "resource_manifest_digest": self.snapshot.resource_digest,
            "authorization_ref": self.authorization_ref(), "job_digest": self._job_digest}

    def authorization_ref(self):
        grant = self.snapshot._formal_grant
        return grant["ref"] if grant and self.stage != "SYNTHETIC_R04" else "AUTHORIZATION.json#" + self.stage

    def validate_model(self, model):
        if model.binding != self.lineage() or model.method_id != self.job["method_id"]:
            raise FitAuthorizationError("MODEL_JOB_FOLD_OR_LINEAGE_MISMATCH")
        wanted = self.job["train_ids"] if self.job["fit_job_id"] else []
        if model.fit["train_ids"] != wanted or not model.fit.get("freeze_time"):
            raise FitAuthorizationError("MODEL_TRAIN_OR_FREEZE_MISMATCH")
        if model.encoder and (model.encoder["train_ids"] != self.job["train_ids"] or model.encoder["fold_id"] != self.job["fold_id"]):
            raise FitAuthorizationError("ENCODER_CROSS_FOLD_MISMATCH")

    def freeze_model(self, model_path):
        if self.phase != "TRAIN_OPEN":
            raise FitAuthorizationError("MODEL_FREEZE_OUT_OF_ORDER")
        model = load_model(model_path)
        self.validate_model(model)
        created = datetime.fromisoformat(model.fit["freeze_time"])
        train_opened = datetime.fromisoformat(next(e["utc"] for e in self.events if e["event"] == "TRAIN_READY"))
        if not train_opened <= created <= datetime.now(timezone.utc):
            raise FitAuthorizationError("MODEL_FREEZE_TIME_OUTSIDE_ACTUAL_TRAIN_AND_SAVE_INTERVAL")
        self.receipt = {"model_id": model.model_id, "model_path": str(Path(model_path).resolve()),
                        "sha256": file_digest(model_path), "saved_and_loaded_at": datetime.now(timezone.utc).isoformat(),
                        "job_digest": self._job_digest}
        self.phase = "MODEL_FROZEN"
        self.event("MODEL_SAVED_LOADED_FROZEN", **self.receipt)
        return model

    def open_test(self, model):
        self.authorize()
        if self.phase != "MODEL_FROZEN":
            raise FitAuthorizationError("OUTER_TEST_BEFORE_MODEL_FREEZE")
        self.validate_model(model)
        if file_digest(self.receipt["model_path"]) != self.receipt["sha256"]:
            raise FitAuthorizationError("FROZEN_MODEL_CHANGED")
        self.phase = "TEST_OPEN"
        entries = self._read(self.snapshot.protocol["data_indices"][self.job["data_origin"]], "OPEN_METADATA_ONLY_TEST_INDEX")
        return {oid: self._read(entries[oid]["features"], "OPEN_OUTER_TEST_FEATURE")["features"]
                for oid in self.job["outer_test_ids"]}

    def close_predictions(self, rows):
        if self.phase not in ("MODEL_FROZEN", "TEST_OPEN"):
            raise FitAuthorizationError("PREDICTION_CLOSURE_OUT_OF_ORDER")
        if [r["opaque_id"] for r in rows] != self.job["outer_test_ids"] or any(r.get("model_unit_id") != self.job["model_unit_id"] for r in rows):
            raise ValueError("PREDICTION_UNIT_RECONCILIATION_FAILED")
        self.phase = "PREDICTIONS_CLOSED"
        self.event("PREDICTIONS_CLOSED_AND_RECONCILED", n=len(rows), predictions_digest=digest(rows))

    def evaluation(self):
        if self.phase != "PREDICTIONS_CLOSED":
            raise FitAuthorizationError("LABEL_JOIN_BEFORE_PREDICTION_CLOSURE")
        entries = self._read(self.snapshot.protocol["data_indices"][self.job["data_origin"]], "OPEN_METADATA_ONLY_EVALUATION_INDEX")
        self.phase = "EVALUATION_OPEN"
        return {oid: self._read(entries[oid]["evaluation"], "OPEN_OUTER_EVALUATION_LABEL") for oid in self.job["outer_test_ids"]}


def formal_access(request, context):
    if type(context) is not JobContext or context not in _CONTEXTS:
        raise FitAuthorizationError("FORMAL_REQUEST_REQUIRES_VERIFIED_CONTEXT")
    j, s = context.job, context.snapshot
    expected = {"stage": j["authorization_stage"], "authorization_record_ref": context.authorization_ref(),
        "freeze_manifest_ref": "FREEZE_MANIFEST.json#" + s.freeze_digest,
        "resource_manifest_ref": "RESOURCE_MANIFEST.json#" + s.resource_digest,
        "expected_fit_job_ref": "expected_fit_jobs.jsonl#" + str(j["fit_job_id"]),
        **{k: j[k] for k in ("protocol_digest", "split_id", "fold_id", "method_id", "operating_point", "source_condition", "input_view")},
        "train_membership_ref": "SPLIT_MANIFEST.json#" + j["fold_id"] + ":" + j["train_membership_digest"]}
    if vars(request) != expected or j not in s.models or not j["fit_job_id"] or j["reuse_model_unit_id"]:
        raise FitAuthorizationError("FORMAL_REQUEST_JOB_BINDING_MISMATCH")
    context.authorize()  # stage denial propagates; never FAILED_FIT
    return context.train()
