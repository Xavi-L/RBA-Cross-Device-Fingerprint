"""Saved outputs only. No numpy, sklearn, source adapter, tree or preprocessing calls."""
import argparse,csv
from collections import defaultdict,Counter
from io_utils import *

def summarize(source,out):
 source=Path(source);out=Path(out);out.mkdir(parents=True,exist_ok=True)
 members=unique(rows(source/'members.jsonl'),lambda m:m['sample_id']);preds=rows(source/'predictions.jsonl');models=read(source/'models.json')
 require(len(members)==951 and len(models)==12,'EXPECTED_MEMBERS_MODELS')
 require(Counter((p['sample_id'],p['model_id']) for p in preds)==Counter((sid,m['model_id']) for sid in members for m in models),'OUTPUT_PRODUCT_MISMATCH')
 groups=defaultdict(list)
 for p in preds:
  m=members[p['sample_id']]
  for group in ['all',m['identity'],'scenario:'+m['scenario']+':'+m['phase']]:groups[p['plan'],p['view'],p['role'],m['cohort'],group].append(p)
  if m['identity']=='EFFECTIVE_INTERVENTION':groups[p['plan'],p['view'],p['role'],m['cohort'],'family:'+m['family']].append(p)
 table=[]
 for (plan,view,role,cohort,group),rs in sorted(groups.items()):
  c=counts(r['state'] for r in rs)
  table.append(dict(plan=plan,view=view,role=role,cohort=cohort,group=group,**c,
   input_complete=sum(r['input_complete'] for r in rs),partial_input_binary=sum(r['state'] in ('T','F') and not r['input_complete'] for r in rs),
   unseen_category_positions=sum(bool(r['unknown_categories']) for r in rs),
   observed_input_rate=f"{sum(r['input_complete'] for r in rs)}/{len(rs)}",binary_output_rate=f"{c['defined']}/{len(rs)}",T_rate=f"{c['T']}/{len(rs)}"))
 write(out/'summary.json',table)
 with (out/'summary.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
 budgets=[]
 for plan in ('P0','P1','P2'):
  for view in ('V_APP','V_BROWSER','V_BOTH','V_BOTH_REL'):
   for cohort,n,budget in [('mtc_discovery',630,31),('pilot18',12,0),('b2b42',34,1)]:
    r=next(r for r in table if (r['plan'],r['view'],r['cohort'],r['group'])==(plan,view,cohort,'NORMAL'))
    require(r['n']==n,'NORMAL_DENOMINATOR_CHANGED')
    budgets.append(dict(plan=plan,view=view,cohort=cohort,role=r['role'],n=n,T=r['T'],defined=r['defined'],input_complete=r['input_complete'],budget=budget,alarm_pass=r['T']<=budget,output_coverage_pass=r['defined']*10>=n*9,all_pass=r['T']<=budget and r['defined']*10>=n*9,
     scope='posthoc fixed-threshold diagnostic; no constrained tree optimization; binary output is not observation completeness'))
 write(out/'normal_budget_checks.json',budgets)
 lookup={(p['plan'],p['view'],p['sample_id']):p for p in preds};changes=[];comparisons=[]
 for plan in ('P0','P1','P2'):
  by=defaultdict(Counter)
  for sid,m in members.items():
   a=lookup[plan,'V_BOTH',sid];b=lookup[plan,'V_BOTH_REL',sid]
   probability_changed=a['probability']!=b['probability'] and (a['probability'] is None or b['probability'] is None or abs(a['probability']-b['probability'])>1e-12)
   by[m['cohort']][a['state']+'->'+b['state']]+=1
   if a['state']!=b['state'] or probability_changed:
    changes.append(dict(plan=plan,sample_id=sid,role=a['role'],cohort=m['cohort'],identity=m['identity'],scenario=m['scenario'],phase=m['phase'],family=m['family'],state_changed=a['state']!=b['state'],both_state=a['state'],rel_state=b['state'],both_probability=a['probability'],rel_probability=b['probability'],both_leaf=a.get('leaf'),rel_leaf=b.get('leaf')))
  comparisons +=[dict(plan=plan,cohort=co,transitions=dict(c)) for co,c in sorted(by.items())]
 jsonl(out/'both_vs_rel_examples.jsonl',changes);write(out/'both_vs_rel.json',comparisons)
 missing=defaultdict(Counter)
 for p in preds:
  for field,reason in p['missing'].items():missing[p['plan'],p['view'],members[p['sample_id']]['cohort']][field+':'+reason]+=1
 write(out/'missing_reasons.json',[dict(plan=k[0],view=k[1],cohort=k[2],reasons=dict(v)) for k,v in sorted(missing.items())])
 # Frozen reference outputs never receive plan-specific holdout labels.
 references=rows(source/'frozen_reference_predictions.jsonl');rg=defaultdict(list)
 require(len(references)==951*6,'REFERENCE_DENOMINATORS')
 for r in references:
  m=members[r['sample_id']]
  for group in ('all',m['identity']):rg[r['model_id'],r['method'],m['cohort'],group].append(r['state'])
 ref_table=[dict(model_id=k[0],method=k[1],cohort=k[2],group=k[3],**counts(v),scope='existing_frozen_reference_not_P1_P2_holdout') for k,v in sorted(rg.items())]
 write(out/'frozen_reference_summary.json',ref_table)
 with (out/'frozen_reference_summary.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(ref_table[0]));w.writeheader();w.writerows(ref_table)
 return table
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('--output',required=True);a=p.parse_args();summarize(a.source,a.output)
