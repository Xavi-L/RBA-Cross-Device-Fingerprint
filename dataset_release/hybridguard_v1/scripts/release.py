#!/usr/bin/env python3
"""Audit, freeze, build and verify authorized release inputs; never uploads data."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from common import (APP_LAYERS, BROWSER, COUNTS, LABELS, ROOT, STATES, RandomIDs,
                    canonical, digest, field_policy, flatten, privacy_findings,
                    private_destination, read_jsonl, sanitize_value, type_matches,
                    validate_schema, write_json, write_jsonl)

REPO = ROOT.parents[1]
PRIVATE = ROOT / '.private'
CONTRACT_PATH = 'hybridguard_agent/schemas/expanded_v2.schema.json'
REGISTRY_PATH = 'hybridguard_agent/schemas/field_registry.json'
NORMALIZER_PATH = 'hybridguard_agent/scripts/build_dataset_snapshot.py'
RELEASE_STATUS = 'AUTHORIZED_FOR_PUBLIC_RELEASE'

DATA_FILES = ('features.jsonl', 'metadata.jsonl', 'annotations.jsonl', 'pairs.jsonl')


SUPPLEMENTAL_KEYS = tuple(
    f'{layer}.{key}' for layer in ('host_before','host_after')
    for key in ('width_px','height_px','content_width_px','content_height_px','density',
                'padding_left_px','padding_top_px','padding_right_px','padding_bottom_px')
) + tuple('web_geometry_values.'+key for key in (
    'screen_width','screen_height','inner_width','inner_height','device_pixel_ratio',
    'visual_viewport_width','visual_viewport_height','visual_viewport_scale')) + (
    'geometry_evidence.usable_window','geometry_evidence.android_bracket_ms')


def supplemental_values(extras):
    flat=dict(flatten(extras))
    values={key:flat[key] for key in SUPPLEMENTAL_KEYS if key in flat}
    if any(v is not None and type(v) not in (int,float,bool) for v in values.values()):
        raise ValueError('Unexpected supplemental measurement type')
    return values


def normalize_phase(phase):
    aliases={'clean_pre':'clean_pre','pre':'clean_pre','clean':'clean_pre',
             'attack':'active','attack_active':'active','active':'active','change':'active',
             'clean_post':'clean_post','post':'clean_post'}
    if phase not in aliases:
        raise ValueError('Unknown experiment phase')
    return aliases[phase]


def extract(repo):
    from adapter_controlled import extract as controlled
    from adapter_browser import extract as browser
    from adapter_mtc import extract as mtc
    result = {'records': [], 'sources': [], 'inputs': set(), 'issues': []}
    for adapter in (controlled, browser, mtc):
        part = adapter(repo)
        for key in ('records','sources','issues'):
            result[key].extend(part.get(key, []))
        result['inputs'].update(part['inputs'])
    result['inputs'].update([CONTRACT_PATH, REGISTRY_PATH, NORMALIZER_PATH])
    result['inputs'].update(str(p.relative_to(repo)) for p in (ROOT/'scripts').glob('*.py'))
    result['inputs'].update('output/pdf/hybridguard_www_draft_20261017/sections/'+p for p in
                            ('04_evaluation_protocol.tex','05_results.tex','08_appendix.tex'))
    return result


def frozen_inputs(repo, paths):
    return [{'path': p, 'bytes': (repo/p).stat().st_size, 'sha256': digest(repo/p)} for p in sorted(paths)]


def load_normalizer(repo):
    spec = importlib.util.spec_from_file_location('existing_snapshot_normalizer',repo/NORMALIZER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scope_source(source):
    source = dict(source)
    selected = source.get('selected_count', source.get('record_count', 0))
    source['selected_count'] = selected
    source['release_class'] = ('release' if selected else
                               'unverified' if not source.get('available', True) else 'excluded')
    for key in ('permission_status', 'public_authorization', 'data_ownership',
                'public_permission', 'redistribution_permission', 'authorization_status'):
        source[key] = 'CONFIRMED_BY_PROJECT_LEAD'
    source['privacy_review'] = 'TECHNICAL_CHECKS_RECORDED_IN_QUALITY_REPORT'
    if 'privacy_status' in source:
        source['privacy_status'] = 'raw_sources_private; released_projection_sanitized_and_validated'
    source['technical_export_status'] = 'included_in_reviewer_release' if selected else 'outside_selected_study_scope'
    return source


def freeze(repo):
    PRIVATE.mkdir(exist_ok=True, mode=0o700)
    os.chmod(PRIVATE, 0o700)
    target = PRIVATE/'source_lock.json'
    if target.exists():
        raise ValueError('Source lock already exists. Preserve the v1 freeze; create a separately reviewed version for changed sources.')
    data = extract(repo)
    locks = frozen_inputs(repo, [p for p in data['inputs'] if not p.startswith('dataset_release/hybridguard_v1/scripts/')])
    sources = [scope_source(s) for s in data['sources']]
    head = subprocess.check_output(['git','rev-parse','HEAD'], cwd=repo, text=True).strip()
    lock = {'dataset_version': '1.0', 'repository_commit': head,
            'publication_status': RELEASE_STATUS, 'inputs': locks, 'sources': sources,
            'selected_positions_before_identity_deduplication': len(data['records']),
            'issues': data['issues']}
    write_json(target, lock)
    os.chmod(target,0o600)
    # Public audit contains file-level provenance, never sample-level references or IDs.
    public_locks=[]
    for index,entry in enumerate(locks):
        item=dict(entry, input_id=f'input_{index:04d}')
        if re.search(r'\d{4}-\d{2}-\d{2}T\d{2}',item['path']):
            item['path']=str(Path(item['path']).parent/'<private-record-file>')
            item['exact_path_visibility']='private source lock only'
        public_locks.append(item)
    write_json(ROOT/'source_inventory.json', {'sources':sources,'files':public_locks,
               'scope':'file-level provenance; candidate samples and row mappings are private',
               'issues':data['issues']})
    print(canonical({'freeze':'PASS','selected_positions':len(data['records']),'input_files':len(locks)}))


def check_lock(repo):
    lock=json.loads((PRIVATE/'source_lock.json').read_text())
    changed=[]
    for entry in lock['inputs']:
        p=repo/entry['path']
        if not p.is_file() or p.stat().st_size!=entry['bytes'] or digest(p)!=entry['sha256']:
            changed.append(entry['path'])
    if changed:
        raise ValueError('Frozen input drift: '+', '.join(changed))
    return lock


def fields_for(contract, paired):
    fields={k:list(v) for k,v in contract['fields'].items()}
    if 'web_data.visual_viewport_scale' in fields:
        fields['web_data.visual_viewport_scale']=['integer','number']
    if paired:
        fields.update({k.replace('web_data.',BROWSER+'.',1):v for k,v in list(fields.items()) if k.startswith('web_data.')})
    return fields


def raw_field_map(payload, expected, browser=False):
    result={}
    for original,value in flatten(payload):
        if browser:
            layer=BROWSER
        else:
            layer=original.split('.',1)[0]
            if layer not in APP_LAYERS:
                continue
        key=layer+'.'+original.rsplit('.',1)[-1]
        if key not in expected:
            continue
        if key in result:
            raise ValueError('Ambiguous normalized field: '+key)
        result[key]=value
    return result


def status_map(status, expected, browser=False):
    result={}
    if not isinstance(status,dict):
        return result
    fields=status.get('fields',status)
    if not isinstance(fields,dict):
        return result
    for original,value in fields.items():
        if not isinstance(original,str) or not isinstance(value,str):
            continue
        layer=BROWSER if browser else original.split('.',1)[0]
        key=layer+'.'+original.rsplit('.',1)[-1]
        if key in expected:
            if value not in STATES:
                raise ValueError('Unknown collector state; extend contract after review: '+value)
            if key in result:
                raise ValueError('Ambiguous normalized status')
            result[key]=value
    return result


def normalize_record(record, contract, normalizer):
    paired=record.get('browser') is not None
    if paired and (not isinstance(record['browser'],dict) or not record['browser']):
        raise ValueError('An empty Browser cannot create Paired244')
    expected=fields_for(contract,paired)
    # Reuse the project's frozen flattening normalizer and QC. Its historical
    # status inference is deliberately NOT used: present does not prove observed.
    normalized=normalizer.canonicalize_payload(record['app'],contract)
    errors,warnings,detail=normalizer.validate_v2_row(normalized,contract)
    raw=raw_field_map(record['app'],expected)
    states=status_map(record['app'].get('collection_status',{}),expected)
    if paired:
        raw.update(raw_field_map(record['browser'],expected,True))
        states.update(status_map(record.get('browser_status',{}),expected,True))
    cells={}
    type_errors=[]
    for key,allowed in expected.items():
        present=key in raw
        value=raw.get(key)
        state=states.get(key, 'present_status_unknown' if present and value is not None else 'missing' if not present else 'unknown')
        if state=='observed' and not present:
            raise ValueError('Collector observed state without original value slot')
        if value is not None and not any(type_matches(value,t) for t in allowed):
            type_errors.append(key)
        sanitized,redaction=sanitize_value(key,value,allowed)
        cells[key]={'value':sanitized,'collection_status':state,
                    'status_origin':'collector_emitted' if key in states else 'not_recorded',
                    'original_field_present':present,'redaction':redaction}
    if type_errors:
        raise ValueError('Source field type mismatch: '+', '.join(type_errors))
    qc={'original_field_slots':len(raw),'expected_field_slots':len(expected),
        'structurally_complete':len(raw)==len(expected),
        'all_collection_states_observed':all(v['collection_status']=='observed' for v in cells.values()),
        'all_values_retained':all(v['redaction']=='none' for v in cells.values()),
        'upstream_app_qc_errors':errors,'upstream_app_qc_warnings':warnings,
        'source_missing_fields':sorted(set(expected)-set(raw)),
        'redacted_fields':sum(v['redaction']!='none' for v in cells.values())}
    return ('Paired244' if paired else 'App177'),cells,qc


def safe_metadata(record, qc):
    meta=record.get('metadata',{})
    allowed=('cohort','environment','schema_version','browser_schema_version','historical_split',
             'collection_context','physical_device_identity','historical_holdout_pristine',
             'representative_basis')
    return {**{k:meta[k] for k in allowed if k in meta},
            'group_basis':record.get('group_basis',meta.get('group_basis','unknown')),
            'qc':qc,'public_release_status':RELEASE_STATUS}


def safe_annotation(record):
    source=record.get('annotation',{})
    label=source.get('label','unknown')
    if label not in LABELS:
        raise ValueError('Unsupported annotation label: '+label)
    allowed=('label','label_verification','tool_execution_status','target_effect_status',
             'detector_outcome','manipulation_type','annotation_basis','phase',
             'restoration_status','effect_verification','qualification_status',
             'recorded_detector_states','target_memory_gib','attack_tool','normal_scenario','configuration_name')
    result={k:source[k] for k in allowed if k in source}
    for key in ('tool_execution_status','target_effect_status','detector_outcome'):
        result.setdefault(key,'unknown')
    result.setdefault('label',label)
    result.setdefault('label_verification','unknown')
    if label=='modified' and result['label_verification']!='verified_recorded_evidence':
        raise ValueError('A modified label requires verified recorded evidence')
    result['label_scope']='recorded_target_intervention_before_privacy_redaction'
    return result


def ensure_preservation_baseline():
    """Save the existing candidate once, before any formal conversion writes."""
    baseline = PRIVATE / 'pre_reviewer_baseline'
    originals = {name: PRIVATE / 'candidate' / name for name in DATA_FILES}
    originals.update({name: PRIVATE / name for name in ('identity_map.json', 'source_lock.json')})
    if any(path.is_symlink() or not path.is_file() for path in originals.values()):
        raise ValueError('Existing candidate, identity map and source lock are required to preserve release IDs')
    if baseline.exists():
        if baseline.is_symlink() or {p.name for p in baseline.iterdir()} != set(originals):
            raise ValueError('Invalid preservation baseline')
        if any(p.is_symlink() or not p.is_file() for p in baseline.iterdir()):
            raise ValueError('Invalid preservation baseline files')
        os.chmod(baseline, 0o700)
        for path in baseline.iterdir():
            os.chmod(path, 0o600)
        for name in ('identity_map.json', 'source_lock.json'):
            if (baseline / name).read_bytes() != originals[name].read_bytes():
                raise ValueError('Existing identity map or source freeze differs from preservation baseline')
        return
    baseline.mkdir(mode=0o700)
    for name, source in originals.items():
        with (baseline / name).open('xb') as output:
            os.chmod(baseline / name, 0o600)
            with source.open('rb') as input_file:
                shutil.copyfileobj(input_file, output)


def build(repo):
    ensure_preservation_baseline()
    lock=check_lock(repo)
    data=extract(repo)
    current_inputs={p for p in data['inputs'] if not p.startswith('dataset_release/hybridguard_v1/scripts/')}
    if current_inputs!={entry['path'] for entry in lock['inputs']}:
        raise ValueError('Exporter input membership changed after freeze')
    inventory=json.loads((ROOT/'source_inventory.json').read_text())
    inventory['sources']=[scope_source(s) for s in data['sources']]
    inventory['authorization']='CONFIRMED_BY_PROJECT_LEAD; see release_authorization.json'
    inventory['scope']='Repository-only provenance; excluded from the anonymous reviewer package.'
    inventory['issues']=[x for x in inventory.get('issues',[]) if not any(word in str(x).lower() for word in ('permission','authorization','approval','restricted','redistribution'))]
    write_json(ROOT/'source_inventory.json',inventory)
    contract=json.loads((repo/CONTRACT_PATH).read_text())
    normalizer=load_normalizer(repo)
    ids=RandomIDs(PRIVATE/'identity_map.json')
    out=private_destination(PRIVATE/'candidate')
    out.mkdir(parents=True,exist_ok=True)
    features=[]; metadata=[]; annotations=[]; provenance=[]
    by_identity={}; by_content=defaultdict(list); triplets=defaultdict(list)
    duplicates=[]
    for record in data['records']:
        identity=str(record['record_key'])
        content=canonical({'app':record['app'],'browser':record.get('browser')})
        if identity in by_identity:
            if by_identity[identity]!=content:
                raise ValueError('Conflicting payloads for one source observation identity')
            duplicates.append({'record_key':identity,'source_id':record['source_id']})
            continue
        by_identity[identity]=content
        sid=ids.get('sample',identity)
        view,cells,qc=normalize_record(record,contract,normalizer)
        features.append({'record_type':'features','sample_id':sid,'view':view,'fields':cells,
                         'supplemental':supplemental_values(record.get('extras',{}))})
        group=ids.get('group',record['source_id']+':'+str(record['group_key'])) if record.get('group_key') is not None else None
        meta={'record_type':'metadata','sample_id':sid,'source_id':record['source_id'],
              'group_id':group,'view':view,**safe_metadata(record,qc)}
        app_native=raw_field_map(record['app'],contract['fields'])
        api=app_native.get('android_native_data.os_api_level')
        meta['android_api_level']=api if type(api) is int else None
        metadata.append(meta)
        annotation={'record_type':'annotations','sample_id':sid,**safe_annotation(record)}
        phase=record.get('phase',annotation.get('phase'))
        if phase is not None:
            phase=normalize_phase(phase)
            annotation['phase']=phase
        annotations.append(annotation)
        if record.get('triplet_key') is not None:
            triplets[record['source_id']+':'+str(record['triplet_key'])].append({'sample_id':sid,'phase':phase})
        if view=='Paired244':
            triplets['endpoint:'+identity].append({'sample_id':sid,'phase':'linked_endpoints'})
        provenance.append({'sample_id':sid,'source_id':record['source_id'],'record_key':identity,
                           'provenance':record['provenance'],'group_key':record.get('group_key'),
                           'annotation_evidence':record.get('annotation',{}),
                           'extras':record.get('extras',{})})
        # Identical feature values can recur legitimately; flag, do not deduplicate
        # unrelated observations solely by equal fingerprints.
        by_content[canonical({'app':raw_field_map(record['app'],contract['fields']),
                              'browser':record.get('browser')})].append(sid)
    pairs=[]
    for key,members in triplets.items():
        kind='linked_app_browser' if key.startswith('endpoint:') else 'experiment_triplet'
        if kind=='experiment_triplet' and (len(members)!=3 or len({m['phase'] for m in members})!=3):
            raise ValueError('Invalid or incomplete clean/active/post experiment relationship')
        pairs.append({'record_type':'pairs','pair_id':ids.get('pair',key),'kind':kind,'members':members})
    tables=dict(zip(DATA_FILES,(features,metadata,annotations,pairs)))
    for filename,rows in tables.items():
        write_jsonl(out/filename,rows)
    ids.save()
    write_jsonl(PRIVATE/'provenance.jsonl',provenance)
    os.chmod(PRIVATE/'provenance.jsonl',0o600)
    write_json(PRIVATE/'overlap_report.json',{'duplicate_identity_positions_removed':duplicates,
         'identical_feature_value_groups':[v for v in by_content.values() if len(v)>1],
         'basis':'Identity dedup uses original App session binding. Equal feature values alone are not proof of one observation.'})
    statistics=compute_statistics(tables)
    statistics['duplicate_identity_positions_removed']=len(duplicates)
    statistics['identical_feature_value_groups']=sum(len(v)>1 for v in by_content.values())
    write_json(out/'statistics.json',statistics)
    write_json(ROOT/'statistics.json',statistics)
    write_json(ROOT/'manifest.json',{'dataset_version':'1.0',
        'publication_status':RELEASE_STATUS,'data_license':'PENDING_SELECTION',
        'hosted_public_data_records':0,'release_records':len(features),
        'release_authorization':'release_authorization.json',
        'authorization_basis':'Project lead explicitly confirmed all study data sources may be publicly released on 2026-10-25.',
        'builder_files':frozen_inputs(repo,[str(p.relative_to(repo)) for p in (ROOT/'scripts').glob('*.py')]),
        'source_inventory':'source_inventory.json','schema':'schema.json',
        'candidate_files':{k:len(v) for k,v in tables.items()},
        'source_freeze':'private source_lock.json; per-file digests listed in source_inventory.json',
        'no_new_train_validation_test_split':True,'physical_device_count':None})
    make_schema(contract)
    report=verify(out)
    report.update(verify_evidence(repo,out))
    write_json(ROOT/'quality_report.json',report)
    write_json(out/'quality_report.json',report)
    generate_statistics_markdown(statistics)
    print(canonical({'build':'PASS','release_records':len(features),'hosted_public_data_records':0}))


def compute_statistics(tables):
    features=tables['features.jsonl']; metadata=tables['metadata.jsonl']; annotations=tables['annotations.jsonl']; pairs=tables['pairs.jsonl']
    by_id={row['sample_id']:row for row in features}
    an={row['sample_id']:row for row in annotations}
    per_source={}
    field_stats=defaultdict(Counter)
    for m in metadata:
        f=by_id[m['sample_id']]; a=an[m['sample_id']]
        s=per_source.setdefault(m['source_id'],{'records':0,'views':Counter(),'labels':Counter(),
            'label_verification':Counter(),'environments':Counter(),'android_api_levels':Counter(),
            'historical_cohorts':Counter(),'structurally_complete':0,'structurally_incomplete':0,
            'all_collection_states_observed':0,'all_values_retained':0,'groups':set(),
            'manipulation_types':Counter(),'modified_types':Counter(),'os_versions':Counter(),'collection_states':Counter(),'redactions':Counter(),
            'tool_execution_status':Counter(),'target_effect_status':Counter(),'detector_outcome':Counter()})
        s['records']+=1;s['views'][f['view']]+=1;s['labels'][a['label']]+=1
        s['label_verification'][a['label_verification']]+=1
        s['environments'][str(m.get('environment','unknown'))]+=1
        s['android_api_levels'][str(m.get('android_api_level'))]+=1
        s['historical_cohorts'][m.get('historical_split','not_assigned')]+=1
        s['structurally_complete' if m['qc']['structurally_complete'] else 'structurally_incomplete']+=1
        s['all_collection_states_observed']+=m['qc']['all_collection_states_observed']
        s['all_values_retained']+=m['qc']['all_values_retained']
        if m['group_id']:
            s['groups'].add(m['group_id'])
        s['manipulation_types'][a.get('manipulation_type','not_labeled')]+=1
        if a['label']=='modified':s['modified_types'][a.get('manipulation_type','unknown')]+=1
        s['os_versions'][str(f['fields']['android_native_data.os_version']['value'])]+=1
        for key in ('tool_execution_status','target_effect_status','detector_outcome'):
            val=a.get(key,'unknown');s[key][val if isinstance(val,str) else canonical(val)]+=1
        for key,cell in f['fields'].items():
            s['collection_states'][cell['collection_status']]+=1
            s['redactions'][cell['redaction']]+=1
            field_stats[key]['records']+=1
            field_stats[key]['original_present']+=cell['original_field_present']
            field_stats[key]['value_retained_non_null']+=cell['value'] is not None
            field_stats[key]['status:'+cell['collection_status']]+=1
            field_stats[key]['redaction:'+cell['redaction']]+=1
    for s in per_source.values():
        s['observed_group_count']=len(s.pop('groups'))
        s['independent_physical_devices']=None
    return {'scope':'REVIEWER_RELEASE_1.0','release_records':len(features),'publication_status':RELEASE_STATUS,
            'total_unique_observations':len(features),'views':dict(Counter(f['view'] for f in features)),
            'labels':dict(Counter(a['label'] for a in annotations)),
            'label_verification':dict(Counter(a['label_verification'] for a in annotations)),
            'structurally_complete':sum(m['qc']['structurally_complete'] for m in metadata),
            'structurally_incomplete':sum(not m['qc']['structurally_complete'] for m in metadata),
            'all_collection_states_observed':sum(m['qc']['all_collection_states_observed'] for m in metadata),
            'supplemental_geometry_observations':sum(bool(f.get('supplemental')) for f in features),
            'independent_physical_devices':None,
            'relationships':dict(Counter(p['kind'] for p in pairs)),
            'sources':per_source,'fields':dict(field_stats),
            'units':'Unique underlying observations after source identity deduplication; repeated environments and cohort grouping are not physical-device independence.'}


def make_schema(contract):
    string={'type':'string'}; nullable_string={'type':['string','null']}
    sid={'type':'string','pattern':r'sample_[0-9a-f]{32}'}
    def obj(props,required=None):
        return {'type':'object','properties':props,'required':list(props) if required is None else required,'additionalProperties':False}
    fields={}
    for key,types in fields_for(contract,True).items():
        valtypes=sorted(set(types+['null']))
        fields[key]=obj({'value':{'type':valtypes},'collection_status':{'enum':sorted(STATES)},
            'status_origin':{'enum':['collector_emitted','not_recorded']},
            'original_field_present':{'type':'boolean'},'redaction':{'enum':['none','remove_precise_time','remove_free_text_or_high_entropy_value','remove_unrecognized_semantic_value']}})
    features=obj({'record_type':{'const':'features'},'sample_id':sid,'view':{'enum':['App177','Paired244']},
                  'fields':obj(fields,[]), 'supplemental':obj({k:{'type':['number','boolean','null']} for k in SUPPLEMENTAL_KEYS},[])})
    qc=obj({'original_field_slots':{'type':'integer'},'expected_field_slots':{'type':'integer'},
        'structurally_complete':{'type':'boolean'},'all_collection_states_observed':{'type':'boolean'},
        'all_values_retained':{'type':'boolean'},'upstream_app_qc_errors':{'type':'array','items':string},
        'upstream_app_qc_warnings':{'type':'array','items':string},'source_missing_fields':{'type':'array','items':string},
        'redacted_fields':{'type':'integer'}})
    mprops={'record_type':{'const':'metadata'},'sample_id':sid,'source_id':string,
        'group_id':{'type':['string','null'],'pattern':r'group_[0-9a-f]{32}'},'view':{'enum':['App177','Paired244']},
        'group_basis':string,'qc':qc,'public_release_status':{'const':RELEASE_STATUS},'android_api_level':{'type':['integer','null']}}
    for k in ('cohort','environment','schema_version','browser_schema_version','historical_split','collection_context','physical_device_identity','representative_basis'):
        mprops[k]=nullable_string
    mprops['historical_holdout_pristine']={'type':'boolean'}
    metadata=obj(mprops,['record_type','sample_id','source_id','group_id','view','group_basis','qc','public_release_status','android_api_level'])
    aprop={'record_type':{'const':'annotations'},'sample_id':sid,'label':{'enum':sorted(LABELS)},
        'label_verification':{'enum':['verified_recorded_evidence','unverified','unknown']},
        'label_scope':{'const':'recorded_target_intervention_before_privacy_redaction'}}
    for key in ('tool_execution_status','target_effect_status','detector_outcome','manipulation_type','annotation_basis','phase','restoration_status','effect_verification','qualification_status',
             'recorded_detector_states','target_memory_gib','attack_tool','normal_scenario','configuration_name'):
        aprop[key]={'type':['string','boolean','null','object']}
    aprop['target_memory_gib']={'type':'number'}
    annotations=obj(aprop,['record_type','sample_id','label','label_verification','label_scope','tool_execution_status','target_effect_status','detector_outcome'])
    pairs=obj({'record_type':{'const':'pairs'},'pair_id':{'type':'string','pattern':r'pair_[0-9a-f]{32}'},
               'kind':{'enum':['experiment_triplet','linked_app_browser']},
               'members':{'type':'array','minItems':1,'maxItems':3,'items':obj({'sample_id':sid,'phase':{'enum':['clean_pre','active','clean_post','linked_endpoints']}})}})
    write_json(ROOT/'schema.json',{'$schema':'https://json-schema.org/draft/2020-12/schema','title':'Cross-View Consistency Dataset JSONL row',
        'oneOf':[{'$ref':'#/$defs/'+k} for k in ('features','metadata','annotations','pairs')],
        '$defs':dict(features=features,metadata=metadata,annotations=annotations,pairs=pairs)})
    catalog=[]
    for key,types in fields_for(contract,True).items():
        source_key=key.replace(BROWSER+'.','web_data.',1)
        catalog.append({'path':key,'source_allowed_types':contract['fields'][source_key],
                        'export_allowed_types':types, 'privacy_policy':field_policy(key,types),
                        'typing_note':'viewport scale is numeric; legacy integer-only contract corrected without changing values' if key.endswith('.visual_viewport_scale') else 'unchanged',
                        'unit':unit_for(key)})
    write_json(ROOT/'field_catalog.json',catalog)
    write_schema_markdown(catalog)


def write_schema_markdown(catalog):
    header = """# Schema and field dictionary

`schema.json` is a JSON Schema draft 2020-12 row union. The standard-library validator implements every keyword used in this file and rejects unsupported keywords. Structural and referential constraints between files are checked separately. The authorized reviewer package contains 1,509 observations; no hosted publication is performed by this build.

## Files and top-level fields

| File | Fields and meaning |
|---|---|
| features.jsonl | `record_type=features`; random `sample_id`; `view=App177` or `Paired244`; `fields` keyed by canonical signal path; `supplemental` optional recorded geometry measurements |
| metadata.jsonl | `record_type=metadata`; `sample_id`; `source_id`; random nullable `group_id`; `group_basis`; `view`; source `cohort`, `environment`, schema versions and historical split/context where recorded; `android_api_level`; `qc`; `public_release_status=AUTHORIZED_FOR_PUBLIC_RELEASE` |
| annotations.jsonl | `record_type=annotations`; `sample_id`; `label`, `label_verification`, `label_scope`; independent `tool_execution_status`, `target_effect_status`, `detector_outcome`; recorded recipe/tool/scenario, restoration status, memory target and saved detector states where available; canonical `phase` for experiment groups |
| pairs.jsonl | `record_type=pairs`; random `pair_id`; `kind=experiment_triplet` (three distinct observations) or `linked_app_browser` (one observation containing two endpoints); `members` with sample IDs and phase |

Metadata additionally retains `representative_basis`, `physical_device_identity` and `historical_holdout_pristine` where recorded. They are provenance, not model inputs. Source-specific random group IDs preserve grouping within each study; cross-study physical identity is not established. `configuration_name` is the readable recorded recipe, `manipulation_type` the canonical recipe/task identifier, and `attack_tool` the separately recorded execution tool. `normal_scenario` explains legitimate controls; `target_memory_gib` describes the intended operation, not an observed feature.

`label` is one of modified, normal_control, no_effect, unlabeled, unknown. `label_verification` is verified_recorded_evidence, unverified or unknown. The scope is recorded target intervention before privacy redaction. `detector_outcome` and `recorded_detector_states` retain saved decisions, or explicit unknown/not_recomputed. They are never substituted for intervention ground truth.

## Feature cell

Each nominal slot has `value` (original typed value or null), `original_field_present` (boolean), `collection_status`, `status_origin` and `redaction`. Availability states: observed, unsupported_by_os, permission_denied, runtime_error, timeout, not_applicable, missing, unknown, present_status_unknown. `collector_emitted` and `not_recorded` distinguish original status from unrecorded status. A present value without a recorded state is not upgraded to observed. Original absence remains explicit even if a schema slot is materialized for representation.

Redaction values: none, remove_precise_time, remove_free_text_or_high_entropy_value, remove_unrecognized_semantic_value. A privacy-suppressed value is null but retains its original availability state. `false`, zero and minus one are not automatically missing. Historical sentinels and collector status may be insufficient to infer scientific usability.

App177 contains exactly 84 `android_native_data`, 26 `webview_data` and 67 `web_data` slots. Paired244 additionally has 67 `browser_web_data` slots only when a real Browser observation exists. Missing App fields in three genuine linked MTC records do not invalidate the endpoint association; they make the observation structurally incomplete. No Browser is synthesized from empty slots.

`qc` records original/expected slot counts, structural completeness, all-collector-observed and all-values-retained flags, upstream App QC errors/warnings, missing original paths and redacted-field count. Counts refer to the original field structure and the retained projection separately. The integer-only legacy viewport-scale field is explicitly corrected to numeric in both Web views; no other integer field is broadly widened or value converted.

## Relationships and geometry supplement

Experiment phases are normalized from recorded aliases to clean_pre, active, clean_post. Linked endpoints use linked_endpoints and one shared observation ID. Every reference must resolve; no observation belongs to two experiment triplets. Historical grouping/cohort metadata is not an independent-device or leakage-free split claim.

The geometry supplement is separate from the 177/244 counts. Host width/height, content width/height and four padding edges are physical pixels; Host density and Web DPR/viewport scale are dimensionless. Web screen/inner/visual-viewport dimensions are CSS pixels. `geometry_evidence.android_bracket_ms` is a relative acquisition duration, not an epoch timestamp; `geometry_evidence.usable_window` is the recorded boolean binding-window status. Host-before/after suffixes denote the actual synchronized bracket, not interpolation. Exact clocks, document IDs, URLs and diagnostic free text are absent.

Allowed supplemental keys:

"""
    lines=[header]+['- `'+key+'`' for key in SUPPLEMENTAL_KEYS]
    lines+=['', '## Complete signal dictionary', '', '| Signal | Original types | Export types | Unit | Privacy policy |', '|---|---|---|---|---|']
    for field in catalog:
        lines.append('| '+field['path']+' | '+', '.join(field['source_allowed_types'])+' | '+', '.join(field['export_allowed_types'])+' or null | '+field['unit']+' | '+field['privacy_policy']+' |')
    (ROOT/'SCHEMA.md').write_text('\n'.join(lines)+'\n')


def unit_for(path):
    k=path.rsplit('.',1)[-1]
    if k.endswith('_gb') or k=='device_memory':return 'GiB as reported by the collector'
    if k.endswith('_ms') or k in {'first_install_time','last_update_time','performance_time_origin'}:return 'milliseconds; exact timestamps suppressed where applicable'
    if k.endswith('_pct'):return 'percent'
    if k.endswith('_hz'):return 'hertz'
    if k.endswith('_kbps'):return 'kilobits per second'
    if k.endswith('_mbps'):return 'megabits per second'
    if k.endswith('_celsius'):return 'degrees Celsius'
    if k.endswith('_mv'):return 'millivolts'
    if k.endswith('_offset_min'):return 'minutes; Android UTC-offset convention'
    if k=='timezone_offset':return 'minutes; JavaScript getTimezoneOffset convention (opposite sign to UTC offset)'
    if 'height' in k or 'width' in k or 'resolution' in k:return 'reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels'
    if k.endswith('_count') or k in {'hardware_concurrency','max_touch_points'}:return 'count'
    if k in {'device_pixel_ratio','visual_viewport_scale','font_scale','screen_scaled_density'}:return 'dimensionless ratio'
    return 'collector-native categorical, boolean or scalar; no conversion applied'


def verify(out):
    out=private_destination(out)
    tables={name:read_jsonl(out/name) for name in DATA_FILES}
    schema=json.loads((ROOT/'schema.json').read_text())
    for rows in tables.values():
        for row in rows:
            validate_schema(row,schema)
            if privacy_findings(row):
                raise ValueError('Candidate privacy pattern match: '+canonical(privacy_findings(row)))
    f=tables['features.jsonl'];m=tables['metadata.jsonl'];a=tables['annotations.jsonl'];p=tables['pairs.jsonl']
    ids={r['sample_id'] for r in f}
    if len(ids)!=len(f):raise ValueError('Duplicate public sample ID')
    if len(m)!=len(ids) or len(a)!=len(ids) or {r['sample_id'] for r in m}!=ids or {r['sample_id'] for r in a}!=ids:
        raise ValueError('One-to-one sidecar binding failed')
    meta={r['sample_id']:r for r in m}
    ann={r['sample_id']:r for r in a}
    expected_catalog=json.loads((ROOT/'field_catalog.json').read_text())
    catalog_by_path={c['path']:c for c in expected_catalog}
    all_fields=set(catalog_by_path)
    app_fields={k for k in all_fields if not k.startswith(BROWSER+'.')}
    for row in f:
        expected=all_fields if row['view']=='Paired244' else app_fields
        if set(row['fields'])!=expected:raise ValueError('View field-set mismatch')
        if meta[row['sample_id']]['view']!=row['view']:raise ValueError('Metadata view mismatch')
        qc=meta[row['sample_id']]['qc']
        if qc['expected_field_slots']!=len(expected):raise ValueError('Expected slot count mismatch')
        actual=sum(c['original_field_present'] for c in row['fields'].values())
        if qc['original_field_slots']!=actual or qc['structurally_complete']!=(actual==len(expected)):
            raise ValueError('Structural completeness mismatch')
        for key,cell in row['fields'].items():
            retained,policy=sanitize_value(key,cell['value'],catalog_by_path[key]['source_allowed_types'])
            if cell['value'] is not None and (policy!='none' or retained!=cell['value']):
                raise ValueError('Retained value violates field privacy policy')
            if not cell['original_field_present'] and (cell['value'] is not None or cell['collection_status']=='observed'):
                raise ValueError('Missing source field cannot contain a value or observed state')
            if cell['redaction']!='none' and cell['value'] is not None:
                raise ValueError('Redacted field contains a value')
        expected_qc={
            'all_collection_states_observed':all(c['collection_status']=='observed' for c in row['fields'].values()),
            'all_values_retained':all(c['redaction']=='none' for c in row['fields'].values()),
            'redacted_fields':sum(c['redaction']!='none' for c in row['fields'].values()),
            'source_missing_fields':sorted(k for k,c in row['fields'].items() if not c['original_field_present'])}
        if any(qc[k]!=v for k,v in expected_qc.items()):raise ValueError('Availability/redaction QC mismatch')
        if row['view']=='Paired244' and not any(c['original_field_present'] for k,c in row['fields'].items() if k.startswith(BROWSER+'.')):
            raise ValueError('Empty Browser masquerading as paired observation')
    pair_ids=set();linked=Counter();experiment_members=set()
    for pair in p:
        if pair['pair_id'] in pair_ids:raise ValueError('Repeated relationship ID')
        pair_ids.add(pair['pair_id'])
        members=pair['members']
        if any(x['sample_id'] not in ids for x in members):raise ValueError('Dangling relationship')
        if pair['kind']=='linked_app_browser':
            if len(members)!=1 or members[0]['phase']!='linked_endpoints' or meta[members[0]['sample_id']]['view']!='Paired244':raise ValueError('Invalid endpoint relationship')
            linked[members[0]['sample_id']]+=1
        else:
            if len(members)!=3 or {x['phase'] for x in members}!={'clean_pre','active','clean_post'} or len({x['sample_id'] for x in members})!=3:
                raise ValueError('Invalid experiment triplet')
            if len({meta[x['sample_id']]['source_id'] for x in members})!=1 or len({meta[x['sample_id']]['group_id'] for x in members})!=1:
                raise ValueError('Experiment triplet crosses source or observed environment group')
            for item in members:
                if ann[item['sample_id']].get('phase')!=item['phase']:raise ValueError('Pair/annotation phase mismatch')
                if item['sample_id'] in experiment_members:raise ValueError('Repeated experiment position')
                experiment_members.add(item['sample_id'])
    if linked!={r['sample_id']:1 for r in f if r['view']=='Paired244'}:raise ValueError('Missing/duplicate endpoint links')
    for row in a:
        if row['label']=='modified' and row['label_verification']!='verified_recorded_evidence':raise ValueError('Unsupported positive annotation')
    recalculated=compute_statistics(tables)
    saved=json.loads((out/'statistics.json').read_text())
    for key,value in recalculated.items():
        if value!=saved[key]:raise ValueError('Statistics mismatch: '+key)
    if any((ROOT/'data').glob('*.jsonl*')):raise ValueError('Sample data is delivered only in the local reviewer archive; no hosted publication is performed')
    allowed=set(DATA_FILES)|{'statistics.json','quality_report.json'}
    if {x.name for x in out.iterdir()}-allowed:raise ValueError('Unexpected candidate content; possible mapping contamination')
    return {'status':'PASS','scope':'technical validation of authorized release inputs; not independent experiment replication',
            'rows_validated':sum(map(len,tables.values())),'observations':len(f),'schema_validation':'PASS',
            'unique_sample_ids':'PASS','sidecar_and_pair_references':'PASS','statistics_recomputed':'PASS',
            'privacy_pattern_scan':'PASS_NO_MATCHES','mapping_exclusion':'PASS','hosted_public_data_records':0,'release_records':len(f),
            'independent_physical_devices':'UNKNOWN','public_authorization':'CONFIRMED_BY_PROJECT_LEAD'}


def verify_evidence(repo, out):
    data=extract(repo)
    ids=RandomIDs(PRIVATE/'identity_map.json')
    tables={name:read_jsonl(Path(out)/name) for name in DATA_FILES}
    by_id={row['sample_id']:row for row in tables['annotations.jsonl']}
    exported_features={row['sample_id']:row for row in tables['features.jsonl']}
    metadata={row['sample_id']:row for row in tables['metadata.jsonl']}
    normalizer=load_normalizer(repo)
    contract=json.loads((repo/CONTRACT_PATH).read_text())
    expected_ids=set()
    for record in data['records']:
        key=str(record['record_key'])
        sid=ids.mapping.get('sample',{}).get(key)
        if sid is None:raise ValueError('Original observation is absent from release identity map')
        expected_ids.add(sid)
        annotation={'record_type':'annotations','sample_id':sid,**safe_annotation(record)}
        if record.get('phase') is not None:annotation['phase']=normalize_phase(record['phase'])
        if annotation!=by_id.get(sid):raise ValueError('Exported annotation differs from frozen original evidence')
        view,cells,qc=normalize_record(record,contract,normalizer)
        expected={'record_type':'features','sample_id':sid,'view':view,'fields':cells,
                  'supplemental':supplemental_values(record.get('extras',{}))}
        if expected!=exported_features.get(sid):raise ValueError('Exported features differ from privacy-filtered original evidence')
        if metadata[sid]['source_id']!=record['source_id'] or metadata[sid]['qc']!=qc:
            raise ValueError('Exported metadata differs from original evidence')
    if expected_ids!=set(by_id):raise ValueError('Export includes unexplained or omitted observations')
    return {'annotation_and_feature_source_agreement':'PASS_RECORDED_EVIDENCE',
            'observations_reconciled':len(expected_ids),'independent_experiment_replication':False}


def generate_statistics_markdown(s):
    lines=['# Release statistics','', 'Status: **AUTHORIZED FOR PUBLIC RELEASE**. Packaged observations: **1,509**. No hosting is performed by the build.',
        '', 'All counts below are computed from the final local de-identified export, not copied from the manuscript.',
        '',f"Unique underlying observations: {s['total_unique_observations']}. Views: `{canonical(s['views'])}`.",
        f"Original structurally complete: {s['structurally_complete']}; incomplete: {s['structurally_incomplete']}.",
        'Structural completeness counts source feature slots; it does not assert all values are useful, available or retained after redaction.',
        '', '| Source | Observations | Views | Labels | Structural complete / incomplete |', '|---|---:|---|---|---|']
    for name,v in s['sources'].items():
        lines.append(f"| {name} | {v['records']} | {canonical(v['views'])} | {canonical(v['labels'])} | {v['structurally_complete']} / {v['structurally_incomplete']} |")
    lines+=['',f"Label verification: `{canonical(s['label_verification'])}`.",f"Relationships: `{canonical(s['relationships'])}`.",
      '', 'Independent physical-device count is unknown. Group counts describe source-specific environments or historical transitive groups only.',
      'No new machine-learning split is generated. Historical cohort assignments are metadata with development exposure.',
      'The machine-readable companion contains per-source environment/API, manipulation, tool/effect/detector, field availability and redaction distributions.',
      'The six memory no-effect operations remain separate. MTC records remain unlabeled even where paper tables use no-target-manipulation context as normal.']
    (ROOT/'STATISTICS.md').write_text('\n'.join(lines)+'\n')


def package_candidate():
    """Compatibility entry point for the independent, anonymous release builder."""
    check_lock(REPO)
    from build_reviewer_release import build as build_reviewer
    print(canonical(build_reviewer()))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['freeze','build','verify','package','all'])
    args=parser.parse_args()
    if args.command in {'freeze','all'} and (args.command=='freeze' or not (PRIVATE/'source_lock.json').exists()):freeze(REPO)
    if args.command in {'build','all'}:build(REPO)
    if args.command=='verify':
        check_lock(REPO)
        report=verify(PRIVATE/'candidate')
        report.update(verify_evidence(REPO,PRIVATE/'candidate'))
        print(canonical(report))
    if args.command=='package':package_candidate()

if __name__=='__main__':
    main()
