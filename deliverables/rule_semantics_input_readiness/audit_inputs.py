#!/usr/bin/env python3
"""Exact-ID, read-only input audit. Never executes a candidate or old extractor.

Only the authoritative supervised_ids may be loaded. A transferred payload and
its external provenance/binding are separate; neither is a semantic result.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.rule_semantics_input_readiness import (
    MODES, inspect_inputs, project_payload, readiness, make_source_binding,
)

MISSING = object()
SECTIONS = ('features', 'field_status', 'field_quality')
LANG = 'app.web_data.navigator_layer.language'
LANGS = 'app.web_data.navigator_layer.languages'
WD = 'app.web_data.automation_surface_layer.webdriver'
MODE_FIELDS = {'LANGUAGE': (LANG, LANGS), 'WEBDRIVER_LEGACY': (WD,), 'WEBDRIVER_RAW': ()}


class AuditError(ValueError):
    def __init__(self, reason, source_status='UNRESOLVED'):
        super().__init__(reason)
        self.reason, self.source_status = reason, source_status


def same_value(left, right):
    """Type- and order-sensitive equality of a field with its own prior version."""
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(same_value(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same_value(left[k], right[k]) for k in left)
    return left == right


def at_path(data, path):
    for key in path.split('.'):
        if not isinstance(data, dict) or key not in data:
            return MISSING
        data = data[key]
    return data


def parse_ref(ref, selector):
    if not isinstance(ref, str) or '#' + selector + '=' not in ref:
        raise AuditError('INVALID_' + selector.upper() + '_REFERENCE')
    path, value = ref.rsplit('#' + selector + '=', 1)
    if not path or not value:
        raise AuditError('EMPTY_REFERENCE')
    return path, value


class InputAudit:
    def __init__(self, root=ROOT, contract=None, registrations=None):
        self.root = Path(root).resolve()
        self.contract = contract or json.loads((HERE / 'AUDIT_CONTRACT.json').read_text())
        self.registrations = registrations or json.loads((HERE / 'SOURCE_BINDINGS.json').read_text())
        self._json_cache, self._line_cache = {}, {}
        self.authority = self.read_json(self.contract['authority'])
        ids = self.authority.get(self.contract['scope_key'], [])
        if not isinstance(ids, list):
            raise AuditError('AUTHORITY_IDS_NOT_ARRAY')
        self.ids = ids
        self.id_set = {x for x in ids if isinstance(x, str)}
        self.scope_issues = []
        if len(ids) != self.contract['expected_denominator']:
            self.scope_issues.append('AUTHORITY_COUNT_MISMATCH')
        if len(self.id_set) != len(ids):
            self.scope_issues.append('AUTHORITY_DUPLICATE_OR_NONSTRING_ID')
        self.index_ref = self.authority.get('source_index')
        if self.index_ref != self.contract['source_index']:
            self.scope_issues.append('AUTHORITY_SOURCE_INDEX_DIFFERS_FROM_SAVED_CONTRACT')
        try:
            self.index = self.read_json(self.index_ref)
        except AuditError:
            self.index = {}
            self.scope_issues.append('SOURCE_INDEX_UNAVAILABLE')
        self.raw_groups = {}
        for group in self.registrations['groups']:
            for path in group['raw_paths']:
                if path in self.raw_groups:
                    raise AuditError('SOURCE_REGISTRY_DUPLICATE_RAW_PATH', 'CONFLICT')
                self.raw_groups[path] = group

    def path(self, ref):
        if not isinstance(ref, str):
            raise AuditError('NONSTRING_PATH')
        p = (self.root / ref).resolve()
        if not p.is_relative_to(self.root):
            raise AuditError('REFERENCE_OUTSIDE_REPOSITORY')
        return p

    def read_json(self, ref):
        if ref not in self._json_cache:
            try:
                self._json_cache[ref] = json.loads(self.path(ref).read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                raise AuditError('JSON_UNAVAILABLE:' + str(ref)) from exc
        data = self._json_cache[ref]
        if not isinstance(data, dict):
            raise AuditError('JSON_OBJECT_REQUIRED:' + str(ref))
        return data

    def lines(self, ref):
        if ref not in self._line_cache:
            try:
                self._line_cache[ref] = self.path(ref).read_text(encoding='utf-8').splitlines()
            except OSError as exc:
                raise AuditError('JSONL_FILE_UNAVAILABLE:' + ref) from exc
        return self._line_cache[ref]

    def line_record(self, ref, line):
        try:
            n = int(line)
            if n < 1:
                raise ValueError('line')
            data = json.loads(self.lines(ref)[n - 1])
            if not isinstance(data, dict):
                raise ValueError('object')
            return data
        except (ValueError, IndexError) as exc:
            raise AuditError('JSONL_TARGET_LINE_INVALID:' + ref + '#line=' + str(line)) from exc

    def find_record(self, ref, key, expected):
        matches, damaged = [], []
        for n, line in enumerate(self.lines(ref), 1):
            try:
                row = json.loads(line)
            except ValueError:
                damaged.append(n)
                continue
            # For all non-target rows only this identity key is inspected.
            if isinstance(row, dict) and row.get(key) == expected:
                matches.append((n, row))
        if not matches:
            raise AuditError('EXACT_SOURCE_ID_NOT_FOUND:' + ref + (':DAMAGED_LINES' if damaged else ''))
        if len(matches) > 1:
            if any(not same_value(matches[0][1], row) for _, row in matches[1:]):
                raise AuditError('CONFLICTING_DUPLICATE_SOURCE:' + ref, 'CONFLICT')
            raise AuditError('DUPLICATE_IDENTICAL_SOURCE_REQUIRES_EXPLICIT_RESOLUTION:' + ref)
        # An unparseable line could contain a conflicting same-ID row.
        if damaged:
            raise AuditError('UNPARSEABLE_SOURCE_LINES:' + ref)
        return matches[0]

    def resolve(self, sample_id):
        self._partial = {'source_refs': {}}
        if sample_id not in self.id_set:
            raise AuditError('OUTSIDE_AUTHORIZED_SUPERVISED_IDS')
        entry = self.index.get(sample_id)
        if not isinstance(entry, dict):
            raise AuditError('INDEX_ENTRY_MISSING')
        index_dir = str(Path(self.index_ref).parent)
        cache_ref = str(Path(index_dir) / entry.get('features', 'MISSING'))
        evaluation_ref = str(Path(index_dir) / entry.get('evaluation', 'MISSING'))
        cache = self.read_json(cache_ref)
        if cache.get('opaque_id') != sample_id:
            raise AuditError('R04_RECORD_IDENTITY_CONFLICT', 'CONFLICT')
        lineage_ref = str(Path(index_dir) / cache.get('cache_lineage_ref', 'MISSING'))
        lineage = self.read_json(lineage_ref)
        manifest_ref = lineage.get('input_manifest_ref')
        manifest_line, manifest = self.find_record(manifest_ref, 'opaque_id', sample_id)
        input_file, input_line = parse_ref(manifest.get('input_ref'), 'line')
        input_ref = str(Path(manifest_ref).parent / input_file)
        inference = self.line_record(input_ref, input_line)
        if inference.get('opaque_id') != sample_id:
            raise AuditError('INFERENCE_IDENTITY_CONFLICT', 'CONFLICT')
        payload = inference.get('payload')
        if not isinstance(payload, dict):
            raise AuditError('ADAPTED_PAYLOAD_NOT_OBJECT')
        self._partial.update(payload=payload, source_refs={'encoded_cache': cache_ref,
            'cache_lineage': lineage_ref, 'input_manifest': manifest_ref + '#line=' + str(manifest_line),
            'adapted_input': input_ref + '#line=' + input_line})
        evaluation = self.read_json(evaluation_ref)
        if evaluation.get('opaque_id') != sample_id:
            raise AuditError('R04_RECORD_IDENTITY_CONFLICT', 'CONFLICT')
        if evaluation.get('S02_input_ref') != input_ref + '#line=' + input_line:
            raise AuditError('EVALUATION_INPUT_REFERENCE_CONFLICT', 'CONFLICT')
        if manifest.get('candidate_id') != evaluation.get('candidate_id'):
            raise AuditError('CANDIDATE_IDENTITY_REFERENCE_CONFLICT', 'CONFLICT')
        raw_relative, session_id = parse_ref(manifest.get('source_raw_ref'), 'session_id')
        raw_ref = str(Path(self.contract['raw_reference_root']) / raw_relative)
        raw_line, raw = self.find_record(raw_ref, 'session_id', session_id)
        binding = manifest.get('source_payload_binding', {})
        if (evaluation.get('session_id') != session_id or
                binding.get('raw_session_ref') != manifest['source_raw_ref'] or
                binding.get('raw_line') != raw_line):
            raise AuditError('RAW_SESSION_REFERENCE_CONFLICT', 'CONFLICT')
        if binding.get('status') != 'BOUND':
            raise AuditError('EXISTING_PAYLOAD_BINDING_NOT_BOUND')
        if binding.get('duplicate_session_other_bundles'):
            raise AuditError('OTHER_REGISTERED_RAW_SOURCES_REQUIRE_RESOLUTION')
        group = self.raw_groups.get(raw_ref)
        if group is None:
            raise AuditError('SOURCE_GROUP_NOT_REGISTERED')
        run = self.read_json(group['paired_run_ref'])
        sessions = [r for r in run.get('sessions', []) if r.get('session_id') == session_id]
        if len(sessions) != 1:
            raise AuditError('PAIRED_RUN_SESSION_NOT_UNIQUE')
        if not same_value(run.get('featureapp'), group['featureapp_registration']):
            raise AuditError('BUILD_REGISTRATION_CONFLICT', 'CONFLICT')
        if any(not same_value(at_path(raw, key), value) for key, value in group['raw_metadata_requirements'].items()):
            raise AuditError('RAW_COLLECTION_METADATA_CONFLICT', 'CONFLICT')
        session = sessions[0]
        # Saved session metadata, not intervention roles or verification labels.
        for session_key, raw_key in group.get('session_metadata_links', {}).items():
            if session_key not in session or not same_value(session[session_key], at_path(raw, raw_key)):
                raise AuditError('RUN_SESSION_METADATA_CONFLICT:' + session_key, 'CONFLICT')
        for left, right in group.get('raw_metadata_links', []):
            if at_path(raw, left) is MISSING or not same_value(at_path(raw, left), at_path(raw, right)):
                raise AuditError('RAW_METADATA_LINK_CONFLICT:' + left, 'CONFLICT')
        if payload.get('record_schema_version') != 'hybridguard-mtc-observation-v2' or payload.get('adapter_version') != 'app177-triplet-adapter-v1':
            raise AuditError('ADAPTER_VERSION_CONFLICT', 'CONFLICT')
        refs = {'index': self.index_ref + '#' + sample_id, 'encoded_cache': cache_ref,
                'evaluation_metadata': evaluation_ref, 'cache_lineage': lineage_ref,
                'input_manifest': manifest_ref + '#line=' + str(manifest_line),
                'adapted_input': input_ref + '#line=' + input_line,
                'raw_input': raw_ref + '#session_id=' + session_id, 'raw_line': raw_line,
                'paired_run': group['paired_run_ref'] + '#session_id=' + session_id}
        return payload, raw, group, refs, evaluation

    def field_preservation(self, payload, raw, field):
        logical = self.contract['mapping'][field]
        alias = 'web_data.' + logical.rsplit('.', 1)[-1]
        values = [(p, at_path(raw, p)) for p in (logical, alias)]
        present = [(p, v) for p, v in values if v is not MISSING]
        states = at_path(raw, 'collection_status.fields')
        states = states if isinstance(states, dict) else {}
        state_entries = [(p, states[p]) for p in (logical, alias) if p in states]
        checks = {'value_present_upstream': bool(present), 'status_present_upstream': bool(state_entries)}
        checks['value_aliases_consistent'] = len(present) < 2 or same_value(present[0][1], present[1][1])
        checks['status_aliases_consistent'] = len(state_entries) < 2 or same_value(state_entries[0][1], state_entries[1][1])
        value = present[0][1] if present else MISSING
        status = state_entries[0][1] if state_entries else MISSING
        def retained(section):
            values = payload.get(section)
            return values.get(field, MISSING) if isinstance(values, dict) else MISSING
        old_value, old_status, old_quality = (retained(section) for section in SECTIONS)
        checks['raw_value_type_and_order_retained'] = value is not MISSING and same_value(value, old_value)
        checks['raw_status_retained'] = status is not MISSING and same_value(status, old_status)
        # This is the old registered quality mapping, not new candidate logic.
        expected_quality = 'observed_value' if status == 'observed' else 'source_unavailable'
        checks['registered_quality_derivation_matches'] = status is not MISSING and same_value(old_quality, expected_quality)
        conflicts = (not checks['value_aliases_consistent'] or not checks['status_aliases_consistent'] or
            value is not MISSING and old_value is not MISSING and not same_value(value, old_value) or
            status is not MISSING and old_status is not MISSING and not same_value(status, old_status) or
            status is not MISSING and old_quality is not MISSING and not same_value(old_quality, expected_quality))
        return {'raw_value_paths': [p for p, _ in present], 'raw_status_paths': [p for p, _ in state_entries],
                'quality_origin': 'S02_ADAPTER_DERIVED_NOT_RAW_COLLECTED',
                'checks': checks, 'pass': all(checks.values()), 'conflict': bool(conflicts),
                'upstream_missing': not present or not state_entries}

    def inspect(self, sample_id):
        row = {'opaque_id': sample_id, 'source_refs': {}, 'modes': {},
               'candidate_evaluation_performed': False}
        try:
            payload, raw, group, refs, evaluation = self.resolve(sample_id)
        except (AuditError, OSError, KeyError, TypeError, ValueError) as exc:
            reason = exc.reason if isinstance(exc, AuditError) else 'MALFORMED_SOURCE:' + type(exc).__name__
            source_status = exc.source_status if isinstance(exc, AuditError) else 'UNRESOLVED'
            partial = getattr(self, '_partial', {})
            row['source_refs'] = partial.get('source_refs', {})
            row['resolution_incomplete'] = True
            payload = partial.get('payload')
            for mode in MODES:
                result = inspect_inputs(payload or {}, mode)
                row['modes'][mode] = {**result, 'source_status': source_status,
                    'readiness': 'BLOCKED', 'reasons': [reason] + result['reasons'], 'binding_constructible': False}
            return row, payload, None
        row.update(source_group_id=group['source_group_id'], source_refs=refs)
        preservation = {field: self.field_preservation(payload, raw, field) for field in (LANG, LANGS, WD)}
        row['upstream_preservation'] = preservation
        # Independent raw object, if actually saved, is transferred explicitly.
        raw_object = at_path(raw, 'web_data.automation_surface_layer.webdriver_observation')
        source_payload = deepcopy(payload)
        if raw_object is not MISSING:
            source_payload['web_data'] = {'automation_surface_layer': {'webdriver_observation': deepcopy(raw_object)}}
        for mode in MODES:
            result = inspect_inputs(source_payload, mode)
            source_status = group['modes'][mode]['source_status']
            reasons = list(result.get('reasons', []))
            relevant = MODE_FIELDS[mode]
            for field in relevant:
                if preservation[field]['conflict']:
                    source_status = 'CONFLICT'
                    reasons.append('UPSTREAM_ADAPTED_PRESERVATION_CONFLICT:' + field)
                elif preservation[field]['upstream_missing']:
                    if source_status != 'CONFLICT':
                        source_status = 'UNRESOLVED'
                    reasons.append('UPSTREAM_VALUE_OR_STATE_MISSING:' + field)
                elif not preservation[field]['pass']:
                    reasons.append('ADAPTED_VALUE_OR_STATE_MISSING_OR_MALFORMED:' + field)
            transfer_ok = False
            try:
                minimal = project_payload(source_payload, mode)
                transfer_ok = all(
                    same_value(source_payload.get(section, {}).get(field, MISSING),
                               minimal.get(section, {}).get(field, MISSING))
                    for section in SECTIONS for field in relevant)
                if mode == 'WEBDRIVER_RAW':
                    projected = at_path(minimal, 'web_data.automation_surface_layer.webdriver_observation')
                    transfer_ok = raw_object is MISSING and projected is MISSING or (
                        isinstance(raw_object, dict) and isinstance(projected, dict) and
                        all(k in raw_object and same_value(v, raw_object[k]) for k, v in projected.items()))
            except ValueError:
                reasons.append('TRANSFER_INPUT_STRUCTURE_INVALID')
            if not transfer_ok:
                reasons.append('TRANSFER_CONSISTENCY_FAILED')
            status = readiness(source_status, result['input_status']) if transfer_ok else 'BLOCKED'
            effective = deepcopy(group)
            effective['modes'][mode]['source_status'] = source_status
            binding = make_source_binding(effective, mode)
            row['modes'][mode] = {**result, 'source_status': source_status, 'readiness': status,
                'reasons': list(dict.fromkeys(reasons)), 'transfer_consistent': transfer_ok,
                'binding_constructible': binding is not None}
        # Only now join evaluation-side descriptive metadata; never passed to inspection/binding.
        row['post_decision_strata'] = {k: evaluation.get(k, 'NOT_RECORDED') for k in
            ('phase', 'config_id', 'environment_group_id')}
        row['post_decision_strata']['source_bundle'] = group['source_group_id']
        row['post_decision_strata']['collector_build'] = str(group['featureapp_registration'].get('app_version_name', 'NOT_RECORDED'))
        row['raw_observation_object_present'] = raw_object is not MISSING
        return row, source_payload, group

    def load_input(self, sample_id, mode):
        """Reusable in-memory loader: returns no semantic result and never calls a candidate."""
        if mode not in MODES:
            raise ValueError('UNKNOWN_MODE')
        if sample_id not in self.id_set:
            raise AuditError('OUTSIDE_AUTHORIZED_SUPERVISED_IDS')
        row, source_payload, group = self.inspect(sample_id)
        if source_payload is None:
            return {'payload': None, 'source_binding': None, 'audit': row['modes'][mode], 'source_refs': row['source_refs']}
        effective = deepcopy(group) if group else None
        if effective:
            effective['modes'][mode]['source_status'] = row['modes'][mode]['source_status']
        return {'payload': project_payload(source_payload, mode),
                'source_binding': make_source_binding(effective, mode),
                'audit': row['modes'][mode], 'source_refs': row['source_refs']}

    def run(self):
        records = []
        for position, sample_id in enumerate(self.ids):
            if not isinstance(sample_id, str) or self.ids.count(sample_id) != 1:
                row = {'opaque_id': sample_id, 'authority_position': position, 'source_refs': {},
                    'candidate_evaluation_performed': False, 'modes': {mode: {
                        'source_status': 'CONFLICT', 'input_status': 'MISSING', 'readiness': 'BLOCKED',
                        'reasons': ['AUTHORITY_ID_NOT_UNIQUE_STRING'], 'binding_constructible': False}
                        for mode in MODES}}
            else:
                row, _, _ = self.inspect(sample_id)
            records.append(row)
        counts = {}
        for mode in MODES:
            results = [r['modes'][mode] for r in records]
            domains = {'source_status': ('SUPPORTED_BY_EXISTING_LINEAGE', 'CONDITIONAL_ASSUMPTION', 'UNRESOLVED', 'CONFLICT'),
                'input_status': ('COMPLETE', 'MISSING', 'LOSSY', 'MALFORMED'),
                'readiness': ('READY', 'CONDITIONAL', 'BLOCKED')}
            counts[mode] = {key: {state: sum(x[key] == state for x in results) for state in states}
                for key, states in domains.items()}
            counts[mode]['reason_counts_nonexclusive'] = dict(Counter(reason for x in results for reason in set(x['reasons'])))
            counts[mode]['transfer_consistent'] = sum(x.get('transfer_consistent') is True for x in results)
            counts[mode]['binding_constructible'] = sum(x['binding_constructible'] for x in results)
            counts[mode]['retained_field_availability'] = {field: dict(Counter(
                x.get('availability', {}).get(field, 'UNKNOWN') for x in results)) for field in MODE_FIELDS[mode]}
        strata = {}
        for dimension in ('phase', 'config_id', 'environment_group_id', 'collector_build', 'source_bundle'):
            buckets = defaultdict(list)
            for row in records:
                buckets[str(row.get('post_decision_strata', {}).get(dimension, 'NOT_RECORDED'))].append(row)
            strata[dimension] = {key: {'n': len(rows), 'modes': {mode: dict(Counter(r['modes'][mode]['readiness'] for r in rows))
                for mode in MODES}} for key, rows in sorted(buckets.items())}
        incomplete = any(not r.get('source_refs') or r.get('resolution_incomplete') for r in records)
        summary = {'schema_version': 'rsr-input-readiness-summary-v1',
            'audit_execution': 'PARTIAL' if self.scope_issues or incomplete else 'COMPLETE',
            'authority_ref': self.contract['authority'], 'expected_denominator': self.contract['expected_denominator'],
            'authority_entries': len(self.ids), 'unique_ids': len(self.id_set),
            'source_index_entries': len(self.index), 'scope_issues': self.scope_issues,
            'record_count': len(records), 'modes': counts, 'post_decision_strata': strata,
            'saved_raw_observation_objects': sum(r.get('raw_observation_object_present') is True for r in records),
            'strata_do_not_change_decisions': True,
            'evaluation_metadata_exposure': 'R04 evaluation records containing historical labels were read for exact references. Decisions do not accept labels/phase/config/tool/predictions; this is already exposed development material.',
            'execution_counts': {'real_fit': 0, 'model_predictions': 0, 'real_new_candidate_evaluations': 0, 'new_collections': 0},
            'limits': ['Input readiness only, no candidate state distribution or performance metrics.',
                       'Existing source registration is association evidence, not binary attestation or genuine-value proof.',
                       'Counts of reasons overlap; use readiness counts for mutually exclusive denominators.']}
        for mode, key in [('LANGUAGE', 'language_readiness'), ('WEBDRIVER_LEGACY', 'webdriver_legacy_readiness'),
                          ('WEBDRIVER_RAW', 'webdriver_raw_readiness')]:
            n = counts[mode]['readiness'].get('READY', 0)
            summary[key] = 'READY' if n == self.contract['expected_denominator'] and not self.scope_issues else 'PARTIALLY_READY' if n else 'BLOCKED'
        return {'summary': summary, 'records': records}


def load_input(sample_id, mode, *, root=ROOT):
    return InputAudit(root=root).load_input(sample_id, mode)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, help='Exclusively create two new reports; never overwrite.')
    args = parser.parse_args(argv)
    result = InputAudit().run()
    if args.output_dir is not None:
        targets = [args.output_dir / 'INPUT_MANIFEST.jsonl', args.output_dir / 'SUMMARY.json']
        if any(p.exists() or p.is_symlink() for p in targets):
            parser.error('REFUSE_EXISTING_REPORT: ' + str(args.output_dir))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        with targets[0].open('x', encoding='utf-8') as f:
            for row in result['records']:
                f.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
        with targets[1].open('x', encoding='utf-8') as f:
            f.write(json.dumps(result['summary'], ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result if args.output_dir is None else result['summary'], ensure_ascii=False, indent=2))
    return 0 if result['summary']['audit_execution'] == 'COMPLETE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
