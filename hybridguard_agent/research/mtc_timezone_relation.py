"""One fixed same-acquisition timezone relation, with pinned IANA interpretation.

Native rawOffset is never treated as a DST-aware offset. Source timestamps only
choose the IANA rule at acquisition; they are not independent model features.
"""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from functools import lru_cache
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo, _common, _zoneinfo

from .rule_learning.contracts import cell
from .rule_learning.models import Atom
from .rule_learning_v2.relations import fixed_offset, timezone_difference

VERSION = 'mtc-timezone-relation-v1'
TIMEZONE_ID = 'MTCREL:NATIVE_ZONE_AT_ACQUISITION_VS_WEB_OFFSET_DIFFERS'
NATIVE_ZONE = 'app.android_native_data.locale_timezone_layer.native_timezone_id'
NATIVE_RAW = 'app.android_native_data.locale_timezone_layer.native_timezone_offset_min'
WEB_OFFSET = 'app.web_data.execution_layer.timezone_offset'
WEB_ZONE = 'app.web_data.execution_layer.timezone_id'
FIELDS = (NATIVE_ZONE, NATIVE_RAW, WEB_OFFSET)
TIME_FIELDS = ('collection_manifest.collection_started_at_ms',
               'collection_diagnostics.collection_finished_at_ms')
TZDB_VERSION = '2026c'
DEFAULT_TZDB = '/usr/share/zoneinfo'


def parameters():
    return {'version': VERSION, 'fitted': False, 'parameter_fit_calls': 0,
            'tzdb_version': TZDB_VERSION, 'library': 'Python stdlib zoneinfo',
            'time_basis': list(TIME_FIELDS), 'time_unit': 'unix_epoch_milliseconds',
            'native_offset_unit': 'minutes_east_of_UTC_standard_only',
            'web_offset_unit': 'minutes_west_of_UTC_current',
            'comparison': 'exact_current_offset_difference',
            'missing_date_fallback': 'existing_fixed_offset_domain_only',
            'web_timezone_id': 'diagnostic_only_no_string_comparison',
            'crossing_offset_transition': 'U', 'learned_tolerance': None}


def registered_atoms():
    return (Atom(TIMEZONE_ID, 'MTC_TIMEZONE_RELATION', ('native84', 'app_web67'),
        ('RESEARCHER_PROPOSED_MTC_TIMEZONE_RELATION_V1',), (TIMEZONE_ID,),
        'CATALOG_CONDITION', {'field': NATIVE_ZONE, 'field_refs': list(FIELDS),
        'metadata_refs': list(TIME_FIELDS), 'relation_version': VERSION,
        'signal_group': 'timezone_semantics', 'condition': {
            'operator': 'NATIVE_ZONE_AT_ACQUISITION_VS_WEB_OFFSET_DIFFERS',
            'operands': list(FIELDS), 'parameters': parameters()},
        'basis': 'timezone_relation_validation_v1/SEMANTICS.md',
        'interpretation': 'research_relation_deviation_not_attack_truth'}),)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _minute(value):
    return _number(value) and value == int(value) and abs(value) < 1440


def _observed(record, field):
    return (field in record.get('features', {}) and
            record.get('field_status', {}).get(field) == 'observed' and
            record.get('field_quality', {}).get(field) == 'observed_value')


def tzdb_directory():
    """Require the frozen database version; never silently use host updates."""
    directory = Path(os.environ.get('HYBRIDGUARD_TZDB_DIR', DEFAULT_TZDB))
    version = (directory / '+VERSION').read_text().strip()
    if version != TZDB_VERSION:
        raise RuntimeError('TIMEZONE_DATABASE_VERSION_MISMATCH:' + version)
    return directory.resolve()


@lru_cache(maxsize=256)
def _load_zone(directory, key):
    if (not isinstance(key, str) or not key or key.startswith('/') or
            any(p in ('', '.', '..') for p in key.split('/'))):
        raise ValueError('INVALID_TIMEZONE_ID')
    path = Path(directory) / key
    # Legitimate IANA alias symlinks may resolve within the database tree.
    if not path.resolve().is_relative_to(Path(directory)):
        raise ValueError('INVALID_TIMEZONE_ID')
    with path.open('rb') as stream:
        zone = ZoneInfo.from_file(stream, key=key)
    with path.open('rb') as stream:
        data = _common.load_data(stream)
    tail = _zoneinfo._parse_tz_str(data[-1].decode()) if data[-1] else None
    return zone, data[1], tail


def _offset(zone, seconds):
    dt = datetime.fromtimestamp(seconds, timezone.utc).astimezone(zone)
    value = dt.utcoffset().total_seconds() / 60
    return value


def _interval_offset(zone, transitions, tail, start, finish):
    """Use CPython's TZif/POSIX-tail parsers; do not hand-code region rules.

    Checking only endpoints misses intervals spanning two seasonal changes.
    Inspect all database transition instants and its parsed future rule tail.
    """
    instants = [float(t) for t in transitions if start < t <= finish]
    first_year = datetime.fromtimestamp(start, timezone.utc).year
    last_year = datetime.fromtimestamp(finish, timezone.utc).year
    if tail is not None and hasattr(tail, 'transitions'):
        for year in range(max(1, first_year - 1), min(9999, last_year + 1) + 1):
            a, b = tail.transitions(year)
            candidates = (a - tail.std.utcoff.total_seconds(), b - tail.dst.utcoff.total_seconds())
            instants.extend(t for t in candidates if start < t <= finish
                            and (not transitions or t > transitions[-1]))
    observed = {_offset(zone, start), _offset(zone, finish)}
    for t in instants:
        observed.add(_offset(zone, max(start, t - 0.001)))
        observed.add(_offset(zone, t))
    return next(iter(observed)) if len(observed) == 1 else None


def evaluate(record):
    diagnostics = {'relation_version': VERSION, 'tzdb_version': TZDB_VERSION,
                   'fields': [], 'date_basis': None, 'expected_web_offset_min': None,
                   'native_effective_offset_min': None, 'native_raw_is_standard_only': True}
    def result(state, reason, category):
        return {TIMEZONE_ID: {**cell(state, reason), 'diagnostics': dict(
            diagnostics, availability_category=category)}}
    if not isinstance(record, dict):
        return result('FAILED', 'TIMEZONE_SOURCE_NOT_AN_OBJECT', 'binding_failure')
    binding = record.get('source_binding', {})
    if (record.get('status') != 'OK' or binding.get('binding_valid') is not True or
            binding.get('same_app_record') is not True or not binding.get('app_session_id')):
        return result('FAILED', 'TIMEZONE_SAME_APP_RECORD_BINDING_REQUIRED', 'binding_failure')
    for field in (*FIELDS, WEB_ZONE):
        diagnostics['fields'].append({'field': field, 'value': deepcopy(record.get('features', {}).get(field)),
            'value_present': field in record.get('features', {}),
            'source_status': record.get('field_status', {}).get(field),
            'source_quality': record.get('field_quality', {}).get(field)})
    for field in (NATIVE_ZONE, WEB_OFFSET):
        if not _observed(record, field):
            return result('U', 'TIMEZONE_OPERAND_MISSING_OR_QUALITY:' + field, 'missing_or_quality')
    native_id = record['features'][NATIVE_ZONE]
    web = record['features'][WEB_OFFSET]
    diagnostics.update(native_timezone_id=native_id, web_timezone_offset_min=web,
                       web_timezone_id=record['features'].get(WEB_ZONE),
                       native_standard_offset_min=record['features'].get(NATIVE_RAW))
    if not isinstance(native_id, str) or not native_id or not _minute(web):
        return result('U', 'TIMEZONE_OPERAND_INVALID_TYPE_OR_VALUE', 'invalid_type_or_value')
    fixed = fixed_offset(native_id)
    if fixed is not None:
        # Preserve the exact pre-existing fixed-zone applicability contract.
        raw = record['features'].get(NATIVE_RAW)
        value = timezone_difference(native_id, raw, web) if _observed(record, NATIVE_RAW) else None
        if value is None:
            return result('U', 'TIMEZONE_FIXED_NATIVE_RAW_INCONSISTENT_OR_UNAVAILABLE', 'quality_or_not_applicable')
        diagnostics.update(date_basis='existing_syntactically_fixed_zone_no_date_required',
                           native_effective_offset_min=fixed, expected_web_offset_min=-fixed)
        return result('T' if value else 'F', 'TIMEZONE_CURRENT_OFFSETS_DIFFER' if value else
                      'TIMEZONE_CURRENT_OFFSETS_MATCH', 'observed_comparable')
    time = record.get('acquisition_time', {})
    diagnostics['date_basis'] = deepcopy(time)
    if not isinstance(time, dict) or time.get('status') != 'observed_device_interval':
        return result('U', 'TIMEZONE_RELIABLE_DEVICE_DATE_INTERVAL_REQUIRED', 'missing_or_invalid_date')
    if time.get('session_id') != binding['app_session_id']:
        return result('FAILED', 'TIMEZONE_DATE_SESSION_BINDING_MISMATCH', 'binding_failure')
    start, finish = time.get('started_at_ms'), time.get('finished_at_ms')
    if (not _number(start) or not _number(finish) or start != int(start) or finish != int(finish)
            or start < 0 or finish < start):
        return result('U', 'TIMEZONE_INVALID_DEVICE_INTERVAL', 'missing_or_invalid_date')
    try:
        directory = tzdb_directory()
    except (OSError, RuntimeError) as exc:
        return result('FAILED', str(exc), 'runtime_dependency')
    try:
        zone, transitions, tail = _load_zone(str(directory), native_id)
    except (OSError, ValueError):
        return result('U', 'TIMEZONE_UNKNOWN_NATIVE_ZONE_IN_PINNED_DATABASE', 'unknown_zone')
    try:
        expected_native = _interval_offset(zone, transitions, tail, start / 1000, finish / 1000)
    except (ValueError, OverflowError, OSError):
        return result('U', 'TIMEZONE_INVALID_DEVICE_INTERVAL', 'missing_or_invalid_date')
    if expected_native is None:
        return result('U', 'TIMEZONE_DEVICE_INTERVAL_CROSSES_OFFSET_CHANGE', 'offset_transition')
    if not _minute(expected_native):
        return result('U', 'TIMEZONE_HISTORICAL_SUBMINUTE_OFFSET_NOT_COMPARABLE', 'not_applicable')
    expected = -expected_native
    diagnostics.update(native_effective_offset_min=expected_native, expected_web_offset_min=expected)
    return result('T' if web != expected else 'F', 'TIMEZONE_CURRENT_OFFSETS_DIFFER' if web != expected
                  else 'TIMEZONE_CURRENT_OFFSETS_MATCH', 'observed_comparable')
