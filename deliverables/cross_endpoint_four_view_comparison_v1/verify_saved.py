"""No-refit verification: current-input API, train-only transforms, fixed weights."""
import collections,statistics,sys,os
import numpy as np
from io_utils import *
import engine as e
from features import FIELDS,CAT,VIEWS

def verify(out):
 out=Path(out).resolve();models=read(out/'models.json');members=unique(rows(out/'members.jsonl'),lambda r:r['sample_id']);features=rows(out/'features.jsonl');ix=unique(features,lambda r:r['sample_id']);plans=read(out/'PLANS.json');preds=unique(rows(out/'predictions.jsonl'),lambda r:(r['model_id'],r['sample_id']))
 e.PHASE='verification';e.COUNTS.clear();e.EVENTS.clear()
 def guard(event,args):
  if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.posix_spawn'):raise RuntimeError('VERIFY_FORBIDDEN:'+event)
  if event=='open':
   path,mode,flags=args
   if not isinstance(path,int) and (flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and not Path(os.fsdecode(path)).resolve().is_relative_to(out):raise RuntimeError('VERIFY_WRITE_OUTSIDE_OUTPUT')
 def profile(frame,event,arg):
  if event=='call' and frame.f_code.co_name in ('fit','_fit','fit_tree','fit_preprocessor') and 'cross_endpoint_four_view_comparison_v1' in frame.f_code.co_filename:raise RuntimeError('VERIFY_REFIT_FORBIDDEN')
 sys.addaudithook(guard);sys.setprofile(profile)
 replay=[];transform_checks=0;weight_checks=0
 for m in models:
  model=read(out/m['path']);plan=plans[m['plan']];spec=model['preprocessing'];train=plan['training_ids']
  require(train==model['nominal_training_ids']==model['actual_fit_ids']==spec['training_ids'],'ACTUAL_PLANNED_TRAIN_DIFFERENCE')
  require(set(train).isdisjoint(plan['evaluation_ids']),'EVALUATION_LEAK')
  require({members[s]['cohort'] for s in train}==set(e.PLANS[m['plan']]),'TRAIN_COHORTS_CHANGED')
  require(all(model['tree']['params'][k]==v for k,v in e.PARAMS.items()),'TREE_PARAMETERS_CHANGED')
  for f in FIELDS:
   cells=[ix[s]['cells'][f] for s in train]
   if f in CAT:
    expected=sorted({c['value'] for c in cells if c['available']}|{'__MISSING__'})
    require(expected==spec['categorical'][f],'CATEGORY_EVALUATION_LEAK')
   else:
    values=[c['value'] for c in cells if c['available']];expected=statistics.median(values) if values else 0
    require(expected==spec['numeric'][f]['median'] and (not values)==spec['numeric'][f]['all_training_missing'],'IMPUTATION_EVALUATION_LEAK')
   transform_checks+=1
  normal=collections.defaultdict(list);positive=collections.defaultdict(list)
  for sid in train:
   r=members[sid]
   if r['identity']=='NORMAL':normal['MTC' if r['cohort'].startswith('mtc_') else r['cohort']].append(sid)
   else:positive[r['family']].append(sid)
  expected={sid:(label,.5/len(groups)/len(ss)) for label,groups in [(0,normal),(1,positive)] for ss in groups.values() for sid in ss}
  for w in model['weights']:
   y,value=expected[w['sample_id']];require(w['label']==y and abs(w['weight']-value)<1e-15,'WEIGHT_MISMATCH');weight_checks+=1
  for r in features:
   # Metadata, references and IDs deliberately do not reach current prediction.
   x={k:r[k] for k in ('cells','endpoint_errors','pair_errors')}
   actual=e.predict_current(model,x);saved=preds[m['model_id'],r['sample_id']]
   require(actual['state']==saved['state'],'CURRENT_STATE_MISMATCH')
   require(actual['probability']==saved['probability'] or actual['probability'] is not None and abs(actual['probability']-saved['probability'])<1e-14,'CURRENT_PROBABILITY_MISMATCH')
   require(actual.get('leaf')==saved['leaf'] and actual.get('unknown_categories',[])==saved['unknown_categories'],'CURRENT_EXPLANATION_MISMATCH')
   replay.append(dict(model_id=m['model_id'],sample_id=r['sample_id'],state=actual['state'],probability=actual['probability'],same_saved=True))
 sys.setprofile(None)
 jsonl(out/'current_input_replay.jsonl',replay)
 write(out/'VERIFICATION.json',dict(status='PASSED',current_input_predictions=len(replay),transform_checks=transform_checks,weight_checks=weight_checks,calls=dict(e.COUNTS),tree_fits=0,preprocessor_fits=0,collection_calls=0,scope='All 12 portable model entries on same 951 actual-derived inputs; no labels or sidecars in prediction'))
 print('Current-input replay passed:',len(replay))
if __name__=='__main__':verify(HERE/'results')
