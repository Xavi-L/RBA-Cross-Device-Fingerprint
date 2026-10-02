#!/usr/bin/env python3
"""Evaluate two fixed conditions, and six frozen models on a distinct new batch."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research import memory_relation_validation as v
from hybridguard_agent.research import mtc_relation_sources as sources
from hybridguard_agent.research import mtc_constrained_reselection as base
from hybridguard_agent.research import mtc_relation_selection as extended


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


prior = module('memory_saved_helpers', ROOT/'deliverables/mtc_constrained_reselection_v1/run_experiment.py')
read = lambda p: json.loads(Path(p).read_text())


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def rows(path):
    if not Path(path).exists():
        return []
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def save_rows(path, data):
    if Path(path).exists():
        raise FileExistsError('Saved predictions exist; use summarize')
    with gzip.open(path, 'xt') as stream:
        for row in data:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n')


def record(sid, bound, **meta):
    return dict(sample_id=sid, **meta, operands=v.operand_details(bound),
                source_binding=bound.get('source_binding'), source_errors=bound.get('errors', []),
                conditions=v.compare(bound))


def historical(out):
    config = read(ROOT/read(out/'SETTINGS.json')['historical_membership'])
    ids = [sid for f in config['folds'] for sid in f['outer_test_ids']]
    assert len(ids) == len(set(ids)) == 378
    meta = prior.controlled_metadata(ROOT/config['controlled_source'], ids)
    bound = sources.load_controlled_sources(ids, allowed_ids=ids)
    result = [record(sid, bound[sid], dataset='controlled', subset=meta[sid]['phase'],
                     config_id=meta[sid]['config_id'], environment=meta[sid]['environment_group_id'],
                     normal_basis=meta[sid]['phase'] != 'attack') for sid in ids]
    index = prior.registry(config)
    mtc_ids = [sid for part in config['mtc_primary_ids'].values() for sid in part]
    observations, issues = prior.load_selected_mtc(index, mtc_ids, ROOT/config['mtc_snapshot'], allowed_ids=mtc_ids)
    basis = prior.normal_evidence(config)
    for sid in mtc_ids:
        bound = sources.bind_mtc_observation(observations[sid], sid, allowed_ids=mtc_ids,
                expected_registry=index[sid]) if sid in observations else {'status':'FAILED','errors':[issues[sid]]}
        result.append(record(sid, bound, dataset='mtc', subset=index[sid]['split'],
                      normal_basis=basis[sid], profile=index[sid].get('profile')))
    # All saved R_REL states must equal the untouched last-round outputs.
    by_id = {r['sample_id']:r for r in result}
    previous = rows(ROOT/'deliverables/mtc_relation_extension_v1/predictions.jsonl.gz')
    original_models = defaultdict(dict)
    checked = 0
    for p in previous:
        if p['sample_id'] not in by_id:
            continue
        if p['dataset'] == 'controlled':
            original_models[p['sample_id']][p['scheme']] = p['decision']
        if p['scheme'] == 'B_REL':
            old = next(x for x in p['relation_results'] if x['atom_id'] == v.relation.MEMORY_ID)
            assert old['state'] == by_id[p['sample_id']]['conditions']['R_REL']['state']
            checked += 1
    for r in result:
        if r['sample_id'] in original_models:
            r['saved_full_model_decisions'] = original_models[r['sample_id']]
    save_rows(out/'historical.jsonl.gz', result)
    write(out/'HISTORICAL_EXECUTION.json', {'planned':1269,'processed':len(result),'relation_saved_state_checks':checked,
          'controlled_unique':len(ids),'mtc_unique':len(mtc_ids),'model_fit_calls':0,
          'normal_basis_reference':config['baseline_mtc_predictions'],'source_issues':issues})
    print('Historical fixed-condition evaluation:',len(result), 'records;',checked,'saved relation-state matches',flush=True)


def fixed_models(settings):
    result = []
    for entry in settings['saved_models']:
        engine = base if entry['scheme'] == 'B' else extended
        model = engine.load_model(ROOT/entry['path'])
        assert model.model_id == entry['model_id']
        result.append((entry, engine, model))
    assert len(result) == 6
    return result


def models_current(models, sid, adapted, bound):
    result=[]
    for entry, engine, model in models:
        prediction = engine.predict_current(model, sid, adapted['raw'])
        rules = prior.rule_rows(model, prediction, adapted)
        for rule in rules:
            atom = next(a for a in model.atoms if a.atom_id == rule['atom_id'])
            refs = atom.provenance.get('field_refs', [atom.provenance.get('field')])
            rule['current_raw_fields'] = {f:deepcopy(bound['features'].get(f)) for f in refs}
        result.append({**entry, 'decision':prediction['decision'], 'rules':rules,
                       'triggered_rules':[r['clause_id'] for r in rules if r['state']=='T']})
    return result


def new_batch(out):
    settings=read(out/'SETTINGS.json'); models=fixed_models(settings)
    result=[]
    for env in settings['environments']:
        eid=env['environment_group_id']; run=out/'runs'/eid
        operations={o['step_id']:o for o in rows(run/'operations.jsonl')}
        archive=run/'backend/raw_expanded_payloads.jsonl'
        raw_index=defaultdict(list)
        for lineno, raw in enumerate(rows(archive),1):
            raw_index[raw.get('session_id')].append((lineno,raw))
        for target in settings['targets_gib']:
            for number in range(1,settings['rounds']+1):
                for phase in settings['phases']:
                    step=f'memory-{target}-r{number}-{phase}'; op=operations.get(step,{})
                    sid=op.get('session_id'); matches=raw_index.get(sid,[]) if sid else []
                    common={'dataset':'memory_only','environment':eid,'target_gib':target,'round':number,'phase':phase,
                            'step_id':step,'operation':op or {'status':'NOT_EXECUTED'}}
                    try:
                        if len(matches)!=1:
                            raise ValueError('PLANNED_CURRENT_RAW_RECORD_MISSING_OR_AMBIGUOUS')
                        lineno,raw=matches[0]
                        ref=f'{archive.relative_to(ROOT) if archive.is_relative_to(ROOT) else archive}:{lineno}'
                        bound=v.bind_memory_batch(raw,session_id=sid,source_reference=ref,
                                      environment_id='memory-validation-'+eid)
                        row=record('memoryonly-'+sid,bound,**common)
                        try:
                            _,adapted=v.adapt_memory_batch(raw,session_id=sid,source_reference=ref,
                                      environment_id='memory-validation-'+eid)
                            row['models']=models_current(models,row['sample_id'],adapted,bound)
                        except Exception as exc:
                            row['model_input_error']=type(exc).__name__+': '+str(exc)
                            row['models']=[{**entry,'decision':'FAILED','reason':str(exc),'rules':[],'triggered_rules':[]}
                                           for entry,_,_ in models]
                        # Comparison-only observables: no phase/target/label in predictor.
                        row['major_non_target_fields']={f:deepcopy(value) for f,value in bound['features'].items()
                            if f.startswith(('app.web_data.navigator_layer.','app.web_data.screen_layer.',
                               'app.web_data.graphics_layer.','app.web_data.automation_surface_layer.')) and f!=v.WEB}
                        row['major_non_target_fields'].update({f:deepcopy(value) for f,value in bound['features'].items()
                            if f.startswith('app.web_data.execution_layer.timezone_') or f==v.NATIVE})
                    except Exception as exc:
                        row=record('unavailable:'+eid+':'+step, {'status':'FAILED','errors':[str(exc)]},**common)
                        row['models']=[{**entry,'decision':'FAILED','reason':str(exc),'rules':[],'triggered_rules':[]}
                                       for entry,_,_ in models]
                    result.append(row)
    save_rows(out/'new_batch.jsonl.gz', result)
    print('New batch planned positions evaluated:',len(result),flush=True)


def counts(data, name):
    c=Counter(r['conditions'][name]['state'] for r in data)
    return {'n':len(data), **{s:c[s] for s in ('T','F','U','FAILED')},
            'evaluable':c['T']+c['F'], 'evaluable_ratio':(c['T']+c['F'])/len(data) if data else None}


def comparison(data):
    both=[r for r in data if all(c['state'] in ('T','F') for c in r['conditions'].values())]
    hist=Counter(str(r['operands'][v.WEB]['value']) for r in data)
    normal=[r for r in data if r.get('normal_basis') is True or
            isinstance(r.get('normal_basis'),dict) and r['normal_basis'].get('supported') is True]
    joint=Counter(r['conditions']['R_REL']['state']+'/'+r['conditions']['R_WEB8']['state'] for r in data)
    return {'planned_n':len(data),'conditions':{n:counts(data,n) for n in ('R_REL','R_WEB8')},
            'common_evaluable':{'n':len(both),'conditions':{n:counts(both,n) for n in ('R_REL','R_WEB8')}},
            'joint_states':dict(joint), 'both_triggered':joint['T/T'],
            'only_relation_triggered_common_evaluable':joint['T/F'],
            'only_web8_triggered_common_evaluable':joint['F/T'],
            'normal_basis_supported':{'n':len(normal),'conditions':{n:counts(normal,n) for n in ('R_REL','R_WEB8')}},
            'web_value_distribution':dict(hist),
            'disagreement_ids':[r['sample_id'] for r in data if r['conditions']['R_REL']['state']!=r['conditions']['R_WEB8']['state']]}


def summary(out):
    old=rows(out/'historical.jsonl.gz');new=rows(out/'new_batch.jsonl.gz')
    result={'historical':{},'new_batch':{},'model_fit_calls':0}
    if old:
        for dataset,subset in [('controlled','all'),('controlled','attack'),('controlled','normal'),
                               ('mtc','discovery'),('mtc','development'),('mtc','reserved_validation')]:
            group=[r for r in old if r['dataset']==dataset and (subset=='all' or
                   subset=='normal' and r['subset']!='attack' or r['subset']==subset)]
            result['historical'][dataset+'/'+subset]=comparison(group)
        configs=sorted({r['config_id'] for r in old if r['dataset']=='controlled'})
        result['historical']['attack_configurations']={c:comparison([r for r in old if r['dataset']=='controlled'
                                        and r['subset']=='attack' and r['config_id']==c]) for c in configs}
        gains=[r for r in old if r.get('saved_full_model_decisions',{}).get('B')!='MANIPULATION_ALERT'
              and r.get('saved_full_model_decisions',{}).get('B_REL')=='MANIPULATION_ALERT']
        result['historical']['saved_B_REL_additional_detections']=comparison(gains)
        result['historical']['normal_W4_W8_examples']={str(w):[r for r in old if r['dataset']=='mtc'
            and r['operands'][v.WEB]['value']==w and r['conditions']['R_REL']['state']=='F'][:3] for w in (4,8)}
        saved=rows(ROOT/'deliverables/mtc_relation_extension_v1/predictions.jsonl.gz')
        context={}
        for p in saved:
            if p['dataset']=='mtc':
                key='/'.join((p['scheme'],p['fold_id'],p['subset']))
                context.setdefault(key,Counter())[p['decision']]+=1
        result['historical']['saved_full_model_mtc_context']={k:dict(c) for k,c in context.items()}
    if new:
        settings=read(out/'SETTINGS.json')
        expected={(env['environment_group_id'],w,r,p) for env in settings['environments']
                  for w in settings['targets_gib'] for r in range(1,settings['rounds']+1) for p in settings['phases']}
        actual=[(r['environment'],r['target_gib'],r['round'],r['phase']) for r in new]
        if len(actual)!=len(expected) or set(actual)!=expected:
            raise ValueError('SAVED_NEW_BATCH_MUST_RETAIN_ALL_PLANNED_POSITIONS')
        result['new_batch']['all']=comparison(new)
        result['new_batch']['native_web_examples']=[{k:r[k] for k in
            ('sample_id','environment','target_gib','operands','conditions','source_binding')}
            for r in new if r['phase']=='attack' and r['target_gib']==8 and r['round']==1]
        result['new_batch']['major_non_target_field_count']=max(len(r.get('major_non_target_fields',{})) for r in new)
        result['new_batch']['hardware_concurrency_values']=sorted({r.get('major_non_target_fields',{}).get(
            'app.web_data.navigator_layer.hardware_concurrency') for r in new}, key=str)
        result['new_batch']['by_environment_target_phase']={}
        for key in sorted({(r['environment'],r['target_gib'],r['phase']) for r in new}):
            result['new_batch']['by_environment_target_phase']['/'.join(map(str,key))]=comparison(
                [r for r in new if (r['environment'],r['target_gib'],r['phase'])==key])
        triplets=[]
        for key in sorted({(r['environment'],r['target_gib'],r['round']) for r in new}):
            members={r['phase']:r for r in new if (r['environment'],r['target_gib'],r['round'])==key}
            pre,active,post=(members[p] for p in ('clean_pre','attack','clean_post'))
            effect=v.intervention_effect(pre,active,post,active['operation'] if active['operation'].get('status')!='NOT_EXECUTED' else None)
            fields=sorted(set(pre.get('major_non_target_fields',{})) | set(active.get('major_non_target_fields',{})) | set(post.get('major_non_target_fields',{})))
            diffs={f:[r.get('major_non_target_fields',{}).get(f) for r in (pre,active,post)] for f in fields
                   if any(r.get('major_non_target_fields',{}).get(f)!=pre.get('major_non_target_fields',{}).get(f) for r in (active,post))}
            comparable=all('major_non_target_fields' in r and r['major_non_target_fields'] for r in (pre,active,post))
            triplets.append({'environment':key[0],'target_gib':key[1],'round':key[2],**effect,
                   'confounded':bool(diffs) if comparable else None,
                   'confound_status':('DIFFERENCE_OBSERVED' if diffs else 'NO_OBSERVED_NON_TARGET_CHANGE') if comparable else 'NOT_EVALUABLE',
                   'non_target_differences':diffs,
                   'active_conditions':{n:c['state'] for n,c in active['conditions'].items()},
                   'active_sample_id':active['sample_id']})
        result['new_batch']['triplets']=triplets
        result['new_batch']['effect_counts']={key:dict(Counter(t[key] for t in triplets)) for key in ('execution','effect','recovery','confound_status')}
        result['new_batch']['normal_phases']=comparison([r for r in new if r['phase']!='attack'])
        for label,predicate in [('observable_changes',lambda t:t['effect_positive']),
                                ('observable_unconfounded',lambda t:t['effect_positive'] and t['confound_status']=='NO_OBSERVED_NON_TARGET_CHANGE'),
                                ('no_observable_effect',lambda t:t['effect']=='NO_OBSERVABLE_EFFECT')]:
            wanted={t['active_sample_id'] for t in triplets if predicate(t)}
            selected=[r for r in new if r['sample_id'] in wanted]
            result['new_batch'][label]=comparison(selected)
        result['new_batch']['models']={}
        for entry in read(out/'SETTINGS.json')['saved_models']:
            mid=entry['model_id']; model_stats={}
            for label,group in [('all',new),('normal',[r for r in new if r['phase']!='attack']),
                ('active_attempts',[r for r in new if r['phase']=='attack']),
                ('observable_changes',[r for r in new if any(t['active_sample_id']==r['sample_id'] and t['effect_positive'] for t in triplets)])]:
                states=Counter(next(m for m in r['models'] if m['model_id']==mid)['decision'] for r in group)
                model_stats[label]={'n':len(group),'decisions':dict(states),
                  'explicit':states['NO_ALERT']+states['MANIPULATION_ALERT']}
            result['new_batch']['models'][mid]={**entry,'subsets':model_stats}
        result['new_batch']['triggered_rule_ids_by_scheme']={scheme:sorted({t for r in new for m in r['models']
            if m['scheme']==scheme for t in m['triggered_rules']}) for scheme in ('B','B_REL')}
    write(out/'summary.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('historical','new','summarize'))
    parser.add_argument('--output-dir',type=Path,default=HERE)
    args=parser.parse_args();out=args.output_dir.resolve()
    if args.command=='historical': historical(out)
    if args.command=='new': new_batch(out)
    summary(out)
    from report import render
    render(out)


if __name__=='__main__':main()
