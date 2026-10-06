"""Saved-results-only tables/claim index. Does not import learning, prediction or timing."""
import argparse,statistics
from collections import defaultdict,Counter
from closeout_io import *

def aggregate(predictions,members,model,cohort,role,group,source,model_family):
    c=counts(p['state'] for p in predictions)
    ids=[p['sample_id'] for p in predictions]
    complete=sum(p.get('input_complete',False) for p in predictions) if model_family=='B3A_fixed_tree' else None
    return dict(model_family=model_family,model_id=model['model_id'],setting=model.get('setting',model.get('view')),plan=model.get('plan','not_cross_validation'),base_config=model.get('fold','not_applicable'),
        input_scope=model.get('input_scope',model.get('view')),cohort=cohort,role=role,group=group,metric='intervention_trigger' if group=='EFFECTIVE_INTERVENTION' or group.startswith('family:') else 'normal_alarm' if group in ('NORMAL','normal_browser_preference_change') else 'T_fraction_not_accuracy',
        numerator=c['T'],denominator=c['n'],T=c['T'],F=c['F'],U=c['U'],FAILED=c['FAILED'],defined=c['defined'],input_complete=complete,
        partial_input_binary=sum(not p.get('input_complete',True) and p['state'] in ('T','F') for p in predictions) if model_family=='B3A_fixed_tree' else None,
        evidence_path=source,member_reference=ref(HERE/'results/members.jsonl'),sample_ids=ids)

def compact(rows_):return [{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items() if k!='sample_ids'} for r in rows_]

def build(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    members=index(rows(HERE/'results/members.jsonl'))
    rule_models=read(HERE/'results/models.json');trees=read(B3A/'results/models.json')
    rule=rows(HERE/'results/predictions.jsonl');tree=rows(B3A/'results/predictions.jsonl')
    index_rows=[];tables={};primary=[]
    for family,models,ps,source in [('B2C_incremental_rule',rule_models,rule,ref(HERE/'results/predictions.jsonl')),('B3A_fixed_tree',trees,tree,ref(B3A/'results/predictions.jsonl'))]:
        require(Counter((p['model_id'],p['sample_id']) for p in ps)==Counter((m['model_id'],sid) for m in models for sid in members),'PREDICTION_PRODUCT')
        table=[]
        for model in models:
            subset=[p for p in ps if p['model_id']==model['model_id']]
            grouped=defaultdict(list)
            for p in subset:
                m=members[p['sample_id']];role=p['role']
                grouped[m['cohort'],role,m['identity']].append(p)
                if m['identity']=='EFFECTIVE_INTERVENTION':grouped[m['cohort'],role,'family:'+m['family']].append(p)
                if m['scenario']=='L_BROWSER_LANG' and m['phase']=='change':grouped[m['cohort'],role,'normal_browser_preference_change'].append(p)
            for (co,role,group),part in sorted(grouped.items()):table.append(aggregate(part,members,model,co,role,group,source,family))
            if family=='B3A_fixed_tree':
                cohorts=('pilot18','b2b42') if model['plan']=='P0' else ('pilot18',) if model['plan']=='P1' else ('b2b42',)
                part=[p for p in subset if members[p['sample_id']]['cohort'] in cohorts]
                attack=[p for p in part if members[p['sample_id']]['identity']=='EFFECTIVE_INTERVENTION'];normal=[p for p in part if members[p['sample_id']]['identity']=='NORMAL']
                row=dict(plan=model['plan'],view=model['view'],model_id=model['model_id'],role='development_fit' if model['plan']=='P0' else 'whole_batch_heldout_development',attack_T=sum(p['state']=='T' for p in attack),attack_n=len(attack),normal_T=sum(p['state']=='T' for p in normal),normal_n=len(normal),U=sum(p['state']=='U' for p in part),FAILED=sum(p['state']=='FAILED' for p in part),input_complete=sum(p['input_complete'] for p in part),input_n=len(part),evidence_path=source)
                row.update(cohort='+'.join(cohorts),input_scope=model['view'])
                for fam in ('App_language','App_timezone','Browser_language','Browser_timezone'):
                    ff=[p for p in attack if members[p['sample_id']]['family']==fam];row[fam+'_T']=sum(p['state']=='T' for p in ff);row[fam+'_n']=len(ff)
                primary.append(row)
            else:
                for group in ('NORMAL','EFFECTIVE_INTERVENTION',*('family:'+f for f in ('App_language','App_timezone','Browser_language','Browser_timezone'))):
                    part=[p for p in subset if members[p['sample_id']]['cohort'] in ('pilot18','b2b42') and (members[p['sample_id']]['family']==group.removeprefix('family:') and members[p['sample_id']]['identity']=='EFFECTIVE_INTERVENTION' if group.startswith('family:') else members[p['sample_id']]['identity']==group)]
                    table.append(aggregate(part,members,model,'small_development60','selection',group,source,family))
        index_rows.extend(table);tables[family]=table
    write(out/'metric_index.json',index_rows);jsonl(out/'metric_index.jsonl',index_rows)
    csv_write(out/'four_view.csv',primary);write(out/'four_view.json',primary)
    csv_write(out/'four_view_all_cohorts.csv',compact(tables['B3A_fixed_tree']))
    csv_write(out/'rule_ablation.csv',compact(tables['B2C_incremental_rule']))
    mtc=[r for r in tables['B2C_incremental_rule'] if r['cohort'].startswith('mtc_') and r['group']=='NORMAL']
    csv_write(out/'rule_mtc_composition.csv',compact(mtc))
    # Same-member transitions retain all gains, losses, U and failures.
    lookup={(r['setting'],r['fold'],r['sample_id']):r for r in rule};changes=[]
    for fold in (1,2,3):
        for setting in SETTINGS_NAMES[1:]:
            for sid,m in members.items():
                a=lookup['R_FULL',fold,sid];b=lookup[setting,fold,sid]
                if a['state']!=b['state']:changes.append(dict(fold=fold,comparison=setting,sample_id=sid,cohort=m['cohort'],role=m['role'],identity=m['identity'],family=m['family'],scenario=m['scenario'],phase=m['phase'],R_FULL=a['state'],ablation=b['state'],source=ref(HERE/'results/predictions.jsonl')))
    jsonl(out/'rule_transitions.jsonl',changes);csv_write(out/'rule_transitions.csv',changes)
    # Actual preferred tags/list lengths, with every repeat traceable.
    feats=index(rows(B3A/'results/features.jsonl'));tp={(r['plan'],r['view'],r['sample_id']):r for r in tree};examples=[]
    for sid,m in members.items():
        keep=m['scenario']=='L_BROWSER_LANG' and m['phase']=='change' or m['identity']=='EFFECTIVE_INTERVENTION' and m['family']=='Browser_language'
        if not keep:continue
        cells=feats[sid]['cells'];r=dict(sample_id=sid,cohort=m['cohort'],identity=m['identity'],scenario=m['scenario'],repeat=m['group_id'])
        for k in ('app_language','app_first_language','app_language_count','browser_language','browser_first_language','browser_language_count','C1','C2'):r[k]=cells[k]['value']
        for plan in ('P0','P1','P2'):
            for view in ('V_BOTH','V_BOTH_REL'):
                row=tp[plan,view,sid];r[plan+'_'+view]=row['state'];r[plan+'_'+view+'_score']=row['probability']
        r['feature_evidence']=ref(B3A/'results/features.jsonl');r['prediction_evidence']=ref(B3A/'results/predictions.jsonl');examples.append(r)
    csv_write(out/'preference_examples.csv',examples);write(out/'preference_examples.json',examples)
    # Dataset units remain separate; historical observations are not paired244 rows.
    data=[]
    for co in ('mtc_discovery','pilot18','b2b42','mtc_development','mtc_reserved_validation'):
        part=[m for m in members.values() if m['cohort']==co]
        data.append(dict(dataset=co,input_scope='paired_App_Browser',positions=len(part),normal=sum(m['identity']=='NORMAL' for m in part),effective_interventions=sum(m['identity']=='EFFECTIVE_INTERVENTION' for m in part),role='development' if co in ('mtc_discovery','pilot18','b2b42') else 'historical_normal_evaluation',unit='paired stage; repeated environments are not independent devices',evidence=ref(HERE/'results/members.jsonl')))
    for name,n,normal,attack,file in [('App_historical_controlled',378,252,126,'timezone_relation_validation_v1/REPORT.md'),('App_memory_only',72,48,18,'memory_relation_validation_v1/REPORT.md'),('App_timezone_specialist',36,30,6,'timezone_relation_validation_v1/REPORT.md'),('App_screen_geometry_v15',72,66,6,'screen_geometry_observation_v1/REPORT.md')]:
        data.append(dict(dataset=name,input_scope='App_only_historical_specialist',positions=n,normal=normal,effective_interventions=attack,role='historical_appendix_separate_denominator',unit='App stage; memory has 6 additional no-observable-effect attempts',evidence='deliverables/'+file))
    csv_write(out/'data_scope.csv',data);write(out/'data_scope.json',data)
    # Benchmarks are read, never rerun, by this command.
    batches=rows(HERE/'timing/batches.jsonl');grouped=defaultdict(list)
    for r in batches:grouped[r['label'],r['stage']].append(r)
    costs=[]
    def percentile(values,p):
        values=sorted(values);x=(len(values)-1)*p;lo=int(x);hi=min(lo+1,len(values)-1);return values[lo]+(values[hi]-values[lo])*(x-lo)
    for (label,stage),rs in sorted(grouped.items()):
        require(len(rs)==10 and {r['repeat'] for r in rs}==set(range(10)),'TIMING_REPEAT_COUNT')
        v=[r['amortized_us'] for r in rs]
        costs.append(dict(label=label,stage=stage,batch_n=rs[0]['n'],repeats=10,median_amortized_us=statistics.median(v),p95_batch_amortized_us=percentile(v,.95),minimum_amortized_us=min(v),maximum_amortized_us=max(v),scope='load item' if rs[0]['n']==1 else '60-stage batch amortization; not single-request tail',evidence=ref(HERE/'timing/batches.jsonl')))
    csv_write(out/'cost.csv',costs);write(out/'cost.json',costs)
    resources=[]
    for m in rule_models:
        predictor=m['predictor'];p=HERE/'results'/(m['setting']+f"_{m['fold']:02d}.json")
        resources.append(dict(model_id=m['model_id'],label=m['setting']+f" / {m['fold']:02d}",file_bytes=p.stat().st_size,base_file_bytes=(ROOT/predictor['base']['path']).stat().st_size,rules=predictor['rule_count'],complexity=predictor['complexity'],nodes=None,depth=None,dependency='Python stdlib + frozen HybridGuard rule/adapter modules',source=ref(p)))
    for m in trees:
        p=B3A/'results'/m['path'];bundle=read(p)
        resources.append(dict(model_id=m['model_id'],label=m['plan']+' / '+m['view'],file_bytes=p.stat().st_size,base_file_bytes=0,rules=None,complexity=None,nodes=len(bundle['tree']['feature']),depth=bundle['tree']['depth'],dependency='Python3.13/numpy2.5.3/sklearn1.7.2 imported by frozen engine; JSON tree inference',source=ref(p)))
    csv_write(out/'model_resources.csv',resources)
    write(out/'BUILD.json',dict(status='PASSED',metric_rows=len(index_rows),models=21,positions=951,predictions=0,selections=0,fit=0,timing=0,collection=0,sources=[ref(HERE/'results/predictions.jsonl'),ref(B3A/'results/predictions.jsonl'),ref(HERE/'timing/batches.jsonl')]))
    print('Saved-only tables:',len(index_rows),'metric rows')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=HERE/'tables');build(p.parse_args().output)
