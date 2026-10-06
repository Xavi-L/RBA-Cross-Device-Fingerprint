"""One current pair inference; no experiment labels or trajectories accepted."""
import argparse, sys
from common import HERE, ROOT, read, require, state, digest
from selector import combine

def predict_saved(model, base_state, condition_states):
    require(model['status'] in ('SELECTED_EXTENSION','BASELINE_RETAINED'), 'NO_FEASIBLE_MODEL')
    return combine(base_state, condition_states, model['extensions'])

def predict_current(model, app_input, pair):
    """app_input: frozen adapter's current App raw atom cells, never Browser.

    pair: current bound pair features/status/quality/errors. Metadata rejected;
    no labels or sample/group/phase IDs affect the output.
    """
    from adapter import b2a
    require(set(app_input)=={'raw'}, 'APP_INPUT_ENVELOPE')
    require(all(not str(k).startswith('browser.') for k in app_input['raw']), 'BROWSER_IN_APP_INPUT')
    allowed={'features','field_status','field_quality','errors'}
    require(set(pair)<=allowed, 'PAIR_INPUT_ENVELOPE')
    allowed_fields=set(b2a.cond.DEPS['C1']+b2a.cond.DEPS['C2'])
    for name in ('features','field_status','field_quality'):
        require(set(pair.get(name,{}))<=allowed_fields, 'PAIR_UNREGISTERED_FIELD')
    path=ROOT/model['base']['path']
    require(digest(path)==model['base']['sha256'], 'BASE_MODEL_CHANGED')
    require(digest(ROOT/model['condition_source']['path'])==model['condition_source']['sha256'], 'CONDITION_IMPLEMENTATION_CHANGED')
    require(model['extensions'] is not None and set(model['extensions'])<= {'C1','C2'} and len(set(model['extensions']))==len(model['extensions']), 'INVALID_EXTENSION_SET')
    base=b2a.selection.load_model(path)
    allowed_app=set(base.encoder['fixed_atoms'])|set(base.encoder['numeric'])|set(base.fit['relation_atom_ids'])
    require(set(app_input['raw'])<=allowed_app, 'APP_UNREGISTERED_FIELD')
    require(base.model_id==model['base_model_id'], 'BASE_ID_CHANGED')
    prediction=b2a.selection.predict_current(base,'current-pair',app_input['raw'])
    conditions={c:b2a.cond.evaluate(c,pair) for c in model['extensions']}
    s=predict_saved(model,state(prediction),{c:r['state'] for c,r in conditions.items()})
    return dict(model_id=model['model_id'],base_state=state(prediction),state=s,
        decision={'T':'MANIPULATION_ALERT','F':'NO_ALERT','U':'INSUFFICIENT_EVIDENCE','FAILED':'FAILED'}[s],
        selected_conditions=conditions,base_prediction=prediction)

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Current bound pair; see README for App v16 and MTC adapters.')
    p.add_argument('--model',required=True);p.add_argument('--input',required=True);a=p.parse_args()
    data=read(a.input)
    import json
    print(json.dumps(predict_current(read(a.model),data['app_input'],data['pair']),ensure_ascii=False))
