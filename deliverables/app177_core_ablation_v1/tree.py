"""One fixed sklearn tree per original outer fold; JSON inference representation."""
from collections import Counter
from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
import time
from data import engine, state_cell

PARAMS=dict(criterion='gini',splitter='best',max_depth=3,min_samples_leaf=2,random_state=20261006,class_weight=None)


def weights(prepared):
    c=prepared.common;attack=[s for s in c.ids if c.metadata[s]['phase']=='attack'];clean=[s for s in c.ids if s not in attack]
    configs=Counter(c.metadata[s]['config_id'] for s in attack)
    result={s:Fraction(1,2*len(configs)*configs[c.metadata[s]['config_id']]) for s in attack}
    result.update({s:Fraction(1,4*len(clean)) for s in clean})
    result.update({s:Fraction(1,4*len(c.mtc_train_ids)) for s in c.mtc_train_ids})
    assert sum(result.values())==1
    return result


def vector(cells,names):
    states=[state_cell(cells[n]) for n in names]
    if 'FAILED' in states: return None,states,'FAILED'
    if not names or not any(s in ('T','F') for s in states):return None,states,'NO_VALID_MEASUREMENT'
    if any(s not in ('T','F','U') for s in states):raise ValueError('TREE_REQUIRES_BOOLEAN_CONDITION_STATES')
    # Three disjoint indicator columns: unknown never equals real false/zero.
    return [int(s==v) for s in states for v in ('T','F','U')],states,None


def fit(prepared, recovery_path=None):
    import sklearn
    from sklearn.tree import DecisionTreeClassifier, export_text
    if sklearn.__version__!='1.7.2': raise ValueError('FIXED_SKLEARN_1_7_2_REQUIRED')
    c=prepared.common; p,_=engine.problem(prepared,time.monotonic()+60)
    names=sorted({l.atom_id for cl in p.candidates for l in cl.literals})
    allrows={**c.controlled_rows,**c.mtc_rows};ids=list(c.ids)+list(c.mtc_train_ids)
    ws=weights(prepared);X=[];y=[];excluded=[]
    for sid in ids:
        v,ss,error=vector(allrows[sid],names)
        if error:excluded.append({'sample_id':sid,'status':error,'states':ss})
        X.append(v);y.append(c.metadata[sid]['supervised_label'] if sid in c.metadata else 0)
    pre={'atoms':names,'columns':[{'atom_id':n,'state':s} for n in names for s in ('T','F','U')],
         'encoding':'FIXED_T_F_U_ONE_HOT','learned_vocabulary':False,'fit_calls':0,
         'admission':'same frozen Full training-side controlled support and MTC >=90% evaluability; either literal polarity admitted',
         'candidate_statistics':engine.base._candidate_statistics(p,()),'all_encoded_atoms':[asdict(a) for a in c.atoms],
         'excluded_members':excluded}
    if excluded or not names:raise ValueError('TREE_TRAIN_VIEW_UNAVAILABLE:'+json.dumps(excluded))
    clf=DecisionTreeClassifier(**PARAMS);start=time.monotonic()
    clf.fit(X,y,sample_weight=[float(ws[s]) for s in ids])
    elapsed=time.monotonic()-start
    t=clf.tree_;positive=list(clf.classes_).index(1)
    model={'schema_version':'app177-fixed-tree-v1','scheme':'APP_TREE','fold_id':c.job['fold_id'],
           'status':'FITTED','parameters':PARAMS,'sklearn_version':sklearn.__version__,'classes':clf.classes_.tolist(),
           'positive_class_index':positive,'threshold':0.5,'preprocessing':pre,'encoder':c.encoder,
           'children_left':t.children_left.tolist(),'children_right':t.children_right.tolist(),
           'feature':t.feature.tolist(),'thresholds':t.threshold.tolist(),'value':t.value.tolist(),
           'weighted_n_node_samples':t.weighted_n_node_samples.tolist(),'elapsed_seconds':elapsed,
           'train_ids':list(c.ids),'mtc_train_ids':list(c.mtc_train_ids),
           'training_weights':[{'sample_id':s,'label':label,'weight':float(ws[s]),'exact_weight':str(ws[s])} for s,label in zip(ids,y,strict=True)],
           'text':export_text(clf,feature_names=[n+'='+s for n in names for s in ('T','F','U')])}
    # Content identity only; this is not an archive integrity scan.
    model['model_id']='app177-tree-'+hashlib.sha256(json.dumps(model,sort_keys=True).encode()).hexdigest()[:24]
    if recovery_path is not None:
        recovery_path.parent.mkdir(parents=True,exist_ok=True)
        recovery_path.write_text(json.dumps(model,ensure_ascii=False,indent=2)+'\n')
    expected=clf.predict_proba(X)[:,positive].tolist()
    got=[traverse(model,v)[0] for v in X]
    if expected!=got:raise ValueError('TREE_JSON_PROBABILITY_REGRESSION')
    return model


def traverse(model,v):
    node=0;path=[]
    while model['children_left'][node]!=-1:
        col=model['feature'][node];entry=model['preprocessing']['columns'][col]
        left=v[col]<=model['thresholds'][node]
        path.append({'node':node,**entry,'value':v[col],'threshold':model['thresholds'][node],'left':left})
        node=model['children_left' if left else 'children_right'][node]
    values=model['value'][node][0]
    # sklearn 1.7.2 predict_proba returns tree_.value directly (already proportions).
    return values[model['positive_class_index']],path


def predict(model,sid,raw):
    names=model['preprocessing']['atoms']
    try:
        cells=engine.encode(raw,model['encoder'],names);v,states,error=vector(cells,names)
        missing=[n for n,s in zip(names,states,strict=True) if s=='U']
        if error:return {'decision':'FAILED' if error=='FAILED' else 'INSUFFICIENT_EVIDENCE','state':'FAILED' if error=='FAILED' else 'U',
                         'probability':None,'failure_reason':error,'input_states':states,'missing_atoms':missing}
        prob,path=traverse(model,v)
        used={x['atom_id'] for x in path};dep=sorted(used&set(missing))
        return {'decision':'ALERT' if prob>=.5 else 'NO_ALERT','state':'T' if prob>=.5 else 'F','probability':prob,
                'input_states':states,'input_defined':len(names)-len(missing),'input_expected':len(names),
                'missing_atoms':missing,'missing_path_dependencies':dep,'path':path,'failure_reason':None}
    except (KeyError,ValueError,TypeError) as e:
        return {'decision':'FAILED','state':'FAILED','probability':None,'failure_reason':str(e)}
