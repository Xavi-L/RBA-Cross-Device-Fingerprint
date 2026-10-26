"""Standard-library release contracts, conservative de-identification and validation."""
from __future__ import annotations
import copy
import hashlib
import json
import getpass
import math
import re
import uuid
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_LAYERS = ('android_native_data', 'webview_data', 'web_data')
BROWSER = 'browser_web_data'
COUNTS = dict(zip(APP_LAYERS, (84, 26, 67)))
STATES = {'observed', 'unsupported_by_os', 'permission_denied', 'runtime_error', 'timeout',
          'not_applicable', 'missing', 'unknown', 'present_status_unknown'}
LABELS = {'modified', 'normal_control', 'no_effect', 'unlabeled', 'unknown'}
# Exact timestamps, runtime clocks, infrastructure and free text are not release features.
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


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True, allow_nan=False) + '\n')


def write_jsonl(path, rows):
    Path(path).write_text(''.join(canonical(row) + '\n' for row in rows))


def read_jsonl(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def private_destination(path):
    path = Path(path).resolve()
    base = (ROOT / '.private').resolve()
    if path == base or base not in path.parents:
        raise ValueError('Candidate outputs must be below the local .private directory')
    return path


def flatten(value, prefix=''):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from flatten(child, f'{prefix}.{key}' if prefix else key)
    else:
        yield prefix, value


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


class RandomIDs:
    """Release-specific, random UUIDs. Mapping is private and reused for rebuilds."""
    def __init__(self, path):
        self.path = Path(path)
        self.mapping = json.loads(self.path.read_text()) if self.path.exists() else {}

    def get(self, namespace, key):
        if key is None:
            return None
        entries = self.mapping.setdefault(namespace, {})
        key = str(key)
        if key not in entries:
            entries[key] = f'{namespace}_{uuid.uuid4().hex}'
        return entries[key]

    def save(self):
        write_json(self.path, self.mapping)
        self.path.chmod(0o600)


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


def privacy_findings(value):
    """Bounded pattern scan; no matching sensitive values are returned."""
    patterns = {
        'email': r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',
        'ipv4': r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])',
        'home_path': r'/(?:Users|home)/[^\s/]+',
        'credential': r'(?i)(?:-----BEGIN .*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{15,}|sk-[A-Za-z0-9]{20,})',
        'source_identity_key': r'(?i)"(?:session_id|collector_install_id|device_manifest_id|android_id|serial_number|client_ip|pair_ticket|email|phone_number)"\s*:',
        'author_identity': r'(?i)\b'+re.escape(getpass.getuser())+r'\b',
        'exact_timestamp': r'\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
        'phone': r'(?<![A-Za-z0-9_])(?:\+86[- ]?)?1[3-9]\d{9}(?![A-Za-z0-9_])',
    }
    findings = Counter()
    # Numeric measurements cannot safely be classified as phones; only scan text leaves.
    def text_leaves(node):
        if isinstance(node,dict):
            for item in node.values():yield from text_leaves(item)
        elif isinstance(node,list):
            for item in node:yield from text_leaves(item)
        else:yield node
    for leaf in text_leaves(value):
        if isinstance(leaf,str):
            for name,pattern in patterns.items():
                if name != 'source_identity_key' and re.search(pattern,leaf):
                    findings[name]+=1
    if re.search(patterns['source_identity_key'], canonical(value)):
        findings['source_identity_key']+=1
    return dict(findings)
