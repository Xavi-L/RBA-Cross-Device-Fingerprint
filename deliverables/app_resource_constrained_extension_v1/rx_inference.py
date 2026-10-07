"""Current pair inference. No scenario, target, identity, phase, or split input."""
from rx_common import *
import rx_sources as s
from functools import lru_cache
@lru_cache(maxsize=3)
def checked_base(reference, dependencies):
    for p,h in dependencies:require(s.digest(ROOT/p)==h,'FROZEN_DEPENDENCY_CHANGED:'+p)
    return read(ROOT/reference)
def components(prepared):
    l=s.legacy()
    return dict(C1=l.c1.evaluate('C1',prepared['pair']),resources=l.rc.evaluate(prepared['record']))
def predict_prepared(model,prepared,component_outputs=None):
    require(model['status'] in ('BASELINE_RETAINED','SELECTED_EXTENSION'),'NO_FEASIBLE_MODEL')
    require(set(model['extensions'])<=set(CANDIDATES) and len(set(model['extensions']))==len(model['extensions']),'INVALID_EXTENSIONS')
    l=s.legacy();base=checked_base(model['base_ref'],tuple(model['frozen_dependencies'].items()));require(base['model_id']==model['base_model_id'] and base['extensions']==['C1'],'BASE_ID_CHANGED')
    outputs=component_outputs if component_outputs is not None else components(prepared)
    fm=l.rd.APP.full_models()[base['base']['fold']]
    if 'app_input' in prepared:
        require(set(prepared['app_input'])=={'raw'},'APP_ENVELOPE')
        require(not any(str(k).startswith('browser.') for k in prepared['app_input']['raw']),'BROWSER_IN_APP')
        pr=l.rd.APP.full_engine.predict_current(fm,'current-pair',prepared['app_input']['raw'])
        ast=pr.get('logical_state') or pr['decision']
    else:
        pr=l.re.predict(fm,'APP_FULL',prepared);ast=pr['state']
    baseline=combine(ast,{'C1':outputs['C1']['state']},['C1'])
    selected={c:outputs['resources'][CANDIDATES[c]]['state'] for c in model['extensions']}
    state=combine(baseline,selected,model['extensions'])
    return dict(model_id=model['model_id'],app_state=ast,C1=outputs['C1']['state'],base_state=baseline,
        state=state,selected_conditions=selected,decision={'T':'MANIPULATION_ALERT','F':'NO_ALERT','U':'INSUFFICIENT_EVIDENCE','FAILED':'FAILED'}[state])
def predict_current(model,app,browser,provenance):
    return predict_prepared(model,s.prepare_v16(app,browser,provenance))
if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--input',required=True);a=p.parse_args()
    obj=read(a.input);require(set(obj)=={'app','browser','provenance'},'CURRENT_PAIR_ENVELOPE')
    print(json.dumps(predict_current(read(a.model),**obj),ensure_ascii=False))
