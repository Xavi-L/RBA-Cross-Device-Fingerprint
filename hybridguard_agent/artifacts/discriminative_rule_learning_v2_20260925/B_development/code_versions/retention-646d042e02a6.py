"""R_KEEP_V1: an explicit training preference, not the old sparse objective."""
import time
from fractions import Fraction

from hybridguard_agent.research.rule_learning.selector import compatible, json_score

VERSION = 'R_KEEP_V1'
GROUP_VERSION = 'SEMANTIC_SIGNAL_GROUPS_V1'


def signal_group(atom):
    """Metadata/semantics only. Grouping does NOT assert predicate equivalence."""
    if atom.provenance.get('signal_group'):
        return atom.provenance['signal_group']
    explicit = {
        'DEVIATION:OFFDER-UA-001': 'web_client_identity',  # Native is only a validity gate.
        'DEVIATION:OFFDER-UA-002': 'web_client_identity',
        'DEVIATION:P3-UA-DEFAULT': 'web_client_identity',
        'DEVIATION:P3-UA-SETTINGS': 'web_client_identity',
        'CAT:NW-006': 'web_client_identity', 'CAT:WVWEB-004': 'web_client_identity',
        'DEVIATION:NW-001': 'device_model_alignment',
        'DEVIATION:NVW-001': 'device_model_alignment',
        'DEVIATION:NW-002': 'os_version_alignment',
        'DEVIATION:NVW-002': 'os_version_alignment',
        'DEVIATION:NW-005': 'graphics_identity',
        'DEVIATION:P3-SCREEN-APP': 'display_geometry',
    }
    if atom.atom_id in explicit:
        return explicit[atom.atom_id]
    refs = atom.provenance.get('field_refs', [])
    field = atom.provenance.get('field')
    if field:
        refs = [field]
    if not refs:
        raise ValueError('UNREGISTERED_SIGNAL_GROUP:' + atom.atom_id)
    joined = ' '.join(refs)
    if any(s in joined for s in ('navigator_layer.user_agent', 'navigator_layer.platform',
                                'kernel_container_layer.default_ua_native', 'webview_settings_layer.settings_user_agent')):
        return 'web_client_identity'
    if 'memory' in joined: return 'memory_capacity'
    if 'hardware_concurrency' in joined: return 'web_cpu_capacity'
    if any(s in joined for s in ('locale_timezone_layer.native_locale', 'locale_timezone_layer.native_language',
                                'navigator_layer.language')): return 'language_preferences'
    if 'timezone' in joined: return 'timezone_semantics'
    if any(s in joined for s in ('plugins_count', 'mime_types_count')): return 'plugin_capability'
    if 'webdriver' in joined: return 'automation_flag'
    if 'sensor_matrix_layer' in joined: return 'native_sensor_structure'
    if 'graphics_layer' in joined: return 'graphics_identity'
    if 'screen' in joined or 'device_pixel_ratio' in joined: return 'display_geometry'
    if 'jsbridge_injected' in joined: return 'host_bridge'
    if 'is_debuggable' in joined or 'is_cleartext_traffic_permitted' in joined: return 'host_debug_cleartext'
    if 'webview_provider' in joined: return 'host_provider_version'
    # All thresholds/categories of the same field share this key. Catalog
    # predicates with multiple operands use their registered semantic family.
    return 'field:' + refs[0] if len(refs) == 1 else 'semantic_family:' + atom.family


def coverage_pairs(problem, selected, groups):
    return {(groups[c.literals[0].atom_id], i) for c in selected
            for i in problem.weights if problem.states[c.id][i] == 'T'}


def diversity(problem, selected, groups):
    return sum((problem.weights[i] for _, i in coverage_pairs(problem, selected, groups)), Fraction())


def exclusion_reasons(problem, selected, candidate, groups):
    proposal = tuple(sorted(selected + (candidate,), key=lambda c: c.id))
    score = problem.score(proposal)
    before = problem.score(selected)
    reasons = []
    if not compatible(proposal, problem.atoms, problem.method, problem.grammar, problem.search):
        reasons.append('STRUCTURE_OR_FAMILY_LIMIT')
    if score['clean_alarms'] > problem.budget: reasons.append('SET_CLEAN_BUDGET')
    if score['minimum_coverage'] < Fraction(str(problem.search['constraints']['min_decision_coverage'])):
        reasons.append('PHASE_DECISION_COVERAGE')
    if any(before['states'][i] == 'T' and score['states'][i] != 'T' for i in problem.weights):
        reasons.append('ATTACK_DETECTION_LOSS')
    increment = diversity(problem, proposal, groups) - diversity(problem, selected, groups)
    if increment <= 0: reasons.append('NO_NEW_SIGNAL_COVERAGE')
    return reasons, score, increment


def retain(problem, initial, groups, deadline):
    """One retention stage using only the problem's train members/statistics."""
    if set(groups) != {a.atom_id for a in problem.atoms}:
        raise ValueError('EXACT_CANDIDATE_SIGNAL_GROUPS_REQUIRED')
    if any(c not in problem.candidates for c in initial):
        raise ValueError('INITIAL_RULE_OUTSIDE_ELIGIBLE_TRAIN_POOL')
    selected = tuple(sorted(initial, key=lambda c: c.id))
    if selected and not problem.score(selected)['feasible']:
        raise ValueError('INITIAL_RULE_SET_NOT_FEASIBLE')
    trace = []
    stop = 'NO_LEGAL_POSITIVE_SIGNAL_INCREMENT'
    while True:
        if time.monotonic() >= deadline:
            stop = 'TIME_LIMIT'; break
        current = problem.score(selected)
        choices = []
        for c in problem.candidates:
            if c in selected: continue
            if time.monotonic() >= deadline:
                stop = 'TIME_LIMIT'; break
            reasons, score, inc = exclusion_reasons(problem, selected, c, groups)
            if not reasons and score['feasible']:
                key = (-(score['macro_tpr'] - current['macro_tpr']), -inc,
                       score['clean_alarms'], score['complexity'], c.id)
                choices.append((key, c, score, inc))
        if stop == 'TIME_LIMIT': break
        if not choices:
            if len(selected) >= problem.search['constraints']['max_clauses']:
                stop = 'ORIGINAL_CLAUSE_LIMIT_REACHED'
            break
        _, c, score, inc = min(choices, key=lambda x: x[0])
        trace.append({'operation': 'RETAIN_SIGNAL', 'added': c.id,
                      'signal_group': groups[c.literals[0].atom_id],
                      'delta_macro_tpr': float(score['macro_tpr'] - current['macro_tpr']),
                      'delta_D': float(inc), 'D_after': float(diversity(problem, selected + (c,), groups)),
                      'score': {k:v for k,v in json_score(score).items() if k!='states'}})
        selected = tuple(sorted(selected + (c,), key=lambda c: c.id))
    return selected, {'status': 'RETENTION_FEASIBLE' if selected else 'RETENTION_EMPTY_MODEL',
                      'stop': stop, 'optimality': 'NONE', 'old_sparse_objective_still_optimized': False,
                      'new_generalization_guarantee': False,
                      'D_initial': float(diversity(problem, initial, groups)),
                      'D_final': float(diversity(problem, selected, groups))}, trace
