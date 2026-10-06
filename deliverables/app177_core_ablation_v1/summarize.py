"""Saved-only aggregation. Never imports prediction, training or collection code."""
from collections import Counter,defaultdict
import csv,gzip,json
from pathlib import Path

STATES=('T','F','U','FAILED','EMPTY_MODEL')
SCHEMES=('APP_FULL','A_NO_MTC_CAP','A_APP_WEB_ONLY','A_NO_MEMORY_REL','A_NO_TIMEZONE_REL','APP_TREE')

def rows(p):
    with (gzip.open if p.suffix=='.gz' else open)(p,'rt') as f:
        result=[json.loads(line) for line in f]
    return result

def write_csv(p,rs):
    with p.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)

def counts(rs):
    c=Counter(r['state'] for r in rs)
    if set(c)-set(STATES):raise ValueError('UNKNOWN_SAVED_OUTPUT_STATE')
    return {'N':len(rs),**{s:c[s] for s in STATES},'defined':c['T']+c['F']}

def summarize(out):
    table=out/'summary';table.mkdir(exist_ok=True)
    full=rows(out/'full_predictions.jsonl.gz');new=rows(out/'predictions.jsonl.gz');allrows=full+new
    keys=[(r['scheme'],r['stage'],r['sample_id'],r['fold_id']) for r in allrows]
    if len(keys)!=len(set(keys)):raise ValueError('DUPLICATE_PREDICTION_KEY')
    if len(full)!=3771 or len(new)!=33939:raise ValueError('MISSING_EXPECTED_PREDICTIONS')
    primary=[r for r in allrows if r['stage'] in ('RETENTION','FITTED')]
    members=rows(out/'members.jsonl');by_id={r['sample_id']:r for r in members}
    for scheme in SCHEMES:
        actual={(r['sample_id'],r['fold_id']) for r in primary if r['scheme']==scheme}
        expected={(r['sample_id'],r['fold_id']) for r in full}
        if actual!=expected:raise ValueError('SCHEME_DENOMINATOR_MISMATCH')
    overall=[];config=[];mtc=[];special=[];paired=[];stage=[];integrity=[]
    for scheme in SCHEMES:
        rs=[r for r in primary if r['scheme']==scheme]
        for identity in ['EFFECTIVE_INTERVENTION','NORMAL']:
            overall.append(dict(scheme=scheme,identity=identity,**counts([r for r in rs if r['cohort']=='controlled' and r['identity']==identity])))
        cfgs=sorted({r['scenario'] for r in rs if r['cohort']=='controlled'})
        for cfg in cfgs:
            for identity in ['EFFECTIVE_INTERVENTION','NORMAL']:
                sub=[r for r in rs if r['cohort']=='controlled' and r['scenario']==cfg and r['identity']==identity]
                config.append(dict(scheme=scheme,configuration=cfg,identity=identity,**counts(sub)))
        for fid in sorted({r['fold_id'] for r in rs}):
            fold=[r for r in rs if r['fold_id']==fid]
            for subset in ['discovery','development','reserved_validation']:
                sub=[r for r in fold if r['cohort']=='mtc' and r['subset']==subset]
                mtc.append(dict(scheme=scheme,fold_id=fid,subset=subset,**counts(sub)))
            for cohort in ['memory','timezone','screen']:
                for scenario in ['ALL',*sorted({r['scenario'] for r in fold if r['cohort']==cohort})]:
                    for phase in ['ALL','change','attack','clean_pre','clean_post']:
                        for identity in ['NORMAL','EFFECTIVE_INTERVENTION','NO_OBSERVABLE_EFFECT','UNCONFIRMED']:
                            sub=[r for r in fold if r['cohort']==cohort and r['identity']==identity and (scenario=='ALL' or r['scenario']==scenario) and (phase=='ALL' or r['phase']==phase)]
                            if sub:special.append(dict(scheme=scheme,fold_id=fid,cohort=cohort,scenario=scenario,phase=phase,identity=identity,**counts(sub)))
            for identity,endpoint in [('NORMAL','ALL'),('EFFECTIVE_INTERVENTION','App'),('EFFECTIVE_INTERVENTION','Browser')]:
                sub=[r for r in fold if r['cohort']=='paired60' and r['identity']==identity and (endpoint=='ALL' or r['affected_endpoint']==endpoint)]
                paired.append(dict(scheme=scheme,fold_id=fid,identity=identity,affected_endpoint=endpoint,**counts(sub)))
            if scheme=='APP_TREE':
                for cohort in ['controlled','mtc','memory','timezone','screen','paired60']:
                    sub=[r for r in fold if r['cohort']==cohort]
                    integrity.append(dict(fold_id=fid,cohort=cohort,N=len(sub),
                        all_input_conditions_defined=sum(r.get('input_defined')==r.get('input_expected') and r.get('input_expected',0)>0 for r in sub),
                        has_unknown_conditions=sum(bool(r.get('missing_atoms')) for r in sub),
                        prediction_path_uses_missing_atom=sum(bool(r.get('missing_path_dependencies')) for r in sub),
                        failed=sum(r['state']=='FAILED' for r in sub),U=sum(r['state']=='U' for r in sub)))
    groups=defaultdict(list)
    for r in allrows:groups[r['scheme'],r['stage'],r['fold_id'],r['cohort'],r['subset'],r['identity']].append(r)
    for key,rs in sorted(groups.items()):
        stage.append(dict(zip(['scheme','stage','fold_id','cohort','subset','identity'],key),**counts(rs)))
    for name,rs in [('main',overall),('configurations14',config),('mtc',mtc),('specialists',special),('paired60',paired),('all_stages',stage),('tree_input_integrity',integrity)]:
        write_csv(table/(name+'.csv'),rs)
        (table/(name+'.json')).write_text(json.dumps(rs,ensure_ascii=False,indent=2)+'\n')
    # No evaluation score is used to pick a stage or fold.
    delta=[]
    base={(r['sample_id'],r['fold_id']):r for r in full}
    for scheme in SCHEMES[1:]:
        for cohort in ['controlled','mtc','memory','timezone','screen','paired60']:
            for identity in ['NORMAL','EFFECTIVE_INTERVENTION','NO_OBSERVABLE_EFFECT']:
                rs=[r for r in primary if r['scheme']==scheme and r['cohort']==cohort and r['identity']==identity]
                byfold=defaultdict(list)
                for r in rs:byfold['OUTER_COMBINED' if cohort=='controlled' else r['fold_id']].append(r)
                for fid,sub in byfold.items():
                    gains=[r['sample_id'] for r in sub if r['state']=='T' and base[r['sample_id'],r['fold_id']]['state']!='T']
                    losses=[r['sample_id'] for r in sub if r['state']!='T' and base[r['sample_id'],r['fold_id']]['state']=='T']
                    transitions=Counter(base[r['sample_id'],r['fold_id']]['state']+'->'+r['state'] for r in sub)
                    delta.append(dict(scheme=scheme,cohort=cohort,fold_id=fid,identity=identity,N=len(sub),gained_alert_ids=gains,lost_alert_ids=losses,transitions=dict(transitions)))
    (table/'versus_full.json').write_text(json.dumps(delta,ensure_ascii=False,indent=2)+'\n')
    (table/'SUMMARY.json').write_text(json.dumps({'main':overall,'mtc':mtc,'paired60':paired,
        'primary_schemes':list(SCHEMES),'core_records':1449,'paired_records':60,'independent_sample_multiplier':1,
        'saved_model_position_rows':len(allrows),'aggregation_only_prediction_calls':0,'aggregation_only_fit_calls':0},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'saved_rows':len(allrows),'main':overall,'summary_prediction_calls':0,'summary_fit_calls':0}),flush=True)

if __name__=='__main__':summarize(Path(__file__).resolve().parent/'results')
