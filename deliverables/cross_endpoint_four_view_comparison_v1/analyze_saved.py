"""Saved-only diagnostic tables: collisions, recipe dependence and primary comparisons."""
import csv
from collections import defaultdict,Counter
from io_utils import *

def analyze(out):
 out=Path(out);members=unique(rows(out/'members.jsonl'),lambda r:r['sample_id']);features=unique(rows(out/'features.jsonl'),lambda r:r['sample_id']);preds=rows(out/'predictions.jsonl');settings=read(out/'SETTINGS.json')
 tables=[]
 for plan in ('P0','P1','P2'):
  cohorts=('pilot18','b2b42') if plan=='P0' else ('pilot18',) if plan=='P1' else ('b2b42',)
  for view in settings['views']:
   data=[p for p in preds if p['plan']==plan and p['view']==view and members[p['sample_id']]['cohort'] in cohorts]
   normal=[p for p in data if members[p['sample_id']]['identity']=='NORMAL'];attack=[p for p in data if members[p['sample_id']]['identity']=='EFFECTIVE_INTERVENTION']
   c=counts(p['state'] for p in attack);n=counts(p['state'] for p in normal)
   r=dict(plan=plan,view=view,scope='small_experiment_development' if plan=='P0' else 'whole_batch_heldout_development',attack_T=c['T'],attack_n=c['n'],normal_T=n['T'],normal_n=n['n'],attack_U=c['U'],attack_FAILED=c['FAILED'],normal_U=n['U'],normal_FAILED=n['FAILED'])
   for family in ('App_language','App_timezone','Browser_language','Browser_timezone'):
    subset=[p for p in attack if members[p['sample_id']]['family']==family];r[family+'_T']=sum(p['state']=='T' for p in subset);r[family+'_n']=len(subset)
   tables.append(r)
 write(out/'main_comparison.json',tables)
 with (out/'main_comparison.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(tables[0]));w.writeheader();w.writerows(tables)
 collisions=[]
 for view,fields in settings['views'].items():
  for cohort in ('pilot18','b2b42'):
   grouped=defaultdict(list)
   for sid,m in members.items():
    if m['cohort']==cohort:
     signature=json.dumps([[field,features[sid]['cells'][field]['value'],features[sid]['cells'][field]['available']] for field in fields],ensure_ascii=False,sort_keys=True)
     grouped[signature].append(sid)
   for signature,sids in grouped.items():
    normals=[s for s in sids if members[s]['identity']=='NORMAL'];attacks=[s for s in sids if members[s]['identity']=='EFFECTIVE_INTERVENTION']
    if normals and attacks:collisions.append(dict(view=view,cohort=cohort,normal_ids=normals,intervention_ids=attacks,families=sorted({members[s]['family'] for s in attacks}),identical_fixed_measurements=json.loads(signature)))
 write(out/'input_collisions.json',collisions)
 # Directly inspect fixed tree splits; absent features are also stated, not assumed.
 splits=read(out/'split_features.json');audit=[]
 for m in read(out/'models.json'):
  ss=[s for s in splits if (s['plan'],s['view'])==(m['plan'],m['view'])];fs=[s['feature'] for s in ss]
  audit.append(dict(plan=m['plan'],view=m['view'],splits=ss,
   fr_FR_split=any('=fr-fr' in f for f in fs),list_length_splits=[s for s in ss if 'language_count' in s['feature']],
   offset_splits=[s for s in ss if 'offset' in s['feature']],missing_indicator_split=any('__missing' in f or '__MISSING__' in f for f in fs),
   native_locale_split=any(f.startswith('native_locale=') for f in fs),relation_splits=[f for f in fs if f.startswith(('C1=','C2='))],
   direct_batch_or_version_feature=False,scope='Fixed measurements can still proxy collection recipes or cohorts; not causal identification of ABI/version'))
 write(out/'recipe_audit.json',audit)
 known=rows(out/'known_15_unknown_reasons.jsonl')
 with (out/'known_15_unknown_reasons.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['sample_id','cohort','condition_reason','unavailable_field','saved_value','status','quality','source'])
  for r in known:
   for o in r['operands']:
    if o['status']!='observed' or o['quality']!='observed_value':w.writerow([r['sample_id'],r['cohort'],r['reason'],o['field'],o['value'],o['status'],o['quality'],r['source']])
 print('Primary rows',len(tables),'mixed-identity identical-input groups',len(collisions))
if __name__=='__main__':analyze(HERE/'results')
