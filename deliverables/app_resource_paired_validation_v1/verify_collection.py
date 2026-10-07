"""Reconcile collection and restoration evidence without model/condition predictions."""
from pathlib import Path
import json,hashlib,collections,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT)]
import data as d
from effects import qualify

def run():
    result={'fit_calls':0,'prediction_calls':0,'condition_calls':0,'batches':{}}
    for batch in ['smoke01','formal01']:
        path=HERE/'private_runs'/batch;plan=d.read(path/'plan.json');caps=d.capture_records(path);counts=collections.Counter(x['sample_id'] for x in caps);ix={x['sample_id']:x for x in caps}
        items={s['sample_id']:d.bind(path,plan,s,ix.get(s['sample_id']),counts[s['sample_id']]>1) for s in plan['positions']}
        effects=[]
        for s in plan['positions']:
            g=[x for x in plan['positions'] if x['scenario_group_id']==s['scenario_group_id']];pre=next(x for x in g if x['phase']=='pre');post=next(x for x in g if x['phase']=='post')
            effects.append({'scenario':s['scenario'],'round':s['round'],'phase':s['phase'],'effect':qualify(s,ix.get(s['sample_id']),items[s['sample_id']],items[pre['sample_id']],items[post['sample_id']])})
        data_counts={k:len(d.rows(path/'data'/v)) if (path/'data'/v).exists() else 0 for k,v in [('app_raw','raw_expanded_payloads.jsonl'),('browser_raw','raw_browser_payloads.jsonl'),('completed_pair_provenance','browser_pair_provenance.jsonl')]}
        result['batches'][batch]={'planned':len(plan['positions']),'recorded_attempts':len(caps),'states':dict(collections.Counter(x['result'] for x in caps)),'unique_capture_ids':len(counts),'actual_archives':data_counts,'endpoint_bindings':{side:sum(x['record']['binding'].get(side,False) for x in items.values()) for side in ['app','browser','pair']},'effects':effects,'backend_lifecycle':d.read(path/'backend_lifecycle_summary.json') if (path/'backend_lifecycle_summary.json').exists() else {'status':'RUNNING'}}
    # Compare only the actually served probe assets. Ticket/receipt checks reuse original bindings.
    environment=d.read(HERE/'ENVIRONMENT.json');pub=ROOT/'deliverables/browser67_pilot_intake_v1/evidence_archive/upstream/browser_probe_site/public'
    expected={str(p.relative_to(pub)):hashlib.sha256(p.read_bytes()).hexdigest() for p in pub.rglob('*') if p.is_file() and p.suffix in ['.html','.js','.json']}
    served=collections.Counter();mismatch=[]
    for batch in ['smoke01','formal01']:
        for event in d.rows(HERE/'private_runs'/batch/'private_command_events.jsonl'):
            if event.get('kind')=='static_file_sent':
                name=event['public_path'];served[name]+=1
                if event.get('sha256')!=expected.get(name):mismatch.append({'batch':batch,'path':name})
            elif event.get('kind') in ['gate_held','gate_released']:
                if event.get('upstream_adapter_sha256')!=expected['browser-probe-adapter.js']:mismatch.append({'batch':batch,'path':'browser-probe-adapter.js'})
    result['browser_probe_identity']={'served_counts':dict(served),'mismatches':mismatch,'comparison_scope':'actual served files and adapter; no entire-archive scan'}
    import zipfile
    apk=ROOT/environment['apk_path']
    with zipfile.ZipFile(apk) as z:result['apk_probe_identity_unchanged']=all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in environment['apk_probe_digests'].items())
    (HERE/'results/COLLECTION_VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({b:{k:v for k,v in value.items() if k!='effects' and k!='backend_lifecycle'} for b,value in result['batches'].items()}))
    return result
if __name__=='__main__':run()
