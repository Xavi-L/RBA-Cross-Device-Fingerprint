#!/usr/bin/env python3
"""Freeze exact raw-only members and prospective jobs; never fit or predict."""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'deliverables/featureapp_webdriver_raw_multienv_v1'))
from analyze_raw_only import MODES, literal_support
from hybridguard_agent.research.manipulation_eval.adapter import adapt_payload
from hybridguard_agent.research.rule_semantics_runtime_input import adapt_runtime_payload, RuntimeInputError
from hybridguard_agent.research.rule_semantics_runtime_matrix import measure_w0_base_inputs
from hybridguard_agent.research.rule_semantics_revision_v1 import web_language_first_difference, webdriver_reported_state
from hybridguard_agent.research.rule_semantics_revision_v1.contracts import SourceBinding, make_cell


def read(p):return json.loads(Path(p).read_text())
def lines(p):return [json.loads(s) for s in Path(p).read_text().splitlines() if s.strip()]
def write(p,data):
    with Path(p).open('x') as stream:json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def prepare(output):
    audit=read(HERE/'EFFECT_AUDIT.json')
    if audit['status']!='PRIMARY_EFFECTS_PASS':raise ValueError('Primary effect and restoration audit not ready')
    assignments=audit['primary_assignments']
    if len({(a['api'],a['configuration_id']) for a in assignments})!=42:raise ValueError('Exact 42 distinct environment/configuration assignments required')
    primary_configs={r['configId'] for r in read(HERE/'CONFIGURATIONS.json')}
    if any(len([a for a in assignments if a['api']==api])!=14 for api in (29,30,36)):raise ValueError('Every environment must contain 14 configurations')
    frozen=ROOT/'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R04_freeze_r1'
    protocol=frozen/'snapshot/hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol'
    contract={'definitions':read(frozen/'data/definitions.json'),
              'candidate_definitions':lines(protocol/'CANDIDATE_LEDGER.jsonl'),
              'control_specs':read(protocol/'SINGLE_SURFACE_FIELDS.json')['fields'],
              'rule_definitions':read(ROOT/'hybridguard_agent/config/paired244_rule_catalog.v3.json')['rules']}
    sources={}
    for ref in {a['source_run'] for a in assignments}:
        run=ROOT/ref
        sources[ref]={'raw':{r['session_id']:r for r in lines(run/'backend/raw_expanded_payloads.jsonl')},
                      'receipts':{r['session_id']:r for r in lines(run/'backend/collection_receipts.jsonl')},
                      'saved':{r['step_id']:r for r in lines(run/'sessions.jsonl')},
                      'config':read(run/'protocol_snapshot.json')}
    inputs={};metadata={};states={};identities=defaultdict(set);raw_stats=Counter();role_index=[]
    for assigned in assignments:
        source=sources[assigned['source_run']]
        config=source['config'];run=ROOT/assigned['source_run']
        for trio in assigned['triplets']:
            if trio['status']!='PASS':raise ValueError('Missing independent triplet effect admission')
            for phase,step_id,sid in zip(('clean_pre','attack','clean_post'),trio['step_ids'],trio['session_ids'],strict=True):
                saved=source['saved'][step_id];raw=source['raw'][sid];payload=raw['canonical_received_payload']
                receipt=source['receipts'][sid];attempt=read(run/'attempts'/step_id/'attempt.json')
                if (not saved['accepted'] or attempt['status']!='ACCEPTED' or attempt['session_id']!=sid
                        or payload['session_id']!=sid or saved['observation']['session_id']!=sid
                        or raw['receipt_id']!=receipt['receipt_id'] or raw['collection_batch_id']!=receipt['collection_batch_id']
                        or receipt['validation_status']!='accepted' or saved['phase']!=phase
                        or payload['collection_manifest']['runtime_context']!=saved['runtime_context']):
                    raise ValueError('Raw/session/attempt/receipt association mismatch')
                manifest=payload['collection_manifest']
                identities[assigned['api']].add((manifest['collector_install_id'],manifest['android_api'],manifest['webview_provider_package'],manifest['webview_provider_version'],manifest['collector_version_code']))
                oid='rawonly-'+sid
                if oid in inputs:raise ValueError('Duplicate primary session')
                bindings={mode:SourceBinding(config['campaign_id'],scope,
                          observer_revision='app-webdriver-observer-v1' if mode=='WEBDRIVER_RAW' else None,
                          realm_binding=f'featureapp:{sid}:main-frame' if mode=='WEBDRIVER_RAW' else None)
                          for mode,(_,_,scope) in MODES.items() if mode!='WEBDRIVER_LEGACY'}
                # The adapter accepts explicit registrations per mode; legacy
                # remains diagnostic and is not used to replace raw observations.
                adapted=adapt_runtime_payload(payload,expected_session_id=sid,source_bindings=bindings)
                cells={};states[oid]={}
                for mode,(cid,interpretation,_) in MODES.items():
                    if mode=='WEBDRIVER_LEGACY':continue
                    try:
                        projected,binding=adapted.input_for(mode)
                        cell=web_language_first_difference(projected,binding) if mode=='LANGUAGE' else webdriver_reported_state(projected,mode=interpretation,source_binding=binding)
                    except RuntimeInputError as error:cell=make_cell(cid,error.state,error.reason)
                    cells[cid]=cell.to_dict();states[oid][mode]=cell.state;raw_stats[mode+':'+cell.state]+=1
                full=adapt_payload(payload)
                if len(full['features'])!=177:raise ValueError('Missing full App177 projection')
                measured=measure_w0_base_inputs(full,**contract)
                inputs[oid]={'opaque_id':oid,'observation_mode':'raw_observation_v1','features':measured,'candidate_cells':cells,
                             'source_ref':assigned['source_run'],'session_id':sid,'source_bindings':{m:asdict(b) for m,b in bindings.items()}}
                metadata[oid]={'opaque_id':oid,'phase':phase,'environment_group_id':config['device_manifest_id'],
                               'config_id':trio['config_id'],'bundle_id':config['device_manifest_id']+':'+trio['config_id'],
                               'triplet_id':config['device_manifest_id']+':'+trio['config_id']+':r'+str(trio['round']),
                               'proposed_supervised_label':int(phase=='attack'),'proposed_supervised_member':True,
                               'fit_permission':'DENIED_PREPARATION_ONLY','label_scope':'Declared controlled intervention present/absent only',
                               'observation_mode':'raw_observation_v1','admission_ref':'EFFECT_AUDIT.json',
                               'source_ref':assigned['source_run'],'step_id':step_id,'session_id':sid}
    if len(inputs)!=378 or any(len(v)!=1 for v in identities.values()) or len({next(iter(v))[0] for v in identities.values()})!=3:
        raise ValueError('Exact 378 members and three stable distinct installations required')
    if any(next(iter(v))[1]!=api for api,v in identities.items()):raise ValueError('Environment API association mismatch')
    folds=[];jobs=[];checks=[]
    for number,env in enumerate(sorted({r['environment_group_id'] for r in metadata.values()}),1):
        train=sorted(i for i,m in metadata.items() if m['environment_group_id']!=env)
        test=sorted(set(metadata)-set(train));fid=f'RAW-LOEO-v1-{number:02}'
        if len(train)!=252 or len(test)!=126 or {metadata[i]['config_id'] for i in train}!={metadata[i]['config_id'] for i in test} or {metadata[i]['config_id'] for i in test}!=primary_configs:
            raise ValueError('Unbalanced environment/configuration fold')
        if {metadata[i]['bundle_id'] for i in train}&{metadata[i]['bundle_id'] for i in test}:raise ValueError('Bundle leakage')
        fold={'fold_id':fid,'heldout_environment':env,'train_ids':train,'outer_test_ids':test}
        folds.append(fold)
        support=[literal_support([metadata[i] for i in train],states,mode,polarity) for mode in ('LANGUAGE','WEBDRIVER_RAW') for polarity in ('POSITIVE','NEGATIVE')]
        checks.append({'fold_id':fid,'literal_support':support})
        for group in ('BASE','LANG_ADD_WD_REPLACE'):
            initial=group+'__'+fid+'__SPARSE'
            jobs.append({**fold,'job_id':initial,'group_id':group,'stage':'SPARSE','max_prediction_calls':0})
            jobs.append({**fold,'job_id':group+'__'+fid+'__RETENTION','group_id':group,'stage':'RETENTION','initializer':initial,'max_prediction_calls':len(test)})
    budget=read(ROOT/'deliverables/rule_semantics_combination/EXECUTION.json')
    if budget['cumulative_fit_jobs']!=177 or budget['remaining_research_fits']!=23:raise ValueError('Shared budget changed; review before any fit')
    feasible=all(s['passes_single_literal_feasibility'] for c in checks for s in c['literal_support'] if s['polarity']=='POSITIVE')
    cell_counts=Counter('FAILED' if c['evaluation_status']=='FAILED' else 'AVAILABLE' if c['available'] else 'U' for r in inputs.values() for c in r['features'].values())
    process_counts={key:sum(r.get(key,0) for r in audit['runs']) for key in ('saved','raw_saved','attempted','failed_attempts','not_attempted')}
    selected_sessions={m['session_id'] for m in metadata.values()}
    for run in audit['runs']:
        ref=run['path'];rawpath=ROOT/ref/'backend/raw_expanded_payloads.jsonl'
        if not rawpath.exists():continue
        selected_steps={m['step_id'] for m in metadata.values() if m['source_ref']==ref}
        saved_by_sid={r['observation']['session_id']:r for r in lines(ROOT/ref/'sessions.jsonl')}
        for row in lines(rawpath):
            sid=row['session_id'];s=saved_by_sid.get(sid)
            role='PRIMARY_MEMBER' if sid in selected_sessions else 'BOUNDARY_ONLY' if run['role']=='COMPATIBILITY_BOUNDARY_ONLY' else 'AUXILIARY_ONLY' if s and (s['group'] in ('smoke','no_attack','debug_transport_control')) else 'EXCLUDED_INCOMPLETE_OR_FAILED_ORIGINAL_TRIPLET'
            role_index.append({'session_id':sid,'source_run':ref,'role':role,'raw_recorded':True,'accepted_collection_record':bool(s and s['accepted'])})
    result={'status':'RAW_ONLY_COMPARISON_READY' if feasible and cell_counts['FAILED']==0 else 'BLOCKED_BY_INPUT_FEASIBILITY',
            'primary_members':len(inputs),'primary_attack':126,'primary_paired_controls':252,'environments':{str(api):list(next(iter(v))) for api,v in identities.items()},
            'configurations':14,'candidate_states':dict(raw_stats),'base_input_cells':dict(cell_counts),'folds':3,'planned_fits':12,
            'planned_model_prediction_calls':756,'budget_used_before':177,'budget_remaining_before':23,
            'process_counts':process_counts,'raw_roles':dict(Counter(r['role'] for r in role_index)),
            'actual_fit_calls':0,'actual_predict_calls':0,'historical162_included':False,
            'evaluation_role':'EXPOSED_RETROSPECTIVE_DEVELOPMENT','normal_app_population_fpr':'NOT_EVALUATED'}
    output.mkdir(parents=True,exist_ok=False);(output/'inputs').mkdir();(output/'evaluation').mkdir()
    for oid,row in inputs.items():write(output/'inputs'/f'{oid}.json',row);write(output/'evaluation'/f'{oid}.json',metadata[oid])
    for name,data in [('SUMMARY.json',result),('FOLDS.json',folds),('JOBS.json',jobs),('SUPPORT.json',checks),('DEFINITIONS.json',contract['definitions']),('RAW_ROLE_INDEX.json',role_index)]:write(output/name,data)
    write(output/'CONTRACT.json',{'experiment_id':'raw-only-rkeep-three-env-fourteen-config-v1','registered_at':datetime.now(timezone.utc).isoformat(),
          'engine_study_version':'rule-semantics-mixed-retraining-v1','engine_phase':'RSR_MIXED_RETRAINING',
          'engine_reuse':'Existing per-record-mode adapter; this exact experiment uses raw mode for every member, no legacy/H162 rows.',
          'sample_ids':sorted(inputs),'source_modes':{i:'raw_observation_v1' for i in sorted(inputs)},'folds':folds,'jobs':jobs,
          'evaluation_role':result['evaluation_role'],'scope':'API29/30/36 controlled local emulators with available boolean webdriver; not independent confirmation',
          'admission_basis':'Recorded original or separately amended execution plus all declared active fields and full paired restoration; independent of candidates or detectors.',
          'constraints':{'minimum_available_triplets':3,'minimum_true_attack_triplets':2,'minimum_support_bundles':1,'minimum_support_environments':1,'min_phase_coverage':0.8,'op05_clean_fraction':0.05,'max_clauses':6,'max_literals':12},
          'budget':{'base_fit_jobs':177,'remaining_fits':23,'reserved_fits':0,'planned_fits':12,'max_worker_seconds':90,'max_total_seconds':1080,'base_charged_seconds':budget['cumulative_charged_seconds']},
          'readiness':result['status'],'execution_started':False})
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=HERE/'prepared')
    prepare(parser.parse_args().output)
