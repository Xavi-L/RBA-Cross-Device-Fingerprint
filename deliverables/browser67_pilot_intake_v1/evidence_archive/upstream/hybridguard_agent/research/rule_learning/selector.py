"""R01 finite-pool selectors. All statistics are exact-own-train operations."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from itertools import combinations
import math
import time

from .access import authorize
from .contracts import PHASES, binding, contract, logic, state
from .models import Clause, Literal, RuleModel, complexity
from .predictor import clause_state


@dataclass
class FitResult:
    model: RuleModel
    trace: list
    support: dict
    candidate_manifest: list


def compatible(clauses, atoms, method, grammar, search):
    if not clauses:
        return True
    comp = complexity(clauses, atoms)
    limits = search["constraints"]
    if (comp["clauses"] > limits["max_clauses"] or comp["literal_occurrences"] > limits["max_literals"]
            or comp["distinct_atoms"] > grammar["composition"]["max_distinct_atoms"]
            or comp["objective_complexity"] > limits["max_complexity_extension" if method == "FINITE_IP_DNF2" else "max_complexity_primary"]):
        return False
    families = {a.atom_id: a.family for a in atoms}
    signs, counts = defaultdict(set), Counter()
    for c in clauses:
        for l in c.literals:
            signs[l.atom_id].add(l.polarity)
        counts.update({families[l.atom_id] for l in c.literals})
    if any(len(v) > 1 for v in signs.values()) or any(n > grammar["composition"]["max_clauses_per_family"] for n in counts.values()):
        return False
    return not any(set(a.literals) <= set(b.literals) or set(b.literals) <= set(a.literals) for a, b in combinations(clauses, 2))


class TrainProblem:
    def __init__(self, access, batch, method, operating_point, deadline=math.inf):
        authorize(access, batch, "combination_selection")
        self.search, self.grammar = contract("learning_search_space"), contract("candidate_grammar")
        if method not in ("GREEDY_OR", "FINITE_IP_OR", "FINITE_IP_DNF2"):
            raise ValueError("UNREGISTERED_SELECTOR")
        points = {p["id"]: p["alpha"] for p in self.search["operating_points"]}
        if operating_point not in points:
            raise ValueError("UNREGISTERED_OPERATING_POINT")
        self.method, self.operating_point = method, operating_point
        self.deadline = deadline
        self.access, self.ids, self.rows = access, batch.ids, batch.records
        self.atoms = tuple(sorted(access.atoms, key=lambda a: a.atom_id))
        if access.view["kind"] in ("RAW_CORE", "RAW_SINGLE_SURFACE") or any(a.atom_id.startswith("UNFITTED_CONTROL:") for a in self.atoms):
            raise ValueError("SOURCE_PROJECTION_AND_TRAIN_ENCODER_REQUIRED_BEFORE_SELECTOR")
        self.meta = access.training_metadata(batch)
        self.phase_indices = {phase: [i for i, oid in enumerate(self.ids) if self.meta[oid]["phase"] == phase] for phase in PHASES}
        self.triplets = defaultdict(dict)
        for i, oid in enumerate(self.ids):
            m = self.meta[oid]
            if m["supervised_label"] != int(m["phase"] == "attack"):
                raise ValueError("LABEL_AND_ADMITTED_PHASE_DISAGREE")
            key = (m["bundle_id"], m["triplet_id"])
            if m["phase"] in self.triplets[key]:
                raise ValueError("DUPLICATE_TRAIN_TRIPLET_PHASE")
            self.triplets[key][m["phase"]] = i
        if not self.triplets or any(set(t) != set(PHASES) for t in self.triplets.values()):
            raise ValueError("TRAIN_REQUIRES_COMPLETE_ADMITTED_TRIPLETS")
        for trio in self.triplets.values():
            if len({(self.meta[self.ids[i]]["config_id"], self.meta[self.ids[i]]["environment_group_id"]) for i in trio.values()}) != 1:
                raise ValueError("TRIPLET_GROUP_METADATA_MISMATCH")
        self.clean = self.phase_indices["clean_pre"] + self.phase_indices["clean_post"]
        self.budget = math.floor(Fraction(str(points[operating_point])) * len(self.clean))
        self.weights = {}
        cfgs = defaultdict(lambda: defaultdict(list))
        for i in self.phase_indices["attack"]:
            m = self.meta[self.ids[i]]
            cfgs[m["config_id"]][m["environment_group_id"]].append(i)
        for envs in cfgs.values():
            for indices in envs.values():
                for i in indices:
                    self.weights[i] = Fraction(1, len(cfgs) * len(envs) * len(indices))
        self.penalty = Fraction(str(self.search["objective"]["lambda"]))
        self.support, self.states, self.manifest = {}, {}, []
        self.candidates = self._pool()

    def _states(self, clause):
        result = []
        for row in self.rows:
            try:
                result.append(clause_state(clause, row))
            except (ValueError, KeyError):
                result.append(None)
        return result

    def _support(self, clause, states):
        complete, triggered = [], []
        for key, trio in self.triplets.items():
            if all(states[i] in ("T", "F") for i in trio.values()):
                complete.append(key)
                if states[trio["attack"]] == "T":
                    triggered.append(key)
        positive_meta = [self.meta[self.ids[self.triplets[t]["attack"]]] for t in triggered]
        rec = {"triplets": len(complete), "true_attack_triplets": len(triggered),
               "bundles": len({m["bundle_id"] for m in positive_meta}),
               "environments": len({m["environment_group_id"] for m in positive_meta}),
               "configurations": len({m["config_id"] for m in positive_meta}),
               "complete_triplet_ids": [list(k) for k in complete], "true_attack_triplet_ids": [list(k) for k in triggered],
               "phase_availability": {}, "train_ids": list(self.ids), "statistics_scope": "TRAIN_FOLD_ONLY"}
        for phase, indices in self.phase_indices.items():
            counts = Counter(states[i] or "FAILED" for i in indices)
            rec["phase_availability"][phase] = {"expected": len(indices), "defined": counts["T"] + counts["F"],
                                               **{s: counts[s] for s in ("T", "F", "U", "FAILED")}}
        s = self.search["support"]
        rec["eligible"] = (rec["triplets"] >= s["minimum_available_triplets"]
            and rec["true_attack_triplets"] >= s["minimum_true_attack_triplets_per_literal_or_clause"]
            and rec["bundles"] >= s["minimum_support_bundles"] and rec["environments"] >= s["minimum_support_environments"])
        return rec

    def _pool(self):
        literals = [Literal(a.atom_id, p) for a in self.atoms for p in sorted(self.grammar["literal"]["polarity_choices"])]
        families = {a.atom_id: a.family for a in self.atoms}
        clauses = [Clause((l,)) for l in literals]
        cap = self.grammar["composition"]["max_candidate_clauses"]
        if self.method == "FINITE_IP_DNF2":
            for a, b in combinations(literals, 2):
                if a.atom_id != b.atom_id and families[a.atom_id] != families[b.atom_id]:
                    if time.monotonic() >= self.deadline:
                        raise TimeoutError("TIME_LIMIT_NO_INCUMBENT_DURING_CANDIDATE_GENERATION")
                    clauses.append(Clause(tuple(sorted((a, b)))))
                    if len(clauses) > cap:
                        raise OverflowError("BRANCH_NOT_RUN_SEARCH_SPACE_EXCEEDS_CAP_NO_LABEL_RANK_TRUNCATION")
        if len(clauses) > cap:
            raise OverflowError("BRANCH_NOT_RUN_SEARCH_SPACE_EXCEEDS_CAP_NO_LABEL_RANK_TRUNCATION")
        eligible_literals = set()
        # Both literal support and compound support are enforced, without ranking.
        for c in clauses:
            if time.monotonic() >= self.deadline:
                raise TimeoutError("TIME_LIMIT_NO_INCUMBENT_DURING_SUPPORT")
            st = self._states(c)
            self.states[c.id] = st
            self.support[c.id] = self._support(c, st)
            if len(c.literals) == 1 and self.support[c.id]["eligible"]:
                eligible_literals.add(c.literals[0])
        admitted = []
        for c in sorted(clauses, key=lambda c: c.id):
            reasons = []
            if not self.support[c.id]["eligible"] or not all(l in eligible_literals for l in c.literals):
                reasons.append("INSUFFICIENT_TRAIN_SUPPORT")
            if None in self.states[c.id]:
                # A selected failed atom is forbidden, even inside an F AND.
                reasons.append("TRAIN_EXECUTION_FAILURE")
            self.manifest.append({"clause_id": c.id, "eligible": not reasons, "reasons": reasons,
                                  "literal_ids": [l.id for l in c.literals]})
            if not reasons:
                admitted.append(c)
        return tuple(admitted)

    def score(self, clauses):
        clauses = tuple(sorted(clauses, key=lambda c: c.id))
        states = [logic((self.states[c.id][i] for c in clauses), "OR") if clauses else "EMPTY_MODEL" for i in range(len(self.ids))]
        macro = sum((self.weights[i] for i in self.weights if states[i] == "T"), Fraction())
        cost = sum(c.cost for c in clauses)
        coverage = {p: Fraction(sum(states[i] in ("T", "F") for i in idx), len(idx)) for p, idx in self.phase_indices.items()}
        alarms = sum(states[i] == "T" for i in self.clean)
        structural = compatible(clauses, self.atoms, self.method, self.grammar, self.search)
        feasible = bool(clauses) and structural and alarms <= self.budget and min(coverage.values()) >= Fraction(str(self.search["constraints"]["min_decision_coverage"]))
        return {"objective": macro - self.penalty * cost, "macro_tpr": macro, "clean_alarms": alarms,
                "coverage": coverage, "minimum_coverage": min(coverage.values()), "complexity": cost,
                "feasible": feasible, "partial_feasible": structural and alarms <= self.budget,
                "clause_ids": tuple(c.id for c in clauses), "states": states}


def better(a, b):
    if b is None:
        return True
    if abs(a["objective"] - b["objective"]) > Fraction(1, 10**12):
        return a["objective"] > b["objective"]
    for key, maximize in (("macro_tpr", True), ("clean_alarms", False), ("minimum_coverage", True), ("complexity", False)):
        if a[key] != b[key]:
            return a[key] > b[key] if maximize else a[key] < b[key]
    return a["clause_ids"] < b["clause_ids"]


def json_score(score):
    def convert(v):
        if isinstance(v, Fraction):
            return {"numerator": v.numerator, "denominator": v.denominator, "value": float(v)}
        if isinstance(v, dict):
            return {k: convert(x) for k, x in v.items()}
        return v
    return convert(score)


def greedy(problem, deadline):
    selected, best, best_score, trace = (), (), None, []
    current = problem.score(())
    stop = "max_additions"
    for _ in range(problem.search["algorithms"]["GREEDY_OR"]["max_additions"]):
        if time.monotonic() >= deadline:
            stop = "time_limit"
            break
        choice, score = None, None
        for c in problem.candidates:
            if time.monotonic() >= deadline:
                stop = "time_limit"
                break
            if c in selected:
                continue
            test = tuple(sorted(selected + (c,), key=lambda x: x.id))
            s = problem.score(test)
            if s["partial_feasible"] and s["objective"] - current["objective"] > Fraction(1, 10**12) and better(s, score):
                choice, score = test, s
        if stop == "time_limit":
            break
        if choice is None:
            stop = "no_positive_objective_improvement"
            break
        selected, current = choice, score
        trace.append({"operation": "ADD", "selected": list(score["clause_ids"]), "score": json_score(score)})
        if score["feasible"] and better(score, best_score):
            best, best_score = choice, score
    # R01 specifies one pass in lexical order, only over the best feasible visit.
    if best:
        for c in tuple(sorted(best, key=lambda c: c.id)):
            if time.monotonic() >= deadline:
                stop = "time_limit"
                break
            candidate = tuple(x for x in best if x != c)
            s = problem.score(candidate)
            if s["feasible"] and s["objective"] >= best_score["objective"]:
                best, best_score = candidate, s
                trace.append({"operation": "PRUNE", "removed": c.id, "score": json_score(s)})
    if stop == "time_limit":
        status = "TIME_LIMIT_FEASIBLE" if best else "FAILED_FIT"
    else:
        status = "HEURISTIC_FEASIBLE" if best else "HEURISTIC_NO_FEASIBLE_MODEL_FOUND_EMPTY_MODEL"
    return best, {"status": status, "stop": stop, "optimality": "NONE", "infeasibility_proved": False,
                  "best_bound": None, "gap": None, "solver": "R03_DETERMINISTIC_GREEDY_V1"}, trace


def fit(access, batch, method="GREEDY_OR", operating_point="OP05"):
    # Authorization failures must never be reclassified as FAILED_FIT.
    authorize(access, batch, "combination_selection")
    access.assert_method(method, operating_point)
    start = time.monotonic()
    search = contract("learning_search_space")
    if method not in ("GREEDY_OR", "FINITE_IP_OR", "FINITE_IP_DNF2"):
        raise ValueError("UNREGISTERED_SELECTOR")
    deadline = start + search["algorithms"][method]["time_limit_seconds_per_fit"]
    problem, selected, trace = None, (), []
    try:
        problem = TrainProblem(access, batch, method, operating_point, deadline)
        authorize(access, batch, "pruning")
        if not problem.candidates:
            outcome = {"status": "EMPTY_CANDIDATE_POOL", "best_bound": None, "gap": None, "infeasibility_proved": False}
        elif method == "GREEDY_OR":
            selected, outcome, trace = greedy(problem, deadline)
        else:
            from .solver import solve_finite_ip
            selected, outcome, trace = solve_finite_ip(problem, deadline)
        if selected and not problem.score(selected)["feasible"]:
            raise ValueError("INCUMBENT_FAILED_INDEPENDENT_CONSTRAINT_CHECK")
        if outcome["status"] == "TIME_LIMIT_FEASIBLE" and not selected:
            raise ValueError("TIME_LIMIT_WITHOUT_INCUMBENT_IS_FAILED_FIT")
    except OverflowError as exc:
        outcome = {"status": str(exc), "best_bound": None, "gap": None, "infeasibility_proved": False}
    except Exception as exc:
        from .access import FitAuthorizationError
        if isinstance(exc, FitAuthorizationError):
            raise
        selected = ()
        outcome = {"status": "FAILED_FIT", "reason": type(exc).__name__ + ":" + str(exc), "best_bound": None, "gap": None, "infeasibility_proved": False}
    failed = outcome["status"].startswith(("FAILED", "NOT_RUN", "BRANCH_NOT_RUN"))
    status = "FAILED" if failed else "FITTED" if selected else "EMPTY_MODEL"
    atom_ids = {l.atom_id for c in selected for l in c.literals}
    metadata = access.model_binding(operating_point)
    audit = dict(outcome, train_ids=list(batch.ids), train_expected_n=len(batch.ids), train_consumed_n=len(batch.records),
                 **access.fit_context(), elapsed_seconds=time.monotonic() - start,
                 freeze_time=datetime.now(timezone.utc).isoformat(),
                 candidate_pool_size=len(problem.candidates) if problem else None,
                 registered_clause_count=len(problem.manifest) if problem else None)
    if problem:
        audit.update(clean_budget_count=problem.budget, clean_denominator=len(problem.clean),
                     stratum_denominators={p: len(i) for p, i in problem.phase_indices.items()},
                     training_result=json_score(problem.score(selected)),
                     support_scope="COMPLETE_ADMITTED_TRAIN_TRIPLETS_ONLY")
    model = RuleModel(method, status, tuple(selected), tuple(a for a in access.atoms if a.atom_id in atom_ids),
                      metadata, access.view, audit, encoder=access.encoder)
    return FitResult(model, trace, problem.support if problem else {}, problem.manifest if problem else [])


def selection_rows(result):
    """Flat explanation/provenance export; no new support calculation or fitting."""
    model = result.model
    atoms = {a.atom_id: a for a in model.atoms}
    rows = []
    for clause in model.clauses:
        support = result.support[clause.id]
        clause_sources = sorted({s for l in clause.literals for s in atoms[l.atom_id].sources})
        for literal in clause.literals:
            a = atoms[literal.atom_id]
            rows.append({**model.binding, "model_id": model.model_id, "clause_id": clause.id,
                "atom_id": a.atom_id, "polarity": literal.polarity, "source_groups": list(a.sources),
                "clause_source_union": clause_sources, "canonical_identity": a.atom_id,
                "aliases": list(a.aliases), "orientation": a.orientation, "provenance": a.provenance,
                "train_id_manifest": model.fit["train_ids"], "support_triplets": support["triplets"],
                "support_bundles": support["bundles"], "support_environments": support["environments"],
                "objective": model.fit["training_result"]["objective"], "solver_status": model.fit["status"],
                "best_bound": model.fit.get("best_bound"), "gap": model.fit.get("gap"),
                "freeze_time": model.fit["freeze_time"]})
    return rows
