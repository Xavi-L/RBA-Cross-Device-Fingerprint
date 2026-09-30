"""Post-hoc explanation from saved cells/traces only; no fit or predict."""
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / 'prepared'
LANG = 'RSR-LANG-FIRST-v1'
WD = 'RSR-WEBDRIVER-STATE-v1'
OLD_WD = 'CONTROL:app.web_data.automation_surface_layer.webdriver:EQ:True'
OLD_LANG = 'UNFITTED_CONTROL:app.web_data.navigator_layer.languages'
TZ = 'UNFITTED_CONTROL:app.web_data.execution_layer.timezone_offset'
DPR = 'UNFITTED_CONTROL:app.web_data.screen_layer.device_pixel_ratio'


def read(path):
    return json.loads(path.read_text())


def literal(row, candidate):
    if candidate in (LANG, WD):
        cell = row['candidate_cells'][candidate]
        assert cell['available'] and cell['evaluation_status'] == 'OK' and type(cell['value']) is bool
        return cell['value']
    field, threshold = {'language_length': (OLD_LANG, 1.0), 'timezone': (TZ, -480.0), 'screen_dpr': (DPR, 2.625)}[candidate]
    cell = row['features'][field]
    assert cell['available'] and cell['evaluation_status'] == 'OK'
    return cell['value'] > threshold


def diagnose():
    contract = read(DATA / 'CONTRACT.json')
    rows = {i: read(DATA / 'inputs' / f'{i}.json') for i in contract['sample_ids']}
    metadata = {i: read(DATA / 'evaluation' / f'{i}.json') for i in rows}
    equivalent = sum(all(r['features'][OLD_WD][k] == r['candidate_cells'][WD][k]
                         for k in ('value', 'available', 'evaluation_status')) for r in rows.values())
    language_ids = {i for i, r in rows.items() if literal(r, LANG)}
    length_ids = {i for i, r in rows.items() if literal(r, 'language_length')}
    folds = []
    for fold in contract['folds']:
        fid = fold['fold_id']
        sparse = read(DATA / 'trials' / f'LANG_ADD_WD_REPLACE__{fid}__SPARSE' / 'training.json')
        trace = sparse['trace']
        ties = []
        # Fixed comparisons explaining the observed choices, not a new search.
        for index, left, right, left_id, right_id in [
            (1, 'timezone', WD, 'CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE', WD + ':POSITIVE'),
            (3, 'language_length', LANG, 'CONTROL:app.web_data.navigator_layer.languages:LE:1.0:NEGATIVE', LANG + ':POSITIVE'),
            (4, 'screen_dpr', WD, 'CONTROL:app.web_data.screen_layer.device_pixel_ratio:LE:2.625:NEGATIVE', WD + ':POSITIVE'),
        ]:
            prefix = trace[index]['score']['states']
            assert len(prefix) == len(fold['train_ids']) and set(prefix) <= {'T', 'F'}
            comparison = []
            for candidate in (left, right):
                union = {i for i, state in zip(fold['train_ids'], prefix, strict=True)
                         if state == 'T' or literal(rows[i], candidate)}
                attack = sum(metadata[i]['phase'] == 'attack' for i in union)
                clean = len(union) - attack
                complexity = trace[index]['score']['complexity'] + 2
                objective = Fraction(attack, 84) - Fraction(5, 1000) * complexity
                comparison.append({'candidate': candidate, 'attack_alerts': attack, 'attack_n': 84,
                                   'clean_alerts': clean, 'coverage': 1.0, 'complexity': complexity,
                                   'objective': str(objective)})
            assert {k: v for k, v in comparison[0].items() if k != 'candidate'} == {k: v for k, v in comparison[1].items() if k != 'candidate'}
            assert left_id < right_id and left_id in trace[index + 1]['selected']
            ties.append({'after_selected_clauses': index + 1, 'comparison': comparison,
                         'registered_lexical_tie_winner': left_id, 'observed_in_saved_next_step': True})
        models = {}
        for group in ('BASE', 'LANG_ADD_WD_REPLACE'):
            original = read(DATA / 'trials' / f'{group}__{fid}__SPARSE' / 'model.json')
            retained = read(DATA / 'trials' / f'{group}__{fid}__RETENTION' / 'model.json')
            assert original['clauses'] == retained['clauses']
            models[group] = {'retention_stop': retained['fit']['stop'], 'clause_count': len(retained['clauses']),
                             'retention_changed_initializer': False,
                             'selected_new_candidates': sorted({l['atom_id'] for c in retained['clauses'] for l in c['literals']} & {LANG, WD})}
        support = {k: {field: value for field, value in v.items() if field in
                       ('triplets', 'true_attack_triplets', 'bundles', 'environments', 'eligible', 'phase_availability')}
                   for k, v in sparse['support'].items() if k in (LANG + ':POSITIVE', WD + ':POSITIVE')}
        folds.append({'fold_id': fid, 'models': models, 'new_positive_support': support, 'saved_trace_tie_diagnostics': ties})
    results = read(DATA / 'RESULTS.json')
    changed = [{**r, **{key: metadata[r['opaque_id']][key] for key in ('config_id', 'environment_group_id', 'triplet_id')}}
               for r in results['changed_decisions']]
    return {'status': 'PASS', 'scope': 'POST_HOC_SAVED_ARTIFACT_DIAGNOSTIC_ONLY',
            'additional_fit_calls': 0, 'additional_model_predict_calls': 0,
            'old_new_webdriver_equal_state_members': equivalent, 'primary_members': len(rows),
            'new_language_true_members': len(language_ids), 'old_length_gt_one_true_members': len(length_ids),
            'new_language_true_outside_old_length': len(language_ids - length_ids),
            'changed_decisions': changed, 'folds': folds,
            'interpretation': 'Both new positive literals are eligible. Name-based tie resolution changes which six clauses fit. R_KEEP only adds and is already at its six-clause limit. No new clause is selected in the combination models.'}


if __name__ == '__main__':
    result = diagnose()
    with (HERE / 'SELECTION_DIAGNOSIS.json').open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('folds', 'changed_decisions')}, ensure_ascii=False, indent=2))
