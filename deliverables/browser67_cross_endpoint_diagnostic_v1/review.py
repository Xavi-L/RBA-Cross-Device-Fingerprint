#!/usr/bin/env python3
"""Independent B2-A audit: raw operands, selected kernels, separate aggregation.

Does not import run.py, conditions.py, the B2 adapter, or the model predictor.
Reuses original rule kernels to preserve frozen semantics, not their B2 wiring.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.manipulation_eval.adapter import adapt_payload
from hybridguard_agent.research.rule_learning.matrix import extract_atom, control_input
from hybridguard_agent.research.rule_semantics_runtime_input import adapt_runtime_payload
from hybridguard_agent.research.rule_semantics_revision_v1.contracts import SourceBinding
from hybridguard_agent.research.rule_semantics_revision_v1.language import web_language_first_difference
from hybridguard_agent.research import mtc_relation_sources as bindings
from hybridguard_agent.research import timezone_relation_sources as dates
from hybridguard_agent.research import mtc_timezone_relation as timezone
from hybridguard_agent.research import mtc_resource_relations as memory

B1 = ROOT / 'deliverables/browser67_pilot_intake_v1'
MTC = ROOT / 'hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final'
P2 = ROOT / 'hybridguard_agent/artifacts/mtc_p2_frozen_20260922'
RAW = ROOT / 'backend_server/collection_backups/mtc_final_20260922/sources'
MODEL = ROOT / 'deliverables/timezone_relation_validation_v1'
FIELDS = {'C1': ('app.web_data.execution_layer.timezone_offset', 'browser.web_data.execution_layer.timezone_offset'),
          'C2': ('app.web_data.navigator_layer.language', 'browser.web_data.navigator_layer.language'),
          'C3': ('app.web_data.navigator_layer.language', 'browser.web_data.navigator_layer.language'),
          'D1': ('app.web_data.navigator_layer.languages', 'browser.web_data.navigator_layer.languages'),
          'D2': ('browser.web_data.navigator_layer.language', 'browser.web_data.navigator_layer.languages')}


def read(path):
    return json.loads(path.read_text())


def lines(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def dump_rows(path, data):
    path.write_text(''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n' for row in data))


def unique_index(records, field):
    index = {}
    for row in records:
        key = row[field]
        assert key not in index, (field, 'duplicate', key)
        index[key] = row
    return index


def operand(raw, path):
    side, *parts = path.split('.')
    value = raw['canonical_received_payload']
    for part in parts:
        value = value[part]
    payload = raw['canonical_received_payload']
    statuses = payload['collection_status']['fields'] if side == 'app' else payload['field_statuses']
    return value, statuses['.'.join(parts)]


def tag(value):
    # Independent expression of the frozen limited grammar, not a new candidate.
    if not isinstance(value, str): return None
    match = re.fullmatch(r'([a-zA-Z]{2,3})(?:-[a-zA-Z]{4})?(?:-(?:[a-zA-Z]{2}|[0-9]{3}))?', value)
    if not match or match[1].lower() in ('und', 'mul', 'zxx', 'iw', 'in', 'ji'): return None
    return value.lower()


def equal(a, b):
    if type(a) in (int, float) and type(b) in (int, float): return a == b
    if type(a) is not type(b): return False
    if type(a) is list: return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    return a == b


def oracle_condition(cid, values):
    operands = [values[field] for field in FIELDS[cid]]
    if any(status != 'observed' or value is None for value, status in operands): return 'U'
    a, b = [value for value, _ in operands]
    if cid == 'C1':
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (a, b)): return 'U'
        different = a != b
    elif cid == 'D1':
        if any(v == '' or isinstance(v, str) and v.strip().lower() in ('unknown', 'error', 'unsupported', 'not available') for v in (a, b)): return 'U'
        different = not equal(a, b)
    else:
        if cid == 'D2':
            if type(b) is not list or not b or any(type(v) is not str for v in b): return 'U'
            b = b[0]
        a, b = tag(a), tag(b)
        if a is None or b is None: return 'U'
        if cid == 'C3': a, b = a.split('-')[0], b.split('-')[0]
        different = a != b
    return 'T' if different else 'F'


def kernel_state(cell):
    if cell['evaluation_status'] != 'OK': return 'FAILED'
    if not cell['available']: return 'U'
    return 'T' if cell['value'] else 'F'


def independent_app(raw, model, metadata):
    payload = raw['canonical_received_payload']
    assert payload['session_id'] == raw['session_id']
    assert payload['collection_manifest']['collector_version_code'] == 16
    current = adapt_payload(payload)
    bound = bindings._result({'app_session_id': raw['session_id']}, current['features'],
                             current['field_status'], current['field_quality'])
    bound['acquisition_time'] = dates._time_evidence(payload, raw['session_id'], 'independent raw check')
    source_binding = SourceBinding('independent raw check', 'navigator_sync_v1')
    language_input = adapt_runtime_payload(payload, expected_session_id=raw['session_id'],
                                           source_bindings={'LANGUAGE': source_binding}).input_for('LANGUAGE')
    numeric = {aid: (field, threshold) for field, entry in model['encoder']['numeric'].items()
               for aid, threshold in zip(entry['atom_ids'], entry['thresholds'])}
    atom_states = {}
    for atom in model['atoms']:
        aid = atom['atom_id']
        if aid in numeric:
            field, threshold = numeric[aid]
            spec = metadata['controls'][field.removeprefix('UNFITTED_CONTROL:')]
            measured = control_input(current, spec)
            state = kernel_state(measured)
            if state not in ('U', 'FAILED'): state = 'T' if measured['value'] <= threshold else 'F'
        elif aid.startswith('CAT:'):
            state = kernel_state(extract_atom(metadata['candidates'][aid], metadata['rules'][aid[4:]], current))
        elif aid == 'RSR-LANG-FIRST-v1':
            state = kernel_state(web_language_first_difference(*language_input).to_dict())
        elif aid == timezone.TIMEZONE_ID:
            state = kernel_state(timezone.evaluate(bound)[aid])
        elif aid == 'MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE':
            state = kernel_state(memory.evaluate(bound)[aid])
        else:
            raise AssertionError(('unexpected selected atom', aid))
        atom_states[aid] = state
    clauses = []
    for clause in model['clauses']:
        states = [atom_states[lit['atom_id']] if lit['polarity'] == 'POSITIVE' else
                  {'T': 'F', 'F': 'T', 'U': 'U', 'FAILED': 'FAILED'}[atom_states[lit['atom_id']]] for lit in clause['literals']]
        state = 'FAILED' if 'FAILED' in states else 'F' if 'F' in states else 'U' if 'U' in states else 'T'
        clauses.append(state)
    state = 'FAILED' if 'FAILED' in clauses else 'T' if 'T' in clauses else 'U' if 'U' in clauses else 'F'
    return {'state': state, 'atoms': atom_states, 'clauses': clauses}


def audit(results, output):
    output.mkdir(parents=True, exist_ok=True)
    frozen = read(HERE / 'CANDIDATES_FROZEN.json')
    assert frozen == read(HERE / 'review_20261006/before/CANDIDATES_FROZEN.json')
    saved_c = {(row['meta']['sample_id'], row['condition_id']): row for row in lines(results / 'condition_results.jsonl')}
    saved_a = {(row['meta']['sample_id'], row['prediction']['model_id']): row for row in lines(results / 'app_predictions.jsonl')}
    assert len(saved_c) == 4545 and len(saved_a) == 54
    captures = lines(B1 / 'evidence_archive/pilot_r8/captures.jsonl')
    stages = unique_index(lines(B1 / 'local_acceptance/stage_inventory.jsonl'), 'capture_id')
    index = unique_index(lines(B1 / 'local_acceptance/paired244_snapshot/sample_index.jsonl'), 'app_session_id')
    app_raw = lines(B1 / 'evidence_archive/data/raw_expanded_payloads.jsonl')
    browser_raw = lines(B1 / 'evidence_archive/data/raw_browser_payloads.jsonl')
    records = []
    for capture in captures:
        stage = stages[capture['capture_id']]
        for key in ('stage', 'repeat', 'configuration_id', 'runtime_context', 'collection_round'):
            assert capture[key] == stage[key]
        binding = capture['binding'];member = index[binding['app_session_id']]
        assert member['sample_id'] == stage['sample_id']
        app = app_raw[capture['archives']['app']['line'] - 1]
        browser = browser_raw[capture['archives']['browser']['line'] - 1]
        assert binding['app_session_id'] == app['session_id'] == browser['app_session_id']
        assert binding['browser_session_id'] == browser['browser_session_id']
        assert binding['pair_id'] == member['browser_pair_id'] == browser['pair_id']
        group = 'normal' if stage['stage'] in ('clean_pre', 'clean_post') else stage['configuration_id']
        records.append((member['sample_id'], 'pilot', group, app, browser, None))
    members = [row for row in lines(P2 / 'sample_registry.jsonl')
               if row['analysis_role'] == 'primary_representative' and row['source_view'] == 'paired_244']
    assert Counter(m['split'] for m in members) == Counter(discovery=630, development=144, reserved_validation=117)
    paired = lines(MTC / 'paired_244.jsonl')
    apps = lines(RAW / 'raw_expanded_payloads.jsonl')
    browsers = lines(RAW / 'raw_browser_payloads.jsonl')
    for member in members:
        row = paired[member['source_line'] - 1]
        assert member['sample_id'] == row['sample_id']
        assert member['app_raw_line'] == row['source_refs']['app_raw_line']
        app = apps[member['app_raw_line'] - 1]
        browser = browsers[row['source_refs']['browser_raw_line'] - 1]
        assert row['pair']['browser_pair_id'] == browser['pair_id'] == browser['canonical_received_payload']['pair_id']
        assert member['app_session_id'] == app['session_id'] == browser['app_session_id'] == app['canonical_received_payload']['session_id']
        assert browser['browser_session_id'] == row['browser']['session_id'] == browser['canonical_received_payload']['browser_session_id']
        assert member['app_payload_sha256'] == app['payload_sha256'] == row['app']['payload_sha256']
        assert member['browser_payload_sha256'] == browser['browser_payload_sha256'] == row['browser']['payload_sha256']
        records.append((member['sample_id'], 'mtc', member['split'], app, browser, row))
    condition_rows = []
    checks = 0
    for sid, cohort, group, app, browser, projected in records:
        values = {field: operand(app if field.startswith('app.') else browser, field)
                  for field in set(sum((list(v) for v in FIELDS.values()), []))}
        if projected is not None:
            for field, (value, status) in values.items():
                assert projected['features'][field] == value and type(projected['features'][field]) is type(value)
                assert projected['field_status'][field] == status
                assert projected['field_quality'][field] == ('observed_value' if status == 'observed' else 'source_unavailable')
                checks += 1
        states = {}
        for cid in FIELDS:
            state = oracle_condition(cid, values)
            saved = saved_c[(sid, cid)]
            assert (saved['meta']['cohort'], saved['meta']['group']) == (cohort, group)
            assert state == saved['state'], (sid, cid, state, saved['state'])
            for field, saved_value in zip(FIELDS[cid], saved['operands']):
                assert (saved_value['value'], saved_value['status']) == values[field]
            states[cid] = state
        condition_rows.append({'sample_id': sid, 'cohort': cohort, 'group': group, 'states': states})
    freeze = ROOT / 'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R04_freeze_r1'
    protocol = freeze / 'snapshot/hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol'
    metadata = {'candidates': unique_index(lines(protocol / 'CANDIDATE_LEDGER.jsonl'), 'atom_id'),
                'controls': unique_index(read(protocol / 'SINGLE_SURFACE_FIELDS.json')['fields'], 'field'),
                'rules': unique_index(read(ROOT / 'hybridguard_agent/config/paired244_rule_catalog.v3.json')['rules'], 'rule_id')}
    app_results = []
    for mid in read(results / 'MODEL_MANIFEST.json'):
        model = read(ROOT / mid['path'])
        assert model['model_id'] == mid['model_id']
        for sid, cohort, group, raw, browser, projected in records:
            if cohort != 'pilot': continue
            predicted = independent_app(raw, model, metadata)
            saved = saved_a[(sid, mid['model_id'])]['prediction']
            assert predicted['state'] == saved['logical_state']
            assert predicted['atoms'] == {a['atom_id']: a['state'] for a in saved['atom_explanations']}
            assert predicted['clauses'] == [c['state'] for c in saved['clause_explanations']]
            app_results.append({'sample_id': sid, 'model_id': mid['model_id'], **predicted})
    dump_rows(output / 'CONDITION_ORACLE.jsonl', condition_rows)
    dump_rows(output / 'APP_ORACLE.jsonl', app_results)
    summary = {'status': 'PASSED', 'source_pair_checks': len(records), 'mtc_raw_projection_field_checks': checks,
               'independent_condition_comparisons': len(condition_rows) * 5,
               'independent_app_comparisons': len(app_results),
               'candidate_definitions_unchanged': True,
               'independence': 'raw JSON paths and separate candidate implementation; original selected App kernels with independent frozen-threshold and clause aggregation; no B2 loader/compiler/predictor',
               'scope': 'reproduction and implementation audit, not new samples or external validation'}
    write(output / 'INDEPENDENT_AUDIT.json', summary)
    print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', type=Path, default=HERE / 'results')
    parser.add_argument('--output', type=Path, default=HERE / 'review_20261006')
    args = parser.parse_args()
    audit(args.results, args.output)
