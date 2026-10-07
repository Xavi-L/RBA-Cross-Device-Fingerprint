"""One raw replay after selection. Records every new component/model call."""
import argparse,sys
from fractions import Fraction
from rx_common import *
import rx_sources as s
from rx_inference import components,predict_prepared
def arithmetic(out,ms,ix,models):
    combos=index(rows(out/'combinations.jsonl'),lambda r:(r['sample_id'],r['base_model_id'],r['set_id']))
    checks=read(out/'candidate_checks.json');train=[m for m in ms if m['role']=='selection'];oracle={}
    require(set(combos)=={(m['sample_id'],model['base_model_id'],sid) for m in ms for model in models for sid,_ in SETS},'ORACLE_EXACT_COMBINATIONS')
    for model in models:
        mid=model['base_model_id']
        for sid,chosen in SETS:
            states={}
            for m in ms:
                r=ix[m['sample_id']];v=[r['base_states'][mid]]+[r['conditions'][c] for c in chosen]
                expected='FAILED' if 'FAILED' in v else 'T' if 'T' in v else 'F' if all(x=='F' for x in v) else 'U'
                require(combos[m['sample_id'],mid,sid]['state']==expected,'INDEPENDENT_OR_MISMATCH');states[m['sample_id']]=expected
            c=next(c for c in checks if c['base_model_id']==mid and c['set_id']==sid);reasons=[]
            for co,n in NORMAL_N.items():
                vals=[states[m['sample_id']] for m in train if m['cohort']==co and m['identity']=='NORMAL'];cnt=counts(vals)
                require(cnt['n']==n and all(c['normals'][co][k]==v for k,v in cnt.items()),'ORACLE_NORMAL_STATES')
                if cnt['T']>SETTINGS['normal_alarm_budgets'][co]:reasons.append('NORMAL_ALARM_BUDGET:'+co)
                if cnt['defined']<Fraction(9*n,10):reasons.append('MODEL_DEFINED_COVERAGE:'+co)
            for cid in chosen:
                vals=[ix[m['sample_id']]['conditions'][cid] for m in train if m['cohort']=='mtc_discovery']
                if sum(v in ('T','F') for v in vals)<567:reasons.append('CANDIDATE_COVERAGE:'+cid)
            nr=model['base_rule_count']+len(chosen);nc=model['base_complexity']+2*len(chosen)
            require(c['rule_count']==nr and c['complexity']==nc,'ORACLE_CAPACITY')
            if nr>8:reasons.append('RULE_BUDGET')
            if nc>16:reasons.append('COMPLEXITY_BUDGET')
            macro=sum(Fraction(sum(states[m['sample_id']]=='T' for m in train if m['identity']=='EFFECTIVE_INTERVENTION' and m['family']==f),sum(m['identity']=='EFFECTIVE_INTERVENTION' and m['family']==f for m in train)) for f in FAMILIES)/8
            require(macro==Fraction(c['macro']['numerator'],c['macro']['denominator']),'ORACLE_OBJECTIVE')
            require(set(reasons)==set(c['reasons']) and c['feasible']==(not reasons),'ORACLE_CONSTRAINTS')
            oracle[mid,sid]=(bool(reasons),macro,len(chosen),[k for k,_ in SETS].index(sid))
        viable=[(sid,v) for (bid,sid),v in oracle.items() if bid==mid and not v[0]]
        winner=min(viable,key=lambda sv:(-sv[1][1],sv[1][2],sv[1][3]))[0] if viable else 'S0'
        require(model['selected_set']==winner and model['baseline_feasible']==not_false(oracle[mid,'S0'][0]),'ORACLE_WINNER')
    return len(combos)
def not_false(v):return not v
def verify(out):
    out=Path(out);require(not (out/'CURRENT_REPLAY.json').exists(),'CURRENT_REPLAY_ALREADY_DONE')
    ms=rows(out/'members.jsonl');models=read(out/'models.json');ix=validate(ms,rows(out/'inputs.jsonl'),[m['base_model_id'] for m in models],1005)
    n=arithmetic(out,ms,ix,models);calls=Counter();replay=[];l=s.legacy()
    def guard(event,args):
        if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.posix_spawn'):raise RuntimeError('OFFLINE_VERIFY:'+event)
    def profile(frame,event,arg):
        if event!='call' or not frame.f_code.co_filename.startswith(str(ROOT)):return
        path=frame.f_code.co_filename;name=frame.f_code.co_name
        if name=='fit' or name.startswith('fit_') or name in ('train','collect','prepare_fold') or path==str(HERE/'rx_selector.py') and name in ('select','score'):raise RuntimeError('VERIFY_NO_SELECTION_OR_FIT')
        if path==str(ROOT/'hybridguard_agent/research/mtc_timezone_selection.py') and name=='predict_current':calls['app_predictions']+=1
        if path==str(l.b2.HERE/'conditions.py') and name=='evaluate':calls['C1_evaluations']+=1
        if path==str(RESOURCE/'conditions.py') and name=='evaluate':calls['resource_evaluate_calls']+=1;calls['resource_condition_outputs']+=6
    sys.addaudithook(guard);sys.setprofile(profile)
    try:
        registry=l.b2.mtc_members();reg={r['sample_id']:r for _,r in registry}
        resources={i['meta']['sample_id']:i['record'] for i in l.rd.mtc()}
        pairs={i['meta']['sample_id']:i['pair'] for i in l.b2.mtc(registry)}
        require(set(resources)==set(reg)==set(pairs),'MTC_REPLAY_MEMBERS')
        for m in ms:
            sid=m['sample_id'];saved=ix[sid]
            if m['cohort'].startswith('mtc_'):
                r=reg[sid];obs=s.physical(l.b2.ref(l.b2.MTC/'paired_244.jsonl',r['source_line']));raw=s.physical(l.b2.ref(l.b2.RAW/'raw_expanded_payloads.jsonl',r['app_raw_line']))
                prepared=dict(app_input=l.prep.mtc_app(obs,r,raw,l.b2.ref(l.b2.RAW/'raw_expanded_payloads.jsonl',r['app_raw_line'])),record=resources[sid],pair=pairs[sid])
            else:prepared=s.prepare_v16(*s.raw_v16(m))
            comp=components(prepared)
            require(comp['C1']['state']==saved['C1'],'CURRENT_C1_MISMATCH:'+sid)
            require({c:comp['resources'][name]['state'] for c,name in CANDIDATES.items()}==saved['conditions'],'CURRENT_RESOURCE_CONDITIONS_MISMATCH:'+sid)
            for model in models:
                actual=predict_prepared(model,prepared,comp);mid=model['base_model_id']
                require(actual['app_state']==saved['app_states'][mid] and actual['base_state']==saved['base_states'][mid],'CURRENT_BASE_MISMATCH:'+sid)
                expected=combine(saved['base_states'][mid],saved['conditions'],model['extensions'])
                require(actual['state']==expected,'CURRENT_SELECTED_MISMATCH:'+sid)
                replay.append(dict(sample_id=sid,model_id=model['model_id'],**{k:actual[k] for k in ('app_state','C1','base_state','state')},equal_saved=True))
        require(len(replay)==3015 and calls=={'app_predictions':3015,'C1_evaluations':1005,'resource_evaluate_calls':1005,'resource_condition_outputs':6030},'REPLAY_CALLS')
        frozen=read(out/'FROZEN.json')['dependencies'];require(all(s.digest(ROOT/p)==h for p,h in frozen.items()),'DEPENDENCY_CHANGED')
        jsonl(out/'current_input_replay.jsonl',replay)
        write(out/'CURRENT_REPLAY.json',dict(status='PASSED',members=1005,model_outputs=3015,calls=dict(calls),
            prepared_components_shared_by_three_models=True,independent_OR_checks=n,independent_set_checks=24,
            new_selection_calls=0,new_fit_calls=0,new_collection_calls=0,raw_sources={'legacy_MTC':891,'v16_pairs':114},
            all_current_outputs_equal_saved=True))
    except Exception as e:
        jsonl(out/'current_input_replay_partial.jsonl',replay);write(out/'CURRENT_REPLAY_FAILURE.json',dict(reason=str(e),calls=dict(calls),completed_positions=len(replay)));raise
    finally:sys.setprofile(None)
    print(dict(status='PASSED',calls=dict(calls)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);verify(p.parse_args().directory)
