"""One documented adapter repair: three preidentified P2 raw references, six conditions each."""
import sys,json
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path[:0]=[str(HERE),str(HERE.parents[1])]
import data as d,conditions as c
from evaluate import jsonl,write
out=HERE/'results';dest=out/'engineering';dest.mkdir(exist_ok=True)
if (dest/'MTC_BINDING_REPAIR.json').exists():raise FileExistsError('REPAIR_ALREADY_RECORDED')
old=d.rows(out/'mtc_conditions.jsonl');ids={r['sample_id'] for r in old if r['reason']=='BINDING_INVALID:app.android_native_data.memory_layer.total_memory_gb'}
assert len(ids)==3
jsonl(dest/'mtc_first_attempt_3members.jsonl',[r for r in old if r['sample_id'] in ids])
items=d.mtc();new={};members=[]
for i in items:
    members.append(i['meta'])
    if i['meta']['sample_id'] in ids:
        assert i['meta'].get('duplicate_session_resolution') and not i['record'].get('field_errors')
        new[i['meta']['sample_id']]=c.evaluate(i['record'])
repaired=[]
for r in old:
    if r['sample_id'] in new:
        r={k:v for k,v in r.items() if k in ['sample_id','cohort','group','identity','condition']}|new[r['sample_id']][r['condition']]
    repaired.append(r)
jsonl(out/'mtc_conditions.jsonl',repaired);jsonl(out/'mtc_members.jsonl',members)
write(dest/'MTC_BINDING_REPAIR.json',{'first_condition_calls':5346,'engineering_condition_calls':18,'actual_total_condition_calls':5364,'affected_sample_ids':sorted(ids),'reason':'App177 generic raw reader rejected duplicate session IDs across different historical uploads. Original P2 members already identify one physical row and payload hash, and the historical paired reader verifies the P1 receipt and pair. Native resource adapter now uses that exact reference like the existing Web diagnostic, rather than an added session-global gate. Duplicate P2 IDs or contradictory references still fail.','formulas_targets_thresholds_unchanged':True,'fit_calls':0,'first_outputs_preserved':'mtc_first_attempt_3members.jsonl'})
print('Repaired exactly three references; 18 additional engineering condition calls; all first outputs retained.')
