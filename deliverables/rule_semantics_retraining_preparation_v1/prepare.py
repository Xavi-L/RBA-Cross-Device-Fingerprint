#!/usr/bin/env python3
"""Prepare explicit input, role and split manifests; there is no training command.

Reads only the fixed local campaign and the historical 162-member registry/cache.
Semantic evaluation is a transfer dry-run, not detector inference. Historical
cells are reused verbatim. Labels never enter the semantic evaluator.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.manipulation_eval.adapter import adapt_payload
from hybridguard_agent.research.rule_semantics_runtime_input import (
    adapt_runtime_payload, RuntimeInputError, QUALITY_POLICY,
)
from hybridguard_agent.research.rule_semantics_runtime_matrix import measure_w0_base_inputs
from hybridguard_agent.research.rule_semantics_revision_v1 import (
    web_language_first_difference, webdriver_reported_state,
)
from hybridguard_agent.research.rule_semantics_revision_v1.contracts import SourceBinding, make_cell

RUN_REF = 'deliverables/featureapp_webdriver_runtime_v1/runs/20260930_local_api36_1_v1'
RUN = ROOT / RUN_REF
CAMPAIGN = '20260930_local_api36_1_v1'
NEW_ENV = 'codex-local-api36-1-raw-v1'
PHASES = ('clean_pre', 'attack', 'clean_post')
LANG = 'RSR-LANG-FIRST-v1'
WD = 'RSR-WEBDRIVER-STATE-v1'
MODES = {'LANGUAGE': (LANG, 'default', 'navigator_sync_v1'),
         'WEBDRIVER_RAW': (WD, 'raw_observation_v1', 'webdriver_raw_observation_v1'),
         'WEBDRIVER_LEGACY': (WD, 'legacy_projection_v1', 'webdriver_legacy_projection_v1')}


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def unique(rows, key):
    result = {}
    for row in rows:
        value = row[key]
        if value in result:
            raise ValueError('DUPLICATE_' + key)
        result[value] = row
    return result


def write(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_lines(path, rows):
    with Path(path).open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def role_for(step):
    paired = step['group'] in ('webdriver', 'language')
    if paired and step['phase'] not in PHASES:
        raise ValueError('INVALID_PAIRED_PHASE')
    return {
        'role': 'CONTROLLED_TARGET_INTERVENTION' if paired and step['phase'] == 'attack'
                else 'PAIRED_TARGET_ABSENCE_CONTROL' if paired
                else 'COLLECTION_SMOKE_ONLY' if step['group'] == 'smoke'
                else 'ADDITIONAL_CONTROL_ONLY',
        'proposed_supervised_label': int(step['phase'] == 'attack') if paired else None,
        'proposed_supervised_member': paired,
        'label_scope': 'Presence/absence of this declared target intervention; not universal maliciousness/benignness.',
        'fit_permission': 'DENIED_PREPARATION_ONLY',
    }


def build_folds(metadata):
    """Keep every environment and each complete supervised triplet together."""
    if not metadata:
        raise ValueError('EMPTY_SUPERVISED_MEMBERS')
    indexed = unique(metadata, 'opaque_id')
    triples = defaultdict(dict)
    bundle_environments = defaultdict(set)
    for row in metadata:
        if (row['phase'] not in PHASES or type(row['supervised_label']) is not int
                or row['supervised_label'] != int(row['phase'] == 'attack')):
            raise ValueError('SUPERVISED_PHASE_LABEL_MISMATCH')
        t = triples[row['bundle_id'], row['triplet_id']]
        if row['phase'] in t:
            raise ValueError('DUPLICATE_TRIPLET_PHASE')
        t[row['phase']] = row
        bundle_environments[row['bundle_id']].add(row['environment_group_id'])
    if any(len(groups) != 1 for groups in bundle_environments.values()):
        raise ValueError('BUNDLE_ENVIRONMENT_SPLIT')
    for t in triples.values():
        if set(t) != set(PHASES):
            raise ValueError('INCOMPLETE_SUPERVISED_TRIPLET')
        if len({(r['environment_group_id'], r['config_id']) for r in t.values()}) != 1:
            raise ValueError('TRIPLET_ENVIRONMENT_OR_CONFIG_SPLIT')
    result = []
    for n, environment in enumerate(sorted({r['environment_group_id'] for r in metadata}), 1):
        test = sorted(i for i, m in indexed.items() if m['environment_group_id'] == environment)
        train = sorted(set(indexed) - set(test))
        result.append({'fold_id': f'MIXED-LOEO-v1-{n:02}', 'heldout_environment': environment,
                       'train_ids': train, 'outer_test_ids': test,
                       'train_n': len(train), 'test_n': len(test)})
    return result


def support_for(ids, metadata, cells, candidate, polarity):
    """Only fixed-state support arithmetic; no thresholds or selection fitted."""
    if polarity not in ('POSITIVE', 'NEGATIVE'):
        raise ValueError('INVALID_POLARITY')
    if len(ids) != len(set(ids)):
        raise ValueError('DUPLICATE_SUPPORT_MEMBER')
    triples = defaultdict(dict)
    counts = Counter()
    for sid in ids:
        m = metadata[sid]
        state = cells[sid][candidate]
        counts[state] += 1
        if polarity == 'NEGATIVE':
            state = {'T': 'F', 'F': 'T', 'U': 'U', 'FAILED': 'FAILED'}[state]
        triple = triples[m['bundle_id'], m['triplet_id']]
        if m['phase'] in triple:
            raise ValueError('DUPLICATE_SUPPORT_PHASE')
        if state not in ('T', 'F', 'U', 'FAILED'):
            raise ValueError('INVALID_SUPPORT_STATE')
        triple[m['phase']] = (sid, state)
    complete, positive = [], []
    for key, t in triples.items():
        if set(t) != set(PHASES):
            raise ValueError('INCOMPLETE_SUPPORT_TRIPLET')
        if all(t[p][1] in ('T', 'F') for p in PHASES):
            complete.append(key)
            if t['attack'][1] == 'T':
                positive.append(metadata[t['attack'][0]])
    clean_alerts = sum(({'T': 'F', 'F': 'T'}.get(cells[i][candidate], cells[i][candidate])
                       if polarity == 'NEGATIVE' else cells[i][candidate]) == 'T'
                      for i in ids if metadata[i]['phase'] != 'attack')
    clean_n = sum(metadata[i]['phase'] != 'attack' for i in ids)
    return {'candidate_id': candidate, 'polarity': polarity,
            'state_counts_before_polarity': {s: counts[s] for s in ('T', 'F', 'U', 'FAILED')},
            'complete_available_triplets': len(complete), 'true_attack_triplets': len(positive),
            'support_bundles': len({m['bundle_id'] for m in positive}),
            'support_environments': len({m['environment_group_id'] for m in positive}),
            'meets_count_support': len(complete) >= 3 and len(positive) >= 2,
            'single_literal_clean_alerts': clean_alerts, 'train_clean_n': clean_n,
            'op05_clean_budget': clean_n // 20,
            'single_literal_within_clean_budget': clean_alerts <= clean_n // 20,
            'selected': 'NOT_EVALUATED_NO_SELECTOR_CALLED'}


def prepare(output):
    if output.exists():
        raise FileExistsError('OUTPUT_EXISTS_NO_OVERWRITE')
    review = read(HERE / 'SOURCE_ADMISSION_REVIEW.json')
    grouping = read(HERE / 'GROUP_CONFIG_REVIEW.json')
    audit = read(RUN / 'AUDIT.json')
    if review['status'] != 'SUPPORTED_FOR_SEPARATE_LOCAL_DEVELOPMENT_PREPARATION' or audit['status'] != 'PASS':
        raise ValueError('SOURCE_REVIEW_NOT_SUPPORTED')
    if grouping['status'] != 'SUPPORTED_FOR_PROPOSED_DEVELOPMENT_SPLIT':
        raise ValueError('GROUP_CONFIG_REVIEW_NOT_SUPPORTED')
    if (grouping['environment_group_id'] != NEW_ENV
            or grouping['new_environment']['stable_identity'] != audit['stable_identity']):
        raise ValueError('REGISTERED_GROUP_IDENTITY_MISMATCH')
    config_map = unique(grouping['config_mappings'], 'runtime_group')
    frozen = ROOT / 'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R04_freeze_r1'
    protocol = frozen / 'snapshot/hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol'
    base_contract = {
        'definitions': read(frozen / 'data/definitions.json'),
        'candidate_definitions': lines(protocol / 'CANDIDATE_LEDGER.jsonl'),
        'control_specs': read(protocol / 'SINGLE_SURFACE_FIELDS.json')['fields'],
        'rule_definitions': read(ROOT / 'hybridguard_agent/config/paired244_rule_catalog.v3.json')['rules'],
    }
    plan = read(RUN / 'plan.json')
    sessions = unique(lines(RUN / 'sessions.jsonl'), 'step_id')
    raw_rows = lines(RUN / 'backend/raw_expanded_payloads.jsonl')
    raws = unique(raw_rows, 'session_id')
    receipts = unique(lines(RUN / 'backend/collection_receipts.jsonl'), 'session_id')
    if len(plan) != 31 or len(sessions) != 31 or len(raws) != 31 or len(receipts) != 31:
        raise ValueError('FIXED_CAMPAIGN_MEMBERSHIP_MISMATCH')
    if set(sessions) != {p['step_id'] for p in plan}:
        raise ValueError('PLAN_SESSION_MEMBERSHIP_MISMATCH')
    session_ids = [r['observation']['session_id'] for r in sessions.values()]
    if len(set(session_ids)) != 31 or set(session_ids) != set(raws) or set(session_ids) != set(receipts):
        raise ValueError('EXACT_UNIQUE_SESSION_RECEIPT_MEMBERS_REQUIRED')
    registrations, inputs, admissions, candidates, newmeta, base_inputs = [], [], [], [], [], []
    semantic_calls = 0
    states = {}
    raw_line = {r['session_id']: n for n, r in enumerate(raw_rows, 1)}
    for step in plan:
        saved = sessions[step['step_id']]
        sid = saved['observation']['session_id']
        record, receipt = raws[sid], receipts[sid]
        raw = record['canonical_received_payload']
        attempt = read(RUN / 'attempts' / step['step_id'] / 'attempt.json')
        if (saved['accepted'] is not True or attempt['status'] != 'ACCEPTED'
                or attempt['session_id'] != sid or raw['session_id'] != sid
                or receipt['validation_status'] != 'accepted'
                or any(record[k] != receipt[k] for k in ('receipt_id', 'payload_sha256', 'collection_batch_id'))
                or raw['collection_manifest']['runtime_context'] != step['runtime_context']
                or any(raw['collection_manifest'].get(k) != v for k, v in audit['stable_identity'].items())):
            raise ValueError('RAW_RECEIPT_ATTEMPT_BINDING_MISMATCH:' + sid)
        oid = 'runtime-' + sid
        refs = [RUN_REF + '/backend/raw_expanded_payloads.jsonl#line=' + str(raw_line[sid]),
                RUN_REF + '/backend/collection_receipts.jsonl#receipt_id=' + receipt['receipt_id'],
                RUN_REF + '/attempts/' + step['step_id'] + '/attempt.json',
                str((HERE / 'SOURCE_ADMISSION_REVIEW.json').relative_to(ROOT))]
        bindings = {mode: SourceBinding(CAMPAIGN, scope,
                    observer_revision='app-webdriver-observer-v1' if mode == 'WEBDRIVER_RAW' else None,
                    realm_binding=f'featureapp:{sid}:main-frame' if mode == 'WEBDRIVER_RAW' else None)
                    for mode, (_, _, scope) in MODES.items()}
        registrations.append({'opaque_id': oid, 'expected_session_id': sid,
            'registration_basis': 'Separately checked plan/receipt/attempt plus registered collector contract, not payload self-attestation.',
            'source_status': 'SUPPORTED_BY_EXISTING_LINEAGE', 'evidence_refs': refs,
            'bindings': {mode: asdict(binding) for mode, binding in bindings.items()}})
        adapted = adapt_runtime_payload(raw, expected_session_id=sid, source_bindings=bindings)
        full = adapt_payload(raw)
        if len(full['features']) != 177:
            raise ValueError('FULL_APP177_MAPPING_FAILED')
        base_inputs.append({'opaque_id': oid, 'features': measure_w0_base_inputs(full, **base_contract),
                            'origin': 'NEW_RUNTIME_FROZEN_W0_INPUT_MEASUREMENT',
                            'numeric_thresholds_fitted': False})
        inputs.append({'opaque_id': oid, 'minimal_semantic_payload': adapted.payload,
                       'full_app177_payload': full, 'field_quality_origin': QUALITY_POLICY,
                       'source_refs': refs})
        for mode, (cid, interpretation, _) in MODES.items():
            gate_error = None
            try:
                payload, binding = adapted.input_for(mode)
                semantic_calls += 1
                cell = (web_language_first_difference(payload, binding) if mode == 'LANGUAGE'
                        else webdriver_reported_state(payload, mode=interpretation, source_binding=binding))
            except RuntimeInputError as error:
                gate_error = error.to_dict()
                cell = make_cell(cid, error.state, error.reason)
            candidates.append({'opaque_id': oid, 'candidate_id': cid, 'mode': interpretation,
                               'state': cell.state, 'semantic_cell': cell.to_dict(),
                               'source_binding': asdict(bindings[mode]), 'gate_error': gate_error,
                               'purpose': 'INPUT_TRANSFER_DRY_RUN_NOT_DETECTOR_PREDICTION',
                               'role_in_planned_training': 'DIAGNOSTIC_ONLY' if mode == 'WEBDRIVER_LEGACY' else 'PROPOSED_PRIMARY'})
            if mode != 'WEBDRIVER_LEGACY':
                states.setdefault(oid, {})[cid] = cell.state
        roles = role_for(step)
        group = step['group']
        triplet = f'{CAMPAIGN}:{group}:r{step["round"]}' if group != 'smoke' else None
        item = {'opaque_id': oid, 'session_id': sid, 'step_id': step['step_id'],
                'phase': step['phase'], 'environment_group_id': NEW_ENV,
                'bundle_id': CAMPAIGN + ':' + group, 'triplet_id': triplet,
                'observation_mode': 'raw_observation_v1', 'source_refs': refs, **roles}
        if roles['proposed_supervised_member']:
            attack_step = f'{group}-r{step["round"]}-attack'
            logs = list((RUN / 'attempts' / attack_step / 'automation').glob('*.json'))
            if len(logs) != 1:
                raise ValueError('ONE_ACTIVE_EXECUTION_RECEIPT_REQUIRED')
            execution = read(logs[0])
            active_sid = sessions[attack_step]['observation']['session_id']
            if execution['status'] != 'MEASURED' or execution['measuredSessionIds'] != [active_sid]:
                raise ValueError('ACTIVE_EXECUTION_SESSION_MISMATCH')
            registered = config_map[group]
            if (execution['configId'] != registered['config_id']
                    or execution['configurationId'] != registered['configuration_id']
                    or execution['injected'] != registered['injection_profile']
                    or execution['declaredObservableFields'] != registered['declared_observable_fields']):
                raise ValueError('REGISTERED_CONFIG_PROFILE_MISMATCH')
            item.update(config_id=execution['configId'], tool_configuration=execution['configurationId'],
                        execution_ref=str(logs[0].relative_to(ROOT)))
            newmeta.append({k: item[k] for k in ('opaque_id', 'phase', 'environment_group_id',
                                               'bundle_id', 'triplet_id', 'config_id')}
                           | {'supervised_label': roles['proposed_supervised_label']})
        admissions.append(item)
    # Historical inputs are references, not copied/repaired raw observations.
    historical = read(ROOT / 'deliverables/rule_semantics_combination/CONTRACT.json')
    ids = historical['sample_ids']
    if len(ids) != 162 or len(set(ids)) != 162:
        raise ValueError('HISTORICAL_EXACT_162_REQUIRED')
    index_path = ROOT / historical['source_index']
    index = read(index_path)
    oldmeta = []
    mixed = []
    for sid in ids:
        meta = read(index_path.parent / index[sid]['evaluation'])
        oldmeta.append(meta)
        mixed.append({'opaque_id': sid, 'observation_mode': 'legacy_projection_v1',
                      'features_ref': str((index_path.parent / index[sid]['features']).relative_to(ROOT)),
                      'metadata_ref': str((index_path.parent / index[sid]['evaluation']).relative_to(ROOT)),
                      'candidate_ref': historical['candidate_cache_ref'] + '#opaque_id=' + sid,
                      'input_action': 'REUSE_EXISTING_UNCHANGED'})
    saved = [r for r in lines(ROOT / historical['candidate_cache_ref']) if r['opaque_id'] in set(ids)]
    if len(saved) != 324 or len({(r['opaque_id'], r['candidate_id']) for r in saved}) != 324:
        raise ValueError('HISTORICAL_CANDIDATE_KEYS_MISMATCH')
    for row in saved:
        expected_mode = 'default' if row['candidate_id'] == LANG else 'legacy_projection_v1'
        if row['candidate_id'] not in (LANG, WD) or row['mode'] != expected_mode:
            raise ValueError('HISTORICAL_MODE_MISMATCH')
        states.setdefault(row['opaque_id'], {})[row['candidate_id']] = row['state']
    metadata = oldmeta + newmeta
    meta_by_id = unique(metadata, 'opaque_id')
    folds = build_folds(metadata)
    if len(metadata) != 180 or len(newmeta) != 18 or len(folds) != 4:
        raise ValueError('PROPOSED_180_FOUR_GROUP_PLAN_MISMATCH')
    old_installs = {m.get('collector_install_id') for m in oldmeta}
    if audit['stable_identity']['collector_install_id'] in old_installs:
        raise ValueError('NEW_INSTALL_OVERLAPS_HISTORICAL_GROUP_REVIEW_REQUIRED')
    for item in admissions:
        if item['proposed_supervised_member']:
            mixed.append({'opaque_id': item['opaque_id'], 'observation_mode': 'raw_observation_v1',
                          'features_ref': 'BASE_INPUTS.jsonl#opaque_id=' + item['opaque_id'],
                          'metadata_ref': 'ADMISSION_MANIFEST.jsonl#opaque_id=' + item['opaque_id'],
                          'candidate_ref': 'CANDIDATE_RESULTS.jsonl#opaque_id=' + item['opaque_id'],
                          'input_action': 'NEW_SEPARATE_VERSIONED_INPUT', 'fit_permission': 'DENIED_PREPARATION_ONLY'})
    support = [{'fold_id': f['fold_id'], 'heldout_environment': f['heldout_environment'],
                'train_n': f['train_n'], 'test_n': f['test_n'],
                'candidates': [support_for(f['train_ids'], meta_by_id, states, candidate, polarity)
                               for candidate in (LANG, WD) for polarity in ('POSITIVE', 'NEGATIVE')]}
               for f in folds]
    counts = {mode: dict(Counter(r['state'] for r in candidates if r['mode'] == mode))
              for mode in ('default', 'raw_observation_v1', 'legacy_projection_v1')}
    jobs = []
    for group in ('BASE', 'LANG_ADD_WD_REPLACE'):
        for fold in folds:
            for stage in ('SPARSE', 'RETENTION'):
                jobs.append({'job_id': group + '__' + fold['fold_id'] + '__' + stage,
                    'group_id': group, 'stage': stage, 'fold_id': fold['fold_id'],
                    'train_ids': fold['train_ids'], 'outer_test_ids': fold['outer_test_ids'],
                    'status': 'PROPOSED_NOT_AUTHORIZED_NOT_RUN',
                    'initializer': group + '__' + fold['fold_id'] + '__SPARSE' if stage == 'RETENTION' else None,
                    'max_prediction_calls': fold['test_n'] if stage == 'RETENTION' else 0})
    summary = {'schema_version': 'rsr-retraining-preparation-v1',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'status': 'PREPARED_FOR_REVIEW_NO_TRAINING', 'source_commit': 'caafacab6094f6a78423b9cba1a4d84eeb40bacf',
        'runtime_samples': 31, 'full_app177_conversion_passed': len(inputs),
        'new_w0_base_rows': len(base_inputs), 'w0_base_atoms_per_row': 48,
        'new_w0_base_cells': sum(len(r['features']) for r in base_inputs),
        'numeric_threshold_fit_calls': 0,
        'proposed_new_supervised_rows': 18, 'proposed_new_triplets': 6,
        'auxiliary_rows_excluded_from_training_and_primary_metrics': 13,
        'historical_rows_unchanged': 162, 'mixed_proposed_rows': 180,
        'new_semantic_calls': semantic_calls, 'historical_semantic_calls': 0,
        'input_gate_failures': sum(r['gate_error'] is not None for r in candidates),
        'new_state_counts': counts, 'fit_calls': 0, 'model_prediction_calls': 0,
        'new_collection_calls': 0, 'overall_improvement': 'NOT_EVALUATED',
        'prospective_jobs': 16, 'prospective_oof_predictions': 360,
        'gates_before_fit': ['Approve the mixed-mode retrospective protocol and target-scoped labels.',
            'Recheck environment linkage, config equivalence and the shared research budget.',
            'Register a new mixed-mode execution identity and worker; historical legacy-only runners must reject these data.'],
        'limitations': ['New raw observations come from one environment/installation.',
            'Holding the new environment out leaves zero raw-complete training triplets for webdriver.',
            'The language intervention also changes array length; it cannot alone separate the old/new predicates.',
            'Support arithmetic is not selection, detection performance or population FPR.']}
    output.mkdir(parents=True)
    write(output / 'SOURCE_BINDINGS.json', registrations)
    write_lines(output / 'RUNTIME_INPUTS.jsonl', inputs)
    write_lines(output / 'BASE_INPUTS.jsonl', base_inputs)
    write_lines(output / 'CANDIDATE_RESULTS.jsonl', candidates)
    write_lines(output / 'ADMISSION_MANIFEST.jsonl', admissions)
    write_lines(output / 'MIXED_INPUT_INDEX.jsonl', mixed)
    write(output / 'SPLIT_PLAN.json', {'status': 'PROPOSED_NO_FIT_AUTHORIZATION', 'folds': folds,
          'primary_groups': ['BASE', 'LANG_ADD_WD_REPLACE'], 'auxiliary_samples_in_folds': False,
          'environment_linkage_policy': 'Same installation/explicit aliases stay together; new fresh userdata is one additional recorded group, not an independent physical-device claim.'})
    write(output / 'TRAIN_SUPPORT.json', support)
    write(output / 'JOB_PLAN.json', {'status': 'PROPOSED_NOT_EXECUTABLE', 'jobs': jobs,
          'same_data_and_splits_for_both_groups': True, 'reuse_historical_models_as_new_controls': False,
          'fit_budget_reserved_or_consumed': 0, 'required_fits_if_authorized': 16,
          'hyperparameter_search': False, 'retention_math_change': False})
    write(output / 'SUMMARY.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'prepared')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), ensure_ascii=False, indent=2))
