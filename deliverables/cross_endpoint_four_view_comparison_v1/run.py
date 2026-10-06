#!/usr/bin/env python3
"""Frozen P0/P1/P2 x four views: exactly twelve planned fits, no grid or acquisition."""
import argparse,hashlib,json,os,sys
from datetime import datetime,timezone
from collections import Counter
from io_utils import *
import engine as e
from features import FIELDS,VIEWS,view_status,RAW_FIELDS
import source_adapter as a
from summarize import summarize

def run(out):
 out=Path(out).resolve();require(out.is_relative_to(HERE) and not out.exists(),'NEW_LOCAL_OUTPUT_DIRECTORY_REQUIRED');out.mkdir(parents=True)
 e.PHASE='experiment';e.COUNTS.clear();e.EVENTS.clear()
 def guard(event,args):
  if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.posix_spawn'):raise RuntimeError('NO_NETWORK_PROCESS_COLLECTION:'+event)
  if event=='open':
   path,mode,flags=args
   if not isinstance(path,int) and (flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and not Path(os.fsdecode(path)).resolve().is_relative_to(out):raise RuntimeError('WRITE_OUTSIDE_NEW_OUTPUT')
 sys.addaudithook(guard)
 start=datetime.now(timezone.utc).isoformat()
 settings=dict(mode=MODE,parameters=e.PARAMS,actual_defaults=e.DecisionTreeClassifier().get_params(),fields=FIELDS,views=VIEWS,
  train_cohorts=e.PLANS,holdout=e.HOLDOUT,threshold=.5,weighting='class halves; positives equal represented families then records; normals equal represented sources then records',
  preprocessing='train-only shared raw one-hot+median+all-numeric-missing-indicators; fixed relational F/T/U columns',expected_tree_fits=12,expected_preprocessor_fits=3)
 write(out/'SETTINGS.json',settings)
 original={ref(a.b2a.HERE/'conditions.py'):digest(a.b2a.HERE/'conditions.py'),ref(a.b2a.HERE/'CANDIDATES_FROZEN.json'):digest(a.b2a.HERE/'CANDIDATES_FROZEN.json'),
  ref(B2C/'results/models.json'):digest(B2C/'results/models.json'),ref(B2C/'results/predictions.jsonl'):digest(B2C/'results/predictions.jsonl'),
  ref(ROOT/'hybridguard_agent/config/latest_experiment_protocol.v1.json'):digest(ROOT/'hybridguard_agent/config/latest_experiment_protocol.v1.json')}
 for model in read(B2C/'results/models.json'):
  require(digest(ROOT/model['base']['path'])==model['base']['sha256'],'BASE_MODEL_CHANGED')
  original[model['base']['path']]=model['base']['sha256']
 write(out/'PRE_FIT_FREEZE.json',dict(time=start,protocol_sha256=digest(HERE/'PROTOCOL.md'),settings=settings,
  original_sources=original,implementation={ref(p):digest(p) for p in HERE.glob('*.py')},environment=read(HERE/'ENVIRONMENT.json'),no_new_scores_read_before_freeze=True))
 # Field catalog authority, not name guesses.
 catalog=a.b2a.read(ROOT/'hybridguard_agent/config/latest_experiment_protocol.v1.json')
 from hybridguard_agent.evidence.paired244 import field_contract
 require(set(RAW_FIELDS)<=set(field_contract()),'FIELD_CATALOG_MISMATCH')
 members,features=a.load();ix=unique(features,lambda r:r['sample_id']);meta=unique(members,lambda r:r['sample_id'])
 jsonl(out/'members.jsonl',members);jsonl(out/'features.jsonl',features)
 write(out/'SOURCE_MANIFEST.json',dict(files=a.USED,raw_fields=RAW_FIELDS,records=951,mtc_basis='verified P1 current paired snapshot, preserved v9/v11 quality',small_basis='v16 archived current pairs with original binding adapters',no_full_raw_copied=True))
 # Register the known 15 additions using old C1 operands, no fresh full-MTC audit.
 known=read(B2C/'results/COVERAGE_ANALYSIS.json');ids=set(s for r in known for s in r['new_C1_U_positions']);require(len(ids)==15,'EXPECTED_15_KNOWN_F_TO_U')
 saved_c=rows(a.b2a.HERE/'results/condition_results.jsonl');reason_rows=[]
 for r in saved_c:
  if r['meta']['sample_id'] in ids and r['condition_id']=='C1':reason_rows.append(dict(sample_id=r['meta']['sample_id'],cohort='mtc_'+r['meta']['group'],reason=r['reason'],operands=r['operands'],source=ref(a.b2a.HERE/'results/condition_results.jsonl',saved_c.index(r)+1)))
 jsonl(out/'known_15_unknown_reasons.jsonl',reason_rows)
 # Six old identities reused as references, never retrained and never labelled new holdouts.
 frozen=[]
 for r in rows(B2C/'results/predictions.jsonl'):
  frozen.extend([dict(sample_id=r['sample_id'],model_id=r['base_model_id'],method='frozen_App',state=r['base_state']),dict(sample_id=r['sample_id'],model_id=r['model_id'],method='frozen_B2C',state=r['state'])])
 jsonl(out/'frozen_reference_predictions.jsonl',frozen)
 predictions=[];models=[];plans={};risk=[]
 for plan in ('P0','P1','P2'):
  train,evaluation=e.split(members,plan);train_ids=[m['sample_id'] for m in train];train_set=set(train_ids)
  plans[plan]=dict(training_ids=train_ids,evaluation_ids=[m['sample_id'] for m in evaluation],training_families=sorted({m['family'] for m in train if m['identity']=='EFFECTIVE_INTERVENTION'}),whole_batch_holdout=e.HOLDOUT[plan])
  spec=e.fit_preprocessor([ix[s] for s in train_ids],train_ids);write(out/(plan+'_preprocessing.json'),spec)
  shared,unknown=e.transform(spec,features)
  both_array=None
  for view in VIEWS:
   X,names=e.view_array(spec,shared,features,view)
   if view=='V_BOTH':both_array=X
   if view=='V_BOTH_REL':require(e.np.array_equal(X[:,:both_array.shape[1]],both_array),'SHARED_RAW_TRANSFORM_CHANGED')
   gates=[view_status(row,view) for row in features];indices=[i for i,row in enumerate(features) if row['sample_id'] in train_set and gates[i]['gate']=='READY' and meta[row['sample_id']]['identity'] in ('NORMAL','EFFECTIVE_INTERVENTION')]
   fitting=[meta[features[i]['sample_id']] for i in indices]
   clf,weight_rows,weight_groups=e.fit_tree(X[indices],fitting)
   tree=e.tree_json(clf,names)
   mid='b3a-'+plan+'-'+view+'-'+hashlib.sha256(json.dumps(dict(tree=tree,preprocessing=spec,train_ids=train_ids),sort_keys=True).encode()).hexdigest()[:12]
   bundle=dict(model_id=mid,mode=MODE,plan=plan,view=view,tree=tree,preprocessing=spec,weights=weight_rows,weight_groups=weight_groups,
    nominal_training_ids=train_ids,actual_fit_ids=[m['sample_id'] for m in fitting],excluded_fit_positions=[dict(sample_id=row['sample_id'],gate=gates[i]) for i,row in enumerate(features) if row['sample_id'] in train_set and i not in indices],
    evaluation_ids=plans[plan]['evaluation_ids'],positive_threshold=.5,raw_feature_dependencies=VIEWS[view],source_freeze_ref='PRE_FIT_FREEZE.json')
   write(out/(plan+'_'+view+'.json'),bundle);(out/(plan+'_'+view+'.txt')).write_text(e.export_text(clf,feature_names=names,show_weights=True))
   valid=[i for i,g in enumerate(gates) if g['gate']=='READY'];probs,leaves=e.predict_tree(clf,X[valid]);jp,jl=e.predict_json(tree,X[valid])
   require(e.np.allclose(probs,jp,atol=1e-14,rtol=0) and e.np.array_equal(leaves,jl),'PORTABLE_TREE_REPLAY_MISMATCH')
   actual={i:(float(p),int(leaf)) for i,p,leaf in zip(valid,probs,leaves)}
   for i,row in enumerate(features):
    sid=row['sample_id'];m=meta[sid];g=gates[i];pr,leaf=actual.get(i,(None,None))
    role='training' if sid in train_set else 'batch_holdout_development' if m['cohort']==e.HOLDOUT[plan] else 'historical_normal_evaluation'
    predictions.append(dict(sample_id=sid,model_id=mid,plan=plan,view=view,role=role,state=('T' if pr>=.5 else 'F') if pr is not None else g['gate'],probability=pr,leaf=leaf,
     input_complete=g['input_complete'],measured_available=g['measured_available'],measured_expected=g['measured_expected'],missing=g['missing'],errors=g['errors'],
     unknown_categories=[u for u in unknown[i] if u['field'] in VIEWS[view]],
     unseen_training_family=m['identity']=='EFFECTIVE_INTERVENTION' and m['family'] not in plans[plan]['training_families']))
   models.append(dict(model_id=mid,plan=plan,view=view,path=plan+'_'+view+'.json',rules_path=plan+'_'+view+'.txt',training_positions=len(train),actual_fit_positions=len(fitting),depth=tree['depth'],leaves=tree['leaves'],feature_count=len(names)))
   for node,f in enumerate(tree['feature']):
    if f>=0:risk.append(dict(plan=plan,view=view,node=node,feature=names[f],threshold=tree['threshold'][node],training_n=tree['n_node_samples'][node],weighted_n=tree['weighted_n_node_samples'][node]))
   # Save completion immediately; a failed later task never silently causes a repeat fit.
   write(out/'models.json',models);jsonl(out/'predictions.jsonl',predictions);write(out/'CALLS_PARTIAL.json',dict(e.COUNTS))
 write(out/'PLANS.json',plans);write(out/'split_features.json',risk)
 write(out/'EXECUTION.json',dict(started_at=start,completed_at=datetime.now(timezone.utc).isoformat(),calls=dict(e.COUNTS),events=e.EVENTS,
  planned_tree_fits=12,completed_tree_fits=len(models),independent_positions=951,new_collection_calls=0,original_rule_fit_calls=0,
  scope='12 representation comparisons; no retry/grid, no old-model refit. Shared preprocessing fits separately counted.'))
 require(e.COUNTS['experiment:tree_fit']==12 and e.COUNTS['experiment:preprocess_fit']==3,'FIT_COUNT_MISMATCH')
 summarize(out,out/'summary')
 print(json.dumps({'models':len(models),'calls':dict(e.COUNTS)},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=HERE/'results');run(p.parse_args().output)
