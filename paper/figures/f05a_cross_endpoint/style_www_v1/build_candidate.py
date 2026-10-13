"""Draw only F05a from saved states; no research or inference entrypoints."""
from pathlib import Path
from collections import Counter
from html import escape
import argparse
import csv
import itertools
import json
import os
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DATA = HERE/'data'
SAVED = ROOT/'paper/figures/round2_paired'
RESOURCE = ROOT/'deliverables/app_resource_constrained_extension_v1/results'
TABLES = ROOT/'deliverables/app_browser_evidence_consolidation_v1/tables.json'
MODELS = ROOT/'deliverables/cross_endpoint_constrained_extension_v1/results/models.json'
METHODS = ['APP_FULL', 'PAIRED_BASE']
ALIASES = {'APP_FULL': 'Full App', 'PAIRED_BASE': 'App + C1'}
FAMILIES = ['App_language', 'App_timezone', 'Browser_language', 'Browser_timezone']
CONFIGS = ['01', '02', '03']
COUNTS = ['N', 'T', 'F', 'U', 'FAILED', 'defined']
COHORTS = {'pilot18', 'b2b42'}
W, H, FONT_SIZE = 860, 403, 31
X0, X1, OFFSET = 362, 820, 17.5
ROW_CENTERS = [74, 144, 214, 284]
INK, GRAY, GREEN = '#343434', '#737A80', '#5B8574'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def jsonl(path):
    return [(i, json.loads(line)) for i, line in enumerate(path.read_text().splitlines(), 1) if line.strip()]


def capture_generation_baseline():
    original = json.loads((HERE/'SOURCE_MANIFEST.json').read_text())['baseline']
    stats = {}
    for name in original['protected_file_stats']:
        stat = (ROOT/name).stat()
        # Node rewrites CHECK.json: strings preserve nanosecond integer precision.
        stats[name] = {'size': stat.st_size, 'mtime_ns': str(stat.st_mtime_ns)}
    return {
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'status_porcelain_v1_z': subprocess.check_output(
            ['git', 'status', '--porcelain=v1', '-z', '--untracked-files=all'], cwd=ROOT).decode(),
        'index_status': subprocess.check_output(['git', 'diff', '--cached', '--name-status'], cwd=ROOT, text=True),
        'protected_file_stats': stats,
    }


def counts(states):
    require(set(states) <= {'T', 'F', 'U', 'FAILED'}, 'Unexpected saved state')
    c = Counter(states)
    return {'N': len(states), **{k: c[k] for k in ['T', 'F', 'U', 'FAILED']}, 'defined': c['T']+c['F']}


def verify_and_extract():
    DATA.mkdir(exist_ok=True)
    rows = read_csv(SAVED/'data/F05a.csv')
    expected_keys = set(itertools.product(METHODS, CONFIGS, FAMILIES+['NORMAL']))
    actual_keys = [(r['method'], r['configuration'], r['family']) for r in rows]
    require(len(rows) == 30 and len(set(actual_keys)) == 30 and set(actual_keys) == expected_keys,
            'F05a.csv must contain exactly 2 methods x 3 configurations x 5 groups')
    require(all(r['figure'] == 'F05a' and r['dataset'] == 'language_timezone60' for r in rows), 'Mixed figure/dataset')
    members = [(line, r) for line, r in jsonl(RESOURCE/'members.jsonl') if r['cohort'] in COHORTS]
    inputs = [(line, r) for line, r in jsonl(RESOURCE/'inputs.jsonl') if r['cohort'] in COHORTS]
    require(len(members) == len(inputs) == 60, 'Expected 60 selected positions')
    require(Counter(r['cohort'] for _, r in members) == {'pilot18': 18, 'b2b42': 42}, 'Cohort partition')
    # The source-local join key is used only in memory, never exported.
    members_by_id = {r['sample_id']: (line, r) for line, r in members}
    inputs_by_id = {r['sample_id']: (line, r) for line, r in inputs}
    require(len(members_by_id) == len(inputs_by_id) == 60 and members_by_id.keys() == inputs_by_id.keys(),
            'Selected membership/input keys differ or repeat')
    selected = []
    for key, (ml, member) in members_by_id.items():
        il, saved = inputs_by_id[key]
        require(all(member[k] == saved[k] for k in ['cohort', 'role', 'identity']), ('Source join disagreement', ml, il))
        require(member['identity'] in {'NORMAL', 'EFFECTIVE_INTERVENTION'}, ('Unsupported identity', ml))
        group = 'NORMAL' if member['identity'] == 'NORMAL' else member['family']
        require(group in FAMILIES+['NORMAL'], ('Wrong intervention family', ml))
        selected.append({'member_line': ml, 'input_line': il, 'cohort': member['cohort'],
                         'identity': member['identity'], 'family': group, '_saved': saved})
    selected.sort(key=lambda r: r['member_line'])
    require(Counter(r['family'] for r in selected) == dict(zip(FAMILIES+['NORMAL'], [2, 2, 5, 5, 46])), 'Group denominators')
    tables = json.loads(TABLES.read_text())
    accepted = json.loads(MODELS.read_text())
    bridges = tables['models']
    mapping = {}
    for config in CONFIGS:
        bridge = [m for m in bridges if m['fold'] == 'WEBGL1-LOEO-v1-'+config]
        require(len(bridge) == 1, ('Ambiguous configuration mapping', config))
        bridge = bridge[0]
        model = [m for m in accepted if m['model_id'] == bridge['base_model_id']]
        require(len(model) == 1, ('Missing accepted model', config))
        model = model[0]
        require(model['extensions'] == ['C1'] and model['status'] == 'SELECTED_EXTENSION', ('C1-only identity', config))
        require(model['base_model_id'] == bridge['app_model_id'] == model['base']['model_id'], ('App identity', config))
        require(model['base']['fold'] == bridge['fold'] and model['base']['stage'] == 'RETENTION', ('App fold/stage', config))
        require(bridge['selected_set'] == 'S0' and bridge['status'] == 'BASELINE_RETAINED', 'Resource baseline identity changed')
        mapping[config] = {'configuration': config, 'fold': bridge['fold'],
            'base_model_id_in_inputs': bridge['base_model_id'], 'app_model_id': bridge['app_model_id'],
            'accepted_extensions': model['extensions'], 'accepted_status': model['status'],
            'resource_selection': 'S0 (retained paired baseline; no resource extension)',
            'tables_locator': '/models/'+str(bridges.index(bridge)),
            'accepted_models_locator': '/'+str(accepted.index(model))}
    normalized, sources = [], []
    for csv_line, row in enumerate(rows, 2):
        method, config, family = (row[k] for k in ['method', 'configuration', 'family'])
        field = 'app_states' if method == 'APP_FULL' else 'base_states'
        require(row['source_path'] == str((RESOURCE/'inputs.jsonl').relative_to(ROOT)), 'Inputs path')
        require(row['members_source_path'] == str((RESOURCE/'members.jsonl').relative_to(ROOT)), 'Members path')
        locator = re.fullmatch(r'(app_states|base_states)\[([^\]]+)\]; input lines ([0-9,]+)', row['source_locator'])
        require(locator is not None, ('Unsupported saved locator', csv_line))
        model_id = mapping[config]['base_model_id_in_inputs']
        require(locator[1] == field and locator[2] == model_id, ('State field/model ID', config, family, csv_line))
        group = [r for r in selected if r['family'] == family]
        input_lines = [r['input_line'] for r in group]; member_lines = [r['member_line'] for r in group]
        require([int(n) for n in locator[3].split(',')] == input_lines, ('Inputs locator/membership mismatch', config, family))
        require(row['members_source_locator'] == 'lines '+','.join(map(str, member_lines)), ('Members locator mismatch', config, family))
        require(row['identity'] == ('NORMAL' if family == 'NORMAL' else 'EFFECTIVE_INTERVENTION'), 'Group identity')
        require(row['method_role'] == ('complete_app' if method == 'APP_FULL' else 'retained_complete_paired_base'), 'Method role')
        states = [r['_saved'][field][model_id] for r in group]
        actual = counts(states)
        for key in COUNTS:
            require(actual[key] == int(row[key]), ('F05a.csv / inputs.jsonl conflict', config, method, family, key, row[key], actual[key]))
        require(float(row['rate']) == actual['T']/actual['N'] and float(row['defined_rate']) == actual['defined']/actual['N'], 'Saved ratio')
        record = {'configuration': config, 'method': method, 'method_label': ALIASES[method],
                  'family': family, 'identity': row['identity'], **actual}
        normalized.append(record)
        sources.append({**record, 'figure_csv_line': csv_line, 'base_model_id_in_inputs': model_id,
                        'state_field': field, 'input_lines': input_lines, 'member_lines': member_lines,
                        'cohorts': dict(Counter(r['cohort'] for r in group))})
    crosschecks = []
    table_rows = [(i, r) for i, r in enumerate(tables['paired']) if r['dataset'] == 'language_timezone60' and r['method'] in METHODS]
    require(len(table_rows) == 6, 'Six independent consolidated comparison rows required')
    for config, method in itertools.product(CONFIGS, METHODS):
        matches = [(i, r) for i, r in table_rows if r['label'] == method+'_'+config and r['method'] == method]
        require(len(matches) == 1, ('Consolidated label', config, method))
        index, saved = matches[0]; actual = {}
        for side in ['App', 'Browser', 'NORMAL']:
            subset = [r for r in normalized if r['configuration'] == config and r['method'] == method
                      and (r['family'] == 'NORMAL' if side == 'NORMAL' else r['family'].startswith(side+'_'))]
            actual[side] = {k: sum(r[k] for r in subset) for k in COUNTS}
            require({('N' if k == 'n' else k): v for k, v in saved[side].items()} == actual[side],
                    ('tables.json conflict', config, method, side))
        crosschecks.append({'configuration': config, 'method': method, 'tables_locator': '/paired/'+str(index), 'counts': actual, 'pass': True})
    equality, common = [], {}
    for method, family in itertools.product(METHODS, FAMILIES+['NORMAL']):
        group = [r for r in normalized if r['method'] == method and r['family'] == family]
        require(len(group) == 3 and {r['configuration'] for r in group} == set(CONFIGS), 'Configuration completeness')
        require(len({tuple(r[k] for k in COUNTS) for r in group}) == 1, ('Cannot compress unequal counts', method, family))
        actual = {k: group[0][k] for k in COUNTS}
        equality.append({'method': method, 'family': family, 'configurations': CONFIGS, 'counts': actual, 'equal': True})
        common[(method, family)] = actual
    # Acceptance assertions only: the graph below uses the verified source counts.
    expected = {'APP_FULL': [0, 2, 0, 0], 'PAIRED_BASE': [0, 2, 0, 5]}
    totals = {}
    for method in METHODS:
        require([common[(method, f)]['T'] for f in FAMILIES] == expected[method], ('Expected detection counts', method))
        normal = common[(method, 'NORMAL')]
        require(normal == {'N': 46, 'T': 0, 'F': 46, 'U': 0, 'FAILED': 0, 'defined': 46}, ('Normal count', method))
        totals[method] = {k: sum(common[(method, f)][k] for f in FAMILIES) for k in COUNTS}
        require(totals[method]['N'] == 14 and totals[method]['T'] == (2 if method == 'APP_FULL' else 7), 'Intervention total')
    require(all(r['U'] == r['FAILED'] == 0 for r in normalized), 'Shown missing/failed results require an explicit visual treatment')
    plotted = []
    for order, family in enumerate(FAMILIES, 1):
        for method in METHODS:
            actual = common[(method, family)]
            plotted.append({'row_order': order, 'family': family, 'label': family.replace('_', ' '),
                            'method': method, 'method_label': ALIASES[method], **actual,
                            'rate_pct': 100*actual['T']/actual['N'], 'display': f"{actual['T']}/{actual['N']}",
                            'configurations': ';'.join(CONFIGS)})
    write_csv(DATA/'F05a_all_configurations.csv', rows)
    write_csv(DATA/'counts_by_configuration.csv', normalized)
    write_csv(DATA/'plot_data.csv', plotted)
    write_csv(DATA/'normal_counts.csv', [r for r in normalized if r['family'] == 'NORMAL'])
    write_csv(DATA/'selected_source_lines.csv', [{k: v for k, v in r.items() if k != '_saved'} for r in selected])
    dump(DATA/'configuration_models.json', mapping)
    dump(DATA/'configuration_equality.json', equality)
    dump(DATA/'consolidated_crosschecks.json', crosschecks)
    dump(DATA/'source_mapping.json', {'figure_csv': str((SAVED/'data/F05a.csv').relative_to(ROOT)),
        'inputs': str((RESOURCE/'inputs.jsonl').relative_to(ROOT)), 'members': str((RESOURCE/'members.jsonl').relative_to(ROOT)),
        'line_numbers_are_one_based': True, 'no_source_local_member_ids_exported': True, 'rows': sources})
    report = {'pass': True, 'original_rows': 30, 'methods': METHODS, 'method_aliases': ALIASES,
        'families': FAMILIES, 'configurations': CONFIGS, 'cohorts': {'pilot18': 18, 'b2b42': 42},
        'unique_evaluation_positions': 60, 'interventions': 14, 'normal_positions': 46,
        'resource54_included': False, 'state_fields_verified': COUNTS, 'configuration_equal_groups': len(equality),
        'consolidated_rows_verified': len(crosschecks), 'actual_base_model_ids_used': True,
        'accepted_extensions': ['C1'], 'counts_by_method': {m: [r['display'] for r in plotted if r['method'] == m] for m in METHODS},
        'intervention_totals': totals, 'normal_by_method': {m: common[(m, 'NORMAL')] for m in METHODS},
        'record_level_equality_claimed': False, 'denominators_pooled': False,
        'independent_repetitions_claimed': False, 'research_entrypoints_called': False, 'C1_recomputed': False,
        'raw_fingerprints_or_member_ids_exported': False, 'plotted_markers': 8}
    return plotted, report


def draw(plotted):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="86mm" height="{H/10:g}mm" viewBox="0 0 {W} {H}">',
        '<title>Detection added by the accepted cross-endpoint timezone check</title>',
        '<desc>Four intervention categories compare Full App (hollow gray circle, upper marker) with App + C1 (filled gray-green square, lower marker). Every point reports T/N. Both methods have 0/46 normal alarms, reported separately in the caption. Counts hold separately across three frozen configurations.</desc>',
        f'<g font-family="Times New Roman" fill="{INK}">', f'<rect width="{W}" height="{H}" fill="#ffffff" data-role="canvas"/>']
    def text(x, y, value, role, anchor='start', attrs=''):
        parts.append(f'<text x="{x:g}" y="{y:g}" font-size="{FONT_SIZE}" text-anchor="{anchor}" data-role="{role}" {attrs}>{escape(value)}</text>')
    def marker(method, x, y, role, attrs=''):
        if method == 'APP_FULL':
            parts.append(f'<circle cx="{x:g}" cy="{y:g}" r="8.5" fill="#ffffff" stroke="{GRAY}" stroke-width="2.8" data-role="{role}" {attrs}/>')
        else:
            parts.append(f'<rect x="{x-8:g}" y="{y-8:g}" width="16" height="16" fill="{GREEN}" data-role="{role}" {attrs}/>')
    for method, x in zip(METHODS, [250, 490]):
        marker(method, x, 18, 'legend-marker', f'data-method="{method}"')
        text(x+23, 28, ALIASES[method], 'legend', attrs=f'data-method="{method}"')
    for tick in [0, 50, 100]:
        x = X0+(X1-X0)*tick/100
        parts.append(f'<line x1="{x:g}" y1="48" x2="{x:g}" y2="328" stroke="#E1E4E7" stroke-width="1.25" data-role="grid" data-rate="{tick}"/>')
        parts.append(f'<line x1="{x:g}" y1="328" x2="{x:g}" y2="332" stroke="#9BA2A8" stroke-width="1.5" data-role="tick"/>')
        text(x, 360, str(tick), 'tick-label', anchor='middle')
    parts.append(f'<line x1="{X0}" y1="328" x2="{X1}" y2="328" stroke="#9BA2A8" stroke-width="1.5" data-role="axis"/>')
    text((X0+X1)/2, 395, 'Detection rate (%)', 'axis-label', anchor='middle')
    for family, y in zip(FAMILIES, ROW_CENTERS):
        text(8, y+10, family.replace('_', ' '), 'row-label', attrs=f'data-family="{family}"')
    positions = []
    for r in plotted:
        x = X0+(X1-X0)*r['rate_pct']/100
        y = ROW_CENTERS[r['row_order']-1]+(-OFFSET if r['method'] == 'APP_FULL' else OFFSET)
        point = r['family']+'-'+r['method']
        attrs = f'data-point="{point}" data-method="{r["method"]}" data-family="{r["family"]}" data-count="{r["display"]}" data-rate="{r["rate_pct"]:g}"'
        marker(r['method'], x, y, 'data-marker', attrs)
        lx = x+23 if r['rate_pct'] <= 50 else x-23
        text(lx, y+10, r['display'], 'count', anchor='start' if r['rate_pct'] <= 50 else 'end', attrs=attrs)
        positions.append({'id': point, 'method': r['method'], 'family': r['family'], 'x': x, 'y': y,
                          'rate': r['rate_pct'], 'display': r['display'], 'label_x': lx, 'label_y': y+10})
    parts.append('</g></svg>')
    (HERE/'F05a_main.svg').write_text('\n'.join(parts)+'\n')
    return {'size_mm': [W/10, H/10], 'viewbox': [W, H], 'font': 'Times New Roman',
        'minimum_font_units': FONT_SIZE, 'ink': INK, 'method_colors': {'APP_FULL': GRAY, 'PAIRED_BASE': GREEN},
        'method_shapes': {'APP_FULL': 'hollow circle', 'PAIRED_BASE': 'filled square'},
        'method_vertical_order': METHODS, 'x0': X0, 'x1': X1, 'x_limits': [0, 100], 'ticks': [0, 50, 100],
        'row_centers': ROW_CENTERS, 'series_vertical_offset': OFFSET, 'horizontal_jitter': 0,
        'normal_result_location': 'formal caption, outside detection axis', 'main_title_visible': False,
        'colorbar': False, 'data_connectors': 0, 'error_bars': False, 'markers': positions}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--baseline', type=Path); args = parser.parse_args()
    if not (HERE/'SOURCE_MANIFEST.json').exists():
        require(args.baseline is not None, 'First build requires a pre-edit baseline')
        baseline = json.loads(args.baseline.read_text())
        sources = [SAVED/'data/F05a.csv', RESOURCE/'members.jsonl', RESOURCE/'inputs.jsonl', TABLES, MODELS]
        dump(HERE/'SOURCE_MANIFEST.json', {'candidate': 'F05a_main', 'baseline': baseline,
            'source_files': [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size} for p in sources],
            'scope': 'Saved states only; pilot18 and b2b42. No model/condition inference or experiment summary entrypoints.',
            'reference_pdf': {'path': '_WWW__Lower_Barriers__Greater_Threat_.pdf', 'figure_1_page': 5, 'table_1_page': 6},
            'accepted_F01': 'paper/figures/f01_app_detection/style_www_v1/F01_main_rev4.pdf',
            'accepted_mechanisms': 'paper/figures/f03a_f04_mechanisms/style_www_v1/F03a_F04_main.pdf',
            'accepted_overview': 'paper/figures/overview_triangle/style_full_v1/HybridGuard_overview_candidate.pdf',
            'checks': 'Targeted saved-state/count comparisons, protected file size/mtime, and Git status; no hash scan.'})
    baseline = capture_generation_baseline()
    plotted, data = verify_and_extract(); layout = draw(plotted)
    dump(HERE/'layout.json', layout)
    dump(HERE/'CHECK.json', {'data': data, 'layout': layout, 'generation_baseline': baseline,
                           'visual_review': {'status': 'PENDING', 'actually_viewed': []}})
    node = os.environ.get('RBA_NODE', str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'))
    subprocess.run([node, str(HERE/'render_candidate.cjs')], check=True, cwd=HERE)
    subprocess.run([sys.executable, '-B', str(HERE/'check_candidate.py')], check=True, cwd=HERE)


if __name__ == '__main__':
    main()
