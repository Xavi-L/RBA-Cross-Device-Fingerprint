"""Final read-only development attribution; never invokes an encoder fit."""
from collections import Counter, defaultdict

from .common import ROOT, OUT as A_OUT, read, lines, write, write_csv, relative, folds, stamp
from .b_experiment import B_OUT
from .diagnose import metadata, ALERT, baseline_jobs
from . import relations as rel


def build():
    meta=metadata();ids=sorted(meta)
    stages={r['opaque_id']:r for r in lines(B_OUT/'stage_comparison.jsonl')}
    manifest=read(B_OUT/'model_manifest.json');metrics=read(B_OUT/'metrics.json')
    primary='W0__R_KEEP_V1'
    equals=[]
    for name in ['S_FLAT__R_KEEP_V1','J0__R_KEEP_V1','JX__R_KEEP_V1','W_X__R_KEEP_V1','S_FLAT_X__R_KEEP_V1']:
        delta=[i for i in ids if stages[i]['decisions'][name]!=stages[i]['decisions'][primary]]
        rules=[]
        for f in folds():
            a=next(m for m in manifest if m['spec_id']==primary and m['fold_id']==f['fold_id'])
            b=next(m for m in manifest if m['spec_id']==name and m['fold_id']==f['fold_id'])
            rules.append({'fold_id':f['fold_id'],'identical_selected_clause_ids_including_thresholds':a['clauses']==b['clauses'],
                          'cross_atoms_selected':b['cross_atoms_selected']})
        equals.append({'comparison':name+' vs '+primary,'different_decision_ids':delta,'folds':rules})
    ratio_rows=[];semantic=[]
    payloads=rel.load_payloads(ids)
    by_env_phase=defaultdict(list)
    for i,p in payloads.items():
        v=rel.raw_relations(p,{'relation_families':['memory','language','timezone'],'matched_single_features':True})
        value=v[rel.RATIO]['value'];by_env_phase[(meta[i]['environment_group_id'],meta[i]['phase'])].append((i,value))
        semantic.append({'opaque_id':i,'native_primary':rel.primary_language(rel.observed(p,rel.N_LANG)),
                         'web_primary':rel.primary_language(rel.observed(p,rel.W_LANG)),
                         'native_offset':rel.observed(p,rel.N_OFFSET),'web_offset':rel.observed(p,rel.W_OFFSET),
                         'cross_language':v[rel.LANG_LIST]['value'],'web_language_control':v[rel.WEB_LIST]['value'],
                         'timezone_relation':v[rel.TZ]['value'],'web_offset_nonzero':rel.observed(p,rel.W_OFFSET)!=0,
                         'source':relative(ROOT/'hybridguard_agent/artifacts/formal_manipulation_v1_20260923/02_inputs/inference_inputs.jsonl')+'#opaque_id='+i})
    for (env,phase),members in sorted(by_env_phase.items()):
        values=[v for _,v in members if v is not None]
        ratio_rows.append({'environment':env,'phase':phase,'n':len(members),'observed_n':len(values),
                           'minimum':min(values) if values else None,'maximum':max(values) if values else None,
                           'ids':[i for i,_ in members]})
    primary_ids=[i for i in ids if meta[i]['supervised_label']==1 and stages[i]['decisions'][primary]!=ALERT]
    import csv
    A_reasons={r['attack_id']:r for r in csv.DictReader((A_OUT/'selection_diagnosis.csv').open())}
    misses=[]
    for i in primary_ids:
        a=A_reasons[i]
        misses.append({'opaque_id':i,'config_id':meta[i]['config_id'],'primary_reason':a['primary_selection_reason'],
                       'source_A_evidence':relative(A_OUT/'selection_diagnosis.csv')+'#attack_id='+i,
                       'current_saved_decision_ref':'stage_comparison.jsonl#opaque_id='+i,
                       'current_train_support_ref':relative(B_OUT/'trials'/('B01_retention__W0__R_KEEP_V1__'+a['fold_id']+'__attempt01')/'training.json'),
                       'next_action':'Independent environment/mechanism support and legal controls; no manual admission of held-out-only positives.' if a['primary_selection_reason']=='PRUNED_BY_SUPPORT' else 'Resolve Native software-renderer/ANGLE semantic domain or collect a valid reference only under a new authorization.'})
    relation_support=[];numeric_reuse=[]
    for batch in read(B_OUT/'linked_budget_ledger.json')['batches']:
        for job in read(ROOT/batch['spec_ref'])['jobs']:
            d=B_OUT/'trials'/(job['job_id']+'__attempt01');training=read(d/'training.json');model=read(d/'model.json')['engine_structure']
            for c in training['candidate_manifest']:
                if c['clause_id'].startswith(('V2REL:','V2SINGLE:')):
                    relation_support.append(dict(c,job_id=job['job_id'],spec_id=job['spec_id'],fold_id=job['fold_id']))
            base=job['base_representation']
            if base=='C0': continue
            f=next(f for f in folds() if f['fold_id']==job['fold_id'])
            old_path=(baseline_jobs()['W0'][folds().index(f)]/'model.json' if base=='W0' else
                      A_OUT/'trials'/('V2-A__'+base+'__'+f['fold_id']+'__attempt01')/'model.json')
            old=read(old_path);old=old.get('engine_structure',old)
            select=lambda e:{k:(v['thresholds'],v['atom_ids']) for k,v in e['numeric'].items()}
            same=select(model['encoder'])==select(old['encoder'])
            assert same
            numeric_reuse.append({'job_id':job['job_id'],'old_numeric_thresholds_equal_own_fold_reference':same,'reference':relative(old_path)})
    clean_alarm_ids=[i for i in ids if meta[i]['supervised_label']==0 and stages[i]['decisions']['CX__GREEDY_OR']==ALERT]
    evidence={'utc':stamp(),'role':'FIXED_SEMANTIC_AND_SAVED_OUTPUT_DIAGNOSTIC_NO_NEW_FIT',
       'equal_primary_variants':equals,
       'memory_ratio_by_environment_phase':ratio_rows,
       'CX_clean_alarm_ids':clean_alarm_ids,
       'CX_clean_alarm_environments':dict(Counter(meta[i]['environment_group_id'] for i in clean_alarm_ids)),
       'CX_memory_only_identical_all_stage_decisions':[i for i in ids if stages[i]['decisions']['CX_MEMORY_ONLY__GREEDY_OR']!=stages[i]['decisions']['CX__GREEDY_OR']]==[],
       'CX_no_memory_identical_C0_all_stage_decisions':[i for i in ids if stages[i]['decisions']['CX_NO_MEMORY__GREEDY_OR']!=stages[i]['decisions']['C0']]==[],
       'cross_vs_single_language_different_ids':[r['opaque_id'] for r in semantic if r['cross_language']!=r['web_language_control']],
       'timezone_vs_web_offset_nonzero_different_ids':[r['opaque_id'] for r in semantic if r['timezone_relation']!=r['web_offset_nonzero']],
       'native_primary_counts':dict(Counter(r['native_primary'] for r in semantic)),
       'web_primary_counts':dict(Counter(r['web_primary'] for r in semantic)),
       'native_offset_counts':dict(Counter(str(r['native_offset']) for r in semantic)),
       'semantic_evidence':semantic,'original_numeric_threshold_readback':numeric_reuse,
       'interpretation':'Current equality is not a global predicate alias. Synthetic Native-value perturbations prove function dependence only; they do not establish real incremental discrimination.'}
    write(B_OUT/'relation_evidence.json',evidence)
    write_csv(B_OUT/'relation_train_support.csv',relation_support)
    write_csv(B_OUT/'remaining_misses.csv',misses)
    write_csv(B_OUT/'candidate_counts.csv',[{'spec_id':m['spec_id'],'fold_id':m['fold_id'],
        'encoded_atoms_before_support':m['registered_clauses']//2 if m['registered_clauses'] is not None else None,
        'registered_literals_before_support':m['registered_clauses'],'support_eligible_literals':m['eligible_clauses'],
        'selected_clauses':m['selected_clauses'],'complexity':m['complexity'],
        'not_selected_reason_counts':m['not_selected_reason_counts']} for m in manifest])
    selection={'schema_version':'v2-b-candidate-selection-v1','decision':'PRIMARY_CANDIDATE_FOR_USER_REVIEW',
        'evaluation_role':'EXPOSED_RETROSPECTIVE_DEVELOPMENT','selected_at':stamp(),
        'primary':{'spec_id':primary,'learning_procedure':'Original W0 train encoder and GREEDY_OR/OP05 initialization, then fixed R_KEEP_V1 signal retention under unchanged limits',
          'metrics':metrics[primary],'complexity_by_fold':[12,12,12],
          'fold_models':[m['model_ref'] for m in manifest if m['spec_id']==primary],
          'no_whole_development_final_model_fitted':True},
        'alternate':None,
        'rationale':['Configuration/environment macro improves as well as micro; no new observed clean alarms, failures or abstentions.',
           'Same decisions and selected clauses as larger flat/joint/matched variants, with only the original Web input scope.',
           'No new cross-relation gain beyond this same-selector single-surface control. CX introduces 18 clean alarms.',
           'Additional third-fold complexity is an explicit cost: 2 to 12; all three folds now use 6 clauses.'],
        'tradeoffs':['All gain over saved W0 occurs in one held-out environment group, across six configurations; only three environment association groups exist.',
           'Absolute memory/concurrency, UA/platform, webdriver and list counts can respond to legitimate browser/hardware/customization changes.',
           '0/108 exposed clean alarms is not population zero FPR. Labels cover only the declared intervention surface.',
           'Manual semantic signal groups and selection were developed after exposure to these materials.'],
        'rejected_new_alternatives':{'flat_joint_matched_variants':'No decision/selected-rule gain; larger input requirements.',
             'CX_GREEDY_OR':'27/54 but pre/post 9/54 each; memory-induced normal environment shift.',
             'CX_R_KEEP_V1':'30/54 with same 18 clean alarms; no advantage over primary clean/detection tradeoff.',
             'CX_NO_MEMORY':'Same decisions as C0 with higher complexity.',
             'CX_MEMORY_ONLY':'Same adverse decisions as CX.'},
        'historical_C0':'Retained low-complexity baseline (2/2/2), not a newly promoted B alternate.',
        'stop_reason':'Key authorized hypotheses tested with same-pool, same-selector, matched-parser and targeted family controls; further tuning lacks a new hypothesis.',
        'C_status':'NOT_STARTED_REQUIRES_USER_AUTHORIZATION','independent_confirmation':'NOT_ESTABLISHED_OR_ACCESSED',
        'minimal_C_plan':['Freeze candidate grammar, group mapping, fit procedure and clean/coverage operating point before opening new confirmation labels.',
             'Authorize independently collected/adjudicated environments crossed with configurations, including legitimate high RAM/CPU, language, timezone, PDF/plugin, UA customization and authorized automation controls.',
             'Use paired expected-ID comparisons against saved-method C0 and W0 procedures, report macro/micro/clean/coverage/complexity with independent-group uncertainty; do not retune on confirmation feedback.'],
        'not_claimed':['new blind test','unseen mechanism guarantee','cross-layer superiority','universal zero FPR','optimization/generalization theorem','V2-C completed']}
    write(B_OUT/'CANDIDATE_SELECTION.json',selection)
    print({'primary':primary,'remaining_misses':len(misses),'reasons':dict(Counter(r['primary_reason'] for r in misses)),
           'equal_decisions_and_rules':all(not e['different_decision_ids'] and all(f['identical_selected_clause_ids_including_thresholds'] for f in e['folds']) for e in equals)})


if __name__=='__main__': build()
