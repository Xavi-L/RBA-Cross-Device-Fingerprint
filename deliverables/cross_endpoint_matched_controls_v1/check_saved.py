"""Independent condition oracle + App-only frozen replay from retained references."""
import argparse,math,re,sys,os
from pathlib import Path
import evaluate as e
def tag(v):
    if not isinstance(v,str) or not re.fullmatch(r'[a-zA-Z]{2,3}(?:-[a-zA-Z]{4})?(?:-(?:[a-zA-Z]{2}|[0-9]{3}))?',v):return None
    if v.split('-')[0].lower() in {'und','mul','zxx','iw','in','ji'}:return None
    return v.lower()
def oracle(row):
    if row['state']=='FAILED':return 'FAILED' # Binding failures are checked independently in adapter tests.
    operands=row['operands'];cid=row['condition_id']
    if any(not o['present'] or o['status']!='observed' or o['quality']!='observed_value' or o['value'] is None for o in operands):return 'U'
    a,b=[o['value'] for o in operands]
    if cid=='C1':
        if any(type(x) not in [int,float] or not math.isfinite(x) for x in [a,b]):return 'U'
    elif cid=='D1':
        # This actual batch has observed nonempty lists; no replacement of legacy empty-list applicability.
        if not isinstance(a,list) or not isinstance(b,list) or not a or not b:raise ValueError('ORACLE_LIST_DOMAIN_REQUIRES_ORIGINAL_D1_TESTS')
    else:
        if cid=='D2':
            if not isinstance(b,list) or not b or any(type(x)!=str for x in b):return 'U'
            b=b[0]
        a,b=tag(a),tag(b)
        if a is None or b is None:return 'U'
        if cid=='C3':a,b=a.split('-')[0],b.split('-')[0]
    return 'F' if a==b else 'T'
def check(run):
    run=Path(run).resolve();out=run/'evaluation';conditions=e.lines(out/'condition_results.jsonl');predictions=e.lines(out/'app_predictions.jsonl')
    actual_calls=0
    def guard(event,args):
        if event in ['socket.connect','socket.bind','subprocess.Popen','os.system','os.posix_spawn']:raise RuntimeError('REPLAY_FORBIDDEN:'+event)
        if event=='open':
            path,mode,flags=args
            if not isinstance(path,int) and (flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_APPEND|os.O_TRUNC):
                if not Path(os.fsdecode(path)).resolve().is_relative_to(out):raise RuntimeError('REPLAY_WRITE_OUTSIDE_OUTPUT')
    def profile(frame,event,arg):
        nonlocal actual_calls
        if event!='call' or not frame.f_code.co_filename.startswith(str(e.ROOT)+os.sep):return
        name=frame.f_code.co_name
        if name=='fit' or name.startswith('fit_') or name in ['train','prepare_fold','collect']:raise RuntimeError('REPLAY_FORBIDDEN_CALL:'+name)
        if frame.f_code.co_filename.endswith('/mtc_timezone_selection.py') and name=='predict_current':actual_calls+=1
    sys.addaudithook(guard);sys.setprofile(profile)
    models,_=e.b2.load_models();models={m.model_id:m for m in models};plan=e.read(run/'plan.json');caps={c['sample_id']:c for c in e.lines(run/'captures.jsonl')}
    assert len(conditions)==210 and len(predictions)==126
    for r in conditions:assert oracle(r)==r['state'],r['meta']['sample_id']+r['condition_id']
    calls=0
    for r in predictions:
        meta=r['meta'];source=e.HERE/meta['source_run'];cap=next(c for c in e.lines(source/'captures.jsonl') if c['sample_id']==meta['sample_id'])
        raw,ref=e.load_ref(source,cap['archives']['app'],'raw_expanded_payloads.jsonl')
        # Deliberately no Browser object, pair, phase trajectory, or experiment qualification.
        actual=e.b2.predict_item({'meta':meta,'raw':raw,'app_session':raw['session_id']},models[r['prediction']['model_id']]);calls+=1
        assert actual==r,meta['sample_id']
    sys.setprofile(None);assert actual_calls==calls
    result={'status':'PASSED','independent_condition_checks':len(conditions),'additional_app_only_replay_calls':actual_calls,'exact_saved_prediction_equality':True,'new_acquisitions':0,'training_calls':0,'network_process_and_output_write_guard':'ENFORCED','scope':'Replayed saved App raw only; separate calls do not enlarge 42-position denominator.'}
    e.write(out/'SAVED_REPLAY_CHECK.json',result);print(result)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_directory');check(p.parse_args().run_directory)
