#!/usr/bin/env python3
"""Second-round figures from saved derived results only; no research-engine imports.

Run with the existing Matplotlib environment. --check-only reads output files only.
"""
import argparse
import csv
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

R2_HERE = Path(__file__).resolve().parent
R2_ROOT = R2_HERE.parents[2]
R2_OWNER = 'rba-round2-paired-saved-counts-v1'
R2_IDS = ['F05a','F05b','F06a','F06b','F07a','F07b','F08']
R2_STATES = ('T','F','U','FAILED')
R2_COUNTS = ('N','T','F','U','FAILED','defined')
R2_FOLDS = ['WEBGL1-LOEO-v1-0'+str(n) for n in (1,2,3)]
R2_STATUS = '初稿已生成／待导师选择'


def r2_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def r2_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def r2_jsonl(path):
    with Path(path).open(encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def r2_write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def r2_write_csv(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)


def r2_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def r2_check(checks,id_,got,want):
    checks.append(dict(id=id_,status='PASS' if got==want else 'FAIL',observed=got,expected=want))


def r2_counts(row):
    n=int(row.get('N',row.get('n',0)))
    states={s:int(row.get(s,0)) for s in R2_STATES}
    defined=int(row.get('defined',states['T']+states['F']))
    return dict(N=n,**states,defined=defined,rate=states['T']/n if n else '',
                defined_rate=defined/n if n else '',numerator=states['T'],denominator=n)


def r2_sum(rows):
    return r2_counts({k:sum(int(r.get(k,0)) for r in rows) for k in R2_COUNTS})


F07_BASE='deliverables/app_resource_constrained_extension_v1/results/'
F07_TABLES='deliverables/app_browser_evidence_consolidation_v1/tables.json'
F07_SOURCES=[F07_BASE+p for p in ['models.json','members.jsonl','combinations.jsonl','candidate_checks.json',
    'summary/SUMMARY.json','summary/families.csv','summary/candidate_checks.csv',
    'summary/member_deltas.json','summary/special_normals.csv','summary/special_normals.json']]+[F07_TABLES]
F07_SETS=['S0','M','B','W']
F07_ALLSETS=['S0','M','B','W','MW','MB','WB','MWB']
F07_FAMILIES=[('App_language','App language'),('App_timezone','App timezone'),
    ('Browser_language','Browser language'),('Browser_timezone','Browser timezone'),
    ('App_resource16_48','App resources 16/48'),('App_memory4','App memory 4'),
    ('Browser_resource16_48','Browser resources 16/48'),('Browser_memory4','Browser memory 4')]


def extract_f07(root):
    checks=[];data={};base=root/F07_BASE
    models=r2_json(base/'models.json');candidates=r2_json(base/'candidate_checks.json')
    families=r2_csv(base/'summary/families.csv');ccsv=r2_csv(base/'summary/candidate_checks.csv')
    summary=r2_json(base/'summary/SUMMARY.json');unified=r2_json(root/F07_TABLES)
    modelmap={r['base_model_id']:r for r in models}
    r2_check(checks,'F07_three_models',sorted(r['fold'] for r in models),R2_FOLDS)
    r2_check(checks,'F07_saved_selected_sets',[r['selected_set'] for r in models],['S0']*3)
    r2_check(checks,'F07_saved_model_status',[r['status'] for r in models],['BASELINE_RETAINED']*3)
    for key,actual in [('candidate_checks',ccsv),('families',families),('special_normals',r2_csv(base/'summary/special_normals.csv'))]:
        expected=[{k:str(v) for k,v in row.items()} for row in summary[key]]
        differences=[]
        for i in range(max(len(actual),len(expected))):
            a=actual[i] if i<len(actual) else {};b=expected[i] if i<len(expected) else {}
            for k in a.keys()|b.keys():
                if a.get(k)!=b.get(k):differences.append(dict(row=i+2,fold=a.get('fold'),set_id=a.get('set_id'),family=a.get('family'),field=k,csv=a.get(k),json=b.get(k)))
        r2_check(checks,'F07_'+key+'_csv_json_conflicts',differences,[])
    r2_check(checks,'F07_24_old_candidates',len(candidates),24)
    r2_check(checks,'F07_unique_candidates',len({(r['base_model_id'],r['set_id']) for r in candidates}),24)
    candmap={(modelmap[r['base_model_id']]['fold'],r['set_id']):(i,r) for i,r in enumerate(candidates)}
    csvmap={(r['fold'],r['set_id']):r for r in ccsv}
    candidate_rows=[];normal_rows=[];candidate_quality=[]
    for fold in R2_FOLDS:
        r2_check(checks,fold+'_eight_sets',sorted(s for f,s in candmap if f==fold),sorted(F07_ALLSETS))
        model=next(m for m in models if m['fold']==fold)
        for set_id in F07_ALLSETS:
            i,c=candmap[fold,set_id];r=csvmap[fold,set_id]
            selected=model['selected_set']==set_id
            role='retained_complete_method' if selected else 'rejected_diagnostic_combination'
            common=dict(fold=fold,base_model_id=c['base_model_id'],set_id=set_id,
                method_short='S0' if set_id=='S0' else 'S0 + '+' + '.join(set_id),method_role=role,
                feasible=c['feasible'],selected=selected,reasons=';'.join(c['reasons']),
                source_path=F07_BASE+'candidate_checks.json',source_locator='/'+str(i))
            for field,want in [('feasible',str(c['feasible'])),('rules',str(c['rule_count'])),('complexity',str(c['complexity'])),('reasons',';'.join(c['reasons']))]:
                r2_check(checks,fold+set_id+'_'+field,r[field],want)
            r2_check(checks,fold+set_id+'_micro_csv',[int(r['micro_n']),int(r['micro_T'])],[c['micro']['n'],c['micro']['T']])
            r2_check(checks,fold+set_id+'_macro_csv',float(r['macro']),c['macro']['value'])
            candidate_rows.append(dict(common,**r2_counts(c['micro']),identity='EFFECTIVE_INTERVENTION',cohort='selection',
                macro_numerator=c['macro']['numerator'],macro_denominator=c['macro']['denominator'],macro_rate=c['macro']['value'],
                rule_count=c['rule_count'],complexity=c['complexity']))
            for cohort,counts in c['normals'].items():
                row=dict(common,**r2_counts(counts),identity='NORMAL',cohort=cohort,
                    alarm_budget=counts['budget'],minimum_defined=counts['minimum_defined'])
                row['source_locator']+='/normals/'+cohort
                normal_rows.append(row)
                for k in ['n','T','F','U','FAILED','defined','budget','minimum_defined']:
                    r2_check(checks,fold+set_id+cohort+'_'+k,int(r[cohort+'_'+k]),counts[k])
            for condition,counts in c['candidate_quality'].items():
                quality=dict(common,**r2_counts(counts),condition=condition,cohort='mtc_discovery',identity='NORMAL',source_locator='/'+str(i)+'/candidate_quality/'+condition)
                quality.update(combination_role=common['method_role'],combination_short=common['method_short'],
                    method_role='fixed_resource_condition',method_short=condition)
                candidate_quality.append(quality)
    famrows=[]
    for i,r in enumerate(families):
        ci,c=candmap[r['fold'],r['set_id']];n=r2_counts(r)
        r2_check(checks,'F07_family_'+str(i),{k:n[k] for k in R2_COUNTS},{k:r2_counts(c['families'][r['family']])[k] for k in R2_COUNTS})
        r2_check(checks,'F07_family_status_'+str(i),[r['feasible'],r['selected']],[str(c['feasible']),str(r['set_id']=='S0')])
        famrows.append(dict(fold=r['fold'],set_id=r['set_id'],family=r['family'],family_short=dict(F07_FAMILIES)[r['family']],
            method_role='retained_complete_method' if r['selected']=='True' else 'rejected_diagnostic_combination',
            feasible=r['feasible'],selected=r['selected'],identity='EFFECTIVE_INTERVENTION',**n,
            source_path=F07_BASE+'summary/families.csv',source_locator='row:'+str(i+2)))
    for fold in R2_FOLDS:
        for set_id in F07_ALLSETS:
            sub=[r for r in famrows if r['fold']==fold and r['set_id']==set_id]
            ref=next(r for r in candidate_rows if r['fold']==fold and r['set_id']==set_id)
            r2_check(checks,fold+set_id+'_8_families',sorted(r['family'] for r in sub),sorted(dict(F07_FAMILIES)))
            r2_check(checks,fold+set_id+'_families_to_micro',r2_sum(sub),r2_counts(ref))
    # All eight historical sets are not in the small consolidated tables. Count
    # the saved combination states, joining identities from the independent roster.
    members=r2_jsonl(base/'members.jsonl');membermap={r['sample_id']:r for r in members}
    r2_check(checks,'F07_independent_roster_unique',len(membermap),1005)
    r2_check(checks,'F07_role_partition',dict(Counter(r['role'] for r in members)),{'selection':744,'historical_evaluation':261})
    r2_check(checks,'F07_selection_identity_partition',dict(Counter(r['identity'] for r in members if r['role']=='selection')),{'NORMAL':718,'EFFECTIVE_INTERVENTION':26})
    combinations=r2_jsonl(base/'combinations.jsonl');groups=defaultdict(list);roster_keys=set();bad_metadata=[]
    for i,r in enumerate(combinations):
        key=(r['base_model_id'],r['set_id'],r['sample_id']);roster_keys.add(key)
        m=membermap[r['sample_id']]
        if any(r[k]!=m[k] for k in ('cohort','role','identity')):bad_metadata.append(dict(line=i+1,base_model_id=r['base_model_id'],set_id=r['set_id'],fields=['cohort','role','identity']))
        if r['state'] not in R2_STATES:raise ValueError('Unknown saved combination state at line '+str(i+1))
        groups[r['base_model_id'],r['set_id'],m['cohort'],m['identity']].append(r['state'])
    r2_check(checks,'F07_combinations_complete_unique',len(roster_keys),24*1005)
    r2_check(checks,'F07_combinations_no_duplicate',len(combinations),len(roster_keys))
    r2_check(checks,'F07_combination_roster_metadata',bad_metadata,[])
    cohorts=['mtc_discovery','pilot18','b2b42','resource54','mtc_development','mtc_reserved_validation']
    group_rows=[]
    for fold in R2_FOLDS:
        model=next(m for m in models if m['fold']==fold)
        for set_id in F07_ALLSETS:
            for cohort in cohorts:
                for identity in ('NORMAL','EFFECTIVE_INTERVENTION'):
                    states=groups[model['base_model_id'],set_id,cohort,identity];count=Counter(states)
                    n=r2_counts(dict(N=len(states),**count))
                    expected_n=sum(m['cohort']==cohort and m['identity']==identity for m in members)
                    r2_check(checks,fold+set_id+cohort+identity+'_roster_N',n['N'],expected_n)
                    group_rows.append(dict(fold=fold,set_id=set_id,base_model_id=model['base_model_id'],cohort=cohort,identity=identity,
                        method_role='retained_complete_method' if set_id=='S0' else 'rejected_diagnostic_combination',**n,
                        source_path=F07_BASE+'combinations.jsonl',
                        source_locator='base_model_id='+model['base_model_id']+';set_id='+set_id+';cohort='+cohort+';identity='+identity,
                        identity_source_path=F07_BASE+'members.jsonl',identity_source_locator='cohort='+cohort+';identity='+identity))
    aggregate_rows=[]
    for fold in R2_FOLDS:
        for set_id in F07_ALLSETS:
            for scope,cs in [('selection',cohorts[:4]),('historical_evaluation',cohorts[4:]),('small_experiments',cohorts[1:4])]:
                for identity in ('NORMAL','EFFECTIVE_INTERVENTION'):
                    rows=[r for r in group_rows if r['fold']==fold and r['set_id']==set_id and r['cohort'] in cs and r['identity']==identity]
                    aggregate_rows.append(dict(fold=fold,set_id=set_id,cohort=scope,identity=identity,**r2_sum(rows),
                        method_role=rows[0]['method_role'],source_path=rows[0]['source_path'],source_locator=' | '.join(r['source_locator'] for r in rows),
                        overlap_note='Derived sum; do not add to component cohort rows.'))
    for row in normal_rows:
        ref=next(r for r in group_rows if all(r[k]==row[k] for k in ('fold','set_id','cohort','identity')))
        r2_check(checks,'F07_saved_normals_cross_'+row['fold']+row['set_id']+row['cohort'],r2_counts(row),r2_counts(ref))
    for key in ('historical_mtc','discovery_mtc'):
        for i,row in enumerate(unified[key]):
            ref=next(r for r in group_rows if r['fold']==row['fold'] and r['set_id']==row['set_id'] and r['cohort']==row['cohort'] and r['identity']=='NORMAL')
            r2_check(checks,'F07_unified_'+key+str(i),r2_counts(ref),r2_counts(row))
    for i,row in enumerate(unified['resource_combinations']):
        for identity,field in [('NORMAL','normal'),('EFFECTIVE_INTERVENTION','modified')]:
            ref=next(r for r in aggregate_rows if r['fold']==row['fold'] and r['set_id']==row['set_id'] and r['cohort']==row['role'] and r['identity']==identity)
            r2_check(checks,'F07_unified_combo_'+str(i)+field,r2_counts(ref),r2_counts(row[field]))
    deltas=r2_json(base/'summary/member_deltas.json')
    delta_rows=[]
    for i,r in enumerate(deltas):
        for event,items in r['events'].items():
            delta_rows.append(dict(fold=r['fold'],set_id=r['set_id'],group=r['group'],event=event,event_count=len(items),
                source_path=F07_BASE+'summary/member_deltas.json',source_locator='/'+str(i)+'/events/'+event))
    for fold in R2_FOLDS:
        for set_id in ['M','B','W']:
            for group,n in [('mtc_discovery',7),('historical_evaluation',2)]:
                r2_check(checks,fold+set_id+group+'_new_unknown_saved',next(r['event_count'] for r in delta_rows if r['fold']==fold and r['set_id']==set_id and r['group']==group and r['event']=='F_to_U'),n)
    special=r2_json(base/'summary/special_normals.json')
    special_rows=[dict(fold=r['fold'],set_id=r['set_id'],group=r['group'],identity='NORMAL',**r2_counts(r),
        source_path=F07_BASE+'summary/special_normals.json',source_locator='/'+str(i)) for i,r in enumerate(special)]
    counterexample_rows=[]
    for i,r in enumerate(summary['counterexamples']):
        for fold,outputs in r['outputs'].items():
            for set_id,state in outputs.items():
                counterexample_rows.append(dict(case='M-normal-'+str(i+1),cohort=r['cohort'],role=r['role'],
                    identity=r['identity'],fold=fold,set_id=set_id,state=state,
                    method_role='retained_complete_method' if set_id=='S0' else 'rejected_diagnostic_combination',
                    source_path=F07_BASE+'summary/SUMMARY.json',source_locator=f'/counterexamples/{i}/outputs/{fold}/{set_id}',
                    interpretation='Existing valid normal counterexample; not missing input; original member linkage omitted'))
    r2_check(checks,'F07_three_M_normal_counterexamples',dict(Counter(r['cohort'] for r in summary['counterexamples'])),{'mtc_discovery':2,'mtc_reserved_validation':1})
    f07a=[r for r in famrows if r['set_id'] in F07_SETS]
    f07b=[r for set_id in F07_SETS for fold in R2_FOLDS for r in normal_rows if r['set_id']==set_id and r['fold']==fold and r['cohort']=='mtc_discovery']
    for family,_ in F07_FAMILIES:
        for set_id in F07_SETS:
            rows=[r for r in f07a if r['family']==family and r['set_id']==set_id]
            r2_check(checks,'F07a_compression_'+family+set_id,len({tuple(r[k] for k in R2_COUNTS)+tuple(r[k] for k in ('feasible','selected','method_role')) for r in rows}),1)
    for fold in R2_FOLDS:
        r2_check(checks,fold+'_F07_micro_regression',[next(r['T'] for r in candidate_rows if r['fold']==fold and r['set_id']==s) for s in F07_SETS],[13,19,16,19])
        r2_check(checks,fold+'_F07_defined_regression',[next(r['defined'] for r in f07b if r['fold']==fold and r['set_id']==s) for s in F07_SETS],[567,560,560,560])
        r2_check(checks,fold+'_F07_alarm_regression',[next(r['T'] for r in f07b if r['fold']==fold and r['set_id']==s) for s in F07_SETS],[6,8,6,46] if fold[-2:]!='03' else [0,2,0,40])
    data.update(F07a=f07a,F07b=f07b,T04_resource_candidates=candidate_rows,T04_resource_families=famrows,
        T04_resource_normals=normal_rows,T04_resource_cohorts=group_rows,T04_resource_aggregates=aggregate_rows,
        T04_resource_candidate_quality=candidate_quality,T04_resource_deltas=delta_rows,T04_resource_special_normals=special_rows,
        T04_resource_normal_counterexamples=counterexample_rows,
        resource_family_mapping=[dict(order=i+1,family=f,short_name=s) for i,(f,s) in enumerate(F07_FAMILIES)],
        resource_combination_mapping=[dict(set_id=s,short_name='S0' if s=='S0' else 'S0 + '+' + '.join(s),method_role='retained_complete_method' if s=='S0' else 'rejected_diagnostic_combination') for s in F07_ALLSETS])
    metadata={
        'F07a':dict(name='Resource combinations: family detections and saved acceptance',sources=F07_SOURCES,
            filtering='Eight EFFECTIVE_INTERVENTION families; S0/M/B/W; all three configurations retained in CSV.',
            aggregation='Eight disjoint families sum to26; compress configurations only after all states and acceptance labels match.',
            method_roles='S0 retained complete method; S0+M/B/W rejected diagnostic combinations. No new selection.',
            denominators='2,2,5,5,3,3,3,3 by family; total26; small-experiment normal88 separately.',
            limits=['Development-exposed materials, not fresh blind testing.','Higher detection does not imply acceptance.','Same26 positions per configuration, never78.','All eight sets and three configurations retained in T04; capacities differ.']),
        'F07b':dict(name='Resource combinations: MTC training normal costs',sources=F07_SOURCES,
            filtering='mtc_discovery NORMAL N630; S0/M/B/W x three configurations.',
            aggregation='None across configurations; historical144/117, derived261, and development718 normals are separate T04 rows.',
            method_roles='Saved development checks and failure reasons; not recomputed acceptance.',
            denominators='630 per row; original alarm budget31; original minimum defined567/630; no substitution by718.',
            limits=['The90% line is a development defined-output criterion, not tolerated alarm rate or a deployment guarantee.','U and original reasons remain unchanged.','M/B fail joint coverage; W also exceeds alarms and candidate coverage.','Seven training and two historical newly unknown positions are existing evidence, not re-evaluated raw data.'])}
    return data,checks,metadata


def plot_f07(data,save):
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import Patch
    cmap=LinearSegmentedColormap.from_list('round2_blue',['#f1f5f8','#a7c8dc','#1b5578'])
    size=(180,120);fig=plt.figure(figsize=(size[0]/25.4,size[1]/25.4))
    ax=fig.add_axes([.31,.34,.65,.43])
    rows=[r for r in data['F07a'] if r['fold']==R2_FOLDS[0]]
    lookup={(r['family'],r['set_id']):r for r in rows}
    rates=np.array([[100*lookup[f,s]['rate'] for s in F07_SETS] for f,_ in F07_FAMILIES])
    im=ax.pcolormesh(np.arange(5)-.5,np.arange(9)-.5,rates,cmap=cmap,vmin=0,vmax=100,shading='flat',rasterized=False,edgecolors='white',linewidth=1)
    ax.set_ylim(7.5,-.5);ax.set_yticks(range(8),[s for _,s in F07_FAMILIES]);ax.set_xticks(range(4),['S0\nRetained','S0 + M\nDiagnostic\nrejected','S0 + B\nDiagnostic\nrejected','S0 + W\nDiagnostic\nrejected']);ax.xaxis.tick_top();ax.tick_params(which='both',length=0,pad=5)
    for i,(family,_) in enumerate(F07_FAMILIES):
        for j,s in enumerate(F07_SETS):
            r=lookup[family,s];ax.text(j,i,f"{r['T']}/{r['N']}",ha='center',va='center',color='white' if r['rate']>.55 else '#142e40')
    for spine in ax.spines.values():spine.set_visible(False)
    fig.text(.04,.955,'F07a  Resource increments: detections and saved acceptance',fontsize=10,weight='bold')
    totals=[next(r for r in data['T04_resource_candidates'] if r['fold']==R2_FOLDS[0] and r['set_id']==s) for s in F07_SETS]
    for j,r in enumerate(totals):fig.text(.31+.65*(j+.5)/4,.28,f"Total {r['T']}/{r['N']}",ha='center')
    fig.text(.31,.225,'Each configuration has these counts; U = FAILED = 0.',fontsize=8)
    cax=fig.add_axes([.31,.135,.65,.025]);cb=fig.colorbar(im,cax=cax,orientation='horizontal',ticks=[0,25,50,75,100]);cb.solids.set_rasterized(False);cb.set_label('Detected interventions (%)',labelpad=3)
    fig.text(.31,.025,'Small-experiment normal alarms: 0/88 each. MTC cost is shown in F07b.',fontsize=8)
    save(fig,'F07a',size)
    # Same T/F/U/FAILED colour and hatch semantics as F02; no widened slivers.
    size=(180,151);fig=plt.figure(figsize=(size[0]/25.4,size[1]/25.4))
    ax=fig.add_axes([.15,.25,.25,.54]);tab=fig.add_axes([.425,.25,.56,.54],sharey=ax)
    rows=data['F07b'];y=np.arange(12);left=np.zeros(12)
    colors={'T':'#ce6b30','F':'#90b8d1','U':'#e5c365','FAILED':'#555561'};hatches={'T':'////','F':'','U':'..','FAILED':'xx'}
    for state in R2_STATES:
        vals=np.array([r[state]/r['N']*100 for r in rows]);ax.barh(y,vals,left=left,height=.67,color=colors[state],hatch=hatches[state],edgecolor='#455765',linewidth=0);left+=vals
    ax.set_yticks(y,[('S0' if r['set_id']=='S0' else 'S0 + '+r['set_id'])+' / '+r['fold'][-2:] for r in rows]);ax.tick_params(axis='y',length=0);ax.set_ylim(11.7,-.7);ax.set_xlim(0,100);ax.set_xticks([0,50,100]);ax.set_xlabel('MTC normal records (%)');ax.axvline(90,color='#152e3d',ls='--',lw=.8,zorder=5)
    tab.set_xlim(0,1);tab.axis('off');cols=[.02,.115,.205,.305,.495,.70,.89]
    for x,label in zip(cols,['T','F','U','FAILED','(T+F)/630','T / 31','Result']):tab.text(x,-1.18,label,ha='center',weight='bold')
    for i,r in enumerate(rows):
        reason='Retained' if r['selected'] else 'Coverage' if r['set_id'] in ('M','B') else 'Cov.+alarm+W'
        for x,value in zip(cols,[r['T'],r['F'],r['U'],r['FAILED'],f"{r['defined']}/{r['N']}",f"{r['T']}/{r['alarm_budget']}",reason]):tab.text(x,i,str(value),ha='center',va='center')
    for split in (2.5,5.5,8.5):ax.axhline(split,color='#d3dbe0',lw=.6);tab.axhline(split,color='#d3dbe0',lw=.6)
    fig.text(.04,.957,'F07b  Resource increments: normal costs and rejection reasons',fontsize=10,weight='bold')
    handles=[Patch(facecolor=colors[s],hatch=hatches[s],edgecolor='#455765',label=l) for s,l in zip(R2_STATES,['T: alarm','F: no alarm','U: unknown','FAILED: failure'])]
    fig.legend(handles=handles,ncol=2,loc='upper center',bbox_to_anchor=(.51,.933),frameon=False,columnspacing=2)
    fig.text(.04,.17,'Dashed line: original defined-output requirement, 567/630 (90%).',fontsize=8)
    fig.text(.04,.13,'Coverage: joint defined output below 567/630. Alarm: exceeds 31 alarms/630.',fontsize=8)
    fig.text(.04,.09,'W: candidate coverage also below its original requirement. S0 + M/B/W are rejected.',fontsize=8)
    fig.text(.04,.045,'Training group only. Historical groups 144 and 117 remain separate in T04.',fontsize=8)
    save(fig,'F07b',size)



"""F05: aggregate saved states only; no experimental entry points."""
import json
import csv
from collections import Counter
from pathlib import Path

F05_BASE = 'deliverables/app_resource_constrained_extension_v1/results/'
F05_FIXED = 'deliverables/app_resource_paired_validation_v1/results/summary/'
F05_B2C = 'deliverables/cross_endpoint_constrained_extension_v1/results/summary/summary.csv'
F05_UNIFIED = 'deliverables/app_browser_evidence_consolidation_v1/tables.json'
F05_SOURCES = [F05_BASE + p for p in ('models.json', 'members.jsonl', 'inputs.jsonl')] + [F05_B2C, F05_UNIFIED] + [F05_FIXED+p for p in ('scenarios.csv', 'model_scenarios.csv', 'models.csv', 'new_conditions.csv', 'mtc.csv')]
F05_FAMILIES = {
 'F05a': ['App_language','App_timezone','Browser_language','Browser_timezone'],
 'F05b': ['App_resource16_48','App_memory4','Browser_resource16_48','Browser_memory4'],
}
F05_LABELS = {'App_language':'App language','App_timezone':'App timezone','Browser_language':'Browser language','Browser_timezone':'Browser timezone', 'App_resource16_48':'App resource 16/48','App_memory4':'App memory 4','Browser_resource16_48':'Browser resource 16/48','Browser_memory4':'Browser memory 4'}
F05_CONDITIONS = {'M':'R_NATIVE_BROWSER_MEMORY','B':'D_BROWSER_MEMORY8','W':'R_WEB_MEMORY_DIFFERENCE'}
F05_COUNT_KEYS = ['N','T','F','U','FAILED','defined']

def _f05_counts(states):
    c=Counter(states)
    if not set(c).issubset({'T','F','U','FAILED'}):
        raise ValueError('Unexpected saved state: '+str(sorted(c)))
    return dict(N=len(states), T=c['T'], F=c['F'], U=c['U'], FAILED=c['FAILED'], defined=c['T']+c['F'])

def _f05_std(r, prefix=''):
    return dict(N=int(r.get('N',r.get('n'))), **{k:int(r[prefix+k]) for k in ['T','F','U','FAILED']}, defined=int(r[prefix+'T'])+int(r[prefix+'F']))

def _f05_sum(rows):
    return {k:sum(int(r[k]) for r in rows) for k in F05_COUNT_KEYS}

def _f05_rates(row):
    row['rate']=row['T']/row['N'] if row['N'] else None
    row['defined_rate']=row['defined']/row['N'] if row['N'] else None
    return row

def extract_f05(root):
    root=Path(root)
    checks=[]
    def check(cid,obs,exp):
        checks.append(dict(id=cid,status='PASS' if obs==exp else 'FAIL',observed=obs,expected=exp))
    def rdjson(path): return json.loads((root/path).read_text())
    def rdcsv(path):
        with (root/path).open(newline='') as f: return list(csv.DictReader(f))
    models=sorted(rdjson(F05_BASE+'models.json'),key=lambda r:r['fold'])
    unified=rdjson(F05_UNIFIED)
    b2c=rdcsv(F05_B2C)
    fixed={p:rdcsv(F05_FIXED+p+'.csv') for p in ['scenarios','model_scenarios','models','new_conditions','mtc']}
    # Read only members and the saved states needed here, never raw fingerprints.
    members={}
    for ln,line in enumerate((root/(F05_BASE+'members.jsonl')).read_text().splitlines(),1):
        r=json.loads(line)
        if r['cohort'] in ['pilot18','b2b42','resource54']:
            members[r['sample_id']]={k:r[k] for k in ['cohort','identity','family']}
            members[r['sample_id']]['member_line']=ln
    inputs={}
    for ln,line in enumerate((root/(F05_BASE+'inputs.jsonl')).read_text().splitlines(),1):
        r=json.loads(line)
        if r['sample_id'] in members:
            inputs[r['sample_id']]={k:r[k] for k in ['cohort','identity','app_states','base_states','conditions']}
            inputs[r['sample_id']]['input_line']=ln
    check('F05_member_input_join',set(members)==set(inputs),True)
    check('F05_saved_model_configurations',[x['fold'][-2:] for x in models],['01','02','03'])
    for co,n in [('pilot18',18),('b2b42',42),('resource54',54)]:
        check('F05_'+co+'_positions',sum(r['cohort']==co for r in members.values()),n)
    rows={k:[] for k in F05_FAMILIES}
    cohort_rows=[]
    member_refs=[]
    methods=[]
    for model in models:
        cfg=model['fold'][-2:]
        for method,statekey in [('APP_FULL','app_states'),('PAIRED_BASE','base_states')]:
            methods.append(dict(method=method,configuration=cfg,method_role='complete_app' if method=='APP_FULL' else 'retained_complete_paired_base',model_id=model['app_model_id'] if method=='APP_FULL' else model['base_model_id'],saved_state_key=model['base_model_id'],fold=model['fold'],description='Full App; no independent Browser' if method=='APP_FULL' else 'App + cross-endpoint timezone; retained resource S0'))
            for fig,cos in [('F05a',['pilot18','b2b42']),('F05b',['resource54'])]:
                for group in F05_FAMILIES[fig]+['NORMAL']:
                    ids=[sid for sid,r in members.items() if r['cohort'] in cos and (r['identity']=='NORMAL' if group=='NORMAL' else r['identity']=='EFFECTIVE_INTERVENTION' and r['family']==group)]
                    states=[inputs[sid][statekey][model['base_model_id']] for sid in ids]
                    row=dict(figure=fig,dataset='language_timezone60' if fig=='F05a' else 'resource54',method=method,configuration=cfg,method_role=methods[-1]['method_role'],family=group,identity='NORMAL' if group=='NORMAL' else 'EFFECTIVE_INTERVENTION',**_f05_counts(states),source_path=F05_BASE+'inputs.jsonl',source_locator=statekey+'['+model['base_model_id']+']; input lines '+','.join(str(inputs[s]['input_line']) for s in ids),members_source_path=F05_BASE+'members.jsonl',members_source_locator='lines '+','.join(str(members[s]['member_line']) for s in ids))
                    rows[fig].append(_f05_rates(row))
                    for sid in ids:
                        member_refs.append(dict(figure=fig,method=method,configuration=cfg,method_role=row['method_role'],cohort=members[sid]['cohort'],identity=row['identity'],family=group,state=inputs[sid][statekey][model['base_model_id']],source_path=F05_BASE+'inputs.jsonl',source_locator='line '+str(inputs[sid]['input_line'])+'; '+statekey+'['+model['base_model_id']+']',members_source_path=F05_BASE+'members.jsonl',members_source_locator='line '+str(members[sid]['member_line'])))
                    # Preserve old pilot and matched cohorts independently in T04.
                    for co in cos:
                        selected=[sid for sid in ids if members[sid]['cohort']==co]
                        cr=dict(row,cohort=co,**_f05_counts([inputs[s][statekey][model['base_model_id']] for s in selected]))
                        cr['source_locator']=statekey+'['+model['base_model_id']+']; input lines '+','.join(str(inputs[s]['input_line']) for s in selected)
                        cr['members_source_locator']='lines '+','.join(str(members[s]['member_line']) for s in selected)
                        cohort_rows.append(_f05_rates(cr))
                        if fig=='F05a':
                            src=[r for r in b2c if r['model_id']==model['base_model_id'] and r['cohort']==co and r['group']==('NORMAL' if group=='NORMAL' else 'family:'+group)]
                            expected=_f05_sum([_f05_std(r,'base_' if method=='APP_FULL' else '') for r in src])
                            check('F05a_B2C_'+cfg+'_'+method+'_'+co+'_'+group,{k:cr[k] for k in F05_COUNT_KEYS},expected)
                # Check independent unified endpoint summary; do not add ALL rows.
                displayed=[r for r in rows[fig] if r['configuration']==cfg and r['method']==method]
                src=[r for r in unified['paired'] if r['dataset']==row['dataset'] and r['label']==method+'_'+cfg]
                check('F05_unified_key_'+fig+'_'+method+'_'+cfg,len(src),1)
                for endpoint in ['App','Browser','NORMAL']:
                    selected=[r for r in displayed if r['family']=='NORMAL'] if endpoint=='NORMAL' else [r for r in displayed if r['family'].startswith(endpoint+'_')]
                    check('F05_unified_'+fig+'_'+method+'_'+cfg+'_'+endpoint,_f05_sum(selected),_f05_std(src[0][endpoint]))
            # Full resource model state verification by configuration, never models[0].
            for r in rows['F05b']:
                if r['method']!=method or r['configuration']!=cfg or method!='APP_FULL': continue
                if r['family']=='NORMAL':
                    source=[s for s in fixed['models'] if s['scheme']==method and s['fold']==model['fold'] and s['identity']=='NORMAL']
                else:
                    scenario={'App_resource16_48':'A_APP_RESOURCE','App_memory4':'A_APP_MEMORY4','Browser_resource16_48':'A_BROWSER_RESOURCE','Browser_memory4':'A_BROWSER_MEMORY4'}[r['family']]
                    source=[s for s in fixed['model_scenarios'] if s['scheme']==method and s['fold']==model['fold'] and s['scenario']==scenario and s['identity']=='CONTROLLED_INTERVENTION']
                check('F05b_original_full_'+cfg+'_'+r['family'],{k:r[k] for k in F05_COUNT_KEYS},_f05_sum([_f05_std(s) for s in source]))
    for method,condition in F05_CONDITIONS.items():
        methods.append(dict(method=method,configuration='fixed',method_role='fixed_resource_condition',model_id='',saved_state_key=condition,fold='',description={'M':'Native-Browser memory upper bound','B':'Browser reported memory > 8','W':'App Web and Browser reported memory differ'}[method]))
        for group in F05_FAMILIES['F05b']+['NORMAL']:
            ids=[sid for sid,r in members.items() if r['cohort']=='resource54' and (r['identity']=='NORMAL' if group=='NORMAL' else r['identity']=='EFFECTIVE_INTERVENTION' and r['family']==group)]
            row=dict(figure='F05b',dataset='resource54',method=method,configuration='fixed',method_role='fixed_resource_condition',family=group,identity='NORMAL' if group=='NORMAL' else 'EFFECTIVE_INTERVENTION',**_f05_counts([inputs[s]['conditions'][method] for s in ids]),source_path=F05_BASE+'inputs.jsonl',source_locator='conditions['+method+']; input lines '+','.join(str(inputs[s]['input_line']) for s in ids),members_source_path=F05_BASE+'members.jsonl',members_source_locator='lines '+','.join(str(members[s]['member_line']) for s in ids))
            rows['F05b'].append(_f05_rates(row))
            if group=='NORMAL': source=[s for s in fixed['new_conditions'] if s['condition']==condition and s['identity']=='NORMAL']
            else:
                scenario={'App_resource16_48':'A_APP_RESOURCE','App_memory4':'A_APP_MEMORY4','Browser_resource16_48':'A_BROWSER_RESOURCE','Browser_memory4':'A_BROWSER_MEMORY4'}[group]
                source=[s for s in fixed['scenarios'] if s['condition']==condition and s['scenario']==scenario and s['identity']=='CONTROLLED_INTERVENTION']
            check('F05b_original_condition_'+method+'_'+group,{k:row[k] for k in F05_COUNT_KEYS},_f05_sum([_f05_std(s) for s in source]))
            for sid in ids:
                member_refs.append(dict(figure='F05b',method=method,configuration='fixed',method_role=row['method_role'],cohort='resource54',identity=row['identity'],family=group,state=inputs[sid]['conditions'][method],source_path=F05_BASE+'inputs.jsonl',source_locator='line '+str(inputs[sid]['input_line'])+'; conditions['+method+']',members_source_path=F05_BASE+'members.jsonl',members_source_locator='line '+str(members[sid]['member_line'])))
        for endpoint in ['App','Browser','NORMAL']:
            selected=[r for r in rows['F05b'] if r['method']==method and (r['family']=='NORMAL' if endpoint=='NORMAL' else r['family'].startswith(endpoint+'_'))]
            src=[r for r in unified['paired'] if r['dataset']=='resource54' and r['label']==method]
            check('F05b_unified_condition_'+method+'_'+endpoint,_f05_sum(selected),_f05_std(src[0][endpoint]))
    mtc=[]
    for method,condition in F05_CONDITIONS.items():
        for n,s in enumerate(fixed['mtc'],2):
            if s['condition']!=condition: continue
            row=dict(method=method,configuration='fixed',method_role='fixed_resource_condition',cohort='mtc_'+s['group'],identity='NORMAL',family='NORMAL',**_f05_std(s),source_path=F05_FIXED+'mtc.csv',source_locator='CSV line '+str(n)+'; '+condition+'; '+s['group'],aggregation_role='original_cohort')
            mtc.append(_f05_rates(row))
            src=[u for u in unified['mtc_resource_conditions'] if u['condition']==condition and u['group']==s['group']]
            check('F05b_mtc_unified_'+method+'_'+s['group'],{k:row[k] for k in F05_COUNT_KEYS},_f05_std(src[0]))
        sources=[r for r in mtc if r['method']==method and r['aggregation_role']=='original_cohort']
        totals=dict(method=method,configuration='fixed',method_role='fixed_resource_condition',cohort='mtc_all891',identity='NORMAL',family='NORMAL',**_f05_sum(sources),source_path=F05_FIXED+'mtc.csv',source_locator=' + '.join(r['source_locator'] for r in sources),aggregation_role='derived_total_do_not_add_to_cohorts')
        mtc.append(_f05_rates(totals))
        check('F05b_mtc891_'+method,[totals[k] for k in ['N','T','F','U','FAILED']],{'M':[891,3,838,50,0],'B':[891,0,841,50,0],'W':[891,62,741,88,0]}[method])
    compression=[]
    for fig,rs in rows.items():
        for method in ['APP_FULL','PAIRED_BASE']:
            for family in F05_FAMILIES[fig]+['NORMAL']:
                selected=[r for r in rs if r['method']==method and r['family']==family]
                vectors=[[r[k] for k in F05_COUNT_KEYS] for r in selected]
                check(fig+'_compress_'+method+'_'+family,len(selected)==3 and all(x==vectors[0] for x in vectors),True)
                compression.append(dict(figure=fig,method=method,family=family,configurations='01;02;03',compared_fields=';'.join(F05_COUNT_KEYS),identical=all(x==vectors[0] for x in vectors),count_vector=json.dumps(vectors[0]),compression='show one configuration-equivalent count; never sum configurations'))
    data=dict(rows,T04_f05_cohorts=cohort_rows,T04_f05_mtc_conditions=mtc,T04_f05_members=member_refs,T04_f05_methods=methods,T04_f05_families=[dict(figure=fig,family=f,short_label=F05_LABELS[f],order=i+1) for fig,fs in F05_FAMILIES.items() for i,f in enumerate(fs)],T04_f05_compression=compression)
    metadata={
      'F05a':dict(name='Two modification directions: language and timezone',sources=F05_SOURCES[:5],filtering='pilot18 + b2b42; EFFECTIVE_INTERVENTION by four families, NORMAL separately',aggregation='Count saved app_states/base_states by actual base_model_id; three configurations retained; all N/T/F/U/FAILED/defined identical before display compression',method_roles={'APP_FULL':'complete_app','PAIRED_BASE':'retained_complete_paired_base'},denominators={'positions':60,'modified':14,'normal':46,'families':[2,2,5,5]},limits=['Development material; not independent blind testing','Only five additional Browser timezone detections; no language modification gain','Counts per configuration; no multiplication of sample size']),
      'F05b':dict(name='Complete methods and fixed resource checks',sources=F05_SOURCES,filtering='resource54; four effective intervention families plus 42 normal positions; MTC fixed-condition background kept separately',aggregation='Complete methods by base configuration; fixed M/B/W counted once per position; MTC groups 630/144/117 preserved with optional 891 total',method_roles={'APP_FULL':'complete_app','PAIRED_BASE':'retained_complete_paired_base','M':'fixed_resource_condition','B':'fixed_resource_condition','W':'fixed_resource_condition'},denominators={'positions':54,'modified':12,'normal':42,'families':[3,3,3,3],'MTC_cohorts':[630,144,117]},limits=['Fixed conditions are diagnostic checks, not equally trained complete models','M/B/W are not S0+M/B/W combinations','Reported memory originally 2; modification to 4 is upward only','Small-batch 0/42 does not establish zero normal-device cost'])}
    return data,checks,metadata

def _f05_heat(ax, rows, methods, families, positions=None):
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap
    cmap=LinearSegmentedColormap.from_list('f05_blue',['#f1f5f8','#1b5578'])
    if positions is None: positions=list(range(len(methods)))
    width=max(positions)+1
    matrix=np.full((len(families),width),np.nan)
    items={}
    for j,(m,x) in enumerate(zip(methods,positions)):
        for i,f in enumerate(families):
            r=next(r for r in rows if r['method']==m and r['family']==f and r['configuration'] in ['01','fixed'])
            matrix[i,x]=100*r['rate'] if r['N'] else np.nan
            items[i,x]=r
    mesh=ax.pcolormesh(np.arange(width+1),np.arange(len(families)+1),np.ma.masked_invalid(matrix),vmin=0,vmax=100,cmap=cmap,edgecolors='white',linewidth=.6,rasterized=False)
    for (i,x),r in items.items():
        label=f"{r['T']}/{r['N']}" if r['N'] else 'N/A'
        ax.text(x+.5,i+.5,label,ha='center',va='center',fontsize=9,color='white' if r['rate'] and r['rate']>=.65 else '#192a35')
    ax.set_ylim(len(families),0)
    ax.set_yticks(np.arange(len(families))+.5,[F05_LABELS[f] for f in families])
    ax.set_xticks([x+.5 for x in positions],methods)
    ax.tick_params(axis='both',length=0,pad=6)
    for spine in ax.spines.values(): spine.set_visible(False)
    return mesh

def plot_f05(data,save):
    import matplotlib.pyplot as plt
    # Single-column figure; counts never summed over model configurations.
    fig=plt.figure(figsize=(85/25.4,113/25.4))
    fig.text(.5,.975,'Language and timezone',ha='center',va='top',fontsize=10,weight='bold')
    fig.text(.5,.925,'Modification detection (T/N)',ha='center',fontsize=8)
    ax=fig.add_axes([.40,.37,.55,.47])
    mesh=_f05_heat(ax,data['F05a'],['APP_FULL','PAIRED_BASE'],F05_FAMILIES['F05a'])
    ax.set_xticklabels(['Full App','App + cross-\nendpoint TZ'])
    cbax=fig.add_axes([.41,.225,.51,.025])
    cb=fig.colorbar(mesh,cax=cbax,orientation='horizontal',ticks=[0,50,100]);cb.solids.set_rasterized(False)
    cb.set_label('Detected modifications (%)',fontsize=8,labelpad=2)
    cbax.xaxis.set_label_position('top')
    fig.text(.04,.145,'Normal (N=46): both methods',fontsize=8)
    normal=[r for r in data['F05a'] if r['family']=='NORMAL' and r['configuration']=='01']
    n=normal[0]
    fig.text(.04,.109,f"T={n['T']}, F={n['F']}, U={n['U']}, FAILED={n['FAILED']}",fontsize=8)
    fig.text(.04,.057,'Counts agree in configurations 01, 02, 03.',fontsize=8)
    fig.text(.04,.022,'Old pilot + matched controls; development.',fontsize=8)
    save(fig,'F05a',(85,113))
    plt.close(fig)
    # Dense two-column figure with explicit gap between complete methods and checks.
    fig=plt.figure(figsize=(180/25.4,142/25.4))
    fig.text(.5,.975,'Resource modifications: method roles',ha='center',va='top',fontsize=10,weight='bold')
    fig.text(.40,.91,'Complete methods',ha='center',fontsize=9,weight='bold')
    fig.text(.765,.91,'Fixed resource checks',ha='center',fontsize=9,weight='bold')
    ax=fig.add_axes([.29,.485,.66,.35])
    mesh=_f05_heat(ax,data['F05b'],['APP_FULL','PAIRED_BASE','M','B','W'],F05_FAMILIES['F05b'],[0,1,3,4,5])
    ax.set_xticklabels(['Full App','App + cross-\nendpoint TZ','M','B','W'])
    ax.xaxis.tick_top();ax.tick_params(axis='x',pad=6)
    fig.text(.29,.445,'Cells: detected modifications, T/3. Complete-method counts agree in 01/02/03.',fontsize=8)
    cbax=fig.add_axes([.37,.385,.46,.025])
    cb=fig.colorbar(mesh,cax=cbax,orientation='horizontal',ticks=[0,50,100]);cb.solids.set_rasterized(False)
    cb.set_label('Modified positions alarmed (%)',fontsize=8,labelpad=2)
    normal=next(r for r in data['F05b'] if r['method']=='APP_FULL' and r['configuration']=='01' and r['family']=='NORMAL')
    fig.text(.04,.304,f"Resource normals (N=42): all five T={normal['T']}, F={normal['F']}, U={normal['U']}, FAILED={normal['FAILED']}",fontsize=8,weight='bold')
    fig.text(.04,.267,'MTC normal background (N=891; fixed checks only)',fontsize=8,weight='bold')
    tax=fig.add_axes([.035,.082,.48,.17]);tax.axis('off')
    totals=[next(r for r in data['T04_f05_mtc_conditions'] if r['method']==m and r['cohort']=='mtc_all891') for m in ['M','B','W']]
    table=tax.table(cellText=[[r['method'],r['T'],r['F'],r['U'],r['FAILED']] for r in totals],colLabels=['Check','T','F','U','FAILED'],loc='center',cellLoc='center',bbox=[0,0,1,1])
    table.auto_set_font_size(False);table.set_fontsize(8)
    for (r,c),cell in table.get_celld().items():
        cell.set_linewidth(.4);cell.set_edgecolor('#d1d8dd')
        if r==0:cell.set_facecolor('#edf1f4')
    fig.text(.55,.236,'M: Native-Browser memory upper bound',fontsize=8)
    fig.text(.55,.198,'B: Browser reported memory > 8',fontsize=8)
    fig.text(.55,.160,'W: two Web memory reports differ',fontsize=8)
    fig.text(.55,.113,'T = alarm; F = no alarm; U = unknown.',fontsize=8)
    fig.text(.04,.04,'MTC groups 630/144/117 remain separate in T04. Memory 2 to 4 is an upward change.',fontsize=8)
    save(fig,'F05b',(180,142))
    plt.close(fig)


"""Saved-results-only extraction and plotting for F06a, F06b and F08."""
import csv
import json
from pathlib import Path

F06_BASE = 'deliverables/cross_endpoint_four_view_comparison_v1/results/'
F08_BASE = 'deliverables/prepaper_evidence_closeout_v1/'
F06_F08_SOURCES = [
    F06_BASE+'main_comparison.csv', F06_BASE+'summary/summary.csv',
    F06_BASE+'SETTINGS.json', F06_BASE+'models.json',
    F06_BASE+'features.jsonl', F06_BASE+'predictions.jsonl', F06_BASE+'P0_V_BOTH_REL.txt',
    F08_BASE+'tables/four_view.csv', F08_BASE+'tables/four_view_all_cohorts.csv',
    F08_BASE+'figures/fig04_preference_recipe.csv',
]
F06_VIEWS = ['V_APP', 'V_BROWSER', 'V_BOTH', 'V_BOTH_REL']
F06_LABELS = ['App\n7 measures', 'Browser\n4 measures', 'Both\n11 measures', 'Both + relations\n11 + C1/C2']


def extract_f06_f08(root):
    root = Path(root)
    def read_csv(p):
        with (root/p).open(encoding='utf-8', newline='') as f:
            return list(csv.DictReader(f))
    checks = []
    def ck(name, actual, expected):
        checks.append({'id': name, 'status': 'PASS' if actual == expected else 'FAIL',
                       'observed': actual, 'expected': expected})
    main = read_csv(F06_BASE+'main_comparison.csv')
    summary = read_csv(F06_BASE+'summary/summary.csv')
    old = read_csv(F08_BASE+'tables/four_view.csv')
    allold = read_csv(F08_BASE+'tables/four_view_all_cohorts.csv')
    cases = read_csv(F08_BASE+'figures/fig04_preference_recipe.csv')
    settings = json.loads((root/(F06_BASE+'SETTINGS.json')).read_text())
    models = json.loads((root/(F06_BASE+'models.json')).read_text())  # metadata only
    ck('F06.main_grid_count',len(main),12)
    ck('F08.case_count',len(cases),7)
    ck('F06.raw_view_sizes',[len(settings['views'][v]) for v in F06_VIEWS],[7,4,11,13])
    sindex = {(x['plan'],x['view'],x['role'],x['cohort'],x['group']):(i,x) for i,x in enumerate(summary,2)}
    oldindex = {(x['plan'],x['view']):x for x in old}
    modelindex = {(x['plan'],x['view']):x for x in models}
    data = {'F06a':[], 'F06b':[], 'F08':[], 'T04_four_view_all_cohorts':[],
            'T04_four_view_input_completeness':[], 'T04_four_view_model_mapping':[],
            'T04_four_view_scheme_mapping':[], 'T04_four_view_view_mapping':[],
            'T04_four_view_main_families':[]}
    def normalized(x, path, locator, **extra):
        n=int(x['n']); t=int(x['T']); f=int(x['F']); u=int(x['U']); failed=int(x['FAILED'])
        return dict(N=n,T=t,F=f,U=u,FAILED=failed,defined=t+f,
                    rate=t/n if n else '',defined_rate=(t+f)/n if n else '',
                    source_path=path,source_locator=locator,method_role='four_view_small_tree',**extra)
    for i,x in enumerate(summary,2):
        row=normalized(x,F06_BASE+'summary/summary.csv',f'CSV row {i}',
             plan=x['plan'],view=x['view'],role=x['role'],cohort=x['cohort'],group=x['group'],
             input_complete=int(x['input_complete']),partial_input_binary=int(x['partial_input_binary']),
             unseen_category_positions=int(x['unseen_category_positions']),
             aggregation_note='all / identity / family / scenario overlap; never sum across group levels')
        data['T04_four_view_all_cohorts'].append(row)
        ck(f'F06.summary_row_{i}.partition', row['T']+row['F']+row['U']+row['FAILED'],row['N'])
        ck(f'F06.summary_row_{i}.defined',row['defined'],int(x['defined']))
    for i,x in enumerate(allold,2):
        group='scenario:L_BROWSER_LANG:change' if x['group']=='normal_browser_preference_change' else x['group']
        key=(x['plan'],x['setting'],x['role'],x['cohort'],group)
        _,s=sindex[key]
        ck(f'F06.old_allcohorts_row_{i}',[int(s[k]) for k in ['n','T','F','U','FAILED','defined','input_complete','partial_input_binary']],
           [int(x[k]) for k in ['denominator','T','F','U','FAILED','defined','input_complete','partial_input_binary']])
    for i,m in enumerate(main,2):
        plan,view=m['plan'],m['view']
        cohorts=['pilot18','b2b42'] if plan=='P0' else [settings['holdout'][plan]]
        role='training' if plan=='P0' else 'batch_holdout_development'
        prev=oldindex[(plan,view)]
        for prefix,group,figid in [('attack','EFFECTIVE_INTERVENTION','F06a'),('normal','NORMAL','F06b')]:
            ss=[sindex[(plan,view,role,c,group)] for c in cohorts]
            sums={k:sum(int(x[k]) for _,x in ss) for k in ['n','T','F','U','FAILED','input_complete','partial_input_binary']}
            ck(f'{figid}.{plan}.{view}.main_vs_summary',[int(m[prefix+'_'+k]) for k in ['n','T','U','FAILED']],
               [sums[k] for k in ['n','T','U','FAILED']])
            ck(f'{figid}.{plan}.{view}.old_crossref',[int(m[prefix+'_'+k]) for k in ['n','T']],
               [int(prev[prefix+'_'+k]) for k in ['n','T']])
            row=normalized(sums,F06_BASE+'main_comparison.csv',f'CSV row {i}; '+prefix,
                  plan=plan,view=view,role=role,cohort='+'.join(cohorts),group=group,
                  model_id=modelindex[(plan,view)]['model_id'],
                  input_complete=sums['input_complete'],partial_input_binary=sums['partial_input_binary'],
                  summary_source_path=F06_BASE+'summary/summary.csv',
                  summary_source_locator='; '.join(f'CSV row {j}' for j,_ in ss))
            data[figid].append(row)
        for family in ['App_language','App_timezone','Browser_language','Browser_timezone']:
            ss=[(j,x) for (p,v,r,c,g),(j,x) in sindex.items() if (p,v,r)==(plan,view,role) and c in cohorts and g=='family:'+family]
            sums={k:sum(int(x[k]) for _,x in ss) for k in ['n','T','F','U','FAILED']}
            ck(f'F06.family.{plan}.{view}.{family}',[sums['T'],sums['n']],[int(m[family+'_T']),int(m[family+'_n'])])
            data['T04_four_view_main_families'].append(normalized(sums,F06_BASE+'main_comparison.csv',f'CSV row {i}; {family}',plan=plan,view=view,role=role,family=family))
    for model in models:
        p,v=model['plan'],model['view']
        row=dict(model,method_role='four_view_small_tree',source_path=F06_BASE+'models.json',source_locator=f'plan={p}; view={v}')
        data['T04_four_view_model_mapping'].append(row)
        ss=[(i,x) for i,x in enumerate(summary,2) if x['plan']==p and x['view']==v and x['group']=='all']
        sums={k:sum(int(x[k]) for _,x in ss) for k in ['n','T','F','U','FAILED','input_complete','partial_input_binary']}
        data['T04_four_view_input_completeness'].append(normalized(sums,F06_BASE+'summary/summary.csv',
            '; '.join(f'CSV row {i}' for i,_ in ss), plan=p,view=v,
            role='all distinct cohorts; training + heldout development + historical evaluation',
            input_complete=sums['input_complete'],partial_input_binary=sums['partial_input_binary']))
        ck(f'F06.input_n.{p}.{v}',sums['n'],951)
        if v in ['V_BOTH','V_BOTH_REL']:
            ck(f'F06.partial_input.{p}.{v}',sums['partial_input_binary'],33)
        train=sum(int(x['n']) for _,x in ss if x['role']=='training')
        ck(f'F06.train_n.{p}.{v}',train,model['training_positions'])
    for p in ['P0','P1','P2']:
        data['T04_four_view_scheme_mapping'].append(dict(plan=p,train_cohorts=' + '.join(settings['train_cohorts'][p]),
            training_N=modelindex[(p,'V_APP')]['training_positions'],
            main_cohort='pilot18 + b2b42' if p=='P0' else settings['holdout'][p],
            main_role='in_sample_training' if p=='P0' else 'whole_batch_holdout_previously_seen_development_material',
            historical_evaluation='mtc_development:144; mtc_reserved_validation:117',
            limitation='P2 has no App-direction intervention in training' if p=='P2' else 'development comparison; not blind test',
            source_path=F06_BASE+'SETTINGS.json',source_locator=f'train_cohorts.{p}; holdout.{p}'))
    for v in F06_VIEWS:
        data['T04_four_view_view_mapping'].append(dict(view=v,short_label=F06_LABELS[F06_VIEWS.index(v)].replace('\n','; '),
            measures='; '.join(settings['views'][v]),method_role='four_view_small_tree',
            source_path=F06_BASE+'SETTINGS.json',source_locator=f'views.{v}',
            limitation='Restricted language/timezone derived inputs; not the full 177/67-field ceiling; V_APP is not Full App'))
    _,counter=sindex[('P1','V_BOTH_REL','training','b2b42','NORMAL')]
    ck('F06.P1_relation_training_counterexample',[int(counter['T']),int(counter['n'])],[2,34])
    for v in ['V_BOTH','V_BOTH_REL']:
        rr=[x for x in data['T04_four_view_main_families'] if x['plan']=='P2' and x['view']==v]
        for side,expected in [('App',[0,4]),('Browser',[4,4])]:
            ck(f'F06.P2.{v}.{side}',[sum(x[k] for x in rr if x['family'].startswith(side)) for k in ['T','N']],expected)
    # Read only the seven previously published case feature rows and saved outputs.
    wanted={x['sample_id'] for x in cases}
    features={}; predictions={}
    with (root/(F06_BASE+'features.jsonl')).open(encoding='utf-8') as f:
        for i,line in enumerate(f,1):
            x=json.loads(line)
            if x['sample_id'] in wanted: features[x['sample_id']]=(i,x)
    with (root/(F06_BASE+'predictions.jsonl')).open(encoding='utf-8') as f:
        for i,line in enumerate(f,1):
            x=json.loads(line)
            if x['sample_id'] in wanted and x['view']=='V_BOTH_REL':
                predictions[(x['sample_id'],x['plan'])]=(i,x)
    ck('F08.saved_feature_count',len(features),7)
    ck('F08.saved_relation_output_count',len(predictions),21)
    for i,x in enumerate(cases,2):
        fl,feat=features[x['sample_id']]
        row={k:x[k] for k in ['cohort','identity','scenario','app_first_language','browser_first_language','browser_language_count','C1','C2']}
        row.update(case=f'C{i-1:02d}',source_row=i,source_path=F08_BASE+'figures/fig04_preference_recipe.csv',source_locator=f'CSV row {i}',
                   feature_source_path=F06_BASE+'features.jsonl',feature_source_locator=f'JSONL line {fl}',method_role='saved_preference_recipe_case')
        for field in ['app_first_language','browser_first_language','browser_language_count','C1','C2']:
            ck(f'F08.row_{i}.{field}',str(feat['cells'][field]['value']),x[field])
        for p in ['P0','P1','P2']:
            pl,pred=predictions[(x['sample_id'],p)]
            row[p+'_state']=x[p+'_V_BOTH_REL']
            row[p+'_role']=pred['role']
            row[p+'_source_locator']=f'JSONL line {pl}'
            expected_role='training' if x['cohort'] in settings['train_cohorts'][p] else 'batch_holdout_development'
            ck(f'F08.row_{i}.{p}.state',pred['state'],row[p+'_state'])
            ck(f'F08.row_{i}.{p}.role',pred['role'],expected_role)
        row['prediction_source_path']=F06_BASE+'predictions.jsonl'
        data['F08'].append(row)
    tree=(root/(F06_BASE+'P0_V_BOTH_REL.txt')).read_text()
    ck('F08.saved_P0_branch_present',all(s in tree for s in ['C1=T <= 0.50','C2=T >  0.50','browser_language_count <= 2.50','browser_language_count >  2.50']),True)
    ck('F08.identities',[sum(x['identity']==s for x in cases) for s in ['NORMAL','EFFECTIVE_INTERVENTION']],[2,5])
    common={
        'sources':F06_F08_SOURCES[:4]+F06_F08_SOURCES[7:9],
        'filtering':'main_comparison.csv: all 12 plan/view rows; P0 both small cohorts training; P1 pilot18 heldout; P2 b2b42 heldout',
        'aggregation':'sum disjoint cohort identity rows from original summary; compare each main cell and all four families; old closeout tables are cross-check only',
        'method_roles':{'all':'four_view_small_tree; restricted language/timezone inputs, separate from Full App and resource rules'},
        'denominators':{'P0':{'modified':14,'normal':46,'training':690},'P1':{'modified':6,'normal':12,'training':672},'P2':{'modified':8,'normal':34,'training':648}},
        'limits':['P0 is in sample; P1/P2 are whole-batch holdout of development material previously encountered in research, not new blind tests.',
                  'P1 relationship tree alarms on 2/34 matched training normals despite 0/12 heldout normal alarms.',
                  'P2 Both and Both+relations each detect App 0/4 and Browser 4/4; App interventions were absent from training.',
                  'Each two-endpoint tree has 33/951 partially observed inputs. Binary output does not restore observations; U is not added.',
                  'Schemes are not independent replicates and must not be pooled; all training/evaluation cohorts and states remain in T04.'],
        'count_compression':'none; each of 12 scheme/view cells is distinct'}
    metadata={'F06a':dict(common,name='Four input views: modified positions'),
              'F06b':dict(common,name='Four input views: normal alarms'),
              'F08':dict(name='Saved language preference and script cases',sources=[F06_F08_SOURCES[i] for i in [2,4,5,6,9]],
               filtering='all 7 rows of fig04_preference_recipe.csv; source CSV row numbers replace original position IDs',
               aggregation='none; 7 source cases, not 21 tests; existing outputs and roles checked against saved predictions',
               method_roles={'C2':'fixed_language_relation','P0/P1/P2':'four_view_relation_small_tree'},
               denominators={'cases':7,'normal':2,'modified':5},count_compression='none; all seven original case rows retained',
               saved_branch='P0_V_BOTH_REL.txt: C1=T <=0.50, C2=T >0.50, browser_language_count <=2.50 alarms; >2.50 no alarm',
               limits=['Preference examples have Browser list length 3, scripted modifications length 1; no list members are inferred.',
                       'P0 separates the saved recipes; P1/P2 alarm on both normal preferences. This is not a general attack rule.',
                       'P0 both cohorts in training; P1 matched training/pilot heldout; P2 pilot training/matched heldout.',
                       'Seven positions do not establish equality across 244 inputs or an attack success rate.'])}
    return data, checks, metadata


def plot_f06_f08(data, save):
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    import numpy as np
    cmap=LinearSegmentedColormap.from_list('fv_blue',['#f1f5f8','#1b5578'])
    for fid,title,metric in [('F06a','F06a  Four input views: modified positions','Alarm on modified positions (%)'),
                             ('F06b','F06b  Four input views: normal alarms','Alarm on normal positions (%) — lower is better')]:
        fig=plt.figure(figsize=(180/25.4,108/25.4))
        fig.text(.03,.962,title,fontsize=10,weight='bold',va='top')
        fig.text(.03,.903,'Restricted language/timezone trees · cell labels: T/N · all cells U = FAILED = 0',fontsize=8)
        ax=fig.add_axes([.31,.445,.65,.33])
        rr={(x['plan'],x['view']):x for x in data[fid]}
        arr=np.array([[rr[(p,v)]['rate']*100 for v in F06_VIEWS] for p in ['P0','P1','P2']])
        mesh=ax.pcolormesh(np.arange(5),np.arange(4),arr,cmap=cmap,vmin=0,vmax=100,
                           edgecolors='white',linewidth=2,rasterized=False)
        ax.invert_yaxis();ax.set_xticks(np.arange(4)+.5,F06_LABELS)
        ax.set_yticks(np.arange(3)+.5,['P0 · in sample\nPilot18 + matched42','P1 · pilot heldout\nPreviously seen material','P2 · matched heldout\nPreviously seen material'])
        ax.xaxis.tick_top();ax.tick_params(length=0,pad=8)
        for i,p in enumerate(['P0','P1','P2']):
            for j,v in enumerate(F06_VIEWS):
                r=rr[(p,v)]
                ax.text(j+.5,i+.5,f"{r['T']}/{r['N']}",ha='center',va='center',fontsize=10,
                        color='white' if arr[i,j]>=58 else '#172e3b')
        for spine in ax.spines.values():spine.set_visible(False)
        cax=fig.add_axes([.31,.352,.65,.025])
        cb=fig.colorbar(mesh,cax=cax,orientation='horizontal',ticks=[0,25,50,75,100]);cb.set_label(metric,labelpad=2)
        cb.outline.set_visible(False)
        if cb.solids is not None: cb.solids.set_rasterized(False)
        fig.text(.03,.24,'Training: P0 = MTC630 + pilot18 + matched42; P1 = MTC630 + matched42;',fontsize=8)
        fig.text(.03,.19,'P2 = MTC630 + pilot18 (no App-side modifications). Pair F06a with F06b.',fontsize=8)
        if fid=='F06a':
            fig.text(.03,.125,'P2 Both / Both + relations: App 0/4; Browser 4/4. Do not pool the three schemes.',fontsize=8)
        else:
            fig.text(.03,.125,'P1 relation tree: heldout normals 0/12, but matched training normals 2/34.',fontsize=8,weight='bold')
        fig.text(.03,.065,'T04: full cohort results; each two-endpoint tree has 33/951 partially observed inputs.',fontsize=8)
        save(fig,fid,(180,108))
    fig=plt.figure(figsize=(180/25.4,122/25.4))
    fig.text(.025,.963,'F08  Browser language preferences and scripted modifications',fontsize=10,weight='bold',va='top')
    fig.text(.025,.908,'Seven saved cases · T = alarm, F = no alarm · model cells also show evaluation role',fontsize=8)
    ax=fig.add_axes([.025,.36,.95,.49]);ax.axis('off')
    labels=['Source /\nCSV row','Identity','App\nfirst','Browser\nfirst','Browser\nlist len.','Fixed\nC2','P0\nrelation tree','P1\nrelation tree','P2\nrelation tree']
    cells=[]
    for r in data['F08']:
        source='Pilot' if r['cohort']=='pilot18' else 'Matched'
        cells.append([f"{source} / {r['source_row']}", 'Normal\npreference' if r['identity']=='NORMAL' else 'Scripted\nmodification',
            r['app_first_language'],r['browser_first_language'],r['browser_language_count'],r['C2']]+[
                f"{r[p+'_state']} / {'train' if r[p+'_role']=='training' else 'heldout'}" for p in ['P0','P1','P2']])
    table=ax.table(cellText=cells,colLabels=labels,cellLoc='center',colLoc='center',
                   colWidths=[.123,.148,.079,.083,.095,.055,.139,.139,.139],bbox=[0,0,1,1])
    table.auto_set_font_size(False);table.set_fontsize(8)
    for (i,j),cell in table.get_celld().items():
        cell.set_edgecolor('#ccd6db');cell.set_linewidth(.55)
        if i==0:cell.set_facecolor('#e7edf1');cell.set_text_props(weight='bold')
        else:
            is_normal=data['F08'][i-1]['identity']=='NORMAL'
            cell.set_facecolor('#f3f6f8' if is_normal else 'white')
            if j>=5:
                state=data['F08'][i-1]['C2'] if j==5 else data['F08'][i-1][['P0','P1','P2'][j-6]+'_state']
                if state=='T':cell.set_facecolor('#1b5578');cell.set_text_props(color='white')
    fig.text(.025,.29,'First-language differences occur in both normal preferences and scripted modifications.',fontsize=8)
    fig.text(.025,.237,'P0 saved branch (C1 = F, C2 = T): Browser list length ≤ 2.5 → T; > 2.5 → F.',fontsize=8)
    fig.text(.025,.184,'P0 distinguishes these recipes; P1 and P2 alarm on both normal preference cases.',fontsize=8)
    fig.text(.025,.131,'train = in sample; heldout = whole-batch development holdout of previously seen material.',fontsize=8)
    fig.text(.025,.078,'P1: matched train / pilot heldout. P2: pilot train / matched heldout. No general length rule.',fontsize=8)
    save(fig,'F08',(180,122))


def r2_plot_all(data, output):
    os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'rba-round2-mpl'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.text import Text
    from PIL import Image
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,
        'axes.labelsize':8,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,
        'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none',
        'svg.hashsalt':R2_OWNER,'savefig.dpi':300,'hatch.linewidth':.35})
    specs={}
    def save(fig,id_,size):
        fig.canvas.draw();renderer=fig.canvas.get_renderer();outside=[];fonts=[]
        for artist in fig.findobj(match=Text):
            if not artist.get_visible() or not artist.get_text():continue
            fonts.append(artist.get_fontsize());box=artist.get_window_extent(renderer)
            if box.width and box.height and (box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.width+1 or box.y1 > fig.bbox.height+1):
                outside.append(artist.get_text())
        if outside:raise ValueError((id_,'text outside canvas',outside))
        if min(fonts)<8:raise ValueError((id_,'font below 8 pt',min(fonts)))
        fig.savefig(output/'figures'/(id_+'.svg'),metadata={'Date':None})
        fig.savefig(output/'figures'/(id_+'.png'),dpi=300,metadata={'Software':R2_OWNER})
        if os.environ.get('RBA_ROUND2_QA_DIR'):
            qa=Path(os.environ['RBA_ROUND2_QA_DIR']);qa.mkdir(parents=True,exist_ok=True)
            fig.savefig(qa/(id_+'_96dpi.png'),dpi=96)
        with Image.open(output/'figures'/(id_+'.png')) as im:pixels=list(im.size)
        specs[id_]=dict(id=id_,svg='figures/'+id_+'.svg',png='figures/'+id_+'.png',
            plotting_csv='data/'+id_+'.csv',size_mm=list(size),dpi=300,
            pixel_dimensions=pixels,minimum_font_pt=min(fonts),text_canvas_bounds='PASS')
        plt.close(fig)
    plot_f05(data,save);plot_f06_f08(data,save);plot_f07(data,save)
    return specs


def r2_saved_checks(output):
    """Read only this delivery's saved files; do not open source results or plot."""
    import struct
    import xml.etree.ElementTree as ET
    manifest=r2_json(output/'FIGURES.json');checks=[];tables={}
    r2_check(checks,'output_owner',manifest['owner'],R2_OWNER)
    r2_check(checks,'seven_ids',[x['id'] for x in manifest['figures']],R2_IDS)
    for file in manifest['data_files']:
        path=output/file['path'];rows=r2_csv(path);tables[path.stem]=rows
        r2_check(checks,file['path']+'_digest',r2_digest(path),file['sha256'])
        r2_check(checks,file['path']+'_rows',len(rows),file['rows'])
        for i,r in enumerate(rows,2):
            key=f'{path.stem}:row{i}'
            if all(k in r and r[k]!='' for k in R2_COUNTS):
                c={k:int(r[k]) for k in R2_COUNTS}
                r2_check(checks,key+'_partition',sum(c[k] for k in R2_STATES),c['N'])
                r2_check(checks,key+'_defined',c['T']+c['F'],c['defined'])
                r2_check(checks,key+'_nonnegative',all(v>=0 for v in c.values()),True)
                for rate,numerator in [('rate','T'),('defined_rate','defined')]:
                    if rate not in r:continue
                    if c['N']:
                        r2_check(checks,key+'_'+rate,abs(float(r[rate])-c[numerator]/c['N'])<1e-12,True)
                    else:r2_check(checks,key+'_'+rate+'_not_applicable',r[rate] in ('','None'),True)
    for id_,n in zip(R2_IDS,[30,45,12,12,96,12,7]):
        r2_check(checks,id_+'_uncompressed_rows',len(tables[id_]),n)
    candidates=tables['T04_resource_candidates']
    r2_check(checks,'24_preserved_candidates',len(candidates),24)
    r2_check(checks,'saved_selection_S0_only',[r['set_id'] for r in candidates if r['selected']=='True'],['S0']*3)
    r2_check(checks,'saved_other_candidates_rejected',all(r['feasible']=='False' and r['reasons'] for r in candidates if r['set_id']!='S0'),True)
    r2_check(checks,'F08_all_original_rows',[int(r['source_row']) for r in tables['F08']],list(range(2,9)))
    r2_check(checks,'F08_two_normal_five_modified',dict(Counter(r['identity'] for r in tables['F08'])),{'NORMAL':2,'EFFECTIVE_INTERVENTION':5})
    for r in tables['F08']:
        expected={'P0':'training','P1':'training' if r['cohort']=='b2b42' else 'batch_holdout_development',
            'P2':'training' if r['cohort']=='pilot18' else 'batch_holdout_development'}
        r2_check(checks,r['case']+'_roles',{p:r[p+'_role'] for p in expected},expected)
    ns='{http://www.w3.org/2000/svg}'
    for fig in manifest['figures']:
        id_=fig['id'];svgpath=output/fig['svg'];pngpath=output/fig['png']
        for kind,path in [('svg',svgpath),('png',pngpath)]:
            r2_check(checks,id_+'_'+kind+'_digest',r2_digest(path),fig[kind+'_sha256'])
        svg=ET.parse(svgpath).getroot()
        for axis,mm in zip(('width','height'),fig['size_mm']):
            value=svg.attrib[axis]
            r2_check(checks,id_+'_svg_'+axis,value.endswith('pt') and abs(float(value[:-2])*25.4/72-mm)<.001,True)
        r2_check(checks,id_+'_svg_no_raster_images',len(svg.findall('.//'+ns+'image')),0)
        r2_check(checks,id_+'_svg_has_vector_paths',len(svg.findall('.//'+ns+'path'))>0,True)
        r2_check(checks,id_+'_svg_has_text',len(svg.findall('.//'+ns+'text'))>0,True)
        b=pngpath.read_bytes();r2_check(checks,id_+'_png_signature',b[:8]==b'\x89PNG\r\n\x1a\n',True)
        pos=8;pixels=None;dpi=None
        while pos<len(b):
            length=struct.unpack('>I',b[pos:pos+4])[0];kind=b[pos+4:pos+8];payload=b[pos+8:pos+8+length]
            if kind==b'IHDR':pixels=list(struct.unpack('>II',payload[:8]))
            if kind==b'pHYs':
                x,y,unit=struct.unpack('>IIB',payload);dpi=[x*.0254,y*.0254] if unit==1 else None
            pos+=12+length
        r2_check(checks,id_+'_png_dimensions',pixels,fig['pixel_dimensions'])
        r2_check(checks,id_+'_png_300dpi',bool(dpi and min(dpi)>=299.99),True)
    return checks


def r2_main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=R2_HERE)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args();output=args.output.resolve()
    if args.check_only:
        checks=r2_saved_checks(output);failed=[r for r in checks if r['status']!='PASS']
        print(json.dumps(dict(mode='saved_outputs_only',checks=len(checks),failed=failed,source_reads=0,output_writes=0),ensure_ascii=False))
        return 1 if failed else 0
    output.mkdir(parents=True,exist_ok=True)
    previous=r2_json(output/'FIGURES.json') if (output/'FIGURES.json').exists() else None
    if previous and previous.get('owner')!=R2_OWNER:raise ValueError('Unknown output ownership: '+str(output))
    if not previous:
        unknown=[str(p.relative_to(output)) for p in output.rglob('*') if p.is_file() and p.name not in ('plot_round2.py','README.md','CAPTIONS.md')]
        if unknown:raise ValueError('Unowned output files: '+str(unknown))
    oldcheck=r2_json(output/'CHECK.json') if (output/'CHECK.json').exists() else {}
    sources=sorted(set(F05_SOURCES+F06_F08_SOURCES+F07_SOURCES))
    before={p:r2_digest(R2_ROOT/p) for p in sources}
    first=R2_HERE.parent/'round1_app'
    round1_before={str(p.relative_to(R2_ROOT)):r2_digest(p) for p in first.rglob('*') if p.is_file()}
    data={};checks=[];metadata={}
    for extract in (extract_f05,extract_f06_f08,extract_f07):
        d,c,m=extract(R2_ROOT)
        if data.keys()&d.keys():raise ValueError('Duplicate data table')
        data.update(d);checks.extend(c);metadata.update(m)
    for id_ in ['F05a','F05b','F06a','F06b','F07a']:
        r2_check(checks,id_+'_display_zero_U_FAILED',all(r['U']==0 and r['FAILED']==0 for r in data[id_]),True)
    r2_check(checks,'F07_small_experiment_normals_all_zero_alarm',all(r['T']==r['U']==r['FAILED']==0 and r['N']==88 for r in data['T04_resource_aggregates'] if r['cohort']=='small_experiments' and r['identity']=='NORMAL'),True)
    failed=[r for r in checks if r['status']!='PASS']
    if failed:raise ValueError(json.dumps(failed,ensure_ascii=False,indent=2))
    (output/'data').mkdir(exist_ok=True);(output/'figures').mkdir(exist_ok=True)
    targets={f'data/{name}.csv' for name in data}|{f'figures/{id_}.{ext}' for id_ in R2_IDS for ext in ('svg','png')}
    if previous:
        owned={r['path'] for r in previous['data_files']}|{r[k] for r in previous['figures'] for k in ('svg','png')}
        unknown=[p for p in targets if (output/p).exists() and p not in owned]
        if unknown:raise ValueError('Refusing to overwrite unowned outputs: '+str(unknown))
    # Render in a temporary staging directory; failed plotting leaves no unowned partial outputs.
    with tempfile.TemporaryDirectory(prefix='rba-round2-render-') as stage_name:
        stage=Path(stage_name);(stage/'data').mkdir();(stage/'figures').mkdir()
        for name,rows in data.items():r2_write_csv(stage/'data'/(name+'.csv'),rows)
        specs=r2_plot_all(data,stage)
        for path in sorted(targets):(stage/path).replace(output/path)
    figures=[]
    for id_ in R2_IDS:
        meta=dict(metadata[id_]);meta['sources']=[dict(path=p,sha256=before[p]) for p in meta['sources']]
        meta.setdefault('count_compression','All N/T/F/U/FAILED/defined counts match before configuration compression; configurations remain separate in CSV.' if id_ in ('F05a','F05b','F07a') else 'No configuration compression.')
        summary_keys=('configuration','fold','method','method_role','family','set_id','plan','view','identity','N','T','F','U','FAILED','defined','selected','feasible','reasons')
        figures.append(dict(meta,**specs[id_],status=R2_STATUS,
            counts=[{k:r[k] for k in summary_keys if k in r} for r in data[id_]] if id_!='F08' else [],
            cases=data[id_] if id_=='F08' else [],
            svg_sha256=r2_digest(output/specs[id_]['svg']),png_sha256=r2_digest(output/specs[id_]['png'])))
    manifest=dict(owner=R2_OWNER,status=R2_STATUS,figures=figures,
        source_files=[dict(path=p,sha256=h) for p,h in before.items()],
        data_files=[dict(path='data/'+name+'.csv',rows=len(rows),sha256=r2_digest(output/'data'/(name+'.csv'))) for name,rows in data.items()],
        operations=dict(collection=0,fitting=0,selection=0,condition_or_model_prediction=0,retiming=0,network=0),
        scope='Saved derived states, count aggregation, plotting only. No model objects or experimental entry points. No raw fingerprints or original member IDs exported.')
    r2_write_json(output/'FIGURES.json',manifest)
    after={p:r2_digest(R2_ROOT/p) for p in sources}
    round1_after={str(p.relative_to(R2_ROOT)):r2_digest(p) for p in first.rglob('*') if p.is_file()}
    r2_check(checks,'input_source_digests_unchanged',before,after)
    r2_check(checks,'round1_files_unchanged',round1_before,round1_after)
    saved=r2_saved_checks(output)
    visual=oldcheck.get('visual_review',{'status':'PENDING','png':'Not yet manually inspected','svg':'Structure only; no manual rendering claim'})
    current_png={f['id']:f['png_sha256'] for f in figures}
    if visual.get('png_sha256')!=current_png:
        visual={'status':'PENDING','png':'Final PNGs and working-size proofs need manual review','svg':'Structure only; no manual rendering claim'}
    report=dict(owner=R2_OWNER,numeric_status='PASS' if all(r['status']=='PASS' for r in checks+saved) else 'FAIL',
        source_numeric_check_count=len(checks),saved_output_check_count=len(saved),
        source_files_unchanged=before==after,round1_files_unchanged=round1_before==round1_after,
        visual_review=visual,source_numeric_checks=checks,saved_output_checks=saved,operations=manifest['operations'])
    r2_write_json(output/'CHECK.json',report)
    print(json.dumps(dict(output=str(output),figures=len(figures),tables=len(data),source_checks=len(checks),saved_checks=len(saved),numeric_status=report['numeric_status'],visual_status=visual['status']),ensure_ascii=False))
    return 0 if report['numeric_status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(r2_main())
