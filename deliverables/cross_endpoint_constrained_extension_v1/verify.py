#!/usr/bin/env python3
"""Independent arithmetic and actual current-input replay after selection has frozen."""
import argparse,collections,copy,os,sys
from fractions import Fraction
from common import *
import adapter as a
from inference import predict_current
from prepare_current import v16_pair,mtc_app,pair_inputs

def verify(directory):
    out=Path(directory).resolve();models=read(out/'models.json');members=rows(out/'members.jsonl');inputs=unique(rows(out/'inputs.jsonl'),lambda r:r['sample_id'])
    preds=unique(rows(out/'predictions.jsonl'),lambda r:(r['sample_id'],r['model_id']))
    checks=read(out/'candidate_checks.json');calls=collections.Counter();replay=[]
    def guard(event,args):
        if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.posix_spawn'):raise RuntimeError('VERIFY_FORBIDDEN:'+event)
        if event=='open':
            path,mode,flags=args
            if not isinstance(path,int) and (flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and not Path(os.fsdecode(path)).resolve().is_relative_to(out):raise RuntimeError('VERIFY_WRITE_OUTSIDE_OUTPUT')
    def profile(frame,event,arg):
        if event!='call':return
        name=frame.f_code.co_name;path=frame.f_code.co_filename
        if not path.startswith(str(ROOT)):return
        if name=='fit' or name.startswith('fit_') or name in ('train','prepare_fold','collect') or path==str(HERE/'selector.py') and name in ('select','score'):raise RuntimeError('NO_FIT_OR_RESELECTION_DURING_VERIFY')
        if path.endswith('/mtc_timezone_selection.py') and name=='predict_current':calls['raw_app_predictions']+=1
        if path==str(a.b2a.HERE/'conditions.py') and name=='evaluate':calls['raw_selected_condition_predictions']+=1
    sys.addaudithook(guard);sys.setprofile(profile)
    # Independent recombination and exact fractional objective for every candidate member.
    selections=unique(rows(out/'candidate_outputs.jsonl'),lambda r:(r['base_model_id'],r['set_id'],r['sample_id']))
    train=[m for m in members if m['role']=='selection']
    for c in checks:
        states={}
        for m in train:
            sid=m['sample_id'];row=inputs[sid];ss=[row['base_states'][c['base_model_id']]]+[row['conditions'][k] for k in c['extensions']]
            expected='FAILED' if 'FAILED' in ss else 'T' if 'T' in ss else 'U' if 'U' in ss else 'F'
            require(selections[c['base_model_id'],c['set_id'],sid]['state']==expected,'INDEPENDENT_CANDIDATE_OR')
            states[sid]=expected
        objective=sum(Fraction(sum(states[m['sample_id']]=='T' for m in train if m['identity']=='EFFECTIVE_INTERVENTION' and m['family']==f),sum(m['identity']=='EFFECTIVE_INTERVENTION' and m['family']==f for m in train)) for f in ('App_language','App_timezone','Browser_language','Browser_timezone'))/4
        require(objective==Fraction(c['macro']['numerator'],c['macro']['denominator']),'OBJECTIVE_MISMATCH')
        violations=[]
        for co,n,b in [('mtc_discovery',630,31),('pilot18',12,0),('b2b42',34,1)]:
            actual=collections.Counter(states[m['sample_id']] for m in train if m['cohort']==co and m['identity']=='NORMAL')
            require(sum(actual.values())==n,'ORACLE_NORMAL_N')
            require(all(c['normals'][co][s]==actual[s] for s in STATES),'ORACLE_NORMAL_STATES')
            if actual['T']>b:violations.append('NORMAL_ALARM_BUDGET:'+co)
            if actual['T']+actual['F']<Fraction(9*n,10):violations.append('MODEL_DEFINED_COVERAGE:'+co)
        for cid in c['extensions']:
            ss=[inputs[m['sample_id']]['conditions'][cid] for m in train if m['cohort']=='mtc_discovery']
            if sum(s in ('T','F') for s in ss)<567:violations.append('CANDIDATE_COVERAGE:'+cid)
        if c['rule_count']>8:violations.append('RULE_BUDGET')
        if c['complexity']>16:violations.append('COMPLEXITY_BUDGET')
        require(set(violations)==set(c['reasons']) and (not violations)==c['feasible'],'FEASIBILITY_MISMATCH')
    for model in models:
        feasible=[c for c in checks if c['base_model_id']==model['base_model_id'] and c['feasible']]
        best=sorted(feasible,key=lambda c:(-Fraction(c['macro']['numerator'],c['macro']['denominator']),len(c['extensions']),c['order']))[0]
        require(best['set_id']==model['selected_set'],'WINNER_NOT_OPTIMAL_IN_FIXED_POOL')
    def check(sid,app,pair):
        for model in models:
            actual=predict_current(model,app,pair);saved=preds[sid,model['model_id']]
            require(actual['state']==saved['state'] and actual['base_state']==saved['base_state'],'CURRENT_PAIR_REPLAY_MISMATCH:'+sid)
            require({k:v['state'] for k,v in actual['selected_conditions'].items()}==saved['selected_conditions'],'SELECTED_CONDITION_MISMATCH')
            replay.append(dict(sample_id=sid,model_id=model['model_id'],base_state=actual['base_state'],state=actual['state'],equal_saved=True))
    # All 60 operation-verified pairs: original private/public raw, no trajectory input.
    for member in members:
        if member['cohort'] not in ('pilot18','b2b42'):continue
        meta=member['source_meta']
        def physical(reference):
            name,n=reference.rsplit(':',1)
            return json.loads((ROOT/name).read_bytes().splitlines()[int(n)-1])
        app=physical(meta['app_reference']);browser=physical(meta['browser_reference'])
        if member['cohort']=='b2b42':provenance=physical(meta['provenance_reference'])
        else:
            provenance_rows=rows(a.b2a.B1/'evidence_archive/data/browser_pair_provenance.jsonl')
            matches=[p for p in provenance_rows if p.get('pair_id')==browser['pair_id']]
            require(len(matches)==1,'PILOT_PROVENANCE');provenance=matches[0]
        app_input,pair=v16_pair(app,browser,provenance,meta['app_reference'])
        require(not pair['errors'],'NEW_CURRENT_BINDING_FAILURE:'+str(pair['errors']))
        check(member['sample_id'],app_input,pair)
    # Original MTC App fields plus original time evidence; preserves legacy quality.
    registry=a.b2a.mtc_members();observations={n:r for n,r,e in a.b2a.rows(a.b2a.MTC/'paired_244.jsonl',{r['source_line'] for _,r in registry}) if not e}
    raw={n:r for n,r,e in a.b2a.rows(a.b2a.RAW/'raw_expanded_payloads.jsonl',{r['app_raw_line'] for _,r in registry}) if not e}
    bound_pairs={i['meta']['sample_id']:i['pair'] for i in a.b2a.mtc(registry)}
    for _,r in registry:
        app=mtc_app(observations[r['source_line']],r,raw[r['app_raw_line']],ref(a.b2a.RAW/'raw_expanded_payloads.jsonl',r['app_raw_line']))
        check(r['sample_id'],app,pair_inputs(bound_pairs[r['sample_id']]))
    sys.setprofile(None)
    require(len(replay)==2853 and calls['raw_app_predictions']==2853 and calls['raw_selected_condition_predictions']==2853,'REPLAY_COUNTS')
    jsonl(out/'current_input_replay.jsonl',replay)
    result=dict(status='PASSED',current_input_positions=951,current_model_predictions=2853,**dict(calls),
        current_input_basis={'v16_archive_pairs':60,'mtc_legacy_p1_app_plus_time_raw':891},
        independent_candidate_member_OR_checks=len(selections),independent_feasibility_objective_checks=12,
        winner_checks=3,new_selection_calls=0,new_app_fit_calls=0,encoder_fit_calls=0,collection_calls=0,
        independent_sample_multiplier=1,all_current_outputs_equal_saved_combinations=True)
    write(out/'REPLAY_VERIFICATION.json',result);print(result)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);verify(p.parse_args().directory)
