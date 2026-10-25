#!/usr/bin/env python3
"""Load and validate the anonymous reviewer data using only Python's standard library.

This validates the exported observations and reproduces their descriptive
statistics. It does not run the original detector, recover redacted values,
re-establish collection evidence, or independently repeat experiments.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DATA_FILES = ('features.jsonl', 'metadata.jsonl', 'annotations.jsonl', 'pairs.jsonl')
PACKAGE_FILES = frozenset(DATA_FILES) | {
    'schema.json', 'field_catalog.json', 'statistics.json', 'README.md',
    'DATASET_CARD.md', 'RELEASE_REVIEW.md', 'LICENSE_DATA.md', 'FIGSHARE_UPLOAD.md',
    'SCHEMA.md', 'STATISTICS.md', 'validate.py', 'load_example.py',
    'quality_report.json', 'manifest.json',
}
DATA_LICENSE = 'CC-BY-4.0'
DATA_LICENSE_URL = 'https://creativecommons.org/licenses/by/4.0/'
SOFTWARE_LICENSE = 'NOT_SPECIFIED'
SOFTWARE_FILES = ('load_example.py', 'validate.py')
DATA_LICENSE_FILES = frozenset(PACKAGE_FILES) - {*SOFTWARE_FILES, 'LICENSE_DATA.md'}
RELEASE_STATUS = 'AUTHORIZED_FOR_PUBLIC_RELEASE'
BROWSER = 'browser_web_data'
LAYER_COUNTS = {'android_native_data': 84, 'webview_data': 26,
                'web_data': 67, BROWSER: 67}
SOURCE_COUNTS = {'controlled_main': 378, 'specialist_memory': 72,
                 'specialist_timezone': 36, 'specialist_geometry': 72,
                 'linked_browser_pilot18': 18, 'linked_browser_b2b42': 42,
                 'mtc_historical_891': 891}


def manifest_license_schema():
    """Return the machine contract for the manifest's license declarations only."""
    def scope(files):
        names = sorted(files)
        return {'type': 'array', 'items': {'type': 'string', 'enum': names},
                'minItems': len(names), 'maxItems': len(names), 'const': names}

    properties = {
        'data_license': {'type': 'string', 'const': DATA_LICENSE},
        'data_license_url': {'type': 'string', 'const': DATA_LICENSE_URL},
        'data_license_file': {'type': 'string', 'const': 'LICENSE_DATA.md'},
        'data_license_scope': scope(DATA_LICENSE_FILES),
        'software_license': {'type': 'string', 'const': SOFTWARE_LICENSE},
        'software_license_scope': scope(SOFTWARE_FILES),
    }
    return {
        'type': 'object', 'title': 'Reviewer manifest licensing declarations',
        'description': 'CC BY 4.0 applies to the enumerated data resources. The two software files have a separately declared license status.',
        'properties': properties, 'required': list(properties), 'additionalProperties': True,
    }


DROP_NUMERIC = {'build_time_ms', 'elapsed_realtime_ms', 'uptime_ms', 'first_install_time',
                'last_update_time', 'performance_time_origin'}
SAFE_TEXT = {
    'native_language': r'[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*',
    'native_country': r'[A-Za-z]{2,3}',
    'native_locale': r'[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*',
    'language': r'[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*',
    'native_timezone_id': r'(?:[A-Za-z_+-]+/){0,2}[A-Za-z_+\-0-9:]+',
    'timezone_id': r'(?:[A-Za-z_+-]+/){0,2}[A-Za-z_+\-0-9:]+',
    'screen_resolution_physical': r'\d{1,5}\s*[xX×,]\s*\d{1,5}',
    'screen_resolution_logical': r'\d{1,5}\s*[xX×,]\s*\d{1,5}',
    'os_version': r'\d{1,2}(?:\.\d{1,3}){0,2}',
}
ENUM_TEXT = {
    'camera_permission_state': {'granted','denied','prompt','unknown','unsupported'},
    'microphone_permission_state': {'granted','denied','prompt','unknown','unsupported'},
    'geolocation_permission_state': {'granted','denied','prompt','unknown','unsupported'},
    'notification_permission_state': {'granted','denied','prompt','unknown','unsupported'},
    'clipboard_read_state': {'granted','denied','prompt','unknown','unsupported'},
    'effective_type': {'slow-2g','2g','3g','4g','unknown'},
    'orientation_type': {'portrait-primary','portrait-secondary','landscape-primary','landscape-secondary'},
    'platform': {'Linux armv7l','Linux armv8l','Linux aarch64','Linux x86_64','Linux i686','Android','Win32','MacIntel'},
}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False)


def field_policy(name, allowed_types):
    leaf = name.rsplit('.', 1)[-1]
    if leaf in DROP_NUMERIC:
        return 'remove_precise_time'
    if leaf in SAFE_TEXT or leaf in ENUM_TEXT or leaf in {'languages', 'supported_abis', 'sensor_type_list', 'active_transport_types'}:
        return 'retain_validated_semantic_value'
    if set(allowed_types) <= {'boolean','integer','number'}:
        return 'retain_numeric_or_boolean_manual_privacy_review'
    return 'remove_free_text_or_high_entropy_value'


def sanitize_value(name, value, allowed_types):
    """Never hash identifiers. Preserve missingness separately from privacy suppression."""
    policy = field_policy(name, allowed_types)
    if value is None:
        return None, 'none'
    leaf = name.rsplit('.', 1)[-1]
    if policy.startswith('remove_'):
        return None, policy
    if isinstance(value, bool):
        return value, 'none'
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError('Non-finite feature')
        return value, 'none'
    if isinstance(value, str):
        if leaf in SAFE_TEXT and re.fullmatch(SAFE_TEXT[leaf], value) and len(value) <= 64:
            return value, 'none'
        if value in ENUM_TEXT.get(leaf, set()):
            return value, 'none'
    if isinstance(value, list):
        if leaf == 'languages' and all(isinstance(v, str) and re.fullmatch(SAFE_TEXT['language'], v) for v in value):
            return value, 'none'
        if leaf == 'sensor_type_list' and all(type(v) is int and 0 <= v < 100000 for v in value):
            return value, 'none'
        if leaf == 'supported_abis' and all(v in {'armeabi','armeabi-v7a','arm64-v8a','x86','x86_64','mips','mips64','riscv64'} for v in value):
            return value, 'none'
        if leaf == 'active_transport_types' and all(v in {'WIFI','CELLULAR','BLUETOOTH','ETHERNET','VPN','WIFI_AWARE','LOWPAN','USB',0,1,2,3,4,5,6,7,8} for v in value):
            return value, 'none'
    return None, 'remove_unrecognized_semantic_value'


def type_matches(value, kind):
    return {'null': value is None, 'object': isinstance(value, dict), 'array': isinstance(value, list),
            'string': isinstance(value, str), 'boolean': type(value) is bool,
            'integer': type(value) is int, 'number': type(value) in (int,float) and math.isfinite(value)}.get(kind, False)


def validate_schema(value, schema, root=None, location='$'):
    """Validate every keyword used by the shipped JSON Schema; reject unsupported keywords."""
    root = root or schema
    supported = {'$schema','$id','$defs','$ref','title','description','type','properties','required',
                 'additionalProperties','items','enum','const','oneOf','minItems','maxItems','pattern'}
    if set(schema) - supported:
        raise ValueError('Unsupported schema keyword')
    if '$ref' in schema:
        ref = root
        for key in schema['$ref'].removeprefix('#/').split('/'):
            ref = ref[key]
        return validate_schema(value, ref, root, location)
    if 'oneOf' in schema:
        passed = 0
        for branch in schema['oneOf']:
            try:
                validate_schema(value, branch, root, location)
                passed += 1
            except ValueError:
                pass
        if passed != 1:
            raise ValueError(f'{location}: expected exactly one schema variant')
    if 'type' in schema:
        kinds = schema['type'] if isinstance(schema['type'],list) else [schema['type']]
        if not any(type_matches(value, kind) for kind in kinds):
            raise ValueError(f'{location}: invalid type')
    if 'const' in schema and value != schema['const']:
        raise ValueError(f'{location}: invalid constant')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{location}: invalid enum')
    if isinstance(value,str) and 'pattern' in schema and not re.fullmatch(schema['pattern'], value):
        raise ValueError(f'{location}: invalid pattern')
    if isinstance(value,dict):
        if set(schema.get('required',[])) - set(value):
            raise ValueError(f'{location}: missing required keys')
        props = schema.get('properties',{})
        extra = schema.get('additionalProperties',True)
        for key, child in value.items():
            if key in props:
                validate_schema(child, props[key], root, location+'.'+key)
            elif extra is False:
                raise ValueError(f'{location}: unexpected key {key}')
            elif isinstance(extra,dict):
                validate_schema(child,extra,root,location+'.'+key)
    if isinstance(value,list):
        if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',float('inf')):
            raise ValueError(f'{location}: invalid array size')
        for i,child in enumerate(value):
            if 'items' in schema:
                validate_schema(child,schema['items'],root,f'{location}[{i}]')


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
    statuses = {m['public_release_status'] for m in metadata}
    if statuses != {RELEASE_STATUS}:
        raise ValueError('Nonuniform or unauthorized release status')
    result = {'scope':'REVIEWER_RELEASE_1.0', 'release_records':len(features),
            'publication_status':next(iter(statuses)),
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

    return json.loads(canonical(result))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Repeated JSON object key')
        result[key] = value
    return result


def _reject_nonfinite(_value):
    raise ValueError('Non-finite JSON number')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),
                      object_pairs_hook=_unique_object, parse_constant=_reject_nonfinite)


def load_tables(package_root):
    """Return the four tables, keyed by their JSONL filenames."""
    root = Path(package_root)
    tables = {}
    for name in DATA_FILES:
        rows = []
        with (root / name).open(encoding='utf-8') as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    raise ValueError(f'{name}:{line_number}: empty JSONL row')
                try:
                    row = json.loads(line, object_pairs_hook=_unique_object,
                                     parse_constant=_reject_nonfinite)
                except (ValueError, TypeError) as error:
                    raise ValueError(f'{name}:{line_number}: invalid JSON row') from error
                if not isinstance(row, dict):
                    raise ValueError(f'{name}:{line_number}: row is not an object')
                rows.append(row)
        tables[name] = rows
    return tables


def privacy_findings(value):
    """Detect bounded identifier patterns without returning matching values.

    This is a screening check, not a guarantee of anonymity or unlinkability.
    Author names require a separate release-specific denylist audit.
    """
    patterns = {
        'email': r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',
        'ipv4': r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])',
        'home_path': r'/(?:Users|home)/[^\s/]+',
        'credential': r'(?i)(?:-----BEGIN .*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{15,}|sk-[A-Za-z0-9]{20,})',
        'exact_timestamp': r'\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
        'phone': r'(?<![A-Za-z0-9_])(?:\+86[- ]?)?1[3-9]\d{9}(?![A-Za-z0-9_])',
        'external_link': r'(?i)(?:https?://|ssh://|git@)',
    }
    identity_keys = {'session_id', 'collector_install_id', 'device_manifest_id',
                     'android_id', 'serial_number', 'client_ip', 'pair_ticket',
                     'email', 'phone_number'}
    strings = set()
    findings = Counter()

    def visit(node):
        if isinstance(node, dict):
            for key, child in node.items():
                strings.add(key)
                if key in identity_keys:
                    findings['source_identity_key'] += 1
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
        elif isinstance(node, str):
            strings.add(node)

    visit(value)
    for name, pattern in patterns.items():
        matcher = re.compile(pattern)
        findings[name] = sum(bool(matcher.search(text)) for text in strings)
    return {key: count for key, count in findings.items() if count}


def _validate_catalog(catalog, schema):
    if not isinstance(catalog, list) or any(not isinstance(c, dict) for c in catalog):
        raise ValueError('Invalid field catalog')
    by_path = {entry['path']: entry for entry in catalog}
    if len(by_path) != len(catalog):
        raise ValueError('Repeated field catalog path')
    if Counter(path.split('.', 1)[0] for path in by_path) != LAYER_COUNTS:
        raise ValueError('Field catalog must contain the four declared layer counts')
    schema_fields = schema['$defs']['features']['properties']['fields']['properties']
    if set(schema_fields) != set(by_path):
        raise ValueError('Schema/catalog field mismatch')
    allowed_types = {'boolean', 'integer', 'number', 'string', 'array', 'object'}
    for path, entry in by_path.items():
        source_types = entry['source_allowed_types']
        export_types = entry['export_allowed_types']
        if not source_types or not export_types or not set(source_types + export_types) <= allowed_types:
            raise ValueError('Invalid field catalog types')
        if entry['privacy_policy'] != field_policy(path, source_types):
            raise ValueError('Field catalog privacy policy mismatch')
        if set(schema_fields[path]['properties']['value']['type']) != set(export_types + ['null']):
            raise ValueError('Schema/catalog field type mismatch')
    return by_path


def _validate_annotation(annotation, metadata):
    label = annotation['label']
    effect = annotation['target_effect_status']
    source = metadata['source_id']
    if source == 'mtc_historical_891':
        if label != 'unlabeled' or annotation['label_verification'] != 'unverified':
            raise ValueError('Historical reference observations must remain unlabeled and unverified')
        if any(annotation[key] != 'unknown' for key in
               ('tool_execution_status', 'target_effect_status', 'detector_outcome')):
            raise ValueError('Historical reference outcomes must remain unknown')
        if 'phase' in annotation or metadata['view'] != 'Paired244':
            raise ValueError('Historical reference context or view mismatch')
        if metadata.get('historical_holdout_pristine') is not False:
            raise ValueError('Historical holdout cannot be represented as pristine')
        if metadata.get('physical_device_identity') != 'not_verified':
            raise ValueError('Physical device identity is not independently verified')
        if metadata.get('historical_split') not in {'discovery', 'development', 'reserved_validation'}:
            raise ValueError('Historical cohort assignment changed')
        return
    if source not in SOURCE_COUNTS:
        raise ValueError('Unrecognized release source')
    if annotation['label_verification'] != 'verified_recorded_evidence':
        raise ValueError('Experimental labels require their recorded-evidence qualification')
    if label not in {'modified', 'normal_control', 'no_effect'}:
        raise ValueError('Experimental observation label mismatch')
    if annotation.get('phase') not in {'clean_pre', 'active', 'clean_post'}:
        raise ValueError('Experimental observation needs a three-phase position')
    if annotation['phase'] != 'active' and label != 'normal_control':
        raise ValueError('Pre/post experimental positions must remain controls')
    if label == 'modified' and effect not in {'observed_target_change', 'OBSERVED_CHANGE'}:
        raise ValueError('Modified annotation requires a recorded target change')
    if label == 'no_effect' and (source != 'specialist_memory' or effect != 'no_observable_effect'):
        raise ValueError('No-effect annotation requires the recorded unsuccessful memory operation')
    # Legitimate active controls may have an observed effect. Detector states do
    # not determine either the intervention label or the target effect status.
    if source.startswith('linked_browser_'):
        if metadata['view'] != 'Paired244' or effect not in {'OBSERVED_CHANGE', 'NO_TARGET_MODIFICATION'}:
            raise ValueError('Linked-browser view/effect mismatch')
        outcome = annotation['detector_outcome']
        if not isinstance(outcome, dict) or set(outcome) != {
                'saved_configuration_1', 'saved_configuration_2', 'saved_configuration_3'}:
            raise ValueError('Unexpected saved detector configuration set')
        for states in outcome.values():
            if not isinstance(states, dict) or set(states) != {'app', 'app_plus_browser_C1'} or not set(states.values()) <= {'T', 'F', 'U'}:
                raise ValueError('Invalid saved detector state')
        if (annotation.get('manipulation_type') == 'none') != (label == 'normal_control'):
            raise ValueError('Linked-browser target intervention/label mismatch')
    else:
        if metadata['view'] != 'App177' or annotation['detector_outcome'] != 'not_recomputed':
            raise ValueError('App experiment view/detector qualification mismatch')
        allowed_effects = {'clean_pre': {'baseline_observation'}, 'clean_post': {'restored'},
                          'active': {'observed_target_change', 'no_observable_effect', 'legitimate_change'}}
        if effect not in allowed_effects[annotation['phase']]:
            raise ValueError('Experimental phase/effect mismatch')
        if annotation['phase'] == 'active':
            if source == 'controlled_main' and label != 'modified':
                raise ValueError('Controlled active intervention label changed')
            if source == 'specialist_memory':
                expected_label = 'no_effect' if effect == 'no_observable_effect' else 'modified'
                if label != expected_label:
                    raise ValueError('Memory operation label/effect mismatch')
            if source in {'specialist_timezone', 'specialist_geometry'}:
                legitimate = annotation.get('manipulation_type', '').startswith('legitimate_')
                if label != ('normal_control' if legitimate else 'modified'):
                    raise ValueError('Specialist intervention/control label mismatch')


def validate_tables(tables, schema, catalog):
    """Validate content without relying on original records or repository files."""
    if set(tables) != set(DATA_FILES):
        raise ValueError('The four release tables are required')
    by_path = _validate_catalog(catalog, schema)
    for filename, rows in tables.items():
        expected_type = filename.removesuffix('.jsonl')
        for row in rows:
            if row.get('record_type') != expected_type:
                raise ValueError('JSONL row belongs to a different table')
            validate_schema(row, schema)
    findings = privacy_findings(list(tables.values()))
    if findings:
        raise ValueError('Exported data privacy pattern match: ' + canonical(findings))
    features, metadata, annotations, pairs = (tables[name] for name in DATA_FILES)
    ids = {row['sample_id'] for row in features}
    if len(ids) != len(features):
        raise ValueError('Repeated observation ID')
    for sidecar in (metadata, annotations):
        if len(sidecar) != len(ids) or {row['sample_id'] for row in sidecar} != ids:
            raise ValueError('One-to-one sidecar binding mismatch')
    meta = {row['sample_id']: row for row in metadata}
    ann = {row['sample_id']: row for row in annotations}
    group_sources = {}
    all_fields = set(by_path)
    app_fields = {key for key in all_fields if not key.startswith(BROWSER + '.')}
    for feature in features:
        metadata_row = meta[feature['sample_id']]
        if metadata_row['public_release_status'] != RELEASE_STATUS:
            raise ValueError('Observation is not authorized for this release')
        if metadata_row['view'] != feature['view']:
            raise ValueError('Metadata/feature view mismatch')
        group_id = metadata_row['group_id']
        if group_id is None:
            raise ValueError('Release observation lost its original source group')
        if group_sources.setdefault(group_id, metadata_row['source_id']) != metadata_row['source_id']:
            raise ValueError('Group crosses data sources')
        expected = all_fields if feature['view'] == 'Paired244' else app_fields
        if set(feature['fields']) != expected:
            raise ValueError('View field-set mismatch')
        for key, cell in feature['fields'].items():
            value = cell['value']
            retained, policy = sanitize_value(key, value, by_path[key]['source_allowed_types'])
            if value is not None and (policy != 'none' or retained != value):
                raise ValueError('Retained value violates field privacy policy')
            if not cell['original_field_present'] and (value is not None or cell['collection_status'] == 'observed' or cell['redaction'] != 'none'):
                raise ValueError('Missing source slot cannot acquire a value, redaction or observed state')
            if cell['redaction'] != 'none' and value is not None:
                raise ValueError('Redacted field contains a value')
            field_rule = by_path[key]['privacy_policy']
            if cell['redaction'].startswith('remove_') and cell['redaction'] != 'remove_unrecognized_semantic_value' and cell['redaction'] != field_rule:
                raise ValueError('Redaction reason violates field policy')
            if cell['status_origin'] == 'not_recorded':
                allowed = {'missing'} if not cell['original_field_present'] else {'unknown', 'present_status_unknown'}
                if cell['collection_status'] not in allowed:
                    raise ValueError('Unrecorded collector state cannot be invented')
            elif cell['collection_status'] == 'present_status_unknown':
                raise ValueError('Synthetic presence status cannot be attributed to the collector')
        qc = metadata_row['qc']
        missing = sorted(key for key, cell in feature['fields'].items() if not cell['original_field_present'])
        derived_qc = {
            'expected_field_slots': len(expected), 'original_field_slots': len(expected) - len(missing),
            'structurally_complete': not missing, 'source_missing_fields': missing,
            'all_collection_states_observed': all(c['collection_status'] == 'observed' for c in feature['fields'].values()),
            'all_values_retained': all(c['redaction'] == 'none' for c in feature['fields'].values()),
            'redacted_fields': sum(c['redaction'] != 'none' for c in feature['fields'].values()),
        }
        if any(qc[key] != value for key, value in derived_qc.items()):
            raise ValueError('Derived structural/status/redaction QC mismatch')
        if metadata_row['android_api_level'] != feature['fields']['android_native_data.os_api_level']['value']:
            raise ValueError('Metadata/feature Android API level mismatch')
        if feature['view'] == 'Paired244' and not any(cell['original_field_present'] for key, cell in feature['fields'].items() if key.startswith(BROWSER + '.')):
            raise ValueError('Empty Browser cannot create a paired observation')
        if bool(feature['supplemental']) != (metadata_row['source_id'] == 'specialist_geometry'):
            raise ValueError('Supplemental geometry/source mismatch')
        if feature['supplemental']:
            supplemental_fields = schema['$defs']['features']['properties']['supplemental']['properties']
            if set(feature['supplemental']) != set(supplemental_fields) or len(supplemental_fields) != 28:
                raise ValueError('Supplemental geometry field-set mismatch')
            for key, value in feature['supplemental'].items():
                if value is not None and (type(value) is not bool if key.endswith('.usable_window') else type(value) not in (int, float)):
                    raise ValueError('Supplemental geometry measurement type mismatch')
        _validate_annotation(ann[feature['sample_id']], metadata_row)
    pair_ids = set()
    linked = Counter()
    triplet_members = set()
    for pair in pairs:
        if pair['pair_id'] in pair_ids:
            raise ValueError('Repeated relationship ID')
        pair_ids.add(pair['pair_id'])
        members = pair['members']
        if any(item['sample_id'] not in ids for item in members):
            raise ValueError('Dangling relationship')
        if pair['kind'] == 'linked_app_browser':
            if len(members) != 1 or members[0]['phase'] != 'linked_endpoints' or meta[members[0]['sample_id']]['view'] != 'Paired244':
                raise ValueError('Invalid endpoint relationship')
            linked[members[0]['sample_id']] += 1
        else:
            if len(members) != 3 or {x['phase'] for x in members} != {'clean_pre', 'active', 'clean_post'} or len({x['sample_id'] for x in members}) != 3:
                raise ValueError('Invalid three-phase experiment relationship')
            if len({meta[x['sample_id']]['source_id'] for x in members}) != 1 or len({meta[x['sample_id']]['group_id'] for x in members}) != 1:
                raise ValueError('Experiment crosses data sources or environment groups')
            for item in members:
                if ann[item['sample_id']].get('phase') != item['phase']:
                    raise ValueError('Relationship/annotation phase mismatch')
                if item['sample_id'] in triplet_members:
                    raise ValueError('Repeated experimental position')
                triplet_members.add(item['sample_id'])
    if linked != {row['sample_id']: 1 for row in features if row['view'] == 'Paired244'}:
        raise ValueError('Missing or repeated linked endpoints')
    expected_experiments = {row['sample_id'] for row in annotations if row['label_verification'] == 'verified_recorded_evidence'}
    if triplet_members != expected_experiments:
        raise ValueError('Experimental triplet coverage mismatch')
    return {'status': 'PASS', 'observations': len(features),
            'rows_validated': sum(len(rows) for rows in tables.values()),
            'schema_validation': 'PASS', 'field_catalog': 'PASS',
            'unique_sample_ids': 'PASS', 'sidecar_and_pair_references': 'PASS',
            'availability_and_redaction': 'PASS', 'annotation_semantic_consistency': 'PASS',
            'privacy_pattern_scan': 'PASS_NO_MATCHES',
            'independent_experiment_replication': False,
            'independent_physical_devices': 'UNKNOWN',
            'scope': 'exported observations and recorded annotation consistency; no original detector replay or independent experiment replication'}


def validate(package_root):
    """Validate the v1 package and exactly reproduce its exported statistics."""
    root = Path(package_root)
    contents = list(root.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in contents):
        raise ValueError('Package cannot contain subdirectories, symbolic links or special files')
    if {path.name for path in contents} != PACKAGE_FILES:
        raise ValueError('Unexpected or missing package file')
    manifest = read_json(root / 'manifest.json')
    schema = read_json(root / 'schema.json')
    definitions = schema.get('$defs') if isinstance(schema, dict) else None
    license_schema = manifest_license_schema()
    if not isinstance(definitions, dict) or definitions.get('reviewer_manifest_licensing') != license_schema:
        raise ValueError('Missing or weakened manifest license schema')
    validate_schema(manifest, definitions['reviewer_manifest_licensing'], schema)
    expected_manifest = {
        'release_records': 1509, 'publication_status': RELEASE_STATUS,
        'dataset_version': '1.0', 'data_license': DATA_LICENSE,
        'data_license_url': DATA_LICENSE_URL, 'data_license_file': 'LICENSE_DATA.md',
        'data_license_scope': sorted(DATA_LICENSE_FILES),
        'software_license': SOFTWARE_LICENSE, 'software_license_scope': sorted(SOFTWARE_FILES),
    }
    if any(manifest.get(key) != value for key, value in expected_manifest.items()):
        raise ValueError('Manifest version, scope, status or license mismatch')
    license_notice = (root / 'LICENSE_DATA.md').read_text(encoding='utf-8')
    if (not re.search(r'\bCreative\s+Commons\s+Attribution\s+4\.0\s+International\b', license_notice, re.I)
            or DATA_LICENSE not in license_notice or DATA_LICENSE_URL not in license_notice):
        raise ValueError('Data license notice must identify CC BY 4.0 and its official terms')
    unselected_data_license = (
        r'\bPENDING_(?:SELECTION|APPROVAL)\b',
        r'\b(?:data(?:set)?|reuse)[ -]?licen[cs]e\b[^\n.]{0,90}\b(?:pending|unselected|not (?:yet )?selected)\b',
        r'\bno\s+(?:data(?:set)?|reuse)[ -]?licen[cs]e\b[^\n.]{0,40}\b(?:selected|granted|applied)\b',
    )
    if any(re.search(pattern, license_notice, re.I) for pattern in unselected_data_license):
        raise ValueError('Data license notice still contains an unselected-license statement')
    inventory = manifest.get('file_inventory')
    if not isinstance(inventory, list) or any(not isinstance(entry, dict) or set(entry) != {'path', 'bytes'} for entry in inventory):
        raise ValueError('Manifest requires a path/byte-size package inventory')
    if len(inventory) != len(PACKAGE_FILES) - 1 or {entry['path'] for entry in inventory} != PACKAGE_FILES - {'manifest.json'}:
        raise ValueError('Manifest file membership mismatch')
    if any(type(entry['bytes']) is not int or entry['bytes'] != (root / entry['path']).stat().st_size for entry in inventory):
        raise ValueError('Manifest package file-size mismatch')
    tables = load_tables(root)
    report = validate_tables(tables, schema, read_json(root / 'field_catalog.json'))
    recalculated = compute_statistics(tables)
    if recalculated != read_json(root / 'statistics.json'):
        raise ValueError('Exported statistics do not exactly match recomputation')
    expected_counts = {'release_records': 1509, 'total_unique_observations': 1509,
                       'views': {'App177': 558, 'Paired244': 951},
                       'labels': {'modified': 170, 'normal_control': 442, 'no_effect': 6, 'unlabeled': 891},
                       'label_verification': {'verified_recorded_evidence': 618, 'unverified': 891},
                       'structurally_complete': 1506, 'structurally_incomplete': 3,
                       'relationships': {'experiment_triplet': 206, 'linked_app_browser': 951},
                       'supplemental_geometry_observations': 72}
    if any(recalculated[key] != value for key, value in expected_counts.items()):
        raise ValueError('Version 1 observation/label/relationship totals changed')
    if {key: value['records'] for key, value in recalculated['sources'].items()} != SOURCE_COUNTS:
        raise ValueError('Version 1 data source totals changed')
    if recalculated['sources']['mtc_historical_891']['historical_cohorts'] != {'discovery': 630, 'development': 144, 'reserved_validation': 117}:
        raise ValueError('Version 1 historical cohort totals changed')
    for row in tables['metadata.jsonl']:
        if not row['qc']['structurally_complete'] and (row['source_id'] != 'mtc_historical_891' or len(row['qc']['source_missing_fields']) != 5):
            raise ValueError('Version 1 original missingness changed')
    report.update(statistics_recomputed='PASS', release_records=1509,
                  publication_status=RELEASE_STATUS, version_1_counts='PASS',
                  package_file_inventory='PASS', data_license=DATA_LICENSE,
                  data_license_binding='PASS', software_license=SOFTWARE_LICENSE)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent,
                        help='Directory containing the four JSONL tables and contracts')
    parser.add_argument('--recompute-statistics', type=Path, metavar='OUTPUT',
                        help='Write independently recomputed exported statistics to a new file')
    args = parser.parse_args()
    try:
        report = validate(args.root)
        if args.recompute_statistics:
            output = args.recompute_statistics
            if output.resolve().parent == args.root.resolve():
                raise ValueError('Statistics output must be outside the package directory')
            if output.exists():
                raise ValueError('Statistics output must be a new file; existing files are preserved')
            output.write_text(json.dumps(compute_statistics(load_tables(args.root)), indent=2,
                                         sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n', encoding='utf-8')
            report['recomputed_statistics_written'] = True
        print(json.dumps(report, sort_keys=True))
    except (ValueError, KeyError, TypeError, OSError) as error:
        # File errors can include local usernames or directory names. Keep CLI
        # reports portable and do not echo data values or absolute file paths.
        reason = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(json.dumps({'status': 'FAIL', 'reason': reason}, sort_keys=True), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
