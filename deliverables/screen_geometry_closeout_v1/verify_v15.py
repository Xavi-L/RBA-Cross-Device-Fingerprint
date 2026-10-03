#!/usr/bin/env python3
"""Compare every saved v15 ID and original field; added tracing may differ."""
import argparse,json
from pathlib import Path
from profile import ROOT,HERE,evidence,load


def differences(old,new,path=''):
    if isinstance(old,dict):
        if not isinstance(new,dict):return [path]
        return [d for k,v in old.items() for d in differences(v,new.get(k),path+'/'+k)]
    if isinstance(old,list):
        if not isinstance(new,list) or len(old)!=len(new):return [path]
        return [d for i,(a,b) in enumerate(zip(old,new)) for d in differences(a,b,path+'/'+str(i))]
    return [] if old==new else [path]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--replay-dir',type=Path,default=HERE/'v15_replay')
    p.add_argument('--output',type=Path,default=HERE/'V15_CONSISTENCY.json');args=p.parse_args()
    if args.output.exists():raise FileExistsError('Comparison exists; choose a new file')
    old=ROOT/'deliverables/screen_geometry_observation_v1';ev=load('evaluate')
    a=evidence.read_jsonl(old/'predictions.jsonl.gz');b=evidence.read_jsonl(args.replay_dir/'predictions.jsonl.gz')
    ai=evidence.index_records(a,'sample_id');bi=evidence.index_records(b,'sample_id')
    if a.errors or b.errors or set(ai)!=set(bi):raise evidence.EvidenceError('Cannot compare missing, damaged or conflicting prediction IDs')
    records=[]
    for sid,items in ai.items():
        x,y=items[0]['value'],bi[sid][0]['value'];diff=differences(x,y)
        records.append({'sample_id':sid,'environment':x['environment'],'step_id':x['step_id'],'unchanged':not diff,'differences':diff})
    sa=evidence.read_object(old/'SUMMARY.json',required=True)[0];sb=evidence.read_object(args.replay_dir/'SUMMARY.json',required=True)[0]
    summary_diff=differences(sa,sb)
    result={'expected_records':72,'compared_records':len(records),'per_id':records,'summary_differences':summary_diff,
            'passed':len(records)==72 and all(r['unchanged'] for r in records) and not summary_diff,
            'comparison_scope':'all original nested fields, including source association, values, normal proof, effect and recovery; new trace keys allowed',
            'collection_calls':0,'model_fit_calls':0}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('compared_records','passed','summary_differences')}))
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':main()
