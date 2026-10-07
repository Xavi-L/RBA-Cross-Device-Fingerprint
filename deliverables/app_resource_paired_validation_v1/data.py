"""Current-stage inputs and existing normal memberships; labels kept outside predictors."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import importlib.util,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
import conditions as c
from hybridguard_agent.research import mtc_relation_sources as src
from hybridguard_agent.research import screen_geometry_io as io

def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
# The original diagnostic reader imports a local conditions module. Bind that import
# temporarily and restore ours; no historical module/file is edited.
def diagnostic():
    old=sys.modules.get('conditions');sys.path.insert(0,str(HERE.parent/'browser67_cross_endpoint_diagnostic_v1'))
    sys.modules['conditions']=module('legacy_resource_source_conditions',HERE.parent/'browser67_cross_endpoint_diagnostic_v1/conditions.py')
    try:return module('resource_source_diagnostic',HERE.parent/'browser67_cross_endpoint_diagnostic_v1/run.py')
    finally:
        if old:sys.modules['conditions']=old
        sys.path.remove(str(HERE.parent/'browser67_cross_endpoint_diagnostic_v1'))
DIAG=diagnostic()
APP=module('resource_frozen_app_data',HERE.parent/'app177_core_ablation_v1/data.py')
FIELDS=set(sum((list(x) for x in c.DEPS.values()),[]))
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    result=io.read_jsonl(p)
    if result.errors:raise ValueError('MEMBER_FILE_UNREADABLE:'+str(result.errors))
    return [r['value'] for r in result.records]
def project(app,browser):
    out={k:{} for k in ('features','field_status','field_quality','field_errors')}
    for side,raw in [('app',app),('browser',browser)]:
        if not raw:continue
        p=raw['canonical_received_payload'];f=src._flatten(p,side)
        statuses=p.get('collection_status',{}).get('fields',{}) if side=='app' else p.get('field_statuses',{})
        fs=p.get('field_session_ids',{})
        for field in FIELDS:
            if not field.startswith(side+'.'):continue
            local=field[len(side)+1:]
            if field in f:out['features'][field]=f[field]
            st=statuses.get(local);out['field_status'][field]=st
            if field in f:out['field_quality'][field]=src._quality(field,f[field],st)
            if side=='app' and (not isinstance(fs,dict) or fs.get(local,raw['session_id'])!=raw['session_id']):out['field_errors'][field]='FIELD_SESSION_MISMATCH'
    return out
@lru_cache(maxsize=12)
def archive(path):
    result=io.read_jsonl(path)
    return {r['line']:r['value'] for r in result.records},result.errors

def raw_ref(run,ref,name):
    if not isinstance(ref,dict) or ref.get('file')!='data/'+name or type(ref.get('line')) is not int or ref['line']<1:raise ValueError('INVALID_RAW_REFERENCE')
    entries,errors=archive(str(run/ref['file']));raw=entries.get(ref['line'])
    if raw is None:raise ValueError('RAW_POSITION_UNREADABLE:'+str(errors))
    key='browser_session_id' if name=='raw_browser_payloads.jsonl' else 'session_id' if name=='raw_expanded_payloads.jsonl' else 'pair_id'
    if not raw.get(key) or sum(x.get(key)==raw[key] for x in entries.values())!=1:raise ValueError('DUPLICATE_OR_MISSING_RAW_ID')
    return raw

def bind(run,plan,slot,cap,duplicate=False):
    a=b=p=None;errors={k:[] for k in ('app','browser','pair')}
    if not cap or duplicate:
        errors={k:['DUPLICATE_CAPTURE' if duplicate else 'CAPTURE_MISSING'] for k in errors}
    else:
        stage_ok=all(cap.get(k)==slot.get(k) for k in ('sample_id','scenario_group_id','scenario','round','phase','runtime_context','collection_round'))
        for side,name in [('app','raw_expanded_payloads.jsonl'),('browser','raw_browser_payloads.jsonl')]:
            try:
                if not stage_ok:raise ValueError('STAGE_BINDING_MISMATCH')
                raw=raw_ref(run,cap.get('archives',{}).get(side),name)
                if cap.get('endpoint_counts',{}).get(side)!=1:raise ValueError('ENDPOINT_NOT_UNIQUE')
                payload=raw['canonical_received_payload']
                if side=='app':
                    m=payload['collection_manifest'];sid=raw['session_id']
                    if (raw.get('raw_payload_archive_schema_version')!='expanded-raw-payload-v1' or payload.get('schema_version')!='expanded-v2.2-status' or sid!=payload.get('session_id') or m.get('runtime_context')!=slot['runtime_context'] or m.get('collection_round')!=slot['collection_round'] or m.get('device_manifest_id')!=plan['device_manifest_id'] or m.get('collector_version_code')!=16 or payload.get('collector_app')!='featureapp' or not raw.get('receipt_id')):raise ValueError('APP_CURRENT_V16_BINDING_INVALID')
                    a=raw
                else:
                    t=cap.get('ticket') or {}
                    if t.get('selected_browser_package')!=t.get('resolved_browser_package') or t.get('selected_browser_package')!=plan['browser_package']:raise ValueError('BROWSER_PACKAGE_MISMATCH')
                    DIAG.check_browser(raw,sid=raw['browser_session_id'],pair_id=t.get('pair_id'),app_sid=t.get('app_session_id'),revision='expanded-web-67-v2',batch=t.get('collection_batch_id'))
                    b=raw
            except (KeyError,TypeError,ValueError,OSError) as e:errors[side].append(str(e))
        try:
            p=raw_ref(run,cap.get('archives',{}).get('provenance'),'browser_pair_provenance.jsonl')
            if not a or not b or p['pair_status']!='completed' or p['pair_id']!=b['pair_id'] or p['app_session_id']!=a['session_id'] or b['app_session_id']!=a['session_id']:raise ValueError('INCOMPLETE_OR_WRONG_PAIR')
            for k in ('receipt_id','payload_sha256'):
                if p['app_'+k]!=a[k] or p['browser_'+k]!=b['browser_'+k]:raise ValueError('PROVENANCE_RECEIPT_MISMATCH')
            if p.get('selected_browser_package')!=plan['browser_package'] or p.get('resolved_browser_package')!=plan['browser_package']:raise ValueError('PAIR_PACKAGE_MISMATCH')
            if p['browser_session_id']!=b['browser_session_id'] or p['collection_batch_id']!=a['collection_batch_id'] or p['collection_batch_id']!=b['collection_batch_id']:raise ValueError('PROVENANCE_ID_MISMATCH')
        except (KeyError,TypeError,ValueError,OSError) as e:errors['pair'].append(str(e))
    record=project(a,b);record['binding']={k:not errors[k] for k in errors};record['binding']['app_session_id']=a['session_id'] if a else None
    if not a or not b:record['binding']['pair']=False
    return {'record':record,'app':a,'browser':b,'errors':errors,'references':cap.get('archives',{}) if cap else {},'times':DIAG.capture_times(a,b,'current_app','paired_browser') if a and b else None}

def mtc():
    d=DIAG
    # Reuse physical-line decoding and existing P2/P1/raw/receipt/normal checks.
    # No archive-wide hashes are needed for this read-only diagnostic.
    d.use=lambda p:Path(p)
    web_deps={k:[f for f in v if '.web_data.' in f] for k,v in c.DEPS.items()}
    from types import SimpleNamespace
    d.cond=SimpleNamespace(DEPS=web_deps)
    def projection(r):
        if not all(isinstance(r.get(k),dict) for k in ('features','field_status','field_quality')):raise ValueError('SNAPSHOT_MAPS_MISSING')
        return {k:{f:deepcopy(v) for f,v in r[k].items() if f in FIELDS} for k in ('features','field_status','field_quality')}
    d.projection=projection
    def complete(pair,ae,be,common):
        pair['binding']={'app':not(ae or common),'browser':not(be or common),'pair':not(ae or be or common)}
        pair['binding_errors']={'app':ae,'browser':be,'pair':common};return pair
    d.complete_pair=complete
    members=d.mtc_members();items=d.mtc(members);lookup={m['sample_id']:m for _,m in members}
    for item in items:
        m=lookup[item['meta']['sample_id']];item['record']=item.pop('pair');r=item['record'];r['binding']['app_session_id']=m['app_session_id']
        # Native operand is checked against its own original raw, without requiring App Web.
        try:
            path=str((d.RAW/'raw_expanded_payloads.jsonl').relative_to(ROOT));entries,_=APP.archive(path)
            raw=entries[m['app_raw_line']]['value']
            if raw.get('session_id')!=m['app_session_id'] or raw.get('payload_sha256')!=m['app_payload_sha256']:raise ValueError('SELECTED_P2_RAW_BINDING_MISMATCH')
            repeats=sum(x['value'].get('session_id')==m['app_session_id'] for x in entries.values())
            if repeats>1:item['meta']['duplicate_session_resolution']={'archived_uploads':repeats,'selected_physical_line':m['app_raw_line'],'basis':'original P2 physical line and payload hash plus P1 receipt binding; no nearest-time or value selection'}
            f=src._flatten(raw['canonical_received_payload'],'app');st=raw['canonical_received_payload']['collection_status']['fields']
            if c.N in r['features'] and (r['features'][c.N]!=f.get(c.N) or r['field_status'].get(c.N)!=st.get(c.N[4:])):r.setdefault('field_errors',{})[c.N]='NATIVE_RAW_PROJECTION_MISMATCH'
        except (ValueError,KeyError,TypeError,OSError) as e:r.setdefault('field_errors',{})[c.N]=str(e)
    return items

def capture_records(run):
    """Keep raw capture logs intact; derive actual endpoint command times from their ledger.

    The legacy capture control_begin denotes preparation before App navigation.
    Browser runtime control starts later, at its own recorded Runtime.evaluate.
    """
    caps=rows(run/'captures.jsonl');events=rows(run/'private_command_events.jsonl');by_capture={}
    for e in events:
        if e.get('kind')=='cdp_sent':by_capture.setdefault(e.get('capture_id'),[]).append(e)
    for cap in caps:
        endpoint=cap.get('control_route',{}).get('endpoint');ev=by_capture.get(cap.get('capture_id'),[])
        controls=[e for e in ev if e.get('endpoint')==endpoint and e.get('command',{}).get('method')==('Runtime.evaluate' if endpoint=='browser' else 'Page.addScriptToEvaluateOnNewDocument') and 'CONTROL_ALREADY_PRESENT' in str(e.get('command',{}).get('params',{}))]
        restores=[e for e in ev if e.get('endpoint')==endpoint and e.get('command',{}).get('method')=='Runtime.evaluate' and e.get('command',{}).get('params',{}).get('expression')=='globalThis.__restoreResource?.()']
        cap['control_preparation_begin']=cap.get('control_begin')
        cap['control_start_command_at']=controls[0]['at'] if len(controls)==1 else None
        cap['control_restoration_begin']=restores[0]['at'] if len(restores)==1 else None
        cap['target_control_timing_basis']='browser runtime command' if endpoint=='browser' else 'App new-document script registration then actual document navigation'
    return caps
