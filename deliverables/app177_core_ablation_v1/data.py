"""Fixed members and current-App-only inputs. Metadata is a separate sidecar."""
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from hybridguard_agent.research import screen_geometry_io as io
from hybridguard_agent.research import mtc_reselection_candidates as base
from hybridguard_agent.research import mtc_timezone_candidates as cand
from hybridguard_agent.research import mtc_timezone_selection as full_engine
from hybridguard_agent.research import mtc_relation_sources as source
from hybridguard_agent.research import timezone_relation_sources as times
from hybridguard_agent.research import mtc_screen_relations as screen
from hybridguard_agent.research import mtc_resource_relations as memory
from hybridguard_agent.research import mtc_timezone_relation as tz
from hybridguard_agent.research import app177_ablation as engine
from hybridguard_agent.research.rule_learning.contracts import cell
from hybridguard_agent.research.rule_learning.matrix import control_input, extract_atom
from hybridguard_agent.research.rule_learning_v2.adapter import approved_atoms
from hybridguard_agent.research.memory_relation_validation import compiler
from hybridguard_agent.research.manipulation_eval.adapter import mapping_contract, at_path, MISSING, equal_value, quality_for

FULL=ROOT/'deliverables/timezone_relation_validation_v1'
IDS=['mtc-rel-tz-6e10284c39b1b601ab406240','mtc-rel-tz-9c5fa0e310ba10a00e520b1c','mtc-rel-tz-4ae67bb9da899cc419dd525f']
STATES=('T','F','U','FAILED','EMPTY_MODEL')
USED=set()

def read(p):
    p=Path(p); USED.add(str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p))
    return io.read_object(p,required=True)[0]
def records(p):
    """A foundational saved member list may never silently lose a physical line."""
    p=Path(p); USED.add(str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p))
    result=io.read_jsonl(p)
    if result.errors: raise io.EvidenceError('MEMBERS_UNREADABLE:'+json.dumps(result.errors))
    return result.records

def unique(rs,key='sample_id'):
    out={}
    for r in rs:
        k=r[key]
        if k in out: raise ValueError('DUPLICATE_MEMBER:'+str(k))
        out[k]=r
    return out

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
prior=module('app177_original_members',ROOT/'deliverables/mtc_constrained_reselection_v1/run_experiment.py')

@lru_cache(maxsize=1)
def settings():
    s=read(ROOT/'deliverables/mtc_constrained_reselection_v1/SETTINGS.json')
    if s['folds']!=json.loads((ROOT/s['controlled_source']/'FOLDS.json').read_text()): raise ValueError('FOLD_LIST_CHANGED')
    tests=[sid for f in s['folds'] for sid in f['outer_test_ids']]
    if len(tests)!=378 or len(set(tests))!=378: raise ValueError('EXACT_378_OUTER_POSITIONS_REQUIRED')
    for f in s['folds']:
        if len(f['train_ids'])!=252 or len(f['outer_test_ids'])!=126 or set(f['train_ids'])!=set(tests)-set(f['outer_test_ids']):
            raise ValueError('ORIGINAL_ENVIRONMENT_FOLD_CHANGED')
    if {k:len(v) for k,v in s['mtc_primary_ids'].items()}!={'discovery':630,'development':144,'reserved_validation':117}:
        raise ValueError('ORIGINAL_MTC_SPLITS_CHANGED')
    if s['mtc_normal_train_ids']!=s['mtc_primary_ids']['discovery']: raise ValueError('MTC_TRAIN_CHANGED')
    return s

@lru_cache(maxsize=1)
def full_models():
    s=settings();freeze=read(FULL/'MODELS_FROZEN.json');entries=read(FULL/'models.json')['models']
    if freeze['new_model_ids']!=IDS or freeze['parameters']!=cand.parameters(): raise ValueError('FULL_FREEZE_CHANGED')
    out={}
    for f,mid in zip(s['folds'],IDS,strict=True):
        e=next(x for x in entries if x['model_id']==mid)
        if e['stage']!='RETENTION' or e['scheme']!='B_REL_TZ': raise ValueError('FULL_STAGE_CHANGED')
        m=full_engine.RelationModel.from_dict(read(FULL/e['path']))
        training=read(FULL/e['training_path'])
        if (m.binding['fold_id']!=f['fold_id'] or m.fit['train_ids']!=f['train_ids'] or
            m.fit['mtc_train_ids']!=s['mtc_normal_train_ids'] or
            m.encoder!=read(FULL/'folds'/f['fold_id']/'encoder.json') or
            json.loads(json.dumps([engine.asdict(a) for a in engine.frozen_atoms(m.encoder)]))!=training['encoded_atoms']):
            raise ValueError('FULL_ENCODER_OR_TRAIN_OR_POOL_MISMATCH')
        out[f['fold_id']]=m
    tz.tzdb_directory() # unchanged 2026c dependency, no fallback to another version
    return out

@lru_cache(maxsize=24)
def archive(path):
    p=ROOT/path;USED.add(path)
    r=io.read_jsonl(p)
    return {v['line']:v for v in r.records},r.errors

def raw_at(ref, expected_session=None):
    path,n=ref.rsplit(':',1); n=int(n)
    if n<1: raise ValueError('INVALID_PHYSICAL_LINE')
    rs,issues=archive(path)
    if n not in rs: raise io.EvidenceError('RAW_POSITION_UNREADABLE:'+ref+':'+str(issues))
    row=rs[n]['value']
    sid=row.get('session_id')
    if expected_session is not None and sid!=expected_session: raise ValueError('RAW_SESSION_REFERENCE_MISMATCH')
    # Preserve duplicate identity failure, even when the requested line exists.
    if sid and sum(v['value'].get('session_id')==sid for v in rs.values())!=1:
        raise ValueError('DUPLICATE_RAW_SESSION:'+ref)
    return row


def base_names(scheme):
    return [a.atom_id for a in (*approved_atoms(base.definitions()),*cand.registered_atoms()) if engine.allowed(a,scheme)]


def adapt_raw(raw, session, ref, version, scheme='APP_FULL', required=None):
    """Explicit v14/v15/v16 projection; evaluate only requested operands.

    Source identity is permitted. Unselected measurements cannot veto a record.
    Legacy screen_layer stays intact; geometry snapshots are never substituted.
    """
    atoms=(*approved_atoms(base.definitions()),*cand.registered_atoms())
    names=set(base_names(scheme) if required is None else required);atoms=tuple(a for a in atoms if a.atom_id in names)
    p=raw.get('canonical_received_payload') if isinstance(raw,dict) else None
    if not isinstance(p,dict): raise ValueError('APP_RAW_PAYLOAD_MISSING')
    m=p.get('collection_manifest',{})
    versions={14:'1.6.7-expanded-v2.2-webgl1',15:'1.6.8-expanded-v2.2-geometry',16:'1.6.9-expanded-v2.2-geometry'}
    if (version not in versions or raw.get('raw_payload_archive_schema_version')!='expanded-raw-payload-v1' or
        raw.get('session_id')!=session or p.get('session_id')!=session or not session or
        p.get('collector_app')!='featureapp' or p.get('schema_version')!='expanded-v2.2-status' or
        m.get('collector_version_code')!=version or m.get('collector_version_name')!=versions[version]):
        raise ValueError('EXPLICIT_VERSION_OR_CURRENT_BINDING_FAILED')
    if not isinstance(p.get('web_data'),dict): raise ValueError('CURRENT_APP_WEB_MISSING')
    cs=p.get('collection_status',{})
    if cs.get('status_schema_version')!='field-status-v1' or not isinstance(cs.get('fields'),dict):
        raise ValueError('CURRENT_APP_STATUS_MISSING')
    refs=set(f for a in atoms for f in engine.dependency(a)['operands'])
    # Preserve diagnostic-only web timezone but it never gates a prediction.
    if tz.TIMEZONE_ID in names: refs.add(tz.WEB_ZONE)
    f,st,q={},{},{};field_issues={}
    for spec in mapping_contract()['fields']:
        key=spec['field']
        if key not in refs: continue
        paths=(spec['source_logical_path'],spec['legacy_alias'])
        values=[at_path(p,x) for x in paths];present=[v for v in values if v is not MISSING]
        statuses=[cs['fields'][x] for x in paths if x in cs['fields']]
        if len(present)>1 and not equal_value(*present): field_issues[key]='VALUE_ALIAS_CONFLICT'
        if len(statuses)>1: field_issues[key]='DUPLICATE_STATUS_ALIAS'
        fs=p.get('field_session_ids',{})
        if not isinstance(fs,dict) or any(fs.get(x,session)!=session for x in (key,*paths)):
            field_issues[key]='FIELD_SESSION_MISMATCH'
        if present:f[key]=deepcopy(present[0])
        st[key]=statuses[0] if statuses else None
        q[key]=quality_for(key,f.get(key),st[key]) if isinstance(st[key],str) and st[key] in source.STATUSES else None
    bound=source._result({'app_session_id':session,'session_id':session,'raw_reference':ref,
                          'collector_version_code':version,'collector_version_name':versions[version]},f,st,q)
    bound['acquisition_time']=times._time_evidence(p,session,ref) if tz.TIMEZONE_ID in names else None
    projection={'record_schema_version':'hybridguard-mtc-observation-v2','adapter_version':'app177-triplet-adapter-v1',
                'features':f,'field_status':st,'field_quality':q}
    c,contract=compiler();catalog={x['atom_id']:x for x in contract['candidate_definitions']}
    rules={x['rule_id']:x for x in contract['rule_definitions']};specs={x['field']:x for x in contract['control_specs']}
    # Original semantic kernels check only their own Web observation and source.
    from hybridguard_agent.research.rule_semantics_runtime_input import adapt_runtime_payload, RuntimeInputError
    from hybridguard_agent.research.rule_semantics_revision_v1 import web_language_first_difference, webdriver_reported_state
    from hybridguard_agent.research.rule_semantics_revision_v1.contracts import SourceBinding
    from hybridguard_agent.research import webgl1_selector_integration as gl
    from hybridguard_agent.research import rule_semantics_webgl1_cap8 as cap
    bindings={mode:SourceBinding(ref,scope,observer_revision='app-webdriver-observer-v1' if mode=='WEBDRIVER_RAW' else None,
              realm_binding='featureapp:'+session+':main-frame' if mode=='WEBDRIVER_RAW' else None)
              for mode,(_,scope) in c.MODES.items()}
    semantic=adapt_runtime_payload(p,expected_session_id=session,source_bindings=bindings)
    out={};details={}
    for a in atoms:
        aid=a.atom_id;deps=engine.dependency(a)['operands'];bad=[field_issues[x] for x in deps if x in field_issues]
        if bad: measured=cell('FAILED',';'.join(bad))
        elif aid in (cap.LANG_ID,cap.WD_ID):
            mode='LANGUAGE' if aid==cap.LANG_ID else 'WEBDRIVER_RAW'
            try:
                inp,bind=semantic.input_for(mode)
                result=web_language_first_difference(inp,bind) if aid==cap.LANG_ID else webdriver_reported_state(inp,mode='raw_observation_v1',source_binding=bind)
                measured=cap.kernel_cell(result.to_dict(),aid)
            except RuntimeInputError as e: measured=cell(e.state,e.reason)
        elif aid==gl.CANDIDATE_ID:
            # v15/v16 stay U under the original frozen v14 WebGL source gate.
            measured=gl.kernel_cell(gl.compile_payload(p,expected_session_id=session,source_registration=gl.SourceRegistration(ref)))
        elif aid==screen.ATOM_ID: measured=screen.evaluate(bound)[aid]
        elif aid==memory.MEMORY_ID: measured=memory.evaluate(bound)[aid]
        elif aid==tz.TIMEZONE_ID: measured=tz.evaluate(bound)[aid]
        elif a.orientation=='CATALOG_CONDITION': measured=extract_atom(catalog[aid],rules[aid[4:]],projection)
        else:
            measured=control_input(projection,specs[a.provenance['field']])
            if a.orientation=='CONTROL_EQUALITY' and measured['evaluation_status']=='OK' and measured['available']:
                measured['value']=measured['value']==a.provenance['equals']
        out[aid]={k:deepcopy(measured[k]) for k in ('value','available','evaluation_status','reason')}
        details[aid]={'field_refs':deps,'state':state_cell(out[aid]),'reason':measured['reason']}
    return {'raw':out,'candidate_inputs':details,'binding_status':'OK','adapter_version':'app177-current-v14-v15-v16-projection-v1'}


def state_cell(c):
    if c['evaluation_status']!='OK':return 'FAILED'
    if not c['available']:return 'U'
    if type(c['value']) is bool:return 'T' if c['value'] else 'F'
    return 'NUMERIC'

def failed(reason,scheme='APP_FULL'):
    return {'raw':{n:cell('FAILED',reason) for n in base_names(scheme)},'candidate_inputs':{},'binding_status':'FAILED','failure':reason}


def controlled(ids):
    s=settings();path=ROOT/s['controlled_source'];meta=prior.controlled_metadata(path,ids)
    raw=prior.controlled_rows(path,ids,ids);bound=times.load_controlled_sources(ids,allowed_ids=ids)
    rows={};members=[]
    for sid in ids:
        try:rows[sid]=cand.adapt_controlled(raw[sid],bound[sid])
        except Exception as e:rows[sid]=failed(str(e))
        m=meta[sid]
        members.append(dict(sample_id=sid,cohort='controlled',subset='heldout',identity='EFFECTIVE_INTERVENTION' if m['phase']=='attack' else 'NORMAL',
            scenario=m['config_id'],phase=m['phase'],environment=m['environment_group_id'],group_id=m['triplet_id'],
            raw_reference=bound[sid].get('source_binding',{}).get('raw_reference'),
            source_reference=str((path/'evaluation'/(sid+'.json')).relative_to(ROOT)),affected_endpoint='App',
            original_metadata=m))
    return rows,meta,members


def selected_mtc(index, ids, snapshot):
    """Decode only authorized physical lines; retain every planned failed slot."""
    if len(ids)!=len(set(ids)): raise ValueError('DUPLICATE_MTC_REQUEST')
    wanted=defaultdict(dict);result={};issues={}
    for sid in ids:
        r=index[sid];line=r['source_line']
        if type(line) is not int or line<1 or line in wanted[r['source_view']]:raise ValueError('INVALID_MTC_REFERENCE')
        wanted[r['source_view']][line]=sid
    for view,lines in wanted.items():
        path=Path(snapshot)/(view+'.jsonl')
        try:
            with path.open('rb') as f:
                for n,body in enumerate(f,1):
                    if n not in lines:continue
                    sid=lines[n]
                    try:
                        r=io._loads(body.decode('utf-8'))
                        if not isinstance(r,dict) or r.get('sample_id')!=sid or r.get('dataset_view')!=view:
                            raise ValueError('P2_CURRENT_MEMBER_BINDING_MISMATCH')
                        result[sid]=r
                    except (ValueError,UnicodeError) as e:issues[sid]=str(path)+':'+str(n)+':'+type(e).__name__
        except OSError as e:
            for n,sid in lines.items():issues[sid]=str(path)+':'+str(n)+':'+type(e).__name__
    for sid in ids:
        if sid not in result and sid not in issues:issues[sid]='PLANNED_PHYSICAL_LINE_MISSING'
    return result,issues


def mtc(ids):
    s=settings();index=prior.registry(s);basis=prior.normal_evidence(s)
    obs,issues=selected_mtc(index,ids,ROOT/s['mtc_snapshot'])
    bound=times.load_mtc_sources(obs,index,ids,allowed_ids=ids)
    rows={};members=[];meta={}
    for sid in ids:
        if not basis[sid]['supported']:raise ValueError('NORMAL_BASIS_CHANGED')
        try:
            if sid in issues:raise ValueError(issues[sid])
            rows[sid]=cand.adapt_mtc(obs[sid],bound[sid]);rows[sid]['binding_status']=bound[sid]['status']
        except Exception as e:rows[sid]=failed(str(e))
        r=index[sid]
        meta[sid]={'split':r['split'],'normal_basis':True,'group_id':r['group_id']}
        members.append(dict(sample_id=sid,cohort='mtc',subset=r['split'],identity='NORMAL',scenario='routine_mtc',phase='observation',
            group_id=r['group_id'],raw_reference=bound[sid]['source_binding'].get('timezone_raw_reference'),
            source_reference=s['mtc_snapshot']+'/'+r['source_view']+'.jsonl:'+str(r['source_line']),
            normal_basis=basis[sid],affected_endpoint=None))
    return rows,meta,members


def training(fold):
    s=settings();rows,meta,members=controlled(fold['train_ids']);mr,mm,ms=mtc(s['mtc_normal_train_ids'])
    if any(x.get('binding_status')=='FAILED' for x in (*rows.values(),*mr.values())):raise ValueError('TRAIN_BINDING_FAILURE')
    train_env={m['environment_group_id'] for m in meta.values()}
    if len(train_env)!=2 or fold['heldout_environment'] in train_env:raise ValueError('ENVIRONMENT_LEAKAGE')
    index=prior.registry(s);ev=s['mtc_primary_ids']['development']+s['mtc_primary_ids']['reserved_validation']
    if {index[i]['group_id'] for i in mm}&{index[i]['group_id'] for i in ev}:raise ValueError('MTC_GROUP_LEAKAGE')
    return rows,meta,mr,mm,members+ms


def specialists():
    out={};members=[]
    mem_review=unique(read(FULL/'MEMORY_NORMAL_REVIEW.json')['records'])
    mem_effect={r['active_sample_id']:r for r in read(ROOT/'deliverables/memory_relation_validation_v1/summary.json')['new_batch']['triplets']}
    tz_effect={sid:t for t in read(FULL/'LOCAL_EVALUATION.json')['trios'] for sid in t['sample_ids']}
    sc_effect={sid:t for t in read(ROOT/'deliverables/screen_geometry_observation_v1/SUMMARY.json')['trios'] for sid in t['sample_ids']}
    sources=[('memory','memory_relation_validation_v1/new_batch.jsonl.gz',14),('timezone','timezone_relation_validation_v1/new_batch.jsonl.gz',14),
             ('screen','screen_geometry_closeout_v1/v15_replay/predictions.jsonl.gz',15)]
    for cohort,path,v in sources:
        rs=records(ROOT/'deliverables'/path);unique([x['value'] for x in rs])
        for rec in rs:
            r=rec['value'];sid=r['sample_id'];bind=r['source_binding'];ref=r.get('raw_reference',bind.get('raw_reference'))
            normal=mem_review[sid]['normal_basis'] if cohort=='memory' else r['normal_basis']
            effect=mem_effect.get(sid,{}) if cohort=='memory' else (tz_effect if cohort=='timezone' else sc_effect)[sid]
            positive=effect.get('effect_positive') if cohort=='memory' else effect.get('observable_intervention') and r['phase']=='change'
            identity='NORMAL' if normal.get('supported') else 'EFFECTIVE_INTERVENTION' if positive else 'NO_OBSERVABLE_EFFECT' if effect.get('effect')=='NO_OBSERVABLE_EFFECT' else 'UNCONFIRMED'
            scenario=('memory_'+str(r['target_gib'])+'GiB') if cohort=='memory' else r['process_type']+'_'+r.get('target_timezone','screen')
            m=dict(sample_id=sid,cohort=cohort,subset='historical_specialist',identity=identity,scenario=scenario,phase=r['phase'],environment=r['environment'],
                group_id=cohort+':'+r['environment']+':'+r['step_id'].rsplit('-',1)[0],raw_reference=ref,
                source_reference=rec['reference'],normal_basis=normal,effect={k:v for k,v in effect.items() if k in ('execution','effect','recovery','requested_orientation_achieved','effect_positive','observable_intervention')},
                affected_endpoint='App',version=v,saved_models=r.get('models',[]))
            try:out[sid]=adapt_raw(raw_at(ref,bind['app_session_id']),bind['app_session_id'],ref,v)
            except Exception as e:out[sid]=failed(type(e).__name__+':'+str(e))
            members.append(m)
    return out,members


def paired():
    rs=records(ROOT/'deliverables/cross_endpoint_constrained_extension_v1/results/members.jsonl')
    selected=[r for r in rs if r['value']['cohort'] in ('pilot18','b2b42')];unique([x['value'] for x in selected])
    selection=read(ROOT/'deliverables/cross_endpoint_matched_controls_v1/ATTEMPT_SELECTION.json')
    out={};members=[]
    for rec in selected:
        r=rec['value'];sid=r['sample_id'];sm=r['source_meta'];ref=sm['app_reference']
        if r['cohort']=='b2b42':
            expected=selection['replacement_run'] if sid in selection['replacement_sample_ids'] else selection['original_run']
            if sm['source_run']!=expected:raise ValueError('ATTEMPT_SELECTION_CHANGED')
        m=dict(sample_id=sid,cohort='paired60',subset=r['cohort'],identity=r['identity'],scenario=r['scenario'],phase=r['phase'],group_id=r['group_id'],
            raw_reference=ref,source_reference=rec['reference'],browser_reference=sm['browser_reference'],
            pair_reference=sm.get('pair_reference',sm.get('provenance_reference')),capture_reference=sm['capture_reference'],
            affected_endpoint='App' if (r.get('family') or '').startswith('App_') else 'Browser' if (r.get('family') or '').startswith('Browser_') else 'normal_setting',
            normal_identity_supported=r['normal_identity_supported'],operation_effect=r['operation_effect'],
            recovery_qualified=r['full_recovery_qualified'],version=16)
        try:
            raw=raw_at(ref);m['app_session_id']=raw['session_id'];out[sid]=adapt_raw(raw,raw['session_id'],ref,16)
        except Exception as e:out[sid]=failed(type(e).__name__+':'+str(e))
        members.append(m)
    if len(members)!=60 or Counter(m['identity'] for m in members)!={'NORMAL':46,'EFFECTIVE_INTERVENTION':14}:raise ValueError('PAIRED60_MEMBERS_CHANGED')
    return out,members


def evaluation():
    s=settings();ids=[i for f in s['folds'] for i in f['outer_test_ids']]
    rows,_,members=controlled(ids)
    for r,m in [(lambda x:(x[0],x[2]))(mtc([i for v in s['mtc_primary_ids'].values() for i in v])),specialists(),paired()]:
        if set(rows)&set(r):raise ValueError('COHORT_ID_OVERLAP')
        rows.update(r);members.extend(m)
    expected={'controlled':378,'mtc':891,'memory':72,'timezone':36,'screen':72,'paired60':60}
    if Counter(m['cohort'] for m in members)!=expected:raise ValueError('EVALUATION_POSITION_COUNT_CHANGED')
    return rows,members
