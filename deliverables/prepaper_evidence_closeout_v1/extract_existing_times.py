"""Extract only already-recorded timing fields; no device/process/network calls."""
from datetime import datetime
from closeout_io import *

def instant(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def interval(a,b):
    if not a or not b:return None
    value=(instant(b)-instant(a)).total_seconds()
    require(value>=0,'NEGATIVE_SAME_CLOCK_INTERVAL');return value

def extract(output):
    out=Path(output);out.mkdir(exist_ok=True)
    members=rows(HERE/'results/members.jsonl');cache={};records=[]
    for member in members:
        if member['cohort'] not in ('pilot18','b2b42'):continue
        reference=member['source_meta']['capture_reference'];name,n=reference.rsplit(':',1)
        if name not in cache:cache[name]=rows(ROOT/name)
        capture=cache[name][int(n)-1]
        require(capture.get('result')==('completed' if member['cohort']=='pilot18' else 'COMPLETED'),'CAPTURE_NOT_COMPLETE')
        setting=capture.get('setting',{});operation=setting.get('operation',{})
        records.append(dict(sample_id=member['sample_id'],cohort=member['cohort'],scenario=member['scenario'],phase=member['phase'],source=reference,
            clock='runner_host_UTC_wall_clock',started_at=capture['started_at'],finished_at=capture['finished_at'],
            capture_orchestration_seconds=interval(capture['started_at'],capture['finished_at']),
            app_navigation_to_pair_complete_seconds=interval(capture.get('app_navigation_begin'),capture.get('pair_completed_at')),
            settings_workflow_seconds=interval(setting.get('started_at'),setting.get('finished_at')),
            explicit_preference_persistence_wait_seconds=operation.get('persistence_wait_seconds',0),
            pure_probe_duration='NOT_RECORDED',scope='same-host wall-clock orchestration, includes UI/controls/upload/polling/restoration; not pure probe, not client-server subtraction'))
    require(len(records)==60,'CAPTURE_MEMBER_COUNT')
    jsonl(out/'collection_log_intervals.jsonl',records);csv_write(out/'collection_log_intervals.csv',records)
    training=[]
    for m in read(B2C/'results/models.json'):
        base=read(ROOT/m['base']['path']);elapsed=base['fit'].get('elapsed_seconds')
        training.append(dict(method='historical_App_RETENTION',model_id=m['base_model_id'],elapsed_seconds=elapsed,clock='time.monotonic duration retained in original model',scope='historical fit from prepared inputs; no new run; not encoder/raw preparation or B3-B selection',source=m['base']['path'],status='RECORDED' if elapsed is not None else 'NOT_RECORDED'))
    for method,path in [('B2C',B2C/'results/EXECUTION.json'),('B3A',B3A/'results/EXECUTION.json')]:
        r=read(path)
        training.append(dict(method=method,model_id='batch_execution',elapsed_seconds=None,clock='only whole-pipeline wall-clock endpoints available',scope='pure fit/selection timing NOT_RECORDED; pipeline endpoints include loading, validation, prediction and output',source=ref(path),status='NOT_RECORDED'))
    training.append(dict(method='B3B_finite_selection',model_id='three_new_tasks',elapsed_seconds=None,clock='no isolated monotonic selector interval was recorded',scope='3 tasks / 12 checks; call counts are not training latency; zero App/encoder/tree fits',source=ref(HERE/'results/EXECUTION.json'),status='NOT_RECORDED'))
    csv_write(out/'historical_training_timing.csv',training);write(out/'historical_training_timing.json',training)
    print('Existing same-host capture intervals:',len(records))

if __name__=='__main__':extract(HERE/'existing_times')
