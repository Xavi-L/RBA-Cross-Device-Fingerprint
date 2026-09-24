"""Versioned finite rule sets; no training or evaluator is invoked on load."""
from dataclasses import asdict, dataclass, field
from collections import Counter, defaultdict
from itertools import combinations
import hashlib
import json
from pathlib import Path


@dataclass(frozen=True)
class Atom:
    atom_id: str
    family: str
    surfaces: tuple[str, ...]
    sources: tuple[str, ...]
    aliases: tuple[str, ...]
    orientation: str = "CANONICAL_DEVIATION"
    provenance: dict = field(default_factory=dict)


@dataclass(frozen=True, order=True)
class Literal:
    atom_id: str
    polarity: str = "POSITIVE"

    def __post_init__(self):
        if self.polarity not in ("POSITIVE", "NEGATIVE"):
            raise ValueError("INVALID_LITERAL_POLARITY")

    @property
    def id(self):
        return self.atom_id + ":" + self.polarity


@dataclass(frozen=True)
class Clause:
    literals: tuple[Literal, ...]

    def __post_init__(self):
        if not 1 <= len(self.literals) <= 2 or len({x.atom_id for x in self.literals}) != len(self.literals):
            raise ValueError("INVALID_CLAUSE_GRAMMAR")
        if self.literals != tuple(sorted(self.literals)):
            raise ValueError("CLAUSE_NOT_CANONICALLY_SORTED")

    @property
    def id(self):
        return " & ".join(x.id for x in self.literals)

    @property
    def cost(self):
        return 1 + len(self.literals)


def complexity(clauses, atoms):
    selected = {lit.atom_id for c in clauses for lit in c.literals}
    metadata = {a.atom_id: a for a in atoms}
    return {"distinct_atoms": len(selected), "clauses": len(clauses),
            "literal_occurrences": sum(len(c.literals) for c in clauses),
            "objective_complexity": sum(c.cost for c in clauses),
            "distinct_families": len({metadata[a].family for a in selected}),
            "distinct_surfaces": len({s for a in selected for s in metadata[a].surfaces}),
            "source_union": sorted({s for a in selected for s in metadata[a].sources})}


@dataclass(frozen=True)
class RuleModel:
    method_id: str
    status: str
    clauses: tuple[Clause, ...]
    atoms: tuple[Atom, ...]
    binding: dict
    view: dict
    fit: dict
    encoder: dict = field(default_factory=dict)
    constant: str | None = None
    schema_version: str = "r03-rule-model-v1"

    def __post_init__(self):
        if self.schema_version != "r03-rule-model-v1" or self.status not in ("FITTED", "FIXED", "EMPTY_MODEL", "FAILED"):
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
            maximum_cost = 18 if maximum_length == 2 else 12
            if (len(self.clauses) > 6 or len(ids) > 12 or sum(len(c.literals) for c in self.clauses) > 12
                    or sum(c.cost for c in self.clauses) > maximum_cost or any(v > 2 for v in families.values())
                    or any(len(c.literals) > maximum_length for c in self.clauses)):
                raise ValueError("FITTED_MODEL_EXCEEDS_R01_BUDGET")
        object.__setattr__(self, "_frozen_content", self._content())

    def _content(self):
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def model_id(self):
        raw = self._content()
        if raw != self._frozen_content:
            raise ValueError("FROZEN_MODEL_CONTENT_CHANGED")
        return "r03-" + hashlib.sha256(raw.encode()).hexdigest()[:24]

    def to_dict(self):
        return dict(asdict(self), model_id=self.model_id, complexity=complexity(self.clauses, self.atoms))

    @classmethod
    def from_dict(cls, raw):
        d = dict(raw)
        expected, reported = d.pop("model_id"), d.pop("complexity")
        d["clauses"] = tuple(Clause(tuple(Literal(**l) for l in c["literals"])) for c in d["clauses"])
        d["atoms"] = tuple(Atom(**dict(a, surfaces=tuple(a["surfaces"]), sources=tuple(a["sources"]), aliases=tuple(a["aliases"]))) for a in d["atoms"])
        result = cls(**d)
        if expected != result.model_id or reported != complexity(result.clauses, result.atoms):
            raise ValueError("MODEL_BINDING_OR_COMPLEXITY_MISMATCH")
        return result


def save_model(model, path):
    with Path(path).open("x") as stream:
        json.dump(model.to_dict(), stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def load_model(path):
    return RuleModel.from_dict(json.loads(Path(path).read_text()))
