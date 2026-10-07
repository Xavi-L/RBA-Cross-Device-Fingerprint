"""Saved outputs only: no raw input, inference, selection, fitting, or network."""
import argparse,csv
from rx_common import *
def csvfile(path,rs):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]),lineterminator='\n');w.writeheader();w.writerows(rs)
def summarize(out,destination=None):
    out=Path(out);dest=Path(destination) if destination else out/'summary';dest.mkdir(parents=True,exist_ok=True)
    ms=rows(out/'members.jsonl');models=read(out/'models.json');mids=[m['base_model_id'] for m in models]
    ix=validate(ms,rows(out/'inputs.jsonl'),mids,1005);mi=index(ms)
    ps=rows(out/'combinations.jsonl');pi=index(ps,lambda r:(r['sample_id'],r['base_model_id'],r['set_id']))
    require(set(pi)=={(m['sample_id'],mid,sid) for m in ms for mid in mids for sid,_ in SETS},'SUMMARY_CARTESIAN')
    for p in ps:require(all(p[k]==mi[p['sample_id']][k] for k in ('cohort','role','identity')),'SUMMARY_METADATA')
    checks=read(out/'candidate_checks.json');ci=index(checks,lambda r:(r['base_model_id'],r['set_id']))
    require(set(ci)=={(mid,sid) for mid in mids for sid,_ in SETS},'CHECKS_CARTESIAN')
    cohorts=list(dict.fromkeys(m['cohort'] for m in ms));tables=[];families=[];deltas=[];unknown=[];detail=[]
    groups=[('selection',[m for m in ms if m['role']=='selection']),('historical_evaluation',[m for m in ms if m['role']=='historical_evaluation'])]+[(co,[m for m in ms if m['cohort']==co]) for co in cohorts]
    for model in models:
        mid=model['base_model_id'];fold=model['fold']
        for sid,chosen in SETS:
            check=ci[mid,sid]
            tables.append(dict(fold=fold,set_id=sid,feasible=check['feasible'],macro=check['macro']['value'],micro_T=check['micro']['T'],micro_n=check['micro']['n'],rules=check['rule_count'],complexity=check['complexity'],reasons=';'.join(check['reasons']),
                **{f'{co}_{k}':v for co,c in check['normals'].items() for k,v in c.items()}))
            for family in FAMILIES:
                sub=[m for m in ms if m['identity']=='EFFECTIVE_INTERVENTION' and m['family']==family]
                families.append(dict(fold=fold,set_id=sid,family=family,feasible=check['feasible'],selected=sid==model['selected_set'],**counts(pi[m['sample_id'],mid,sid]['state'] for m in sub)))
            for gn,gm in groups:
                normals=[m for m in gm if m['identity']=='NORMAL'];attacks=[m for m in gm if m['identity']=='EFFECTIVE_INTERVENTION']
                events={'new_detection':[],'lost_detection':[],'new_normal_alarm':[],'lost_normal_alarm':[],'F_to_U':[],'U_to_T':[],'to_FAILED':[]}
                transitions={}
                for m in gm:
                    sample=m['sample_id'];a=ix[sample]['base_states'][mid];b=pi[sample,mid,sid]['state'];key=a+'->'+b
                    transitions.setdefault(key,[]).append(sample)
                    if m['identity']=='EFFECTIVE_INTERVENTION':
                        if a!='T' and b=='T':events['new_detection'].append(sample)
                        if a=='T' and b!='T':events['lost_detection'].append(sample)
                    elif m['identity']=='NORMAL':
                        if a!='T' and b=='T':events['new_normal_alarm'].append(sample)
                        if a=='T' and b!='T':events['lost_normal_alarm'].append(sample)
                    if a=='F' and b=='U':events['F_to_U'].append(sample)
                    if a=='U' and b=='T':events['U_to_T'].append(sample)
                    if a!='FAILED' and b=='FAILED':events['to_FAILED'].append(sample)
                deltas.append(dict(fold=fold,set_id=sid,group=gn,feasible=check['feasible'],**{k:len(v) for k,v in events.items()}))
                detail.append(dict(fold=fold,set_id=sid,group=gn,events=events,all_transitions=transitions,
                    normal=counts(pi[m['sample_id'],mid,sid]['state'] for m in normals),attacks=counts(pi[m['sample_id'],mid,sid]['state'] for m in attacks)))
        for co in cohorts:
            sub=[m['sample_id'] for m in ms if m['cohort']==co and m['identity']=='NORMAL']
            sets={'app_U':{x for x in sub if ix[x]['app_states'][mid]=='U'},'C1_U':{x for x in sub if ix[x]['C1']=='U'},'base_U':{x for x in sub if ix[x]['base_states'][mid]=='U'}}
            sets.update({c+'_U':{x for x in sub if ix[x]['conditions'][c]=='U'} for c in CANDIDATES})
            for c in CANDIDATES:
                a=sets['base_U'];b=sets[c+'_U'];sets['base_intersection_'+c]=a&b;sets['base_union_'+c]=a|b
                sets['new_F_to_U_'+c]={x for x in sub if ix[x]['base_states'][mid]=='F' and pi[x,mid,c]['state']=='U'}
                sets['result_U_'+c]={x for x in sub if pi[x,mid,c]['state']=='U'}
            unknown.append(dict(fold=fold,cohort=co,n=len(sub),counts={k:len(v) for k,v in sets.items()},ids={k:sorted(v) for k,v in sets.items()}))
    special=[]
    for model in models:
        for sid,_ in SETS:
            for name,sub in [('normal_browser_language_preference',[m for m in ms if m['cohort']=='b2b42' and m['scenario']=='L_BROWSER_LANG' and m['phase']=='change']),('resource_sham',[m for m in ms if m['cohort']=='resource54' and m['scenario'].startswith('N_')])]:
                special.append(dict(fold=model['fold'],set_id=sid,group=name,**counts(pi[m['sample_id'],model['base_model_id'],sid]['state'] for m in sub)))
    counterexamples=[]
    for m in ms:
        if m['cohort'].startswith('mtc_') and ix[m['sample_id']]['conditions']['M']=='T':
            counterexamples.append(dict(sample_id=m['sample_id'],cohort=m['cohort'],role=m['role'],identity=m['identity'],source=m['source_meta'],
                outputs={mo['fold']:{sid:pi[m['sample_id'],mo['base_model_id'],sid]['state'] for sid,_ in SETS} for mo in models}))
    summary=dict(records=1005,selection_records=744,selection_normals=718,selection_modifications=26,historical_evaluation_normals=261,
        selections=[{k:m[k] for k in ('model_id','fold','selected_set','status','baseline_feasible')} for m in models],
        candidate_checks=tables,families=families,deltas=deltas,special_normals=special,counterexamples=counterexamples)
    for name,data in [('SUMMARY',summary),('unknown_overlap',unknown),('member_deltas',detail),('normal_counterexamples',counterexamples),('special_normals',special)]:write(dest/(name+'.json'),data)
    csvfile(dest/'candidate_checks.csv',tables);csvfile(dest/'families.csv',families);csvfile(dest/'deltas.csv',deltas);csvfile(dest/'special_normals.csv',special)
    return summary
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();summarize(a.directory,a.output)
