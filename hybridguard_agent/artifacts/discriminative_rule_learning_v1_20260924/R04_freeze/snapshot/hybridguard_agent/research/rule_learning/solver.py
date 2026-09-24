"""Finite binary MILP with exact alert unions and lexicographic refinement.

No restricted master, pricing, generated columns or paid fallback exists.
The 120 second deadline is shared by primary solve and every tie-break solve.
"""
from itertools import combinations
import math
import time


def solver_environment():
    try:
        import highspy
        import numpy
        return {"available": True, "solver": "HiGHS", "version": highspy.Highs().version(),
                "numpy": numpy.__version__, "threads": 1, "mip_rel_gap": 0.0,
                "mip_abs_gap": 0.0, "mip_feasibility_tolerance": 1e-9}
    except ImportError:
        return {"available": False, "solver": "HiGHS", "status": "NOT_RUN_SOLVER_UNAVAILABLE_NO_PAID_FALLBACK"}


def solve_finite_ip(problem, deadline):
    env = solver_environment()
    if not env["available"]:
        return (), dict(env, best_bound=None, gap=None, infeasibility_proved=False), []
    import highspy
    h = highspy.Highs()
    for name, value in {"output_flag": False, "threads": 1, "parallel": "off", "mip_rel_gap": 0.0,
                        "mip_abs_gap": 0.0, "random_seed": 20260924, "mip_feasibility_tolerance": 1e-9}.items():
        if h.setOptionValue(name, value) != highspy.HighsStatus.kOk:
            raise ValueError("SOLVER_OPTION_REJECTED:" + name)

    def binary(name):
        return h.addVariable(lb=0, ub=1, type=highspy.HighsVarType.kInteger, name=name)

    def expr(terms):
        return h.qsum(terms)

    candidates = problem.candidates
    z = [binary("clause_" + str(j)) for j in range(len(candidates))]
    h.addConstr(expr(z) >= 1)  # Empty is an explicit abstention, not an F classifier.
    limits = problem.search["constraints"]
    h.addConstr(expr(z) <= limits["max_clauses"])
    literals = expr(z[j] * len(c.literals) for j, c in enumerate(candidates))
    cost = expr(z[j] * c.cost for j, c in enumerate(candidates))
    h.addConstr(literals <= limits["max_literals"])
    h.addConstr(cost <= limits["max_complexity_extension" if problem.method == "FINITE_IP_DNF2" else "max_complexity_primary"])
    families = {a.atom_id: a.family for a in problem.atoms}
    for family in sorted(set(families.values())):
        h.addConstr(expr(z[j] for j, c in enumerate(candidates) if family in {families[l.atom_id] for l in c.literals}) <= 2)
    # Selected clauses may neither subsume each other nor reverse one atom.
    for counter, (j, k) in enumerate(combinations(range(len(candidates)), 2)):
        if counter % 1024 == 0 and time.monotonic() >= deadline:
            raise TimeoutError("TIME_LIMIT_NO_INCUMBENT_DURING_MILP_CONSTRUCTION")
        a, b = set(candidates[j].literals), set(candidates[k].literals)
        reversed_atom = any(x.atom_id == y.atom_id and x.polarity != y.polarity for x in a for y in b)
        if a <= b or b <= a or reversed_atom:
            h.addConstr(z[j] + z[k] <= 1)
    # max_literals=12 implies max_distinct_atoms<=12; no weaker surrogate used.
    alert, unknown, decided = [], [], []
    for i in range(len(problem.ids)):
        if time.monotonic() >= deadline:
            raise TimeoutError("TIME_LIMIT_NO_INCUMBENT_DURING_MILP_CONSTRUCTION")
        a, u, d = binary("alert_" + str(i)), binary("unknown_" + str(i)), binary("decided_" + str(i))
        for value, target in (("T", a), ("U", u)):
            members = [z[j] for j, c in enumerate(candidates) if problem.states[c.id][i] == value]
            h.addConstr(target <= expr(members))
            for member in members:
                h.addConstr(target >= member)
        h.addConstr(d >= a)
        h.addConstr(d >= 1 - u)
        h.addConstr(d <= a + 1 - u)
        alert.append(a); unknown.append(u); decided.append(d)
    clean = expr(alert[i] for i in problem.clean)
    h.addConstr(clean <= problem.budget)
    coverage_scale = math.lcm(*(len(v) for v in problem.phase_indices.values()))
    min_coverage = h.addVariable(lb=0, ub=coverage_scale, type=highspy.HighsVarType.kInteger, name="minimum_coverage_scaled")
    for indices in problem.phase_indices.values():
        defined = expr(decided[i] for i in indices)
        h.addConstr(defined >= math.ceil(len(indices) * limits["min_decision_coverage"] - 1e-12))
        h.addConstr(min_coverage <= defined * (coverage_scale // len(indices)))
    objective_scale = math.lcm(problem.penalty.denominator, *(w.denominator for w in problem.weights.values()))
    if objective_scale > 2**45:
        raise OverflowError("NOT_RUN_EXACT_OBJECTIVE_SCALING_EXCEEDS_FLOAT_INTEGER_RANGE")
    macro = expr(alert[i] * int(w * objective_scale) for i, w in problem.weights.items())
    primary = macro - cost * int(problem.penalty * objective_scale)
    objectives = [("primary_objective", primary), ("higher_MacroTPR", macro),
                  ("fewer_clean_alarms", -clean), ("higher_min_coverage", min_coverage),
                  ("lower_complexity", -cost)]
    objectives.extend(("lex:" + c.id, z[j]) for j, c in enumerate(candidates))
    trace, incumbent, primary_bound, primary_gap, primary_optimal = [], (), None, None, False
    lex_selected_cost, fixed_complexity = 0, None
    stop_status = "OPTIMAL_FINITE_POOL"
    for phase, objective in objectives:
        if phase.startswith("lex:") and lex_selected_cost == fixed_complexity:
            # Positive clause costs make all remaining z zero at fixed complexity.
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            stop_status = "TIME_LIMIT_FEASIBLE" if incumbent else "FAILED_FIT"
            break
        h.setOptionValue("time_limit", remaining)
        h.setObjective(objective, highspy.ObjSense.kMaximize)
        run_status = h.run()
        status = h.getModelStatus()
        info, solution = h.getInfo(), h.getSolution()
        candidate = ()
        if solution.value_valid:
            values = list(solution.col_value)
            if all(abs(values[int(v)] - round(values[int(v)])) <= 1e-7 for v in z):
                candidate = tuple(c for c, v in zip(candidates, z) if values[int(v)] > .5)
                if not candidate or not problem.score(candidate)["feasible"]:
                    candidate = ()
        if candidate:
            incumbent = candidate
        if phase == "primary_objective":
            primary_bound = info.mip_dual_bound / objective_scale if math.isfinite(info.mip_dual_bound) else None
            primary_gap = float(info.mip_gap) if math.isfinite(info.mip_gap) else None
            primary_optimal = status == highspy.HighsModelStatus.kOptimal
        trace.append({"phase": phase, "solver_model_status": status.name, "run_status": run_status.name,
                      "objective_integer": round(h.getObjectiveValue()) if candidate else None,
                      "incumbent_validated": bool(candidate), "node_count": info.mip_node_count})
        if status == highspy.HighsModelStatus.kTimeLimit:
            stop_status = "TIME_LIMIT_FEASIBLE" if incumbent else "FAILED_FIT"
            break
        if status == highspy.HighsModelStatus.kInfeasible and phase == "primary_objective":
            return (), dict(env, status="NO_FEASIBLE_MODEL_EMPTY_MODEL", infeasibility_proved=True,
                            optimality_scope="FINITE_SUPPORTED_POOL_ONLY", best_bound=None, gap=None), trace
        if run_status == highspy.HighsStatus.kError or status != highspy.HighsModelStatus.kOptimal or not candidate:
            return (), dict(env, status="FAILED_FIT", reason="SOLVER_ERROR_OR_INVALID_INCUMBENT:" + status.name,
                            best_bound=primary_bound, gap=primary_gap, infeasibility_proved=False), trace
        optimum = round(h.getObjectiveValue())
        # Every objective has integer coefficients/variables. Exact equality locks
        # each hierarchy level; do not perturb the primary objective with epsilon.
        h.addConstr(objective == optimum)
        if phase == "lower_complexity":
            fixed_complexity = -optimum
        if phase.startswith("lex:") and optimum == 1:
            lex_selected_cost += next(c.cost for c in candidates if "lex:" + c.id == phase)
    return incumbent, dict(env, status=stop_status, best_bound=primary_bound, gap=primary_gap,
        infeasibility_proved=False, primary_optimal=primary_optimal,
        tie_break_complete=stop_status == "OPTIMAL_FINITE_POOL", objective_integer_scale=objective_scale,
        optimality_scope="FINITE_SUPPORTED_POOL_ONLY", column_generation=False), trace
