"""Inference input preparation. Operation/label/split metadata never enters features."""
import copy
from adapter import b2a,b2b
from common import require

def pair_inputs(pair):
    fields=set(b2a.cond.DEPS['C1']+b2a.cond.DEPS['C2'])
    return {**{k:{f:v for f,v in pair.get(k,{}).items() if f in fields} for k in ('features','field_status','field_quality')},'errors':list(pair.get('errors',[]))}

def v16_pair(app,browser,provenance,app_reference='current-app'):
    """Current archive envelopes + same-pair provenance; no pre/post or targets."""
    errors=[];app_input={'raw':{}}
    try:
        sid=app['session_id']; adapted,_=b2a.compile_app(app,sid,app_reference)
        app_input={'raw':adapted['raw']}
    except (KeyError,ValueError,TypeError,PermissionError) as e:errors.append('APP:'+str(e))
    try:
        require(browser is not None and provenance is not None,'BROWSER_OR_PROVENANCE_MISSING')
        b2a.check_browser(browser,sid=browser['browser_session_id'],pair_id=provenance['pair_id'],
            app_sid=app['session_id'],revision='expanded-web-67-v2',batch=app['collection_batch_id'])
        require(provenance['pair_status']=='completed','INCOMPLETE_PAIR')
        for key in ('app_session_id','browser_session_id','pair_id','browser_receipt_id','browser_payload_sha256','app_receipt_id','collection_batch_id'):
            require(provenance[key]==browser[key],'PROVENANCE_BROWSER:'+key)
        for key,original in [('app_session_id','session_id'),('app_receipt_id','receipt_id'),('app_payload_sha256','payload_sha256'),('collection_batch_id','collection_batch_id')]:
            require(provenance[key]==app[original],'PROVENANCE_APP:'+key)
    except (KeyError,ValueError,TypeError) as e:errors.append('PAIR:'+str(e))
    try:pair=b2b.project(app,browser)
    except (KeyError,ValueError,TypeError):pair={'features':{},'field_status':{},'field_quality':{}};errors.append('PAIR_PROJECTION_FAILED')
    pair['errors']=errors
    return app_input,pair_inputs(pair)

def mtc_app(observation,registry,raw,reference):
    """Original MTC v9/v11 App preparation, with Browser and experiment sidecars removed."""
    sid=observation['sample_id']
    app_only={k:copy.deepcopy(observation[k]) for k in ('record_schema_version','sample_id','dataset_view','app','source_refs')}
    for k in ('features','field_status','field_quality'):
        app_only[k]={f:copy.deepcopy(v) for f,v in observation[k].items() if f.startswith('app.')}
    bound=b2a.time_source.bind_mtc_observation(app_only,sid,allowed_ids=[sid],expected_registry=registry,raw_record=raw,raw_reference=reference)
    adapted=b2a.candidates.adapt_mtc(app_only,bound)
    return {'raw':adapted['raw']}
