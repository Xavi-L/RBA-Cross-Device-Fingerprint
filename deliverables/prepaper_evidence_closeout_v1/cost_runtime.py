"""Timing-only decomposition of frozen public paths; no production modifications."""
import copy
from collections import Counter
from closeout_io import *
from bridges import runtime,original_inference,original_selector

a,prep,e,f,sa=runtime()
CALLS=Counter()

def forbid(*args,**kwargs):raise RuntimeError('FIT_SELECTION_COLLECTION_FORBIDDEN')

def block_learning():
    original_selector.select=forbid;original_selector.score=forbid
    e.fit_tree=forbid;e.fit_preprocessor=forbid;e.DecisionTreeClassifier.fit=forbid
    for name in ('fit','prepare_fold','train'):
        if hasattr(a.b2a.selection,name):setattr(a.b2a.selection,name,forbid)

def load_pairs(members):
    """Actual 60 selected archived pairs; raw contents stay only in memory."""
    cache={}
    def physical(reference):
        name,n=reference.rsplit(':',1)
        if name not in cache:cache[name]=rows(ROOT/name)
        return cache[name][int(n)-1]
    provenance=rows(a.b2a.B1/'evidence_archive/data/browser_pair_provenance.jsonl')
    loaded=[]
    for member in members:
        meta=member['source_meta']
        app=physical(meta['app_reference']);browser=physical(meta['browser_reference'])
        if member['cohort']=='b2b42':binding=physical(meta['provenance_reference'])
        else:
            matches=[r for r in provenance if r.get('pair_id')==browser['pair_id']]
            require(len(matches)==1,'PILOT_BINDING');binding=matches[0]
        loaded.append(dict(app=app,browser=browser,provenance=binding,app_reference=meta['app_reference']))
    return loaded

def adapt_loaded(raw):
    CALLS['shared_raw_adaptation']+=1
    app,pair=prep.v16_pair(raw['app'],raw['browser'],raw['provenance'],raw['app_reference'])
    projection=sa.v16_projection(raw['app'],raw['browser'],pair_errors=pair['errors'])
    return dict(app=app,pair=pair,projection=projection)

def load_descriptor(descriptor):
    CALLS['load_parse_validate']+=1
    obj=read(ROOT/descriptor['path'])
    if descriptor['kind']=='rule':
        model=obj['predictor']
        require(model['model_id']==descriptor['model_id'],'WRAPPER_ID')
        require(digest(ROOT/model['base']['path'])==model['base']['sha256'],'BASE_CHANGED')
        require(digest(ROOT/model['condition_source']['path'])==model['condition_source']['sha256'],'CONDITION_CHANGED')
        base=a.b2a.selection.load_model(ROOT/model['base']['path'])
        require(base.model_id==model['base_model_id'],'BASE_ID')
        return dict(descriptor=descriptor,model=model,base=base)
    tree=obj['tree'];spec=obj['preprocessing']
    require(obj['model_id']==descriptor['model_id'] and tree['params']==dict(tree['params'],**e.PARAMS),'TREE_PARAMS_OR_ID')
    n=len(tree['feature'])
    require(all(len(tree[k])==n for k in ('children_left','children_right','threshold','values')),'TREE_SHAPE')
    require(all(x==-2 or 0<=x<len(tree['features']) for x in tree['feature']),'TREE_FEATURE_INDEX')
    require(set(spec['columns'])==set(f.FIELDS),'PREPROCESS_FIELDS')
    return dict(descriptor=descriptor,model=obj)

def tree_cells(model,adapted):
    """View-specific measured cells, with original conditions only when required."""
    CALLS['tree_measurement_cells']+=1
    source=adapted['projection'];view=model['view'];cells={}
    for field in f.VIEWS[view]:
        if field not in f.FIELDS:continue
        path,transform,side,kind=f.FIELDS[field];cell=f.measure(source,path,transform)
        if source['endpoint_errors'][side]:cell.update(value=None,available=False,reason='ENDPOINT_BINDING_FAILED')
        cells[field]=cell
    if view=='V_BOTH_REL':
        for cid in ('C1','C2'):
            CALLS['C1_C2_evaluate']+=1
            r=a.b2a.cond.evaluate(cid,adapted['pair'])
            cells[cid]=dict(value=r['state'],available=r['state'] in ('T','F'),reason=r['reason'])
    return dict(cells=cells,endpoint_errors=source['endpoint_errors'],pair_errors=source['pair_errors'])

def prepare(runtime,adapted):
    CALLS['model_input_prepare']+=1
    model=runtime['model']
    if runtime['descriptor']['kind']=='tree':
        item=tree_cells(model,adapted);gate=f.view_status(item,model['view'])
        if gate['gate']!='READY':return dict(gate=gate,X=None)
        fields=[k for k in f.VIEWS[model['view']] if k in f.FIELDS]
        shared,_=e.transform(model['preprocessing'],[item],fields)
        X,_=e.view_array(model['preprocessing'],shared,[item],model['view'])
        return dict(gate=gate,X=X)
    base=runtime['base'];raw=adapted['app']['raw'];names=[x.atom_id for x in base.atoms]
    encoded=a.b2a.selection.transform_numeric(raw,base.encoder,names)
    for name in set(names)&set(base.fit['relation_atom_ids']):encoded[name]=copy.deepcopy(raw[name])
    conditions={}
    for cid in model['extensions']:
        CALLS['C1_C2_evaluate']+=1
        conditions[cid]=a.b2a.cond.evaluate(cid,adapted['pair'])['state']
    return dict(payload={'features':encoded,'view_id':base.view['view_id']},conditions=conditions)

def infer_prepared(runtime,prepared):
    CALLS['prepared_model_inference']+=1
    if runtime['descriptor']['kind']=='tree':
        if prepared['gate']['gate']!='READY':return dict(state=prepared['gate']['gate'],probability=None)
        prob,leaf=e.predict_json(runtime['model']['tree'],prepared['X'])
        return dict(state='T' if prob[0]>=.5 else 'F',probability=float(prob[0]))
    prediction=a.b2a.selection.predict(runtime['base'],'current-pair',prepared['payload'])
    state=original_inference.predict_saved(runtime['model'],original_inference.state(prediction),prepared['conditions'])
    return dict(state=state)

def original_current(runtime,current):
    CALLS['original_current_interface']+=1
    if runtime['descriptor']['kind']=='tree':return e.predict_current(runtime['model'],current)
    return original_inference.predict_current(runtime['model'],current['app'],current['pair'])

def current_input(runtime,adapted):
    return tree_cells(runtime['model'],adapted) if runtime['descriptor']['kind']=='tree' else {'app':adapted['app'],'pair':adapted['pair']}

def cached_current(runtime,adapted):return infer_prepared(runtime,prepare(runtime,adapted))
def loaded_raw_original(runtime,raw):return original_current(runtime,current_input(runtime,adapt_loaded(raw)))
def loaded_raw_cached(runtime,raw):return cached_current(runtime,adapt_loaded(raw))

def descriptors():
    result=[]
    for m in read(HERE/'results/models.json'):
        result.append(dict(model_id=m['model_id'],kind='rule',setting=m['setting'],fold=m['fold'],label=m['setting']+f" / {m['fold']:02d}",path=ref(HERE/'results'/(m['setting']+f"_{m['fold']:02d}.json"))))
    for m in read(B3A/'results/models.json'):
        result.append(dict(model_id=m['model_id'],kind='tree',setting=m['view'],fold=None,label=m['plan']+' / '+m['view'],path=ref(B3A/'results'/m['path'])))
    return result
