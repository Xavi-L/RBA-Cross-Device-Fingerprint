#!/usr/bin/env python3
"""Only saved membership and outputs: no selector, predictor, raw, or network imports."""
import argparse, csv
from collections import Counter,defaultdict
from common import *

def summarize(directory,output):
    source=Path(directory);out=Path(output);out.mkdir(parents=True,exist_ok=True)
    members=rows(source/'members.jsonl');preds=rows(source/'predictions.jsonl');models=read(source/'models.json')
    ix=unique(members,lambda r:r['sample_id']);ids={r['model_id'] for r in models}
    require(len(ix)==951 and Counter(m['cohort'] for m in members)==dict(zip(COHORTS,(630,18,42,144,117))),'MEMBER_COHORT_MISMATCH')
    require(Counter((r['sample_id'],r['model_id']) for r in preds)==Counter((s,m) for s in ix for m in ids),'OUTPUT_MEMBERSHIP_MISMATCH')
    trajectory=defaultdict(list)
    for m in members:
        if m['cohort'] in ('pilot18','b2b42'):trajectory[m['group_id']].append(m)
    recovery_groups={k for k,v in trajectory.items() if len(v)==3 and all(m['full_recovery_qualified'] is True for m in v)}
    groups=defaultdict(list)
    for p in preds:
        m=ix[p['sample_id']]
        require(p['state'] in STATES and p['base_state'] in STATES,'INVALID_OUTPUT')
        for group in ('all',m['identity'],'scenario:'+m['scenario']+':'+m['phase']):groups[p['model_id'],m['cohort'],group].append(p)
        if m['identity']=='EFFECTIVE_INTERVENTION':groups[p['model_id'],m['cohort'],'family:'+m['family']].append(p)
        if m['group_id'] in recovery_groups:groups[p['model_id'],m['cohort'],'recovery_complete'].append(p)
    table=[];overlaps=[]
    for (mid,cohort,group),items in sorted(groups.items()):
        c=counts(p['state'] for p in items);b=counts(p['base_state'] for p in items)
        table.append(dict(model_id=mid,cohort=cohort,role=items and ix[items[0]['sample_id']]['role'],group=group,**c,
            base_T=b['T'],base_F=b['F'],base_U=b['U'],base_FAILED=b['FAILED'],
            coverage=f"{c['defined']}/{c['n']}",trigger_rate=f"{c['T']}/{c['n']}"))
        transitions=defaultdict(list)
        for p in items:transitions[p['base_state']+'->'+p['state']].append(p['sample_id'])
        normal=[p for p in items if ix[p['sample_id']]['identity']=='NORMAL']
        attacks=[p for p in items if ix[p['sample_id']]['identity']=='EFFECTIVE_INTERVENTION']
        overlaps.append(dict(model_id=mid,cohort=cohort,group=group,transitions=dict(transitions),
            baseline_detected=[p['sample_id'] for p in attacks if p['base_state']=='T'],
            new_detected=[p['sample_id'] for p in attacks if p['base_state']!='T' and p['state']=='T'],
            new_normal_alerts=[p['sample_id'] for p in normal if p['base_state']!='T' and p['state']=='T'],
            F_to_U=transitions.get('F->U',[]),U_to_T=transitions.get('U->T',[])))
    write(out/'summary.json',table);write(out/'intersections.json',overlaps)
    with (out/'summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    flow={c:dict(planned=sum(m['cohort']==c for m in members),
        identities=dict(Counter(m['identity'] for m in members if m['cohort']==c)),
        operation_effects=dict(Counter(m['operation_effect'] for m in members if m['cohort']==c)),
        restoration=dict(Counter(str(m['runtime_restored']) for m in members if m['cohort']==c)),
        full_recovery_qualified=sum(m['full_recovery_qualified'] is True for m in members if m['cohort']==c),
        app_available=sum(m['app_input_available'] for m in members if m['cohort']==c),
        browser_available=sum(m['browser_input_available'] for m in members if m['cohort']==c)) for c in COHORTS}
    write(out/'denominators.json',flow)
    return table
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--output',required=True);a=p.parse_args();summarize(a.directory,a.output)
