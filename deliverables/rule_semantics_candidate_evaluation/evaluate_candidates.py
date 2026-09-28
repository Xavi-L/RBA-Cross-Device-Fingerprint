#!/usr/bin/env python3
"""Fixed 162-record execution; saved-result analysis is a separate command.

Only two approved callables, one explicit webdriver legacy mode, no learner or
model entry point. Historical references are reused single-literal cache cells.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from deliverables.rule_semantics_input_readiness.audit_inputs import InputAudit
from hybridguard_agent.research.rule_semantics_revision_v1 import (
    web_language_first_difference, webdriver_reported_state,
)

STATES = ('T', 'F', 'U', 'FAILED')
PHASES = ('clean_pre', 'attack', 'clean_post')
LANG_ID = 'RSR-LANG-FIRST-v1'
WD_ID = 'RSR-WEBDRIVER-STATE-v1'
REFERENCE_IDS = ('REFERENCE_LANG_LENGTH_GT1', 'REFERENCE_WEBDRIVER_STRICT_TRUE')
REFERENCE_CLAUSES = {
    REFERENCE_IDS[0]: ('CONTROL:app.web_data.navigator_layer.languages:LE:1.0', 'NEGATIVE'),
    REFERENCE_IDS[1]: ('CONTROL:app.web_data.automation_surface_layer.webdriver:EQ:True', 'POSITIVE'),
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write_json_new(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def validate_result_keys(rows, sample_ids, candidates):
    expected = {(sid, c['candidate_id'], c['mode']) for sid in sample_ids for c in candidates}
    keys = [(r['opaque_id'], r['candidate_id'], r['mode']) for r in rows]
    if len(sample_ids) != len(set(sample_ids)) or len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('RESULT_KEYS_MISSING_DUPLICATED_OR_OUTSIDE_SCOPE')
    if any(r['state'] not in STATES for r in rows):
        raise ValueError('INVALID_RESULT_STATE')


def validate_reference_keys(rows, sample_ids):
    keys = [(r['opaque_id'], r['reference_id']) for r in rows]
    expected = {(sid, ref) for sid in sample_ids for ref in REFERENCE_IDS}
    if len(keys) != len(set(keys)) or set(keys) != expected or any(r['state'] not in STATES for r in rows):
        raise ValueError('REFERENCE_KEYS_OR_STATES_INVALID')


def assert_execution_identity(contract):
    """Bounded identity checks on registered dependencies, never a whole-tree scan."""
    ids = contract['sample_ids']
    expected = [(LANG_ID, '1.0.0', 'default', 'LANGUAGE', 'rsr-language-first-gate-v1'),
                (WD_ID, '1.0.0', 'legacy_projection_v1', 'WEBDRIVER_LEGACY', 'rsr-webdriver-legacy-gate-v1')]
    actual = [(c['candidate_id'], c['version'], c['mode'], c['loader_mode'], c['gate_version'])
              for c in contract['candidates']]
    if actual != expected:
        raise ValueError('CORE_CANDIDATE_IDENTITY_CONFLICT')
    authority = read_json(ROOT / contract['authority_ref'])
    admitted = read_jsonl(ROOT / contract['readiness_manifest_ref'])
    if len(ids) != 162 or len(set(ids)) != 162 or authority['supervised_ids'] != ids:
        raise ValueError('CORE_SAMPLE_SET_CONFLICT')
    if {r['opaque_id'] for r in admitted} != set(ids) or len(admitted) != 162:
        raise ValueError('CORE_READINESS_IDENTITY_CONFLICT')
    for row in admitted:
        for mode in ('LANGUAGE', 'WEBDRIVER_LEGACY'):
            item = row['modes'][mode]
            if (item['readiness'] != 'READY' or item['source_status'] != 'SUPPORTED_BY_EXISTING_LINEAGE'
                    or item['input_status'] != 'COMPLETE' or not item['binding_constructible']):
                raise ValueError('CORE_READINESS_REGISTRATION_CONFLICT')
    for entry in contract['file_identities']:
        path = ROOT / entry['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('CORE_FILE_IDENTITY_CONFLICT:' + entry['path'])
    source_head = subprocess.check_output(['git', '-C', str(ROOT / contract['source_repository']),
                                           'rev-parse', 'HEAD'], text=True).strip()
    if source_head != contract['source_commit']:
        raise ValueError('CORE_SOURCE_VERSION_CONFLICT')
    # Check only this task's registered raw/source files for local edits.
    changed = subprocess.check_output(['git', '-C', str(ROOT / contract['source_repository']),
        'diff', '--name-only', contract['source_commit'], '--', *contract['source_required_paths']], text=True)
    if changed.strip():
        raise ValueError('CORE_REGISTERED_SOURCE_WORKTREE_DIFFERS')


def load_saved_references(contract):
    """Read exactly two singleton clause cells; never use model decisions."""
    ids = set(contract['sample_ids'])
    found = {}
    for line, row in enumerate(read_jsonl(ROOT / contract['reference_cache_ref']), 1):
        sid = row.get('opaque_id')
        if sid not in ids:
            continue
        if sid in found:
            raise ValueError('REFERENCE_DUPLICATE_ID')
        if any(row.get(k) != v for k, v in contract['reference_cache_identity'].items()):
            raise ValueError('REFERENCE_CACHE_IDENTITY_CONFLICT')
        if row.get('source_rows') != [sid]:
            raise ValueError('REFERENCE_SOURCE_ROW_CONFLICT')
        found[sid] = {}
        for ref, (atom, polarity) in REFERENCE_CLAUSES.items():
            clause_id = atom + ':' + polarity
            hits = [c for c in row['clause_explanations'] if c.get('clause_id') == clause_id]
            atoms = [a for a in row['atom_explanations'] if a.get('atom_id') == atom]
            if len(hits) != 1 or len(atoms) != 1 or hits[0]['literals'] != [{'atom_id': atom, 'polarity': polarity}]:
                raise ValueError('REFERENCE_NOT_EXACT_SINGLE_LITERAL')
            cell = hits[0]
            if cell['state'] not in STATES:
                raise ValueError('INVALID_REFERENCE_STATE')
            found[sid][ref] = {'reference_id': ref, 'state': cell['state'],
                'origin': 'REUSED_FROZEN_SINGLE_LITERAL_CACHE', 'reference_computed': False,
                'cache_ref': contract['reference_cache_ref'] + '#line=' + str(line),
                'clause_id': clause_id, 'literal': cell['literals'][0],
                'cached_atom': atoms[0], 'cache_model_id': row['model_id'],
                'cache_candidate_version': row['candidate_version']}
    if set(found) != ids:
        raise ValueError('REFERENCE_EXPECTED_ID_MISSING')
    return found


def input_summary(payload):
    fields = {}
    for field, value in payload.get('features', {}).items():
        fields[field] = {'type': type(value).__name__,
            'array_length': len(value) if isinstance(value, list) else None,
            'field_status': payload.get('field_status', {}).get(field),
            'field_quality': payload.get('field_quality', {}).get(field)}
    return {'minimal_payload_sha256': canonical_digest(payload), 'fields': fields}


def evaluate_records(sample_ids, contract, audit, reference_rows, output_dir, *, attempt=1):
    """One call per expected key, with per-key failure retention and no label join."""
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError('DUPLICATE_SAMPLE_IDS')
    candidates = contract['candidates']
    expected_modes = {(LANG_ID, 'default', 'LANGUAGE'),
                      (WD_ID, 'legacy_projection_v1', 'WEBDRIVER_LEGACY')}
    if len(candidates) != 2 or {(c['candidate_id'], c['mode'], c['loader_mode']) for c in candidates} != expected_modes:
        raise ValueError('UNAUTHORIZED_CANDIDATE_OR_MODE')
    if 'sample_ids' in contract and contract['sample_ids'] != list(sample_ids):
        raise ValueError('EXECUTION_SAMPLE_SET_CONFLICT')
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / name for name in ('CANDIDATE_RESULTS.jsonl', 'REFERENCE_RESULTS.jsonl', 'EXECUTION.json')]
    if any(p.exists() or p.is_symlink() for p in paths):
        raise FileExistsError('EXISTING_RESULTS_USE_ANALYZE_ONLY')
    counts = Counter()
    started = datetime.now(timezone.utc).isoformat()
    with paths[0].open('x', encoding='utf-8') as candidate_file, paths[1].open('x', encoding='utf-8') as reference_file:
        for sid in sample_ids:
            for definition in candidates:
                cid = definition['candidate_id']
                row = {'opaque_id': sid, 'candidate_id': cid, 'version': definition['version'],
                    'mode': definition['mode'], 'gate_version': definition['gate_version'],
                    'input_schema_version': 'rsr-input-v1', 'source_binding': None,
                    'source_refs': {}, 'input_summary': None, 'candidate_invoked': False,
                    'execution_phase': 'FIXED_CANDIDATE_EVALUATION_BEFORE_ANALYSIS',
                    'attempt': attempt, 'exception_type': None}
                try:
                    item = audit.load_input(sid, definition['loader_mode'])
                    row['source_refs'] = item.get('source_refs', {})
                    row['input_readiness'] = item.get('audit')
                    if item.get('payload') is None or item.get('audit', {}).get('readiness') != 'READY':
                        raise ValueError('INPUT_NOT_READY:' + json.dumps(item.get('audit', {}).get('reasons', [])))
                    if item.get('source_binding') is None:
                        raise ValueError('SOURCE_BINDING_UNAVAILABLE')
                    payload, binding = item['payload'], item['source_binding']
                    if payload.get('record_schema_version') != 'rsr-input-v1':
                        raise ValueError('INPUT_SCHEMA_CONFLICT')
                    row['source_binding'] = asdict(binding)
                    row['input_summary'] = input_summary(payload)
                    row['candidate_invoked'] = True
                    counts['candidate_calls'] += 1
                    counts[cid] += 1
                    cell = (web_language_first_difference(payload, source_binding=binding)
                            if cid == LANG_ID else webdriver_reported_state(
                                payload, mode='legacy_projection_v1', source_binding=binding))
                    if cell.candidate_id != cid or cell.version != definition['version']:
                        raise ValueError('RETURNED_CANDIDATE_IDENTITY_CONFLICT')
                    row.update(state=cell.state, semantic_cell=cell.to_dict(), reason=cell.reason,
                               source_reason=cell.source_reason, diagnostics=cell.diagnostics,
                               origin='CANDIDATE_RETURN')
                except Exception as exc:
                    row.update(state='FAILED', semantic_cell=None, reason=str(exc),
                        source_reason=None, diagnostics={}, exception_type=type(exc).__name__,
                        origin='CANDIDATE_EXECUTION_FAILURE' if row['candidate_invoked'] else 'INPUT_OR_EXECUTION_FAILURE')
                    counts['runner_failures'] += 1
                candidate_file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
                candidate_file.flush()
                counts['candidate_positions'] += 1
            for ref in REFERENCE_IDS:
                try:
                    stored = reference_rows[sid][ref]
                    if stored['state'] not in STATES:
                        raise ValueError('INVALID_REFERENCE_STATE')
                    reference = {**stored, 'opaque_id': sid, 'reference_id': ref, 'attempt': attempt,
                                 'execution_phase': 'FIXED_REFERENCE_REUSE_BEFORE_ANALYSIS'}
                    counts['reference_cache_reuses'] += 1
                except Exception as exc:
                    reference = {'opaque_id': sid, 'reference_id': ref, 'state': 'FAILED',
                        'origin': 'REFERENCE_CACHE_FAILURE', 'reference_computed': False,
                        'reason': str(exc), 'exception_type': type(exc).__name__, 'attempt': attempt}
                    counts['reference_failures'] += 1
                reference_file.write(json.dumps(reference, ensure_ascii=False, allow_nan=False) + '\n')
                reference_file.flush()
                counts['reference_positions'] += 1
    # This receipt is written only after both result streams have closed.
    execution = {'schema_version': 'rsr-candidate-execution-v1', 'started_at': started,
        'closed_at': datetime.now(timezone.utc).isoformat(), 'results_closed_before_analysis': True,
        'attempt': attempt, 'independent_historical_records': len(sample_ids),
        'candidate_positions': counts['candidate_positions'], 'reference_positions': counts['reference_positions'],
        'new_candidate_actual_calls': counts['candidate_calls'],
        'candidate_calls_by_id': {c['candidate_id']: counts[c['candidate_id']] for c in candidates},
        'reference_actual_computations': 0, 'reference_cached_states_reused': counts['reference_cache_reuses'],
        'runner_failures': counts['runner_failures'], 'reference_failures': counts['reference_failures'],
        'additional_retry_calls': 0, 'fit': 0, 'model_prediction': 0, 'new_collection': 0,
        'contract_sha256': canonical_digest(contract)}
    write_json_new(paths[2], execution)
    return execution


def state_table(rows):
    counts = Counter(r['state'] for r in rows)
    n = len(rows)
    out = {'N_expected': n, **{'N_' + s: counts[s] for s in STATES}}
    for name, k in (('condition_true', counts['T']), ('valid_TF', counts['T'] + counts['F']),
                    ('unknown', counts['U']), ('failed', counts['FAILED'])):
        out[name] = {'k': k, 'n': n, 'ratio': k / n if n else None}
    return out


def triplet_summary(rows_by_id, metadata, sample_ids):
    grouped = defaultdict(list)
    gaps = []
    for sid in sample_ids:
        meta = metadata[sid]
        if not meta.get('bundle_id') or not meta.get('triplet_id'):
            gaps.append({'opaque_ids': [sid], 'reason': 'EXPLICIT_TRIPLET_ID_MISSING'})
        else:
            grouped[(meta['bundle_id'], meta['triplet_id'])].append(sid)
    patterns, categories, groups = Counter(), Counter(), []
    for key, ids in sorted(grouped.items()):
        phases = Counter(metadata[sid].get('phase') for sid in ids)
        if phases != Counter(PHASES):
            gaps.append({'bundle_id': key[0], 'triplet_id': key[1], 'opaque_ids': ids,
                         'reason': 'PHASES_NOT_EXACTLY_ONE_EACH'})
            continue
        if len({(metadata[sid].get('config_id'), metadata[sid].get('environment_group_id')) for sid in ids}) != 1:
            gaps.append({'bundle_id': key[0], 'triplet_id': key[1], 'opaque_ids': ids,
                         'reason': 'TRIPLET_GROUP_METADATA_CONFLICT'})
            continue
        ordered = [next(sid for sid in ids if metadata[sid]['phase'] == phase) for phase in PHASES]
        states = [rows_by_id[sid]['state'] for sid in ordered]
        pattern = '->'.join(states)
        category = ('CONTAINS_FAILED' if 'FAILED' in states else 'CONTAINS_U' if 'U' in states else
                    'F_T_F' if states == ['F', 'T', 'F'] else 'ALL_F' if states == ['F', 'F', 'F'] else 'OTHER')
        patterns[pattern] += 1
        categories[category] += 1
        groups.append({'bundle_id': key[0], 'triplet_id': key[1], 'opaque_ids_in_phase_order': ordered,
                       'states': states, 'pattern': pattern, 'category': category})
    return {'explicit_group_count': len(grouped), 'complete_triplets': len(groups),
            'patterns': dict(patterns), 'exclusive_categories': dict(categories),
            'gaps': gaps, 'groups': groups, 'phase_order': list(PHASES)}


def build_summary(candidates, references, metadata_by_id, sample_ids):
    definitions = [{'candidate_id': LANG_ID, 'mode': 'default'},
                   {'candidate_id': WD_ID, 'mode': 'legacy_projection_v1'}]
    validate_result_keys(candidates, sample_ids, definitions)
    validate_reference_keys(references, sample_ids)
    if set(metadata_by_id) != set(sample_ids):
        raise ValueError('ANALYSIS_METADATA_IDENTITY_CONFLICT')
    output = {'independent_historical_records': len(sample_ids), 'candidate_result_positions': len(candidates),
              'reference_result_positions': len(references), 'candidates': {}, 'comparisons': {},
              'macro_average': 'NOT_REPORTED; all tables retain actual k/n',
              'metric_scope': 'Candidate condition response on exposed historical stages, not model TPR/FPR/accuracy.'}
    for cid in (LANG_ID, WD_ID):
        rows = [r for r in candidates if r['candidate_id'] == cid]
        by_id = {r['opaque_id']: r for r in rows}
        result = {'overall': state_table(rows), 'by_phase': {}, 'by_config': {}, 'by_environment': {}}
        for phase in PHASES:
            result['by_phase'][phase] = state_table([r for r in rows if metadata_by_id[r['opaque_id']]['phase'] == phase])
        result['combined_clean'] = state_table([r for r in rows if metadata_by_id[r['opaque_id']]['phase'] in ('clean_pre', 'clean_post')])
        for key, target in (('config_id', 'by_config'), ('environment_group_id', 'by_environment')):
            for group in sorted({str(metadata_by_id[r['opaque_id']].get(key, 'NOT_RECORDED')) for r in rows}):
                selected = [r for r in rows if str(metadata_by_id[r['opaque_id']].get(key, 'NOT_RECORDED')) == group]
                result[target][group] = {'overall': state_table(selected), 'by_phase': {
                    phase: state_table([r for r in selected if metadata_by_id[r['opaque_id']]['phase'] == phase]) for phase in PHASES}}
        result['primary_unavailable_reasons'] = {state: dict(Counter(r['reason'] for r in rows if r['state'] == state))
                                                for state in ('U', 'FAILED')}
        result['nonexclusive_diagnostic_reasons'] = dict(Counter(
            reason for r in rows for reason in {str(issue.get('reason')) for issue in r.get('diagnostics', {}).get('issues', [])}))
        result['triplets'] = triplet_summary(by_id, metadata_by_id, sample_ids)
        output['candidates'][cid] = result
        reference_id = REFERENCE_IDS[0] if cid == LANG_ID else REFERENCE_IDS[1]
        old = {r['opaque_id']: r for r in references if r['reference_id'] == reference_id}
        crosses = Counter(old[sid]['state'] + '->' + by_id[sid]['state'] for sid in sample_ids)
        changes = {kind: [sid for sid in sample_ids if old[sid]['state'] + '->' + by_id[sid]['state'] == kind]
                   for kind in sorted(crosses)}
        comp = {'reference_id': reference_id, 'cross_table_old_to_new': dict(crosses),
            'ids_by_transition': changes, 'by_phase': {phase: dict(Counter(
                old[sid]['state'] + '->' + by_id[sid]['state'] for sid in sample_ids
                if metadata_by_id[sid]['phase'] == phase)) for phase in PHASES}}
        old_t = {sid for sid in sample_ids if old[sid]['state'] == 'T'}
        new_t = {sid for sid in sample_ids if by_id[sid]['state'] == 'T'}
        comp.update(same_T_set=old_t == new_t, old_T_count=len(old_t), new_T_count=len(new_t),
                    old_only_T_ids=sorted(old_t - new_t), new_only_T_ids=sorted(new_t - old_t))
        output['comparisons'][cid] = comp
    return output


def load_metadata(sample_ids, contract):
    index_ref = contract['evaluation_source_index']
    index = read_json(ROOT / index_ref)
    base = (ROOT / index_ref).parent
    metadata = {sid: read_json(base / index[sid]['evaluation']) for sid in sample_ids}
    if any(row.get('opaque_id') != sid for sid, row in metadata.items()):
        raise ValueError('EVALUATION_METADATA_IDENTITY_CONFLICT')
    return metadata


def analyze_saved(output_dir, *, metadata_loader=None, support_builder=None):
    out = Path(output_dir)
    contract = read_json(out / 'EVALUATION_CONTRACT.json')
    execution = read_json(out / 'EXECUTION.json')
    if not execution['results_closed_before_analysis'] or execution['contract_sha256'] != canonical_digest(contract):
        raise ValueError('RESULTS_NOT_CLOSED_UNDER_THIS_CONTRACT')
    candidates = read_jsonl(out / 'CANDIDATE_RESULTS.jsonl')
    references = read_jsonl(out / 'REFERENCE_RESULTS.jsonl')
    ids = contract['sample_ids']
    validate_result_keys(candidates, ids, contract['candidates'])
    validate_reference_keys(references, ids)
    # First analysis-only access to phase/label/config/environment/triplet metadata.
    metadata = metadata_loader(ids) if metadata_loader else load_metadata(ids, contract)
    summary = build_summary(candidates, references, metadata, ids)
    if support_builder is None:
        from deliverables.rule_semantics_candidate_evaluation.support_diagnostic import build_train_support
        support = build_train_support(candidates, metadata, read_json(ROOT / contract['support']['split_manifest_ref']),
            contract['support']['definition'], [(c['candidate_id'], c['mode']) for c in contract['candidates']])
    else:
        support = support_builder(candidates, metadata, contract)
    summary['execution'] = execution
    summary['execution_complete'] = (execution['new_candidate_actual_calls'] == len(ids) * 2
        and execution['runner_failures'] == 0 and execution['reference_failures'] == 0
        and not any(r['state'] == 'FAILED' for r in candidates))
    summary['status'] = 'CANDIDATE_EVALUATION_COMPLETE_PENDING_REVIEW' if summary['execution_complete'] else 'PARTIAL'
    summary['analysis_reads_saved_results_only'] = True
    return {'summary': summary, 'train_support': support}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('evaluate', 'analyze'))
    parser.add_argument('--directory', type=Path, default=HERE)
    parser.add_argument('--output-dir', type=Path, help='Analyze only: exclusively save new SUMMARY and TRAIN_SUPPORT_DIAGNOSTIC.')
    args = parser.parse_args(argv)
    if args.action == 'evaluate':
        if args.output_dir is not None:
            parser.error('--output-dir is for analyze only')
        contract = read_json(args.directory / 'EVALUATION_CONTRACT.json')
        assert_execution_identity(contract)
        result = evaluate_records(contract['sample_ids'], contract, InputAudit(), load_saved_references(contract), args.directory)
    else:
        targets = [args.output_dir / name for name in ('SUMMARY.json', 'TRAIN_SUPPORT_DIAGNOSTIC.json')] if args.output_dir else []
        if any(p.exists() or p.is_symlink() for p in targets):
            parser.error('REFUSE_EXISTING_ANALYSIS_REPORT')
        result = analyze_saved(args.directory)
        if targets:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            write_json_new(targets[0], result['summary'])
            write_json_new(targets[1], result['train_support'])
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
