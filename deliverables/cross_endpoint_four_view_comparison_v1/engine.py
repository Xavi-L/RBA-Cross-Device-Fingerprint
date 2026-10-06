"""One fixed weighted tree per plan/view; transparent preprocessing and JSON inference."""
import copy,statistics
from collections import Counter,defaultdict
import numpy as np
from sklearn.tree import DecisionTreeClassifier,export_text
from io_utils import *
from features import FIELDS,CAT,NUM,VIEWS,view_status
PARAMS=dict(criterion='gini',splitter='best',max_depth=3,min_samples_leaf=2,random_state=20261006,class_weight=None)
PLANS={'P0':('mtc_discovery','pilot18','b2b42'),'P1':('mtc_discovery','b2b42'),'P2':('mtc_discovery','pilot18')}
HOLDOUT={'P0':None,'P1':'pilot18','P2':'b2b42'}
COUNTS=Counter();EVENTS=[];PHASE='unspecified'
def record(operation,n=0):
 COUNTS[PHASE+':'+operation]+=1;COUNTS[PHASE+':'+operation+'_rows']+=n
 EVENTS.append(dict(phase=PHASE,operation=operation,rows=n))
def label(m):
 require(m['identity'] in ('NORMAL','EFFECTIVE_INTERVENTION'),'UNKNOWN_IDENTITY_NOT_SUPERVISED')
 return int(m['identity']=='EFFECTIVE_INTERVENTION')
def split(members,plan):
 train=[m for m in members if m['cohort'] in PLANS[plan]]
 evaluation=[m for m in members if m['cohort'] not in PLANS[plan]]
 require(not {m['group_id'] for m in train}&{m['group_id'] for m in evaluation},'SPLIT_BREAKS_GROUP')
 require(len(train)=={'P0':690,'P1':672,'P2':648}[plan],'TRAIN_POSITION_COUNT')
 return train,evaluation

def weights(members):
 ys=[label(m) for m in members]; groups={0:defaultdict(list),1:defaultdict(list)}
 for i,(m,y) in enumerate(zip(members,ys)):
  group=m['family'] if y else ('MTC' if m['cohort'].startswith('mtc_') else m['cohort'])
  require(group is not None,'POSITIVE_FAMILY_MISSING');groups[y][group].append(i)
 require(all(groups[y] for y in (0,1)),'BOTH_CLASSES_REQUIRED')
 w=np.zeros(len(members));detail=[]
 for y in (0,1):
  for group,indices in sorted(groups[y].items()):
   value=.5/len(groups[y])/len(indices)
   for i in indices:w[i]=value
   detail.append(dict(label=y,group=group,n=len(indices),per_record=value,total=float(sum(w[i] for i in indices))))
 return ys,w,detail

def fit_preprocessor(records,train_ids):
 require([r['sample_id'] for r in records]==list(train_ids),'PREPROCESS_TRAIN_MEMBERSHIP')
 record('preprocess_fit',len(records));spec={'training_ids':list(train_ids),'categorical':{},'numeric':{},'feature_names':[],'columns':{}}
 for field in FIELDS:
  cells=[r['cells'][field] for r in records]
  if field in CAT:
   categories=sorted({c['value'] for c in cells if c['available']}|{'__MISSING__'})
   spec['categorical'][field]=categories;names=[field+'='+s for s in categories]
  else:
   measured=[c['value'] for c in cells if c['available']]
   spec['numeric'][field]={'median':statistics.median(measured) if measured else 0,'all_training_missing':not measured,'observed_training_n':len(measured),'placeholder_not_observation':not measured}
   names=[field,field+'__missing']
  start=len(spec['feature_names']);spec['feature_names']+=names;spec['columns'][field]=list(range(start,start+len(names)))
 # Relation domain is fixed before any data; not a learned evaluation vocabulary.
 spec['relation_categories']={c:['F','T','U'] for c in ('C1','C2')}
 return spec

def transform(spec,records,fields=None):
 fields=list(FIELDS) if fields is None else list(fields)
 record('preprocess_transform',len(records));X=np.zeros((len(records),len(spec['feature_names'])));unknown=[]
 for i,row in enumerate(records):
  require(set(row['cells'])<=set(FIELDS)|{'C1','C2'} and set(fields)<=set(row['cells']),'UNREGISTERED_OR_MISSING_FEATURE')
  unseen=[]
  for field in fields:
   c=row['cells'][field];columns=spec['columns'][field]
   if field in CAT:
    value=c['value'] if c['available'] else '__MISSING__';categories=spec['categorical'][field]
    if value in categories:X[i,columns[categories.index(value)]]=1
    else:unseen.append(dict(field=field,value=value))
   else:X[i,columns]=[c['value'] if c['available'] else spec['numeric'][field]['median'],int(not c['available'])]
  unknown.append(unseen)
 return X,unknown

def view_array(spec,shared,records,view):
 record('view_projection',len(records));fields=[f for f in VIEWS[view] if f in FIELDS]
 cols=[j for f in fields for j in spec['columns'][f]];names=[spec['feature_names'][j] for j in cols];X=shared[:,cols]
 if view=='V_BOTH_REL':
  rel=np.zeros((len(records),6))
  for i,r in enumerate(records):
   for n,c in enumerate(('C1','C2')):
    value=r['cells'][c]['value']
    if value in ('F','T','U'):rel[i,n*3+['F','T','U'].index(value)]=1
  X=np.column_stack((X,rel));names +=[c+'='+s for c in ('C1','C2') for s in ('F','T','U')]
 return X,names

def positive_probability(probabilities,classes):
 classes=list(classes)
 return probabilities[:,classes.index(1)] if 1 in classes else np.zeros(len(probabilities))

def fit_tree(X,members):
 y,w,detail=weights(members);model=DecisionTreeClassifier(**PARAMS)
 record('tree_fit',len(members));model.fit(X,y,sample_weight=w)
 return model,[dict(sample_id=m['sample_id'],label=int(y[i]),weight=float(w[i])) for i,m in enumerate(members)],detail

def tree_json(model,names):
 t=model.tree_
 return dict(classes=model.classes_.tolist(),features=names,children_left=t.children_left.tolist(),children_right=t.children_right.tolist(),feature=t.feature.tolist(),threshold=t.threshold.tolist(),values=t.value[:,0,:].tolist(),n_node_samples=t.n_node_samples.tolist(),weighted_n_node_samples=t.weighted_n_node_samples.tolist(),impurity=t.impurity.tolist(),params=model.get_params(),depth=int(model.get_depth()),leaves=int(model.get_n_leaves()))

def predict_tree(model,X):
 record('predict_proba',len(X));prob=positive_probability(model.predict_proba(X),model.classes_)
 record('apply',len(X));leaves=model.apply(X)
 return prob,leaves

def predict_json(tree,X):
 """Portable frozen-tree replay. sklearn converts its computation array to float32."""
 record('json_predict',len(X));probs=[];leaves=[]
 for row in np.asarray(X,dtype=np.float32):
  node=0
  while tree['children_left'][node]!=-1:
   node=tree['children_left'][node] if row[tree['feature'][node]]<=tree['threshold'][node] else tree['children_right'][node]
  value=tree['values'][node];p=value[tree['classes'].index(1)]/sum(value) if 1 in tree['classes'] else 0.
  probs.append(p);leaves.append(node)
 return np.asarray(probs),np.asarray(leaves)

def predict_current(bundle,item):
 """One already-bound current measurement projection; no label/scenario/phase accepted."""
 require(set(item)<= {'cells','endpoint_errors','pair_errors'},'INFERENCE_SIDECAR')
 gate=view_status(item,bundle['view'])
 if gate['gate']!='READY':return dict(state=gate['gate'],probability=None,gate=gate)
 spec=bundle['preprocessing'];fields=[f for f in VIEWS[bundle['view']] if f in FIELDS]
 shared,unknown=transform(spec,[item],fields);X,_=view_array(spec,shared,[item],bundle['view'])
 p,leaf=predict_json(bundle['tree'],X)
 fields=set(VIEWS[bundle['view']])
 return dict(state='T' if p[0]>=.5 else 'F',probability=float(p[0]),leaf=int(leaf[0]),gate=gate,unknown_categories=[v for v in unknown[0] if v['field'] in fields])
