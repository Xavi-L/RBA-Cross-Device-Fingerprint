"""Read-only exposed-material diagnosis and saved-prediction arithmetic; no fit."""
import argparse
from collections import Counter, defaultdict
import itertools

from hybridguard_agent.research.rule_learning.baselines import project_core, transform_numeric
from hybridguard_agent.research.rule_learning.contracts import ledger, state, negate, PHASES
from hybridguard_agent.research.rule_learning.models import load_model as load_v1_model
from hybridguard_agent.research.rule_learning.evaluation import evaluate
from .adapter import load_model, transform_current
from .common import *

ALERT = 'MANIPULATION_ALERT'
RAW_REF = 'hybridguard_agent/artifacts/formal_manipulation_v1_20260923/02_inputs/inference_inputs.jsonl'


def metadata():
    return {r['opaque_id']: r for r in lines(V1 / 'R02_matrix/evaluation_index.jsonl') if r['supervised_label'] is not None}


def raw_cache(ids):
    index = read(FROZEN / 'DATA_INDEX.json')
    return {i: read(FROZEN / index[i]['features'])['features'] for i in ids}


def baseline_jobs():
    return {'C0': [V1 / 'R05_primary/dispatch/jobs' / ('R05_PRIMARY__' + f['fold_id'] + '__GREEDY_OR__OP05__SRC-111__core') for f in folds()],
            'W0': [V1 / 'R07_representation/dispatch/jobs' / ('R07_SINGLE_SURFACE_REFIT__' + f['fold_id'] + '__GREEDY_OR__OP05__SRC-111__app_web67') for f in folds()]}


def saved_predictions(directories):
    rows, evidence = {}, []
    for directory in directories:
        predictions = lines(directory / 'predictions.jsonl')
        events = read(directory / 'access_log.json')
        closed = next(e for e in events if e['event'] == 'PREDICTIONS_CLOSED_AND_RECONCILED')
        model = load_v1_model(directory / 'model.json')
        for n, r in enumerate(predictions, 1):
            if r['opaque_id'] in rows or r['model_id'] != model.model_id:
                raise ValueError('SAVED_PREDICTION_DUPLICATE_OR_MODEL_MISMATCH')
            rows[r['opaque_id']] = dict(r, evidence_ref=relative(directory / 'predictions.jsonl') + f'#line={n}')
        evidence.append({'directory': relative(directory), 'n': len(predictions),
                         'closed_event': closed, 'model_id': model.model_id,
                         'selected': [c.id for c in model.clauses], 'complexity': model.to_dict()['complexity'],
                         'training_ref': relative(directory / 'training.json')})
    return rows, evidence


def posthoc_decision(a, b):
    if 'FAILED' in (a, b): return 'FAILED'
    if ALERT in (a, b): return ALERT
    if a == b == 'NO_ALERT': return 'NO_ALERT'
    return 'INSUFFICIENT_EVIDENCE'


def explicit_oof(name, rows, meta, role=ROLE):
    expected = sorted(meta)
    # Derived OOF identity is explicit; original predictions remain in their files.
    derived = [dict(rows[i], executed_model_id=rows[i].get('model_id'), executed_fold_id=rows[i].get('fold_id'),
                    model_id='OOF:' + name, fold_id='EXPLICIT_OOF_AGGREGATE', split_id='LOEO-v1') for i in expected]
    return evaluate(expected, derived, meta, evaluation_role=role)


def collision_groups(name, rows, meta, fold_id=None):
    columns = sorted(next(iter(rows.values())))
    groups = defaultdict(list)
    for i, row in rows.items():
        vector = tuple(state(row[n]) if row[n]['evaluation_status'] == 'OK' else 'FAILED' for n in columns)
        groups[vector].append(i)
    records = []
    for vector, ids in sorted(groups.items()):
        attack = [i for i in ids if meta[i]['supervised_label'] == 1]
        clean = [i for i in ids if meta[i]['supervised_label'] == 0]
        records.append({'representation': name, 'fold_id': fold_id, 'vector': vector, 'columns': columns,
                        'attack_ids': attack, 'clean_ids': clean, 'mixed_labels': bool(attack and clean),
                        'scope': 'FIXED_REPRESENTATION_EXPOSED_DEVELOPMENT_SEPARABILITY_NOT_GENERALIZATION_BOUND'})
    mixed = [r for r in records if r['mixed_labels']]
    return records, {'representation': name, 'fold_id': fold_id, 'input_atoms': len(columns),
                     'groups': len(records), 'mixed_groups': len(mixed),
                     'attacks_in_mixed_groups': sum(len(r['attack_ids']) for r in mixed),
                     'clean_in_mixed_groups': sum(len(r['clean_ids']) for r in mixed)}


def baseline_diagnosis():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = metadata(); ids = sorted(meta)
    raw = raw_cache(ids)
    payloads = {r['opaque_id']: r['payload'] for r in lines(ROOT / RAW_REF) if r['opaque_id'] in meta}
    base, evidence = {}, {}
    for name, dirs in baseline_jobs().items():
        base[name], evidence[name] = saved_predictions(dirs)
        if set(base[name]) != set(meta): raise ValueError('BASELINE_MUST_COVER_ALL_162_STAGES')
    posthoc = []
    for i in ids:
        c, w = base['C0'][i], base['W0'][i]
        if c['fold_id'] != w['fold_id']: raise ValueError('POSTHOC_MUST_MATCH_FOLD_AND_ID')
        posthoc.append({'opaque_id': i, 'fold_id': c['fold_id'], 'model_id': None,
                        'role': 'POST_HOC_ENSEMBLE_DIAGNOSTIC', 'decision': posthoc_decision(c['decision'], w['decision']),
                        'C0_decision': c['decision'], 'W0_decision': w['decision'],
                        'component_evidence': [c['evidence_ref'], w['evidence_ref']],
                        'selected_atoms_available': c['selected_atoms_available'] + w['selected_atoms_available'],
                        'selected_atoms_expected': c['selected_atoms_expected'] + w['selected_atoms_expected'],
                        'clauses_defined': c['clauses_defined'] + w['clauses_defined'],
                        'clauses_expected': c['clauses_expected'] + w['clauses_expected']})
    write_lines(OUT / 'posthoc_ensemble_diagnostic.jsonl', posthoc)
    write(OUT / 'posthoc_ensemble_diagnostic.json', explicit_oof('POST_HOC_ENSEMBLE_DIAGNOSTIC',
          {r['opaque_id']: r for r in posthoc}, meta, 'POST_HOC_ENSEMBLE_DIAGNOSTIC'))
    write(OUT / 'baseline_references.json', evidence)
    # Reuse R06 E-only and R08 LOCO to distinguish source/transfer evidence.
    auxiliary = {}
    for name, dirs in {
        'R06_E_ONLY': sorted((V1 / 'R06_sources/dispatch/jobs').glob('*GREEDY_OR__OP05__SRC-001__core')),
        'R08_LOCO_C0': sorted((V1 / 'R08_validation/dispatch/jobs').glob('*GREEDY_OR__OP05__SRC-111__core')),
    }.items():
        rows, ev = saved_predictions(dirs)
        auxiliary[name] = rows
        write(OUT / (name + '_saved_reference.json'), {'role': 'READ_ONLY_OTHER_TRACK_REFERENCE_NOT_POOLED_WITH_LOEO',
              'evidence': ev, 'attack_alerts': sum(rows[i]['decision'] == ALERT for i in ids if meta[i]['supervised_label'] == 1)})
    core, core_atoms = project_core(raw, ledger(), 'SRC-111')
    triples = defaultdict(dict)
    for i, m in meta.items(): triples[m['bundle_id'], m['triplet_id']][m['phase']] = i
    wmodels, wtraining, wencoded = {}, {}, {}
    collisions, collision_summary = collision_groups('C0', core, meta)
    for d in baseline_jobs()['W0']:
        m = load_v1_model(d / 'model.json'); fold = m.binding['fold_id']
        wmodels[fold], wtraining[fold] = m, read(d / 'training.json')
        wencoded[fold] = {i: transform_numeric(row, m.encoder) for i, row in raw.items()}
        recs, summary = collision_groups('W0', wencoded[fold], meta, fold)
        collisions += recs
        if not isinstance(collision_summary, list): collision_summary = [collision_summary]
        collision_summary.append(summary)
    write_lines(OUT / 'baseline_input_collision_groups.jsonl', collisions)
    write(OUT / 'baseline_input_collision_summary.json', collision_summary)
    diagnostic, chains, missed_candidate_evidence = [], [], []
    core_reason_by_id = {r['opaque_id']: {} for r in lines(V1 / 'R02_matrix/row_manifest.jsonl')}
    for r in lines(V1 / 'R02_matrix/atom_records.jsonl'):
        if r['opaque_id'] in meta: core_reason_by_id[r['opaque_id']][r['atom_id']] = {'state': r['state'], 'reason': r['reason']}
    for t in triples.values():
        p, a, q = (t[s] for s in PHASES); m = meta[a]; cfg = m['config_id']; fold = base['C0'][a]['fold_id']
        declared = ['app.' + f if not f.startswith('app.') else f for f in m['declared_modified_fields']]
        field_records = []
        for f in declared:
            # Hash/ID values are never exported as diagnostic vectors or predictors.
            vals = [payloads[i]['features'].get(f) for i in (p,a,q)]
            hash_field = f.endswith('_hash')
            field_records.append({'field': f, 'values_pre_attack_post': ['HASH_EXCLUDED']*3 if hash_field else vals,
                'hash_or_id_excluded': hash_field, 'changed_pre_attack': vals[0] != vals[1], 'post_restored': vals[0] == vals[2],
                'status_pre_attack_post': [payloads[i]['field_status'].get(f) for i in (p,a,q)],
                'quality_pre_attack_post': [payloads[i]['field_quality'].get(f) for i in (p,a,q)]})
        changed = [r['field'] for r in field_records if r['changed_pre_attack'] and not r['hash_or_id_excluded']]
        cg = {n: [state(core[i][n]) for i in (p,a,q)] for n in core[a]}
        cdet, wdet = (base[k][a]['decision'] == ALERT for k in ('C0','W0'))
        cohort = 'BOTH_DETECTED' if cdet and wdet else 'CROSS_ONLY' if cdet else 'SINGLE_ONLY' if wdet else 'BOTH_MISSED'
        wm, tr = wmodels[fold], wtraining[fold]
        alternatives = []
        for n in wencoded[fold][a]:
            for polarity in ('POSITIVE', 'NEGATIVE'):
                states = [state(wencoded[fold][i][n]) for i in (p,a,q)]
                if polarity == 'NEGATIVE': states = [negate(s) for s in states]
                if states != ['F','T','F']: continue
                literal = n + ':' + polarity; sup = tr['support'][literal]
                clean_t = sum(sup['phase_availability'][s]['T'] for s in ('clean_pre','clean_post'))
                selected = literal in [c.id for c in wm.clauses]
                reasons = []
                if not sup['eligible']: reasons.append('PRUNED_BY_SUPPORT')
                if clean_t > wm.fit['clean_budget_count']: reasons.append('BUDGET_OR_COMPLEXITY')
                selected_states = wm.fit['training_result']['states']
                train_meta = {i: meta[i] for i in wm.fit['train_ids']}
                selected_attack_triplets = {(train_meta[i]['bundle_id'], train_meta[i]['triplet_id'])
                    for i,s in zip(wm.fit['train_ids'],selected_states) if train_meta[i]['phase']=='attack' and s=='T'}
                true_trips = {tuple(k) for k in sup['true_attack_triplet_ids']}
                gain = len(true_trips - selected_attack_triplets)
                if not selected and sup['eligible'] and clean_t <= wm.fit['clean_budget_count'] and gain == 0:
                    reasons.append('FOLD_SHIFT_ZERO_MARGINAL_TRAIN_GAIN')
                if not reasons and not selected: reasons.append('UNRESOLVED_SELECTION_REASON')
                alternatives.append({'literal_id': literal, 'selected': selected, 'support_eligible': sup['eligible'],
                    'train_true_attack_triplets': sup['true_attack_triplets'], 'available_triplets': sup['triplets'],
                    'train_clean_alarms': clean_t, 'train_clean_budget': wm.fit['clean_budget_count'],
                    'new_train_attack_triplets_over_selected': gain, 'reasons': reasons})
        if cdet:
            primary = 'NOT_A_C0_MISS_REFERENCE'
        elif not changed:
            primary = 'NO_OBSERVABLE_CHANGE'
        elif 'webgl-pair' in cfg:
            primary = 'MEASUREMENT_UNAVAILABLE'
        elif any(x in cfg for x in ('webdriver-only','plugins-mime','legacy-default')):
            primary = 'SIGNAL_WITHOUT_CROSS_REFERENCE'
        else:
            primary = 'REPRESENTATION_GAP'
        secondary = sorted({r for c in alternatives for r in c['reasons']})
        train_configs = sorted({meta[i]['config_id'] for i in wm.fit['train_ids'] if meta[i]['phase']=='attack'})
        if cfg not in train_configs: secondary.append('FOLD_SHIFT_CONFIGURATION_ABSENT_FROM_TRAIN')
        action = {
            'NO_OBSERVABLE_CHANGE': 'Keep attack denominator; request separately authorized collection inspection if needed.',
            'MEASUREMENT_UNAVAILABLE': 'Retain GPU U; inspect software/ANGLE semantics before proposing any finite renderer-family extension.',
            'SIGNAL_WITHOUT_CROSS_REFERENCE': 'Keep same-surface signals; no fabricated Native CPU/plugin/webdriver mirror. Inspect joint selection and legal automation.',
            'REPRESENTATION_GAP': 'Use field_reference_inventory; distinguish existing predicate invariance from missing relation and fold support.',
            'NOT_A_C0_MISS_REFERENCE': 'Keep detected/control examples; inspect W0 lost cases and Native gate before attributing cross-surface benefit.'}[primary]
        chain = {'attack_id': a, 'pre_id': p, 'post_id': q, 'config_id': cfg, 'environment': m['environment_group_id'],
                 'cohort': cohort, 'raw_declared_fields': field_records, 'C0_states_pre_attack_post': cg,
                 'selected_C0': base['C0'][a]['clause_explanations'], 'selected_W0': base['W0'][a]['clause_explanations'],
                 'C0_raw_atom_availability_reasons': core_reason_by_id[a],
                 'W0_FTF_alternatives': alternatives, 'W0_training_configurations': train_configs,
                 'W0_trace_ref': relative(baseline_jobs()['W0'][int(fold[-2:])-1] / 'training.json'),
                 'source_refs': [meta[i]['S01_fact_ref'] for i in (p,a,q)] + [meta[i]['S02_input_ref'] for i in (p,a,q)]}
        chains.append(chain)
        for i in (p,a,q):
            diagnostic.append({'opaque_id': i, 'attack_id': a, 'pre_id': p, 'post_id': q, 'phase': meta[i]['phase'],
                'config_id': cfg, 'environment': m['environment_group_id'], 'fold_id': fold, 'attack_cohort': cohort,
                'primary_reason': primary, 'secondary_reasons': secondary, 'changed_semantic_fields': changed,
                'C0_decision': base['C0'][i]['decision'], 'W0_decision': base['W0'][i]['decision'],
                'R06_E_only_decision': auxiliary['R06_E_ONLY'][i]['decision'], 'R08_LOCO_C0_decision': auxiliary['R08_LOCO_C0'][i]['decision'],
                'evidence_paths': [meta[i]['S01_fact_ref'], meta[i]['S02_input_ref'], base['C0'][i]['evidence_ref'],
                                   base['W0'][i]['evidence_ref'], relative(OUT/'triplet_evidence.jsonl')+'#attack_id='+a],
                'next_action': action})
        if not wdet: missed_candidate_evidence.append({'attack_id': a, 'config_id': cfg, 'fold_id': fold, 'alternatives': alternatives})
    write_lines(OUT / 'triplet_evidence.jsonl', chains)
    write_csv(OUT / 'diagnosis.csv', diagnostic)
    write(OUT / 'missed_candidate_diagnostics.json', missed_candidate_evidence)
    configs = []
    for cfg in sorted({m['config_id'] for m in meta.values()}):
        rs = [r for r in diagnostic if r['config_id']==cfg and r['phase']=='attack']
        configs.append({'config_id': cfg, 'attacks': len(rs), 'C0_detected': sum(r['C0_decision']==ALERT for r in rs),
                        'W0_detected': sum(r['W0_decision']==ALERT for r in rs),
                        'cohorts': dict(Counter(r['attack_cohort'] for r in rs)),
                        'primary_reasons': sorted({r['primary_reason'] for r in rs}),
                        'secondary_reasons': sorted({x for r in rs for x in r['secondary_reasons']})})
    write_csv(OUT / 'configuration_diagnosis.csv', configs)
    anchor = 'app.android_native_data.build_fingerprint_layer.os_version'
    discrepancies = [i for i in ids if state(core[i]['DEVIATION:OFFDER-UA-001']) != state(raw[i]['CAT:NW-006'])]
    write(OUT / 'native_anchor_diagnostic.json', {
        'native_field': anchor, 'observed_values': dict(Counter(str(payloads[i]['features'].get(anchor)) for i in ids)),
        'native_validity_gate_pass_n': sum(payloads[i]['field_status'].get(anchor)=='observed' for i in ids), 'n': len(ids),
        'values_are_not_constant': len({str(payloads[i]['features'].get(anchor)) for i in ids}) > 1,
        'native_value_is_only_validity_gate_in_selected_predicate': True,
        'C0_UA_and_W0_NW006_differing_ids': discrepancies,
        'empirical_equality_is_not_global_alias': True,
        'domain_difference': 'NW-006 requires both UA/platform classes interpretable; OFFDER-UA-001 permits one interpretable Web class but additionally requires Native Android major.',
        'code_refs': ['hybridguard_agent/official_semantics/evaluator.py:221',
                      'hybridguard_agent/rules/executor.py:97', 'hybridguard_agent/research/rule_learning/matrix.py:149'],
        'synthetic_check_ref': 'hybridguard_agent/tests/test_rule_learning_v2.py#test_native_anchor_is_validity_gate_not_version_comparison'})
    summary = {'supervised_stages': len(ids), 'attack_triplets': len(triples), 'configurations': len(configs),
               'cohort_attack_counts': dict(Counter(c['cohort'] for c in chains)),
               'attack_with_observed_semantic_change': sum(any(r['changed_pre_attack'] and not r['hash_or_id_excluded'] for r in c['raw_declared_fields']) for c in chains),
               'primary_miss_reasons': dict(Counter(r['primary_reason'] for r in diagnostic if r['phase']=='attack' and r['C0_decision']!=ALERT)),
               'search_limit': 'NOT_ESTABLISHED_NO_IP_OR_ALTERNATE_SEARCH_AUTHORIZED',
               'engineering_inconsistency_in_saved_predictions': 'NONE_DETECTED_BY_TARGETED_MEMBER_AND_MODEL_CHECKS',
               'posthoc_role': 'POST_HOC_ENSEMBLE_DIAGNOSTIC'}
    write(OUT / 'diagnosis_summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False))


def after_trials():
    from .pilot import attempt_predictions
    meta = metadata(); ids = sorted(meta); raw = raw_cache(ids)
    predictions, model_rows, metrics = {}, [], {}
    for name, dirs in baseline_jobs().items():
        predictions[name], _ = saved_predictions(dirs)
        for d in dirs:
            m = load_v1_model(d/'model.json')
            model_rows.append({'representation': name, 'fold_id': m.binding['fold_id'], 'model_id': m.model_id,
                'status': m.status, 'complexity': m.to_dict()['complexity']['objective_complexity'],
                'clauses': [c.id for c in m.clauses], 'path': relative(d/'model.json')})
    predictions['POST_HOC_ENSEMBLE_DIAGNOSTIC'] = {r['opaque_id']:r for r in lines(OUT/'posthoc_ensemble_diagnostic.jsonl')}
    collisions, summaries, candidate_stats, changes = [], [], [], []
    for rep in ('S_FLAT','J0'):
        predictions[rep] = {}
        for f in folds():
            d = OUT/'trials'/('V2-A__'+rep+'__'+f['fold_id']+'__attempt01')
            rows = attempt_predictions(d)
            predictions[rep].update({r['opaque_id']:r for r in rows})
            if not (d/'model.json').exists(): continue
            m = load_model(d/'model.json'); training = read(d/'training.json')
            model_rows.append({'representation': rep, 'fold_id': f['fold_id'], 'model_id': m.model_id,
                'status': m.status, 'complexity': m.engine.to_dict()['complexity']['objective_complexity'],
                'clauses': [c.id for c in m.clauses], 'path': relative(d/'model.json'),
                'cross_atoms_selected': [a.atom_id for a in m.atoms if len(a.surfaces)>1]})
            if m.status in ('FITTED','EMPTY_MODEL') and m.encoder:
                # Full candidate vectors with this already-frozen fold encoder;
                # do not merge vectors made by different fold encoders.
                encoded = {i: transform_numeric(r,m.encoder) for i,r in raw.items()}
                if rep=='J0':
                    core,_=project_core(raw,ledger(),'SRC-111')
                    for i in encoded: encoded[i].update(core[i])
                recs, sm = collision_groups(rep,encoded,meta,f['fold_id']); collisions+=recs; summaries.append(sm)
                for phase in PHASES:
                    phase_ids=[i for i in f['outer_test'] if meta[i]['phase']==phase]
                    values=[c for i in phase_ids for c in encoded[i].values()]
                    candidate_stats.append({'representation':rep,'fold_id':f['fold_id'],'phase':phase,
                        'raw_flat_inputs':143,'canonical_core_atoms':10 if rep=='J0' else 0,
                        'encoded_atoms':len(m.view['input_atom_ids']), 'registered_literals':m.fit['registered_clause_count'],
                        'support_eligible_literals':m.fit['candidate_pool_size'],
                        'available_candidate_cells':sum(c['available'] and c['evaluation_status']=='OK' for c in values),
                        'expected_candidate_cells':len(values), 'failed_candidate_cells':sum(c['evaluation_status']!='OK' for c in values)})
                changes.append({'representation':rep,'fold_id':f['fold_id'], 'candidate_ids':m.view['input_atom_ids'],
                                'new_predicates':0,'threshold_fit_scope':'EXACT_OWN_TRAIN',
                                'source_alias_handling':'C0 12 raw aliases ->10 canonical atoms; no merge solely on observed equality',
                                'model_id':m.model_id})
    write_lines(OUT/'input_collision_groups.jsonl',collisions)
    write(OUT/'input_collision_summary.json',summaries)
    write_csv(OUT/'candidate_availability.csv',candidate_stats)
    write_lines(OUT/'candidate_changes.jsonl',changes)
    write(OUT/'model_manifest.json',model_rows)
    table, per_config, per_fold = [], [], []
    for name,rows in predictions.items():
        result=explicit_oof(name,rows,meta, 'POST_HOC_ENSEMBLE_DIAGNOSTIC' if name.startswith('POST_HOC') else ROLE)
        metrics[name]=result
        def flatten(group, ms):
            record={'representation':name,'stratum':group}
            for metric,r in ms.items():
                record[metric+'_k']=r['numerator'];record[metric+'_n']=r['denominator'];record[metric]=r['value']
            return record
        row=flatten('ALL',result['metrics'])
        row['complexity_by_fold']=[r['complexity'] for r in model_rows if r['representation']==name]
        row['role']=result['evaluation_role'];table.append(row)
        per_config.extend(flatten(cfg,ms) for cfg,ms in result['strata']['config'].items())
        for f in folds():
            sub={i:meta[i] for i in f['outer_test']}
            ms=explicit_oof(name,{i:rows[i] for i in sub},sub)['metrics']
            per_fold.append(flatten(f['fold_id'],ms))
    write(OUT/'metrics.json',metrics);write_csv(OUT/'metrics.csv',table)
    write_csv(OUT/'metrics_by_configuration.csv',per_config);write_csv(OUT/'metrics_by_fold.csv',per_fold)
    comparisons=[]
    for rep in ('S_FLAT','J0'):
        for ref in ('C0','W0'):
            attacks=[i for i in ids if meta[i]['supervised_label']==1];clean=[i for i in ids if meta[i]['supervised_label']==0]
            gained=[i for i in attacks if predictions[rep][i]['decision']==ALERT and predictions[ref][i]['decision']!=ALERT]
            lost=[i for i in attacks if predictions[rep][i]['decision']!=ALERT and predictions[ref][i]['decision']==ALERT]
            alarms=[i for i in clean if predictions[rep][i]['decision']==ALERT and predictions[ref][i]['decision']!=ALERT]
            comparisons.append({'representation':rep,'reference':ref,'gained_attack_ids':gained,'lost_attack_ids':lost,
                                'new_clean_alarm_ids':alarms,'gained_by_config':dict(Counter(meta[i]['config_id'] for i in gained)),
                                'lost_by_config':dict(Counter(meta[i]['config_id'] for i in lost))})
    write(OUT/'gained_lost.json',comparisons)
    write_lines(OUT/'stage_comparison.jsonl',[{'opaque_id':i,'phase':meta[i]['phase'],'config_id':meta[i]['config_id'],
        'decisions':{name:rows[i]['decision'] for name,rows in predictions.items()}} for i in ids])
    print(json.dumps([{k:r[k] for k in ('representation','attack_tpr_k','attack_tpr_n','MacroTPR_config_environment','pre_alarm_rate_k','post_alarm_rate_k','decision_coverage','complexity_by_fold')} for r in table],ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('baseline','after'))
    args=parser.parse_args();{'baseline':baseline_diagnosis,'after':after_trials}[args.command]()
