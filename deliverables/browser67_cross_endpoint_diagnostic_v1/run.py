#!/usr/bin/env python3
"""Read-only B2-A inference. No collection/training/formal split capabilities."""
import argparse, copy, csv, hashlib, json, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
import conditions as cond
from hybridguard_agent.research import mtc_relation_sources as source
from hybridguard_agent.research import timezone_relation_sources as time_source
from hybridguard_agent.research import mtc_timezone_selection as selection
from hybridguard_agent.research import mtc_timezone_candidates as candidates
from hybridguard_agent.research import mtc_reselection_candidates as base
from hybridguard_agent.research import mtc_cap8_data as historical
from hybridguard_agent.research.memory_relation_validation import compiler
from hybridguard_agent.research.manipulation_eval.adapter import adapt_payload
B1=ROOT/'deliverables/browser67_pilot_intake_v1'
P2=ROOT/'hybridguard_agent/artifacts/mtc_p2_frozen_20260922'
MTC=ROOT/'hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final'
RAW=ROOT/'backend_server/collection_backups/mtc_final_20260922/sources'
MODEL=ROOT/'deliverables/timezone_relation_validation_v1'
MODE='PILOT_DIAGNOSTIC_ONLY'
IDS=['mtc-rel-tz-6e10284c39b1b601ab406240','mtc-rel-tz-9c5fa0e310ba10a00e520b1c','mtc-rel-tz-4ae67bb9da899cc419dd525f']
USED={}
READ_ERRORS=[]
def ref(p,n=None):
    p=Path(p).resolve()
    s=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    return s+(':'+str(n) if n else '')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def use(p):
    key, current = ref(p), digest(p)
    if key in USED and USED[key] != current:
        raise ValueError('USED_INPUT_CHANGED:' + key)
    USED.setdefault(key, current)
    return Path(p)
def read(p):return json.loads(use(p).read_text())
def write(p,data):Path(p).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def jsonl(p,rows):Path(p).write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rows))
def rows(p, selected=None):
    """Physical lines, no dropping malformed positions; optional selective decoding."""
    out=[]
    try:
        p=use(p)
        with p.open('rb') as stream:
            for n,line in enumerate(stream,1):
                if selected is not None and n not in selected:continue
                try:
                    r=json.loads(line)
                    if type(r) is not dict:raise ValueError('NOT_OBJECT')
                    out.append((n,r,None))
                except (ValueError,TypeError,UnicodeError) as e:out.append((n,None,type(e).__name__))
    except OSError as e:
        READ_ERRORS.append({'path':ref(p),'error':type(e).__name__})
    return out

def unique(records,key,value):
    found=[(n,r,e) for n,r,e in records if r and r.get(key)==value]
    if len(found)!=1:raise ValueError('MISSING_OR_DUPLICATE_'+key)
    return found[0]

def projection(r, *, derive_quality=False):
    if not isinstance(r,dict):raise ValueError('MISSING_PAIR')
    fs=r.get('features');st=r.get('field_status')
    if not isinstance(fs,dict) or not isinstance(st,dict):raise ValueError('INVALID_PAIR_MAPS')
    quality = r.get('field_quality', {})
    if not isinstance(quality, dict):raise ValueError('INVALID_FIELD_QUALITY_MAP')
    fields=set(sum(cond.DEPS.values(),[]))
    return {'features':{k:copy.deepcopy(v) for k,v in fs.items() if k in fields},
            'field_status':{k:copy.deepcopy(v) for k,v in st.items() if k in fields},
            'field_quality':{k:quality.get(k,source._quality(k,v,st.get(k)) if derive_quality else None) for k,v in fs.items() if k in fields},'errors':[]}

def capture_times(app,browser,ar,br):
    a=app.get('canonical_received_payload',{});b=browser.get('canonical_received_payload',{})
    at,bt=a.get('timestamp'),b.get('timestamp')
    numeric=lambda x:type(x) in (int,float)
    return {'app':time_source._time_evidence(a,app.get('session_id'),ar),
            'browser_payload_timestamp':bt,'browser_timestamp_source':br+'#canonical_received_payload.timestamp',
            'browser_collection_diagnostics':{k:v for k,v in b.get('collection_diagnostics',{}).items() if k in ('collection_started_at_ms','collection_finished_at_ms','collection_duration_ms')},
            'browser_minus_app_payload_seconds':bt-at if numeric(at) and numeric(bt) else None,
            'scope':'payload timestamps only; not atomic field read; never an App timezone date fallback'}

def bind_v16(raw,sid,reference):
    """New explicit v16 contract; original compiler and timezone cells unchanged."""
    p=object_at(raw,'canonical_received_payload');m=object_at(p,'collection_manifest')
    if (raw.get('raw_payload_archive_schema_version')!='expanded-raw-payload-v1' or
        raw.get('session_id')!=sid or p.get('session_id')!=sid or not sid or
        m.get('collector_version_code')!=16 or type(m.get('collector_version_code')) is not int or
        m.get('collector_version_name')!='1.6.9-expanded-v2.2-geometry' or
        m.get('web_probe_revision')!='expanded-web-67-v2' or
        m.get('collection_protocol_version')!='featureapp-collection-protocol-v3'):
        raise ValueError('V16_CURRENT_APP_CONTRACT_MISMATCH')
    errors=source._field_sessions(p,sid)
    if errors:raise ValueError(';'.join(errors))
    full=adapt_payload(p)
    bound=source._result({'app_session_id':sid,'session_id':sid,'collector_version_code':16,
        'collector_version_name':m['collector_version_name'],'payload_id':raw.get('payload_sha256'),
        'adapter_version':'pilot-v16-current-app-v1','raw_reference':reference},
        full['features'],full['field_status'],full['field_quality'])
    bound=time_source._attach(bound,raw,reference)
    if bound['status']!='OK':raise ValueError(';'.join(bound['errors']))
    return bound

def compile_app(raw,sid,reference):
    bound=bind_v16(raw,sid,reference)
    c,contract=compiler()
    prepared=c.compile_record(raw['canonical_received_payload'],expected_session_id=sid,
        source_reference=reference,measurement_contract=contract)
    adapted=candidates.extend(base.adapt_controlled(prepared),bound)
    return adapted,bound

def load_models():
    frozen=read(MODEL/'MODELS_FROZEN.json')
    if frozen['status']!='FROZEN' or frozen['new_model_ids']!=IDS:raise ValueError('MODEL_FREEZE_MISMATCH')
    model_index=read(MODEL/'models.json')
    if isinstance(model_index,dict): model_index=model_index.get('models',model_index)
    models=[];manifest=[]
    for i,mid in enumerate(IDS,1):
        fold=f'WEBGL1-LOEO-v1-{i:02}'
        path=MODEL/f'trials/B_REL_TZ__{fold}__RETENTION/model.json';use(path)
        model=selection.load_model(path)
        if model.model_id!=mid or model.binding['fold_id']!=fold:raise ValueError('MODEL_ID_MISMATCH')
        if model.fit['relation_parameters']!=frozen['parameters'] or candidates.parameters()!=frozen['parameters']:raise ValueError('FROZEN_RELATION_PARAMETERS_MISMATCH')
        if not any(r['model_id']==mid and r['stage']=='RETENTION' and r['scheme']=='B_REL_TZ' for r in model_index):raise ValueError('MODEL_INDEX_MISMATCH')
        models.append(model);manifest.append({'model_id':mid,'fold':fold,'stage':'RETENTION','path':ref(path),'sha256':digest(path),'atoms':[a.atom_id for a in model.atoms]})
    return models,manifest

def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def object_at(value, key):
    result = value.get(key) if isinstance(value, dict) else None
    require(isinstance(result, dict), 'INVALID_OBJECT:' + key)
    return result


def positive_line(value):
    return type(value) is int and value > 0


def raw_web(raw, side):
    payload = object_at(raw, 'canonical_received_payload')
    web = object_at(payload, 'web_data')
    statuses = (object_at(payload, 'collection_status').get('fields') if side == 'app'
                else payload.get('field_statuses'))
    require(isinstance(statuses, dict), 'INVALID_RAW_WEB_STATUSES:' + side)
    return (source._flatten(web, side + '.web_data'),
            {side + '.' + k: v for k, v in statuses.items() if isinstance(k, str)})


def check_web_projection(pair, raw, side):
    values, statuses = raw_web(raw, side)
    for field in set(sum(cond.DEPS.values(), [])):
        if not field.startswith(side + '.'):
            continue
        # A missing projected field remains U, rather than borrowing raw values.
        if field in pair['features']:
            require(field in values and type(values[field]) is type(pair['features'][field])
                    and values[field] == pair['features'][field], 'RAW_VALUE_MISMATCH:' + field)
        if field in pair['field_status']:
            require(pair['field_status'][field] == statuses.get(field), 'RAW_STATUS_MISMATCH:' + field)


def check_browser(raw, *, sid, pair_id, app_sid, revision, batch):
    payload = object_at(raw, 'canonical_received_payload')
    require(raw.get('raw_browser_payload_schema_version') == 'browser-raw-payload-v1'
            and payload.get('schema_version') == 'browser-web-v1-status'
            and payload.get('collector_app') == 'browserprobe', 'BROWSER_SCHEMA_MISMATCH')
    require(raw.get('browser_session_id') == payload.get('browser_session_id') == sid
            and raw.get('pair_id') == payload.get('pair_id') == pair_id
            and raw.get('app_session_id') == app_sid
            and raw.get('collection_batch_id') == batch
            and payload.get('web_probe_revision') == revision, 'BROWSER_BINDING_MISMATCH')


def complete_pair(pair, app_errors, browser_errors, common_errors):
    pair['errors'] = [*common_errors, *app_errors, *browser_errors]
    # A Browser-only relation needs its own binding, not App operand availability.
    pair['browser_errors'] = [*common_errors, *browser_errors]
    return pair


def pilot():
    stages = rows(B1 / 'local_acceptance/stage_inventory.jsonl')
    ix = rows(B1 / 'local_acceptance/paired244_snapshot/sample_index.jsonl')
    paired = rows(B1 / 'local_acceptance/paired244_snapshot/paired_244.jsonl')
    captures_path = B1 / 'evidence_archive/pilot_r8/captures.jsonl'
    captures = rows(captures_path)
    ap = B1 / 'evidence_archive/data/raw_expanded_payloads.jsonl'
    bp = B1 / 'evidence_archive/data/raw_browser_payloads.jsonl'
    apps, browsers = rows(ap), rows(bp)
    verification_path = B1 / 'evidence_archive/verification.json'
    v = read(verification_path)
    require(v['verification'] == 'passed' and v['verified_stages'] == 18, 'B1_VERIFICATION_REQUIRED')
    pub = read(B1 / 'PUBLICATION.json')
    expected = {r['stored_path']: r['sha256'] for r in pub['archive_files']}
    archive_errors = {}
    for path in (ap, bp, captures_path, verification_path):
        try:
            require(digest(path) == expected[str(path.relative_to(B1 / 'evidence_archive'))],
                    'B1_USED_MEMBER_DIGEST_MISMATCH:' + ref(path))
        except (OSError, ValueError) as exc:
            archive_errors[path] = str(exc)
    out = []
    counts = Counter(r.get('sample_id') for _, r, _ in stages if r)
    for n, stage, error in stages:
        sid = stage.get('sample_id') if stage else f'bad-pilot-line-{n}'
        meta = {'sample_id': sid, 'cohort': 'pilot',
                'group': 'normal' if stage and stage.get('stage') in ('clean_pre', 'clean_post')
                         else stage.get('configuration_id', 'FAILED') if stage else 'FAILED',
                'stage': stage.get('stage') if stage else None,
                'configuration': stage.get('configuration_id') if stage else None,
                'repeat': stage.get('repeat') if stage else None,
                'evaluation_basis': ref(B1 / 'local_acceptance/stage_inventory.jsonl', n),
                'label_scope': 'independent B1 verified stage; original labels unchanged'}
        pair = {'features': {}, 'field_status': {}, 'field_quality': {}}
        item = {'meta': meta, 'raw': None, 'app_session': None}
        common, app_errors, browser_errors = [], [], []
        index = capture = app = browser = None
        try:
            require(not error and stage and counts[sid] == 1, 'INVALID_STAGE_ID')
            require(stage.get('stage') in ('clean_pre', 'attack_active', 'clean_post')
                    and stage.get('pair_binding_checked') is True and stage.get('result') == 'completed',
                    'INVALID_STAGE_BINDING')
            require(captures_path not in archive_errors and verification_path not in archive_errors,
                    'B1_STAGE_EVIDENCE_UNAVAILABLE')
            _, index, _ = unique(ix, 'sample_id', sid)
            cn, capture, _ = unique(captures, 'capture_id', stage['capture_id'])
            for key in ('stage', 'configuration_id', 'repeat', 'runtime_context', 'collection_round'):
                require(capture.get(key) == stage.get(key), 'CAPTURE_STAGE_MISMATCH:' + key)
            require(capture.get('result') == 'completed' and capture.get('pair_completed') is True,
                    'CAPTURE_NOT_COMPLETED')
            binding = object_at(capture, 'binding')
            for key in ('app_session_id', 'app_payload_sha256', 'app_receipt_id', 'collection_batch_id'):
                require(binding.get(key) == index.get(key) and bool(index.get(key)), 'CAPTURE_INDEX_MISMATCH:' + key)
            for key in ('browser_session_id', 'browser_payload_sha256', 'browser_receipt_id'):
                if binding.get(key) != index.get(key) or not index.get(key):
                    browser_errors.append('CAPTURE_INDEX_MISMATCH:' + key)
            if binding.get('pair_id') != index.get('browser_pair_id'):
                browser_errors.append('CAPTURE_PAIR_MISMATCH')
            meta['capture_reference'] = ref(captures_path, cn)
        except (ValueError, KeyError, TypeError) as exc:
            common.append(str(exc))
        # Binding App precedes and is independent of Browser loading/validation.
        if index and not common:
            try:
                require(ap not in archive_errors, archive_errors.get(ap, 'APP_ARCHIVE_FAILED'))
                an, app, _ = unique(apps, 'session_id', index['app_session_id'])
                require(app['payload_sha256'] == index['app_payload_sha256']
                        and app['receipt_id'] == index['app_receipt_id']
                        and app['collection_batch_id'] == index['collection_batch_id'], 'PILOT_APP_REFERENCE_MISMATCH')
                require(an == capture['archives']['app']['line'], 'CAPTURE_APP_LINE_MISMATCH')
                ar = ref(ap, an)
                bind_v16(app, index['app_session_id'], ar)
                item.update(raw=app, app_session=index['app_session_id'])
                meta['app_reference'] = ar
            except (ValueError, KeyError, TypeError) as exc:
                app_errors.append(str(exc))
            try:
                require(bp not in archive_errors, archive_errors.get(bp, 'BROWSER_ARCHIVE_FAILED'))
                bn, browser, _ = unique(browsers, 'browser_session_id', index['browser_session_id'])
                check_browser(browser, sid=index['browser_session_id'], pair_id=index['browser_pair_id'],
                              app_sid=index['app_session_id'], revision='expanded-web-67-v2', batch=index['collection_batch_id'])
                require(browser['browser_payload_sha256'] == index['browser_payload_sha256']
                        and browser['browser_receipt_id'] == index['browser_receipt_id']
                        and browser['app_receipt_id'] == index['app_receipt_id'], 'PILOT_BROWSER_REFERENCE_MISMATCH')
                require(bn == capture['archives']['browser']['line'], 'CAPTURE_BROWSER_LINE_MISMATCH')
                meta['browser_reference'] = ref(bp, bn)
            except (ValueError, KeyError, TypeError) as exc:
                browser_errors.append(str(exc))
            try:
                pn, observation, _ = unique(paired, 'sample_id', sid)
                pair = projection(observation, derive_quality=True)
                meta['pair_reference'] = ref(B1 / 'local_acceptance/paired244_snapshot/paired_244.jsonl', pn)
            except (ValueError, KeyError, TypeError) as exc:
                common.append(str(exc))
            for side, raw, errors in [('app', app, app_errors), ('browser', browser, browser_errors)]:
                if raw and not errors:
                    try:
                        check_web_projection(pair, raw, side)
                    except (ValueError, KeyError, TypeError) as exc:
                        errors.append(str(exc))
            if app and browser and not app_errors and not browser_errors:
                pair['times'] = capture_times(app, browser, meta['app_reference'], meta['browser_reference'])
        item['pair'] = complete_pair(pair, app_errors, browser_errors, common)
        item['app_errors'] = app_errors + common if item['raw'] is None else []
        out.append(item)
    require(len(out) == 18, 'EXPECTED_18_PLANNED_PILOT_POSITIONS')
    return out


def mtc_members():
    registry = rows(P2 / 'sample_registry.jsonl')
    require(not any(e for _, _, e in registry), 'UNREADABLE_REGISTRY_MEMBERSHIP_NOT_INFERRED')
    members = [(n, r) for n, r, _ in registry if r.get('analysis_role') == 'primary_representative'
               and r.get('source_view') == 'paired_244']
    require(Counter(r.get('split') for _, r in members) == Counter({'discovery': 630, 'development': 144,
            'reserved_validation': 117}), 'P2_MEMBERSHIP_COUNTS_CHANGED')
    return members


def mtc(members):
    pp = MTC / 'paired_244.jsonl'
    decoded = {n: (r, e) for n, r, e in rows(pp, {r.get('source_line') for _, r in members if positive_line(r.get('source_line'))})}
    apps = {n: (r, e) for n, r, e in rows(RAW / 'raw_expanded_payloads.jsonl',
            {r.get('app_raw_line') for _, r in members if positive_line(r.get('app_raw_line'))})}
    blines = {r['source_refs']['browser_raw_line'] for r, e in decoded.values() if r and not e
              and isinstance(r.get('source_refs'), dict) and positive_line(r['source_refs'].get('browser_raw_line'))}
    browsers = {n: (r, e) for n, r, e in rows(RAW / 'raw_browser_payloads.jsonl', blines)}
    batches = rows(RAW / 'collection_batches.jsonl')
    closed = {r['collection_batch_id'] for _, r, e in batches if r and r.get('lifecycle_status') == 'closed_cleanly'}
    docs = all((ROOT / p).is_file() for p in historical.TASK_REFS)
    for path in historical.TASK_REFS:
        if (ROOT / path).is_file(): use(ROOT / path)
    ids = Counter(r.get('sample_id') for _, r in members)
    refs = Counter(r.get('source_line') for _, r in members)
    out = []
    for line, m in members:
        sid = m.get('sample_id', f'bad-mtc-line-{line}')
        meta = {'sample_id': sid, 'cohort': 'mtc', 'group': m.get('split'),
                'evaluation_basis': ref(P2 / 'sample_registry.jsonl', line),
                'original_label_status': m.get('label_status'), 'pair_reference': ref(pp, m.get('source_line'))}
        pair = {'features': {}, 'field_status': {}, 'field_quality': {}}
        common, app_errors, browser_errors = [], [], []
        app = browser = None
        try:
            require(ids[sid] == 1 and refs[m.get('source_line')] == 1, 'DUPLICATE_P2_ID_OR_REFERENCE')
            require(positive_line(m.get('source_line')) and positive_line(m.get('app_raw_line')), 'INVALID_P2_REFERENCE')
            r, error = decoded.get(m['source_line'], (None, 'MISSING_PAIR'))
            require(not error and r, error or 'MISSING_PAIR')
            require(r.get('sample_id') == sid and r.get('dataset_view') == 'paired_244'
                    and r.get('record_schema_version') == 'hybridguard-mtc-observation-v2', 'P2_P1_IDENTITY_MISMATCH')
            refs_row = object_at(r, 'source_refs')
            require(refs_row.get('app_raw_line') == m['app_raw_line'], 'P2_P1_RAW_REFERENCE_MISMATCH')
            require(object_at(r, 'pair').get('pair_status') == 'completed', 'MTC_PAIR_NOT_COMPLETED')
            require(object_at(r, 'qc').get('status') == 'passed', 'MTC_PAIR_QC_NOT_PASSED')
            pair = projection(r)
            require(isinstance(r.get('field_quality'), dict), 'MTC_FIELD_QUALITY_REQUIRED')
        except (ValueError, KeyError, TypeError) as exc:
            common.append(str(exc))
        if not common:
            try:
                app, error = apps.get(m['app_raw_line'], (None, 'MISSING_APP'))
                require(not error and app, error or 'MISSING_APP')
                app_side = object_at(r, 'app');payload = object_at(app, 'canonical_received_payload')
                require(app['payload_sha256'] == m['app_payload_sha256'] == app_side.get('payload_sha256')
                        and app['session_id'] == m['app_session_id'] == app_side.get('session_id') == payload.get('session_id'),
                        'MTC_APP_BINDING_MISMATCH')
                manifest = object_at(payload, 'collection_manifest')
                require(app.get('raw_payload_archive_schema_version') == 'expanded-raw-payload-v1'
                        and payload.get('schema_version') == 'expanded-v2.2-status'
                        and payload.get('collector_app') == 'featureapp'
                        and type(manifest.get('collector_version_code')) is int
                        and manifest.get('collector_version_code') in (9, 11)
                        and manifest.get('collector_version_code') == app_side.get('collector_version_code'), 'MTC_APP_CONTRACT_MISMATCH')
                require(app.get('collection_batch_id') == r.get('collection_batch_id'), 'MTC_APP_BATCH_MISMATCH')
                check_web_projection(pair, app, 'app')
                meta['app_reference'] = ref(RAW / 'raw_expanded_payloads.jsonl', m['app_raw_line'])
                meta['normal_basis'] = historical._normal_basis(r, historical._raw_metadata(app), closed, docs,
                                                [meta['app_reference'], *historical.TASK_REFS])
            except (ValueError, KeyError, TypeError) as exc:
                app_errors.append(str(exc))
            try:
                bn = refs_row.get('browser_raw_line')
                require(positive_line(bn), 'INVALID_BROWSER_RAW_REFERENCE')
                browser, error = browsers.get(bn, (None, 'MISSING_BROWSER'))
                require(not error and browser, error or 'MISSING_BROWSER')
                side = object_at(r, 'browser')
                check_browser(browser, sid=side.get('session_id'), pair_id=r['pair'].get('browser_pair_id'),
                              app_sid=m['app_session_id'], revision='expanded-web-67-v1', batch=r.get('collection_batch_id'))
                require(browser['browser_payload_sha256'] == m['browser_payload_sha256'] == side.get('payload_sha256')
                        and browser['browser_receipt_id'] == side.get('receipt_id'), 'MTC_BROWSER_REFERENCE_MISMATCH')
                check_web_projection(pair, browser, 'browser')
                meta['browser_reference'] = ref(RAW / 'raw_browser_payloads.jsonl', bn)
            except (ValueError, KeyError, TypeError) as exc:
                browser_errors.append(str(exc))
            if app and browser and not app_errors and not browser_errors:
                pair['times'] = capture_times(app, browser, meta['app_reference'], meta['browser_reference'])
        # Keep the established evidence serialization order for unchanged records.
        if 'normal_basis' in meta:
            meta['normal_basis'] = meta.pop('normal_basis')
        out.append({'meta': meta, 'pair': complete_pair(pair, app_errors, browser_errors, common)})
    return out

def predict_item(item,model):
    meta=item['meta']
    try:
        if item['raw'] is None:raise ValueError(';'.join(item.get('app_errors',[])) or 'CURRENT_APP_RAW_MISSING')
        adapted,bound=compile_app(item['raw'],item['app_session'],meta['app_reference'])
        result=selection.predict_current(model,meta['sample_id'],adapted['raw'])
        evidence=[]
        for a in model.atoms:
            fields=a.provenance.get('field_refs') or [a.provenance.get('field')]
            fields=[f for f in fields if f]
            evidence.append({'atom_id':a.atom_id,'raw_operands':[{'field':f,'value':bound['features'].get(f),'present':f in bound['features'],'status':bound['field_status'].get(f),'quality':bound['field_quality'].get(f)} for f in fields],
                'relation_diagnostics':adapted['candidate_inputs'].get(a.atom_id,{}).get('diagnostics')})
        result.update(selected_rule_inputs=evidence,acquisition_time=bound['acquisition_time'])
    except (ValueError,KeyError,TypeError,PermissionError) as exc:
        result={'model_id':model.model_id,'decision':'FAILED','logical_state':None,'failure_reason':str(exc)}
    return dict(meta=meta,prediction=result)

def run(output):
    USED.clear(); READ_ERRORS.clear()
    if output.exists():raise FileExistsError('NEW_OUTPUT_DIRECTORY_REQUIRED')
    output.mkdir(parents=True)
    definitions=read(HERE/'CANDIDATES_FROZEN.json')
    if definitions['mode']!=MODE:raise ValueError('DIAGNOSTIC_MODE_REQUIRED')
    models,model_manifest=load_models();members=mtc_members()
    write(output/'MODEL_MANIFEST.json',model_manifest)
    jsonl(output/'MTC_MEMBERS.jsonl',[dict(registry_line=n,**r) for n,r in members])
    ps=pilot();jsonl(output/'PILOT_EVALUATION_SIDECAR.jsonl',[x['meta'] for x in ps])
    predictions=[predict_item(x,m) for m in models for x in ps]
    jsonl(output/'app_predictions.jsonl',predictions)
    pairs=ps+mtc(members)
    results=[dict(meta=x['meta'],**cond.evaluate(cid,x['pair'])) for x in pairs for cid in cond.DEPS]
    jsonl(output/'condition_results.jsonl',results)
    jsonl(output/'failures.jsonl',[{'sample_id':x['meta']['sample_id'],'errors':x['pair']['errors']} for x in pairs if x['pair']['errors']]+[{'sample_id':x['meta']['sample_id'],'model_id':x['prediction']['model_id'],'error':x['prediction'].get('failure_reason')} for x in predictions if x['prediction']['decision']=='FAILED'])
    # Exact metadata dependencies used by the original pure compiler/adapter.
    frozen=ROOT/'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R04_freeze_r1'
    contract=frozen/'snapshot/hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol'
    for path in [frozen/'data/definitions.json',contract/'CANDIDATE_LEDGER.jsonl',contract/'SINGLE_SURFACE_FIELDS.json',ROOT/'hybridguard_agent/config/paired244_rule_catalog.v3.json',ROOT/'deliverables/webgl1_fresh_comparison_v1/prepared/DEFINITIONS.json',ROOT/'hybridguard_agent/config/latest_experiment_protocol.v1.json']:
        use(path)
    # Only loaded source modules and metadata contracts, not an exhaustive repo scan.
    for module in list(sys.modules.values()):
        p=getattr(module,'__file__',None)
        if p and Path(p).suffix=='.py' and Path(p).resolve().is_relative_to(ROOT):use(Path(p))
    for p in [ROOT/'web_probe/canonical_web_probe.js',HERE/'SOURCES.md',B1/'local_acceptance/experiment_plan/experiment_readiness.json',ROOT/'RBA_SUPERVISOR_REPORT.md',ROOT/'RBA_PRE_PAPER_EXPERIMENT_PLAN.md']:
        use(p)
    for path,sha in USED.items():
        if digest(ROOT/path)!=sha:raise ValueError('USED_INPUT_CHANGED:'+path)
    write(output/'RUN_MANIFEST.json',{'mode':MODE,'fit_calls':0,'new_collection_calls':0,'app_prediction_calls':len(predictions),'condition_calls':len(results),'planned_pairs':len(pairs),'original_formal_permissions_unchanged':True,'input_and_loaded_dependency_sha256':USED,'source_read_errors':READ_ERRORS,'normal_basis_counts':dict(Counter(x['meta'].get('normal_basis',{}).get('status','missing') for x in pairs if x['meta']['cohort']=='mtc'))})
    summarize(output)

def validate_saved_positions(output, predictions, results):
    """Validate the saved Cartesian products, not just aggregate row counts."""
    def saved(name):
        values = rows(output / name)
        require(not any(error or row is None for _, row, error in values), 'UNREADABLE_MEMBERS:' + name)
        return [row for _, row, _ in values]
    pilot_members = saved('PILOT_EVALUATION_SIDECAR.jsonl')
    mtc_members_saved = saved('MTC_MEMBERS.jsonl')
    model_manifest = read(output / 'MODEL_MANIFEST.json')
    require([r['model_id'] for r in model_manifest] == IDS, 'SAVED_MODEL_MEMBERS_CHANGED')
    require(len(pilot_members) == 18 and Counter(m['group'] for m in pilot_members)
            == Counter(normal=12, language_fr=3, timezone_tokyo=3), 'SAVED_PILOT_MEMBERS_CHANGED')
    require(len(mtc_members_saved) == 891 and Counter(m['split'] for m in mtc_members_saved)
            == Counter(discovery=630, development=144, reserved_validation=117), 'SAVED_MTC_MEMBERS_CHANGED')
    expected = {}
    def register(meta):
        key = (meta['cohort'], meta['evaluation_basis'])
        require(key not in expected, 'DUPLICATE_PLANNED_POSITION')
        expected[key] = meta
    for meta in pilot_members:
        register(meta)
    for member in mtc_members_saved:
        require(member.get('analysis_role') == 'primary_representative'
                and member.get('source_view') == 'paired_244', 'UNREGISTERED_MTC_ROLE')
        register({'sample_id': member.get('sample_id', f"bad-mtc-line-{member['registry_line']}"),
                  'cohort': 'mtc', 'group': member['split'],
                  'evaluation_basis': ref(P2 / 'sample_registry.jsonl', member['registry_line'])})
    def position(row):
        meta = row['meta']; key = (meta['cohort'], meta['evaluation_basis'])
        require(key in expected, 'UNPLANNED_OUTPUT_POSITION')
        for name in ('sample_id', 'cohort', 'group'):
            require(meta.get(name) == expected[key].get(name), 'OUTPUT_SIDECAR_MISMATCH:' + name)
        if meta['cohort'] == 'pilot':
            for name in ('stage', 'configuration', 'repeat'):
                require(meta.get(name) == expected[key].get(name), 'OUTPUT_PHASE_MISMATCH:' + name)
        return key
    actual_app = []
    for row in predictions:
        key = position(row)
        require(key[0] == 'pilot', 'APP_OUTPUT_OUTSIDE_PILOT')
        require(row['prediction']['decision'] in ('MANIPULATION_ALERT', 'NO_ALERT', 'INSUFFICIENT_EVIDENCE', 'FAILED'),
                'INVALID_SAVED_MODEL_STATE')
        actual_app.append((key, row['prediction']['model_id']))
    actual_conditions = []
    for row in results:
        require(row['state'] in ('T', 'F', 'U', 'FAILED'), 'INVALID_SAVED_CONDITION_STATE')
        actual_conditions.append((position(row), row['condition_id']))
    require(Counter(actual_app) == Counter((key, mid) for key in expected if key[0] == 'pilot' for mid in IDS),
            'APP_POSITION_PRODUCT_MISMATCH')
    require(Counter(actual_conditions) == Counter((key, cid) for key in expected for cid in cond.DEPS),
            'CONDITION_POSITION_PRODUCT_MISMATCH')


def summarize(output):
    saved_a=rows(output/'app_predictions.jsonl');saved_c=rows(output/'condition_results.jsonl')
    if any(e or r is None for _,r,e in saved_a+saved_c):raise ValueError('UNREADABLE_SAVED_OUTPUT')
    predictions=[r for _,r,e in saved_a];results=[r for _,r,e in saved_c]
    if len(predictions)!=54 or len(results)!=4545:raise ValueError('SAVED_OUTPUT_DENOMINATORS_CHANGED')
    validate_saved_positions(output, predictions, results)
    tables=[]
    for kind,records,key,st in [('model',predictions,lambda x:x['prediction']['model_id'],lambda x: {'MANIPULATION_ALERT':'T','NO_ALERT':'F','INSUFFICIENT_EVIDENCE':'U'}.get(x['prediction']['decision'],'FAILED')),('condition',results,lambda x:x['condition_id'],lambda x:x['state'])]:
        groups=defaultdict(Counter)
        for r in records:groups[(key(r),r['meta']['cohort'],r['meta']['group'])][st(r)]+=1
        for (name,cohort,group),c in sorted(groups.items()):
            n=sum(c.values());ev=c['T']+c['F'];tables.append(dict(kind=kind,id=name,cohort=cohort,group=group,n=n,**{s:c[s] for s in ('T','F','U','FAILED')},evaluable_fraction=f'{ev}/{n}',deviation_per_planned=f'{c["T"]}/{n}',deviation_per_evaluable=f'{c["T"]}/{ev}'))
    write(output/'SUMMARY.json',tables)
    with (output/'SUMMARY.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(tables[0]));w.writeheader();w.writerows(tables)
    trajectories=defaultdict(dict)
    for r in predictions:
        m=r['meta'];trajectories[(r['prediction']['model_id'],m['configuration'],m['repeat'])][m['stage']]={'sample_id':m['sample_id'],'decision':r['prediction']['decision'],'triggered_clauses':[c['clause_id'] for c in r['prediction'].get('clause_explanations',[]) if c['state']=='T']}
    write(output/'TRAJECTORIES.json',[{'model_id':k[0],'configuration':k[1],'repeat':k[2],'stages':v} for k,v in sorted(trajectories.items())])
    bypair=defaultdict(dict)
    for r in results:bypair[(r['meta']['sample_id'],r['meta']['evaluation_basis'])][r['condition_id']]=r
    examples=defaultdict(list)
    for (sid,position),rs in sorted(bypair.items()):
        m=rs['C1']['meta'];cats=[]
        if m['group']=='normal' and rs['D1']['state']=='T' and rs['C2']['state']=='F':cats.append('normal_list_diff_preferred_same')
        if m['cohort']=='pilot' and m['group'] in ('language_fr','timezone_tokyo'):cats.append('browser_intervention')
        if m['cohort']=='mtc' and any(rs[c]['state']=='T' for c in ('C1','C2','C3')):cats.append('mtc_normal_deviation')
        if any(x['state'] in ('U','FAILED') for x in rs.values()):cats.append('insufficient_input_or_semantics')
        for c in cats:
            if len(examples[c])<3:examples[c].append({'sample_id':sid,'rows':list(rs.values())})
    for r in sorted(predictions,key=lambda r:(r['meta']['sample_id'],r['prediction']['model_id'])):
        if r['meta']['group']=='normal' and r['prediction']['decision']=='MANIPULATION_ALERT' and len(examples['app_normal_alert'])<3:examples['app_normal_alert'].append(r)
    write(output/'EXAMPLES.json',dict(examples))
    overlap=[]
    for model in IDS:
        for cid in ('C1','C2','C3'):
            c=Counter()
            for r in predictions:
                if r['prediction']['model_id']==model and bypair[(r['meta']['sample_id'],r['meta']['evaluation_basis'])][cid]['state']=='T':c[r['prediction']['decision']]+=1
            overlap.append({'model_id':model,'condition':cid,'candidate_T_model_decisions':dict(c)})
    write(output/'OVERLAP.json',overlap)
    print(json.dumps({'models':len(predictions),'conditions':len(results),'summary':str(output/'SUMMARY.json')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['run','summarize']);parser.add_argument('--output',type=Path,default=HERE/'results');args=parser.parse_args()
    if args.command=='run':run(args.output)
    else:summarize(args.output)
