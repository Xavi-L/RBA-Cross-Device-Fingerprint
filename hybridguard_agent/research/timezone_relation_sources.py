"""Explicit same-App time evidence for the timezone extension and new batch.

Old source contracts remain untouched. The added device interval is sidecar
metadata passed only to the timezone relation, never into old numeric features.
"""
from collections import defaultdict
from copy import deepcopy
import json
import math
from pathlib import Path

from . import mtc_relation_sources as original
from . import mtc_timezone_relation as relation

VERSION = 'timezone-relation-source-binding-v1'
ROOT = original.ROOT
RAW_MTC = ROOT / 'backend_server/collection_backups/mtc_final_20260922/sources/raw_expanded_payloads.jsonl'


def _time_evidence(payload, session, reference):
    manifest = payload.get('collection_manifest', {})
    diagnostics = payload.get('collection_diagnostics', {})
    start = manifest.get('collection_started_at_ms') if isinstance(manifest, dict) else None
    finish = diagnostics.get('collection_finished_at_ms') if isinstance(diagnostics, dict) else None
    timestamp = payload.get('timestamp')
    evidence = {'status': 'unavailable_device_interval', 'session_id': session,
        'started_at_ms': deepcopy(start), 'finished_at_ms': deepcopy(finish),
        'payload_timestamp_seconds': deepcopy(timestamp), 'source_reference': reference,
        'source_fields': list(relation.TIME_FIELDS), 'unit': 'unix_epoch_milliseconds',
        'scope': 'device_range_encloses_Native_then_Web_reads_not_exact_synchrony',
        'payload_timestamp_use': 'consistency_check_only_never_date_fallback'}
    valid = lambda x: type(x) in (int, float) and math.isfinite(x) and x == int(x) and x >= 0
    if not valid(start) or not valid(finish) or finish < start:
        evidence['reason'] = 'MISSING_OR_INVALID_DEVICE_RANGE'
    elif timestamp is not None and (not valid(timestamp) or not (start // 1000 <= timestamp <= finish // 1000)):
        evidence['reason'] = 'DEVICE_RANGE_PAYLOAD_SECONDS_INCONSISTENT'
    else:
        evidence.update(status='observed_device_interval', reason='KNOWN_COLLECTOR_DEVICE_BRACKETING')
    return evidence


def _attach(bound, raw_record, reference):
    bound = deepcopy(bound)
    if bound.get('status') != 'OK':
        return bound
    binding = bound['source_binding']
    session = binding.get('app_session_id')
    raw_record = raw_record if isinstance(raw_record, dict) else {}
    payload = raw_record.get('canonical_received_payload')
    errors = []
    if not isinstance(payload, dict):
        errors.append('TIMEZONE_RAW_PAYLOAD_NOT_AN_OBJECT')
        payload = {}
    manifest = payload.get('collection_manifest', {})
    if not isinstance(manifest, dict):
        manifest = {}
    if (raw_record.get('session_id') != session or payload.get('session_id') != session):
        errors.append('TIMEZONE_RAW_APP_SESSION_BINDING_MISMATCH')
    if (raw_record.get('raw_payload_archive_schema_version') != 'expanded-raw-payload-v1' or
            payload.get('schema_version') != 'expanded-v2.2-status' or payload.get('collector_app') != 'featureapp'):
        errors.append('TIMEZONE_UNSUPPORTED_RAW_APP_CONTRACT')
    if manifest.get('collector_version_code') != binding.get('collector_version_code'):
        errors.append('TIMEZONE_RAW_COLLECTOR_VERSION_MISMATCH')
    if binding.get('payload_id') is not None and raw_record.get('payload_sha256') != binding['payload_id']:
        errors.append('TIMEZONE_RAW_PAYLOAD_REFERENCE_MISMATCH')
    errors.extend(original._field_sessions(payload, session))
    flattened = {}
    for name in original.APP_ROOTS:
        if isinstance(payload.get(name), dict):
            flattened.update(original._flatten(payload[name], 'app.' + name))
    # Existing P1 projections must retain the actual same-App operands. No
    # labels, other-record values, Browser values, or temporal imputation.
    for field in (*relation.FIELDS, relation.WEB_ZONE):
        if (field in flattened) != (field in bound['features']) or flattened.get(field) != bound['features'].get(field):
            errors.append('TIMEZONE_RAW_OPERAND_BINDING_MISMATCH:' + field)
    if errors:
        return original._result({**binding, 'timezone_binding_version': VERSION}, errors=errors)
    bound['source_binding'].update(timezone_binding_version=VERSION, timezone_raw_reference=reference)
    bound['acquisition_time'] = _time_evidence(payload, session, reference)
    return bound


def load_controlled_sources(sample_ids, *, allowed_ids, repo_root=None, prepared_dir=None):
    ids = original._allowed(sample_ids, allowed_ids)
    root = Path(repo_root or ROOT).resolve()
    result = original.load_controlled_sources(ids, allowed_ids=allowed_ids,
                repo_root=root, prepared_dir=prepared_dir)
    groups = defaultdict(list)
    for sid, bound in result.items():
        if bound['status'] == 'OK':
            path, line = bound['source_binding']['raw_reference'].rsplit(':', 1)
            groups[root / path].append(sid)
    for path, members in groups.items():
        sessions = {result[s]['source_binding']['app_session_id'] for s in members}
        try:
            rows = original._archive_selected(path, sessions)
        except (OSError, UnicodeError) as exc:
            for sid in members:
                result[sid] = original._result(result[sid]['source_binding'],
                    errors=['TIMEZONE_RAW_SOURCE_UNREADABLE:' + type(exc).__name__])
            continue
        for sid in members:
            bound = result[sid]
            rows_for_session = rows.get(bound['source_binding']['app_session_id'], [])
            if len(rows_for_session) != 1 or rows_for_session[0][1] is None:
                result[sid] = original._result(bound['source_binding'], errors=['TIMEZONE_RAW_SESSION_NOT_UNIQUE_OR_MISSING'])
            else:
                result[sid] = _attach(bound, rows_for_session[0][1], bound['source_binding']['raw_reference'])
    return result


def bind_mtc_observation(observation, expected_sample_id, *, allowed_ids, expected_registry,
                         raw_record, raw_reference=None):
    bound = original.bind_mtc_observation(observation, expected_sample_id,
                allowed_ids=allowed_ids, expected_registry=expected_registry)
    return _attach(bound, raw_record, raw_reference)


def load_mtc_sources(observations, index, sample_ids, *, allowed_ids, raw_path=None):
    """Mappings are {ID: historical P1 observation}, {ID: P2 registry row}."""
    ids = original._allowed(sample_ids, allowed_ids)
    path = Path(raw_path or RAW_MTC)
    by_line = defaultdict(list)
    result = {}
    for sid in ids:
        observation, registry = observations.get(sid), index.get(sid)
        if not isinstance(registry, dict) or type(registry.get('app_raw_line')) is not int:
            result[sid] = original._result({'sample_id': sid}, errors=['TIMEZONE_MTC_REGISTRY_REFERENCE_MISSING'])
        else:
            by_line[registry['app_raw_line']].append(sid)
    try:
        with path.open('rb') as stream:
            for number, line in enumerate(stream, 1):
                if number not in by_line:
                    continue
                try:
                    raw = json.loads(line)
                except (ValueError, UnicodeError):
                    raw = None
                reference = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
                for sid in by_line[number]:
                    result[sid] = bind_mtc_observation(observations.get(sid), sid,
                        allowed_ids=allowed_ids, expected_registry=index[sid], raw_record=raw,
                        raw_reference=reference + ':' + str(number))
    except OSError as exc:
        for sid in ids:
            if sid not in result:
                result[sid] = original._result({'sample_id': sid}, errors=['TIMEZONE_RAW_SOURCE_UNREADABLE:' + type(exc).__name__])
    for sid in ids:
        if sid not in result:
            result[sid] = original._result({'sample_id': sid}, errors=['TIMEZONE_RAW_LINE_MISSING'])
    return {sid: result[sid] for sid in ids}


def bind_timezone_batch(raw, *, session_id, source_reference, environment_id):
    """New v14 timezone batch; no old cohort ID/version/path restrictions removed."""
    binding = {'sample_id': 'timezoneonly-' + session_id, 'app_session_id': session_id,
               'mode': VERSION, 'raw_reference': source_reference}
    errors = []
    if not isinstance(raw, dict):
        return original._result(binding, errors=['TIMEZONE_RAW_ROW_NOT_OBJECT'])
    payload = raw.get('canonical_received_payload')
    if not isinstance(payload, dict):
        return original._result(binding, errors=['TIMEZONE_RAW_PAYLOAD_NOT_OBJECT'])
    manifest = payload.get('collection_manifest', {})
    if not isinstance(manifest, dict):
        manifest = {}
    if (not session_id or raw.get('session_id') != session_id or payload.get('session_id') != session_id):
        errors.append('TIMEZONE_CURRENT_APP_SESSION_MISMATCH')
    if (raw.get('raw_payload_archive_schema_version') != 'expanded-raw-payload-v1' or
            payload.get('schema_version') != 'expanded-v2.2-status' or payload.get('collector_app') != 'featureapp' or
            type(manifest.get('collector_version_code')) is not int or manifest['collector_version_code'] != 14):
        errors.append('TIMEZONE_UNSUPPORTED_BATCH_COLLECTOR')
    if not environment_id or manifest.get('device_manifest_id') != environment_id:
        errors.append('TIMEZONE_CURRENT_APP_ENVIRONMENT_MISMATCH')
    errors.extend(original._field_sessions(payload, session_id))
    features = {}
    for name in original.APP_ROOTS:
        if name in payload:
            if not isinstance(payload[name], dict):
                errors.append('TIMEZONE_APP_SURFACE_NOT_OBJECT:' + name)
            else:
                features.update(original._flatten(payload[name], 'app.' + name))
    statuses = payload.get('collection_status', {})
    if not isinstance(statuses, dict) or not isinstance(statuses.get('fields'), dict):
        errors.append('TIMEZONE_FIELD_STATUS_MISSING')
        statuses = {}
    else:
        statuses = {'app.' + k: v for k, v in statuses['fields'].items()
            if isinstance(k, str) and k.startswith(tuple(n + '.' for n in original.APP_ROOTS))}
    qualities = {k: original._quality(k, features.get(k), v) for k, v in statuses.items()}
    binding.update(collector_version_code=manifest.get('collector_version_code'),
        collector_version_name=manifest.get('collector_version_name'), receipt_id=raw.get('receipt_id'),
        payload_id=raw.get('payload_sha256'))
    bound = original._result(binding, features, statuses, qualities, errors)
    return _attach(bound, raw, source_reference)
