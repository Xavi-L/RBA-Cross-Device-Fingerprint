#!/usr/bin/env python3
"""Audit two saved local campaigns and measure unfitted inputs; no learner calls."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'deliverables/featureapp_webdriver_runtime_v1'))
from runtime_analysis import campaign_plan, smoke_plan, payload_issues, describe_payload, summarize_sessions
from hybridguard_agent.research.manipulation_eval.adapter import adapt_payload
from hybridguard_agent.research.rule_semantics_runtime_input import adapt_runtime_payload, RuntimeInputError
from hybridguard_agent.research.rule_semantics_runtime_matrix import measure_w0_base_inputs
from hybridguard_agent.research.rule_semantics_revision_v1 import web_language_first_difference, webdriver_reported_state
from hybridguard_agent.research.rule_semantics_revision_v1.contracts import SourceBinding, make_cell

RUNS = (
    ROOT / 'deliverables/featureapp_webdriver_runtime_v1/runs/20260930_local_api36_1_v1',
    HERE / 'runs/20260930_local_api29_v1',
)
PHASES = ('clean_pre', 'attack', 'clean_post')
MODES = {
    'LANGUAGE': ('RSR-LANG-FIRST-v1', 'default', 'navigator_sync_v1'),
    'WEBDRIVER_RAW': ('RSR-WEBDRIVER-STATE-v1', 'raw_observation_v1', 'webdriver_raw_observation_v1'),
    'WEBDRIVER_LEGACY': ('RSR-WEBDRIVER-STATE-v1', 'legacy_projection_v1', 'webdriver_legacy_projection_v1'),
}
PROFILES = {
    'webdriver': ('cdp_webdriver_only_v1', 'w9-rule-boundary-cdp-webdriver-only-v1', {'webdriver': True}, ['webdriver']),
    'language': ('stealth_languages_only_v1', 'w9-stealth-boundary-languages-only-v1', {'languages': ['fr-FR', 'fr']}, ['languages']),
}


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def unique(rows, key):
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError('DUPLICATE_' + key)
    return result


def write(path, value, jsonl=False):
    with Path(path).open('x') as stream:
        if jsonl:
            for row in value:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
        else:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def literal_support(members, states, mode, polarity):
    """Arithmetic on a predeclared literal, never fit or score a detector."""
    trios = defaultdict(dict)
    counts = {p: Counter() for p in PHASES}
    for row in members:
        state = states[row['opaque_id']][mode]
        if polarity == 'NEGATIVE':
            state = {'T': 'F', 'F': 'T', 'U': 'U', 'FAILED': 'FAILED'}[state]
        counts[row['phase']][state] += 1
        trio = trios[row['triplet_id']]
        if row['phase'] in trio:
            raise ValueError('DUPLICATE_TRIPLET_PHASE')
        trio[row['phase']] = (state, row)
    available, positive = [], []
    for tid, trio in trios.items():
        if set(trio) != set(PHASES):
            raise ValueError('INCOMPLETE_TRIPLET')
        if all(state in ('T', 'F') for state, _ in trio.values()):
            available.append(tid)
            if trio['attack'][0] == 'T':
                positive.append(trio['attack'][1])
    phase_counts = {p: {s: counts[p][s] for s in ('T', 'F', 'U', 'FAILED')} for p in PHASES}
    coverage = {p: (counts[p]['T'] + counts[p]['F']) / sum(counts[p].values()) for p in PHASES}
    clean_n = sum(sum(counts[p].values()) for p in ('clean_pre', 'clean_post'))
    clean_t = sum(counts[p]['T'] for p in ('clean_pre', 'clean_post'))
    bundles = len({row['bundle_id'] for row in positive})
    environments = len({row['environment_group_id'] for row in positive})
    support = len(available) >= 3 and len(positive) >= 2 and bundles >= 1 and environments >= 1
    return {
        'mode': mode, 'polarity': polarity, 'phase_states': phase_counts,
        'phase_defined_fraction': coverage, 'complete_available_triplets': len(available),
        'true_attack_triplets': len(positive), 'support_bundles': bundles,
        'support_environments': environments, 'meets_existing_support_counts': support,
        'clean_n': clean_n, 'clean_true': clean_t, 'op05_clean_budget': clean_n // 20,
        'passes_single_literal_feasibility': support and clean_t <= clean_n // 20
            and min(coverage.values()) >= 0.8 and not any(c['FAILED'] for c in counts.values()),
        'selected': 'NOT_EVALUATED', 'scope': 'PROPOSED_TRAIN_FOLD_ONLY_FIXED_LITERAL_ARITHMETIC',
    }


def analyze(output=None):
    output = HERE / 'analysis' if output is None else Path(output)
    if output.exists():
        raise FileExistsError('OUTPUT_EXISTS_NO_OVERWRITE')
    frozen = ROOT / 'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R04_freeze_r1'
    protocol = frozen / 'snapshot/hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol'
    contract = {
        'definitions': read(frozen / 'data/definitions.json'),
        'candidate_definitions': lines(protocol / 'CANDIDATE_LEDGER.jsonl'),
        'control_specs': read(protocol / 'SINGLE_SURFACE_FIELDS.json')['fields'],
        'rule_definitions': read(ROOT / 'hybridguard_agent/config/paired244_rule_catalog.v3.json')['rules'],
    }
    inputs, cells, base, index, campaigns, checks, states = [], [], [], [], [], [], {}

    def check(name, passed):
        checks.append({'check': name, 'pass': bool(passed)})
        if not passed:
            raise ValueError('AUDIT_FAILED:' + name)

    for run in RUNS:
        config, release = read(run / 'protocol_snapshot.json'), read(run / 'release_snapshot.json')
        campaign = config['campaign_id']
        planned = [smoke_plan(campaign)] + campaign_plan(campaign)
        saved = unique(lines(run / 'sessions.jsonl'), 'step_id')
        raw = unique(lines(run / 'backend/raw_expanded_payloads.jsonl'), 'session_id')
        exports = unique(lines(run / 'backend/expanded_collected_data.jsonl'), 'session_id')
        receipts = unique(lines(run / 'backend/collection_receipts.jsonl'), 'session_id')
        import csv
        with (ROOT / release['field_catalog']['path']).open() as stream:
            fields = {row['field'] for row in csv.DictReader(stream)
                      if row['field'].startswith(('android_native_data.', 'webview_data.', 'web_data.'))}
        check(campaign + ':exact_31_members', len(saved) == len(raw) == len(exports) == len(receipts) == 31
              and set(saved) == {s['step_id'] for s in planned} and set(raw) == set(exports) == set(receipts)
              and {s['observation']['session_id'] for s in saved.values()} == set(raw))
        check(campaign + ':frozen_plan', read(run / 'plan.json') == planned)
        identity = saved['smoke']['observation']['identity']
        measured_sessions = []
        for step in planned:
            record = saved[step['step_id']]
            sid = record['observation']['session_id']
            payload = raw[sid]['canonical_received_payload']
            receipt, attempt = receipts[sid], read(run / 'attempts' / step['step_id'] / 'attempt.json')
            observation = describe_payload(payload)
            check(campaign + ':' + step['step_id'] + ':binding_and_contract',
                  record['accepted'] is True and attempt['status'] == 'ACCEPTED' and attempt['session_id'] == sid
                  and receipt['validation_status'] == 'accepted' and raw[sid]['receipt_id'] == receipt['receipt_id']
                  and raw[sid]['collection_batch_id'] == receipt['collection_batch_id']
                  and payload['session_id'] == sid and exports[sid]['collection_observations'] == payload['collection_observations']
                  and observation == record['observation'] and observation['identity'] == identity
                  and not payload_issues(payload, step, config, release, fields))
            measured_sessions.append({**step, 'accepted': True, 'observation': observation})
            oid = 'raw-only-' + sid
            check('unique_session:' + sid, oid not in states)
            bindings = {mode: SourceBinding(campaign, scope,
                        observer_revision='app-webdriver-observer-v1' if mode == 'WEBDRIVER_RAW' else None,
                        realm_binding=f'featureapp:{sid}:main-frame' if mode == 'WEBDRIVER_RAW' else None)
                        for mode, (_, _, scope) in MODES.items()}
            adapted = adapt_runtime_payload(payload, expected_session_id=sid, source_bindings=bindings)
            inputs.append({'opaque_id': oid, 'expected_session_id': sid, 'payload': adapted.payload,
                           'bindings': {m: asdict(b) for m, b in bindings.items()}})
            states[oid] = {}
            for mode, (cid, interpretation, _) in MODES.items():
                try:
                    semantic_input, binding = adapted.input_for(mode)
                    cell = (web_language_first_difference(semantic_input, binding) if mode == 'LANGUAGE'
                            else webdriver_reported_state(semantic_input, mode=interpretation, source_binding=binding))
                except RuntimeInputError as error:
                    cell = make_cell(cid, error.state, error.reason)
                states[oid][mode] = cell.state
                cells.append({'opaque_id': oid, 'mode': mode, 'state': cell.state, 'cell': cell.to_dict(),
                              'role': 'DIAGNOSTIC_ONLY' if mode == 'WEBDRIVER_LEGACY' else 'UNFITTED_CANDIDATE'})
            full = adapt_payload(payload)
            check('app177:' + sid, len(full['features']) == 177)
            base.append({'opaque_id': oid, 'cells': measure_w0_base_inputs(full, **contract), 'numeric_thresholds_fitted': False})
            paired = step['group'] in PROFILES
            group = step['group']
            item = {'opaque_id': oid, 'session_id': sid, 'campaign_id': campaign,
                    'environment_group_id': config['device_manifest_id'], 'step_id': step['step_id'],
                    'group': group, 'phase': step['phase'], 'round': step['round'],
                    'proposed_supervised_member': paired,
                    'proposed_supervised_label': int(step['phase'] == 'attack') if paired else None,
                    'role': ('CONTROLLED_TARGET_INTERVENTION' if step['phase'] == 'attack' else 'PAIRED_TARGET_ABSENCE_CONTROL')
                            if paired else 'AUXILIARY_ONLY',
                    'label_scope': 'Presence/absence of declared target intervention only.',
                    'source_run': str(run.relative_to(ROOT)), 'raw_session_id': sid,
                    'receipt_id': receipt['receipt_id'], 'fit_permission': 'DENIED_PREPARATION_ONLY'}
            if paired:
                active_step = f'{group}-r{step["round"]}-attack'
                logs = list((run / 'attempts' / active_step / 'automation').glob('*.json'))
                check(campaign + ':' + active_step + ':one_execution_receipt', len(logs) == 1)
                execution = read(logs[0])
                configuration, config_id, injected, observable = PROFILES[group]
                check(campaign + ':' + active_step + ':execution_profile',
                      execution['status'] == 'MEASURED'
                      and execution['measuredSessionIds'] == [saved[active_step]['observation']['session_id']]
                      and execution['configurationId'] == configuration and execution['configId'] == config_id
                      and execution['injected'] == injected and execution['declaredObservableFields'] == observable)
                item.update(config_id=config_id, bundle_id=f'{campaign}:{group}',
                            triplet_id=f'{campaign}:{group}:r{step["round"]}',
                            execution_ref=str(logs[0].relative_to(ROOT)))
            index.append(item)
        summary = summarize_sessions(measured_sessions, campaign_plan(campaign))
        check(campaign + ':all_triplets_complete', all(t['status'] == 'COMPLETE' for t in summary['triplets']))
        summary.update(campaign_id=campaign, stable_identity=identity, environment=read(run / 'environment.json'))
        campaigns.append(summary)

    check('distinct_environment_and_install', len({c['stable_identity']['collector_install_id'] for c in campaigns}) == 2
          and len({(c['stable_identity']['android_api'], c['stable_identity']['webview_provider_version']) for c in campaigns}) == 2)
    supervised = [r for r in index if r['proposed_supervised_member']]
    folds = []
    for n, environment in enumerate(sorted({r['environment_group_id'] for r in supervised}), 1):
        train = [r for r in supervised if r['environment_group_id'] != environment]
        test = [r for r in supervised if r['environment_group_id'] == environment]
        check(f'fold_{n}:split', len(train) == len(test) == 18
              and not ({r['triplet_id'] for r in train} & {r['triplet_id'] for r in test})
              and {r['config_id'] for r in train} == {r['config_id'] for r in test} == {p[1] for p in PROFILES.values()})
        folds.append({'fold_id': f'RAW-ONLY-FEASIBILITY-LOEO-{n:02}', 'heldout_environment': environment,
                      'train_ids': [r['opaque_id'] for r in train], 'outer_test_ids': [r['opaque_id'] for r in test],
                      'training_status': 'NOT_STARTED', 'outer_test_exposure': 'EXPOSED_DEVELOPMENT_NOT_BLIND_CONFIRMATION',
                      'literal_support': [literal_support(train, states, m, p)
                                          for m in ('LANGUAGE', 'WEBDRIVER_RAW') for p in ('POSITIVE', 'NEGATIVE')]})
    passed = all(s['passes_single_literal_feasibility'] for f in folds for s in f['literal_support'] if s['polarity'] == 'POSITIVE')
    counts = {mode: dict(Counter(states[r['opaque_id']][mode] for r in index)) for mode in MODES}
    failures = []
    for campaign in campaigns:
        for trio in campaign['triplets']:
            middle, post = trio['pre_vs_middle'], trio['pre_vs_post']
            changed_as_declared = (
                middle['webdriver_known_values_equal'] is (trio['group'] != 'webdriver')
                and middle['language_and_ordered_languages_equal'] is (trio['group'] != 'language'))
            restored = (post['webdriver_known_values_equal'] is True
                        and post['webdriver_raw_tuple_equal_excluding_realm'] is True
                        and post['language_and_ordered_languages_equal'] is True)
            active = trio.get('declared_active_value_observed') is True if trio['group'] in PROFILES else True
            if not (changed_as_declared and restored and active):
                failures.append({'campaign_id': campaign['campaign_id'], 'triplet': trio})
    base_counts = Counter('FAILED' if cell['evaluation_status'] == 'FAILED'
                          else 'AVAILABLE' if cell['available'] else 'UNAVAILABLE'
                          for row in base for cell in row['cells'].values())
    result = {'status': 'MINIMAL_RAW_ONLY_FEASIBILITY_PASS' if passed and not failures else 'FEASIBILITY_REQUIRES_REVIEW',
              'saved_captures': len(index), 'potential_supervised_rows': len(supervised),
              'target_interventions': sum(r['proposed_supervised_label'] == 1 for r in supervised),
              'paired_controls': sum(r['proposed_supervised_label'] == 0 for r in supervised),
              'auxiliary_rows': len(index) - len(supervised), 'environment_groups': 2, 'configurations': 2,
              'semantic_states_all_captures': counts, 'base_input_cell_status_counts': dict(base_counts),
              'effect_or_restoration_review_items': failures,
              'audit_checks_passed': len(checks), 'real_fit_calls': 0, 'real_predict_calls': 0,
              'numeric_threshold_fit_calls': 0, 'training_authorized': False,
              'historical162_included': False, 'overall_detection_improvement': 'NOT_EVALUATED',
              'normal_physical_app_fpr': 'NOT_EVALUATED',
              'resolution_scope': 'Historical-legacy U obstacle removed for these two raw-only development environments; not evidence of full detector improvement.',
              'next_requirements': ['Freeze a separately identified raw-only study and register its runner before training.',
                                    'A third environment is recommended before the intended three-fold comparison.',
                                    'Broaden beyond two intervention profiles before claiming overall detection changes.',
                                    'Current language intervention changes both first item and length, so it cannot distinguish those hypotheses.']}
    output.mkdir()
    for filename, data, jsonl in (
        ('SOURCE_INDEX.jsonl', index, True), ('CANDIDATE_INPUTS.jsonl', inputs, True),
        ('SEMANTIC_CELLS.jsonl', cells, True), ('BASE_W0_INPUTS.jsonl', base, True),
        ('CAMPAIGNS.json', campaigns, False), ('FOLDS_AND_SUPPORT.json', folds, False),
        ('AUDIT.json', {'status': 'PASS', 'checks': checks}, False), ('SUMMARY.json', result, False),
    ):
        write(output / filename, data, jsonl)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New output directory; existing output is never overwritten.')
    analyze(parser.parse_args().output)
