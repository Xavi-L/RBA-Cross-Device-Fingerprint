#!/usr/bin/env python3
"""Six fixed B_REL_TZ fits; saved B_REL is never refitted."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


prior = module('saved_mtc_runner_helpers', ROOT/'deliverables/mtc_constrained_reselection_v1/run_experiment.py')
read, write, stamp = prior.read, prior.write, prior.stamp


def config(out):
    if not (out/'SETTINGS.json').exists(): write(out/'SETTINGS.json', read(HERE/'SETTINGS.json'))
    new = read(out/'SETTINGS.json')
    if new != read(HERE/'SETTINGS.json'):
        raise ValueError('FIXED_RELATION_SETTINGS_CHANGED')
    parent = read(ROOT/new['membership_and_baseline_settings'])
    return new, parent


def modules():
    from hybridguard_agent.research import mtc_timezone_candidates as adapter
    from hybridguard_agent.research import timezone_relation_sources as sources
    from hybridguard_agent.research import mtc_timezone_selection as engine
    return adapter, sources, engine


def split_inputs(adapted, relation_ids):
    relations = set(relation_ids)
    old = {sid: {k:v for k,v in item['raw'].items() if k not in relations} for sid,item in adapted.items()}
    new = {sid: {k:v for k,v in item['raw'].items() if k in relations} for sid,item in adapted.items()}
    return old, new


def load_mtc(parent, ids):
    index = prior.registry(parent)
    observations, issues = prior.load_selected_mtc(index, ids, ROOT/parent['mtc_snapshot'], allowed_ids=ids)
    if issues:
        raise ValueError('FROZEN_BASE_MTC_INPUT_UNREADABLE:' + json.dumps(issues))
    return index, observations


def relation_results(adapted):
    adapter, _, _ = modules()
    return [{'atom_id': atom.atom_id, **adapted['candidate_inputs'][atom.atom_id]}
            for atom in adapter.registered_atoms()]


def relation_diagnostics(adapted, metadata, normal=False):
    adapter, _, _ = modules()
    result = {}
    for atom in adapter.registered_atoms():
        aid = atom.atom_id
        counts, reasons, examples = Counter(), Counter(), {'T': [], 'F': [], 'U': [], 'FAILED': []}
        by_phase, by_config = {}, {}
        for sid,item in adapted.items():
            info = item['candidate_inputs'][aid]
            state = info['state']; counts[state] += 1; reasons[info['reason']] += 1
            if len(examples[state]) < 3:
                examples[state].append({'sample_id':sid, 'fields':info['fields'],
                    'reason':info['reason'], 'diagnostics':info['diagnostics'],
                    'source_binding':info['source_binding'],
                    'profile':metadata[sid].get('profile') if normal else None})
            if not normal:
                m=metadata[sid]
                by_phase.setdefault(m['phase'],Counter())[state] += 1
                if m['phase']=='attack': by_config.setdefault(m['config_id'],Counter())[state] += 1
        result[aid]={'records':len(adapted),'states':dict(counts),'reasons':dict(reasons),
            'by_phase':by_phase,'attack_configurations':by_config,'examples':examples}
    return result


def train(out):
    adapter, sources, engine = modules()
    from hybridguard_agent.research import mtc_reselection_candidates as old
    from hybridguard_agent.research import mtc_relation_selection as baseline
    new, parent = config(out)
    if (out/'FIT_CALLS.jsonl').exists(): raise FileExistsError('Use a new output directory; no automatic refits')
    write(out/'RELATIONS.json', adapter.registry())
    train_ids = parent['mtc_normal_train_ids']
    eval_ids = parent['mtc_primary_ids']['development'] + parent['mtc_primary_ids']['reserved_validation']
    index, observations = load_mtc(parent, train_ids)
    basis = prior.normal_evidence(parent)
    if any(index[sid]['split']!='discovery' or not basis[sid]['supported'] for sid in train_ids):
        raise PermissionError('ONLY_PRESPECIFIED_NORMAL_DISCOVERY_TRAIN')
    if ({index[sid]['group_id'] for sid in train_ids} & {index[sid]['group_id'] for sid in eval_ids}):
        raise PermissionError('MTC_GROUP_CROSSES_TRAIN_EVALUATION')
    mtc_bound = sources.load_mtc_sources(observations, index, train_ids, allowed_ids=train_ids)
    mtc_adapted = {sid:adapter.adapt_mtc(observations[sid],mtc_bound[sid]) for sid in train_ids}
    atoms = adapter.registered_atoms(); ids = [a.atom_id for a in atoms]
    mtc_old, mtc_rel = split_inputs(mtc_adapted,ids)
    mtc_meta={sid:{'split':'discovery','normal_basis':True,'group_id':index[sid]['group_id']} for sid in train_ids}
    saved_baseline = read(ROOT/new['baseline_models'])['models']
    entries, events, diagnostics = [], [], {'mtc_discovery':relation_diagnostics(mtc_adapted,index,True),'folds':{}}
    start=time.monotonic()
    with (out/'FIT_CALLS.jsonl').open('x') as log:
        for fold in parent['folds']:
            fid=fold['fold_id']; allowed=fold['train_ids']
            current=prior.controlled_rows(ROOT/parent['controlled_source'],allowed,allowed)
            bound=sources.load_controlled_sources(allowed,allowed_ids=allowed)
            adapted={sid:adapter.adapt_controlled(current[sid],bound[sid]) for sid in allowed}
            raw, rel=split_inputs(adapted,ids)
            meta=prior.controlled_metadata(ROOT/parent['controlled_source'],allowed)
            diagnostics['folds'][fid]=relation_diagnostics(adapted,meta)
            old_entry=next(m for m in saved_baseline if m['scheme']=='B_REL' and m['fold_id']==fid and m['stage']=='RETENTION')
            saved=baseline.load_model(ROOT/Path(new['baseline_models']).parent/old_entry['path'])
            prepared=engine.prepare_fold(fold,raw,meta,old.definitions(),mtc_old,mtc_meta,rel,mtc_rel,
                atoms,adapter.parameters(),mtc_train_ids=train_ids,mtc_evaluation_ids=eval_ids,
                expected_old_encoder=saved.encoder)
            write(out/'folds'/fid/'encoder.json',prepared.common.encoder)
            write(out/'folds'/fid/'relation_parameters.json',prepared.relation_parameters)
            initial,initial_training=None,None
            for stage in new['new_fit_stages']:
                event={'fold_id':fid,'stage':stage,'started_at':stamp(),'attempt':1}
                log.write(json.dumps(event)+'\n'); log.flush()
                model,detail=engine.fit(prepared,stage=stage,initial_model=initial,initial_training=initial_training)
                dest=out/'trials'/('B_REL_TZ__'+fid+'__'+stage);dest.mkdir(parents=True,exist_ok=False)
                engine.save_model(model,dest/'model.json');write(dest/'training.json',detail)
                loaded=engine.load_model(dest/'model.json')
                if loaded.model_id != model.model_id or loaded.encoder != saved.encoder:
                    raise ValueError('ROUNDTRIP_OR_OLD_ENCODER_CHANGED')
                entries.append({'scheme':'B_REL_TZ','fold_id':fid,'stage':stage,'model_id':loaded.model_id,
                    'status':loaded.status,'rule_count':len(loaded.clauses),
                    'selected_clauses':[asdict(c) for c in loaded.clauses],
                    'path':str((dest/'model.json').relative_to(out)),
                    'training_path':str((dest/'training.json').relative_to(out)),
                    'train_score':loaded.fit['training_result'],'closed_at':stamp()})
                events.append({**event,'model_id':loaded.model_id,'status':loaded.status,'closed_at':stamp()})
                if stage=='SPARSE': initial,initial_training=loaded,detail
                print(json.dumps({'fold':fid,'stage':stage,'status':loaded.status,'rules':len(loaded.clauses)}),flush=True)
    write(out/'RELATION_TRAIN_DIAGNOSTICS.json',diagnostics)
    write(out/'models.json',{'models':entries,'baseline_models_ref':new['baseline_models']})
    write(out/'EXECUTION.json',{'all_fits_closed':True,'planned_fit_calls':6,'actual_fit_calls':len(events),
        'encoder_fit_calls':3,'relation_parameter_fit_calls':0,'fits':events,
        'all_models_frozen_at':stamp(),'elapsed_seconds':time.monotonic()-start,
        'old_encoders_equal_saved_B_REL':True,'new_mtc_evaluation_opened_during_training':False,
        'mtc_evaluation_ids_used_for_fit':[],'engineering_reruns':0,
        'source_binding_errors':{'mtc_discovery':{sid:r['errors'] for sid,r in mtc_bound.items() if r['status']!='OK'}}})


    write(out/'MODELS_FROZEN.json', {'status':'FROZEN','actual_fit_calls':len(events),
        'frozen_at':stamp(), 'baseline_model_ids':[m['model_id'] for m in saved_baseline if m['stage']=='RETENTION'],
        'new_model_ids':[m['model_id'] for m in entries if m['stage']=='RETENTION'],
        'parameters':adapter.parameters(), 'all_models_fitted':all(m['status']=='FITTED' for m in entries)})


def evaluation_ready(out):
    new,parent=config(out)
    execution=read(out/'EXECUTION.json'); manifest=read(out/'models.json')['models']
    expected={(f['fold_id'],stage) for f in parent['folds'] for stage in new['new_fit_stages']}
    actual={(m['fold_id'],m['stage']) for m in manifest}
    if not execution.get('all_fits_closed') or execution['actual_fit_calls']!=6 or len(manifest)!=6 or expected!=actual:
        raise PermissionError('ALL_SIX_B_REL_FITS_MUST_CLOSE_BEFORE_EVALUATION')
    if len(list(prior.jsonl(out/'FIT_CALLS.jsonl')))!=6:
        raise PermissionError('SIX_RECORDED_FIT_INVOCATIONS_REQUIRED')
    return new,parent,manifest


def evaluate(out):
    new,parent,manifest=evaluation_ready(out)
    adapter,sources,engine=modules()
    if (out/'predictions.jsonl.gz').exists(): raise FileExistsError('Use summarize on saved predictions')
    opened=stamp()
    subset_ids=parent['mtc_primary_ids']; mtc_ids=[sid for ids in subset_ids.values() for sid in ids]
    index,observations=load_mtc(parent,mtc_ids)
    basis=prior.normal_evidence(parent)
    bound=sources.load_mtc_sources(observations, index, mtc_ids, allowed_ids=mtc_ids)
    mtc_adapted={sid:adapter.adapt_mtc(observations[sid],bound[sid]) for sid in mtc_ids}
    subset_of={sid:s for s,ids in subset_ids.items() for sid in ids}
    with gzip.open(ROOT/new['baseline_predictions'],'rt') as stream:
        old={(r['fold_id'],r['sample_id']):r for line in stream for r in [json.loads(line)]
             if r['scheme']=='B_REL' and (r['dataset']=='controlled' or r['subset'] in subset_ids)}
    processed=0; errors={'mtc':{sid:r['errors'] for sid,r in bound.items() if r['status']!='OK'},'controlled':{}}
    with gzip.open(out/'predictions.jsonl.gz','xt',encoding='utf-8') as stream:
        for fold in parent['folds']:
            fid=fold['fold_id']; ids=fold['outer_test_ids']
            current=prior.controlled_rows(ROOT/parent['controlled_source'],ids,ids)
            current_bound=sources.load_controlled_sources(ids,allowed_ids=ids)
            errors['controlled'].update({sid:r['errors'] for sid,r in current_bound.items() if r['status']!='OK'})
            adapted={sid:adapter.adapt_controlled(current[sid],current_bound[sid]) for sid in ids}
            metadata=prior.controlled_metadata(ROOT/parent['controlled_source'],ids)
            selected=next(m for m in manifest if m['fold_id']==fid and m['stage']=='RETENTION')
            model=engine.load_model(out/selected['path'])
            expected={(fid,sid) for sid in ids+mtc_ids}
            if {key for key in old if key[0]==fid}!=expected:
                raise ValueError('BASELINE_B_SAVED_MEMBERS_MISMATCH')
            for sid in ids+mtc_ids:
                original=old[fid,sid]
                stream.write(json.dumps(original,ensure_ascii=False,separators=(',',':'))+'\n');processed+=1
                item=adapted[sid] if sid in adapted else mtc_adapted[sid]
                pred=engine.predict_current(model,sid,item['raw'])
                rules=prior.rule_rows(model,pred,item)
                for rule in rules:
                    info=item['candidate_inputs'].get(rule['atom_id'],{})
                    if 'diagnostics' in info: rule['diagnostics']=info['diagnostics']
                shared={k:v for k,v in original.items() if k not in (
                    'scheme','fold_id','model_id','sample_id','dataset','subset','decision','logical_state',
                    'model_status','failure_reason','rules','triggered_rules','saved_baseline_reused')}
                shared.update(saved_baseline_reused=False,relation_results=relation_results(item),
                    relation_source_status=item['relation_source_status'],relation_source_errors=item['relation_source_errors'],
                    adapter_version=adapter.VERSION)
                prior.emit_prediction(stream,scheme='B_REL_TZ',fold=fid,model=model,prediction=pred,rules=rules,
                    sid=sid,dataset=original['dataset'],subset=original['subset'],metadata=shared)
                processed+=1
    write(out/'EVALUATION.json',{'opened_at':opened,'closed_at':stamp(),
        'after_all_models_frozen_at':read(out/'EXECUTION.json')['all_models_frozen_at'],
        'predictions_saved':processed,'baseline_new_prediction_calls':0,
        'baseline_saved_rows_reused':len(old),'new_prediction_calls':processed-len(old),
        'source_binding_errors':errors,'extra_fit_calls':0,'evaluation_used_for_selection':False})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('train','evaluate','run','summarize'))
    parser.add_argument('--output-dir',type=Path,default=HERE)
    args=parser.parse_args();out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    if args.command in ('train','run'): train(out)
    if args.command in ('evaluate','run'): evaluate(out)
    if args.command in ('evaluate','run','summarize'):
        from summarize import summarize
        summarize(out)


if __name__=='__main__': main()
