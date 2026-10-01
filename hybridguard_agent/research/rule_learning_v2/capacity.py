"""Explicit seven-clause experiment profile; frozen six-clause kernels stay intact."""
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from itertools import combinations

from ..rule_learning.models import RuleModel

EXPERIMENT = "semantic-capacity-six-vs-seven-v1"
STUDY = "rule-semantics-capacity-v1"
PHASE = "RSR_CAPACITY_COMPARISON"
PROFILE = {"profile_id": "W0_CAPACITY_7_V1", "max_clauses": 7,
           "max_complexity": 14, "max_additions": 7, "max_literals": 12,
           "max_distinct_atoms": 12, "max_clauses_per_family": 2}


def apply_capacity(problem):
    """Only capacity controls change; support, scoring, ties and data stay fixed."""
    problem.search = deepcopy(problem.search)
    problem.grammar = deepcopy(problem.grammar)
    problem.search["constraints"]["max_clauses"] = PROFILE["max_clauses"]
    problem.search["constraints"]["max_complexity_primary"] = PROFILE["max_complexity"]
    problem.search["algorithms"]["GREEDY_OR"]["max_additions"] = PROFILE["max_additions"]
    problem.grammar["composition"]["max_selected_clauses"] = PROFILE["max_clauses"]
    return problem


@dataclass(frozen=True)
class CapacityRuleModel(RuleModel):
    """R03 structural checks with a separate schema and explicit capacity identity.

    The base validator is preserved verbatim except its schema and capacity
    branches. This avoids widening the acceptance of existing RuleModel files.
    Serialization and immutable-content checking are inherited unchanged.
    """
    schema_version: str = "rsr-capacity-rule-model-v1"

    def __post_init__(self):
        expected = {"experiment_id": EXPERIMENT, "study_version": STUDY, "phase": PHASE,
                    "capacity_profile": PROFILE["profile_id"]}
        if (any(self.binding.get(k) != v for k, v in expected.items())
                or self.method_id not in ("GREEDY_SEMANTIC_V2", "R_KEEP_SWAP_V2")
                or self.fit.get("capacity_profile") != PROFILE
                or self.view.get("capacity_profile") != PROFILE):
            raise ValueError("EXPLICIT_CAPACITY_MODEL_IDENTITY_REQUIRED")

        if self.schema_version != "rsr-capacity-rule-model-v1" or self.status not in ("FITTED", "FIXED", "EMPTY_MODEL", "FAILED"):
            raise ValueError("INVALID_MODEL_SCHEMA_OR_STATUS")
        ids = [a.atom_id for a in self.atoms]
        if len(ids) != len(set(ids)) or len({c.id for c in self.clauses}) != len(self.clauses):
            raise ValueError("DUPLICATE_MODEL_ATOM_OR_CLAUSE")
        if any(l.atom_id not in ids for c in self.clauses for l in c.literals):
            raise ValueError("UNBOUND_MODEL_LITERAL")
        if self.status in ("FAILED", "EMPTY_MODEL") and (self.clauses or self.constant):
            raise ValueError("NONEXECUTABLE_MODEL_HAS_RULES")
        if self.status in ("FITTED", "FIXED") and not self.clauses and self.constant is None:
            raise ValueError("EMPTY_IS_NOT_ALWAYS_NO_ALERT")
        if self.constant is not None and (self.status != "FIXED" or self.clauses or self.constant not in ("NO_ALERT", "INSUFFICIENT_EVIDENCE")):
            raise ValueError("INVALID_CONSTANT_REFERENCE")
        if set(ids) != {l.atom_id for c in self.clauses for l in c.literals}:
            raise ValueError("MODEL_ATOMS_MUST_EQUAL_SELECTED_DEPENDENCIES")
        atom_index = {a.atom_id: a for a in self.atoms}
        signs, families = defaultdict(set), Counter()
        for c in self.clauses:
            fs = {atom_index[l.atom_id].family for l in c.literals}
            if len(fs) != len(c.literals):
                raise ValueError("SAME_FAMILY_AND_FORBIDDEN")
            families.update(fs)
            for l in c.literals:
                signs[l.atom_id].add(l.polarity)
        if any(len(s) > 1 for s in signs.values()):
            raise ValueError("MODEL_OPPOSITE_POLARITIES_FORBIDDEN")
        if any(set(a.literals) <= set(b.literals) or set(b.literals) <= set(a.literals) for a, b in combinations(self.clauses, 2)):
            raise ValueError("MODEL_SUBSUMED_CLAUSES_FORBIDDEN")
        if self.status == "FITTED":
            maximum_length = 2 if self.method_id == "FINITE_IP_DNF2" else 1
            maximum_cost = PROFILE["max_complexity"]
            if (len(self.clauses) > PROFILE["max_clauses"] or len(ids) > 12 or sum(len(c.literals) for c in self.clauses) > 12
                    or sum(c.cost for c in self.clauses) > maximum_cost or any(v > 2 for v in families.values())
                    or any(len(c.literals) > maximum_length for c in self.clauses)):
                raise ValueError("FITTED_MODEL_EXCEEDS_REGISTERED_CAPACITY")
        object.__setattr__(self, "_frozen_content", self._content())

    @property
    def model_id(self):
        return "rsr-capacity-" + super().model_id.removeprefix("r03-")
