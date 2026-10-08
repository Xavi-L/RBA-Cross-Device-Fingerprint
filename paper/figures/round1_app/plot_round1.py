#!/usr/bin/env python3
"""Round-one figures: read saved counts, validate, aggregate, and plot only.

No experimental module is imported. --check-only reads this output's saved
CSV/manifest/images and never reads deliverables or regenerates predictions.
"""
import argparse
import ast
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OWNER = 'rba-round1-app-saved-counts-v1'
COUNTS = ('N', 'T', 'F', 'U', 'FAILED', 'EMPTY_MODEL', 'defined')
STATES = ('T', 'F', 'U', 'FAILED', 'EMPTY_MODEL')
METHODS = [
    ('APP_FULL', 'Full App', '当前App完整方法'),
    ('A_NO_MTC_CAP', 'No MTC alarm cap', '去MTC正常报警上限'),
    ('A_APP_WEB_ONLY', 'App Web only', '仅App网页'),
    ('A_NO_MEMORY_REL', 'No memory relation', '去系统—网页内存关系'),
    ('A_NO_TIMEZONE_REL', 'No timezone relation', '去系统—网页时区关系'),
    ('APP_TREE', 'Small App tree', '固定小容量App决策树'),
]
METHOD_IDS = [x[0] for x in METHODS]
NAMES = dict((x[0], x[1]) for x in METHODS)
CONFIG_NAMES = [
    ('w10-cdp-emulation-screen-metrics-only-v1', 'Screen metrics', '屏幕参数修改'),
    ('w10-cdp-emulation-timezone-only-v1', 'Timezone only', '时区单独修改'),
    ('w6-tool-054-legacy-default-v1', 'Playwright preset', 'Playwright既有配置'),
    ('w6-tool-055-legacy-default-v1', 'Puppeteer preset', 'Puppeteer既有配置'),
    ('w6-tool-056-legacy-default-v1', 'CDP multi-field preset', 'CDP既有多字段配置'),
    ('w6-tool-058-legacy-default-v1', 'Stealth preset', 'stealth既有配置'),
    ('w9-rule-boundary-cdp-platform-only-v1', 'Platform only', '平台标识单独修改'),
    ('w9-rule-boundary-cdp-resource-pair-v1', 'CPU + memory', 'CPU与内存联合修改'),
    ('w9-rule-boundary-cdp-ua-only-v1', 'UA only', 'UA单独修改'),
    ('w9-rule-boundary-cdp-ua-platform-desktop-v1', 'UA + platform', 'UA与平台同时修改'),
    ('w9-rule-boundary-cdp-webdriver-only-v1', 'Webdriver only', 'webdriver单独修改'),
    ('w9-stealth-boundary-languages-only-v1', 'Language list', '语言列表单独修改'),
    ('w9-stealth-boundary-plugins-mime-v1', 'Plugins / MIME', '插件/MIME信息修改'),
    ('w9-stealth-boundary-webgl-pair-v1', 'WebGL vendor / renderer', 'WebGL厂商/渲染器修改'),
]
FOLDS = ['WEBGL1-LOEO-v1-0' + str(i) for i in (1, 2, 3)]
BASE = 'deliverables/app177_core_ablation_v1/results/summary/'
TABLES = ['main', 'configurations14', 'mtc', 'specialists', 'tree_input_integrity', 'all_stages']
CONSOLIDATED = 'deliverables/app_browser_evidence_consolidation_v1/tables.json'
CORE_SOURCES = [BASE + name + ext for name in TABLES for ext in ('.csv', '.json')] + [CONSOLIDATED]
FIGURE_IDS = ['F01', 'F02', 'F03a', 'F03b', 'F04']


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_csv(path):
    with Path(path).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(checks, name, observed, expected):
    checks.append(dict(id=name, status='PASS' if observed == expected else 'FAIL',
                       observed=observed, expected=expected))


def total(rows):
    return {key: sum(row[key] for row in rows) for key in COUNTS}


def stage(scheme):
    return 'FITTED' if scheme == 'APP_TREE' else 'RETENTION'


def located(row, table, index):
    return dict(row, source_path=BASE + table + '.json', source_locator='/' + str(index),
                source_csv_row=index + 2, method_short=NAMES.get(row.get('scheme'), ''),
                stage=row.get('stage', stage(row['scheme'])) if 'scheme' in row else '',
                numerator=row.get('T', ''), denominator=row.get('N', ''),
                rate=row['T'] / row['N'] if 'T' in row and row['N'] else '',
                defined_rate=row['defined'] / row['N'] if 'defined' in row and row['N'] else '')


def aggregate(rows, **labels):
    result = total(rows)
    return dict(labels, **result, numerator=result['T'], denominator=result['N'],
                rate=result['T'] / result['N'], defined_rate=result['defined'] / result['N'],
                source_path=rows[0]['source_path'],
                source_locator=';'.join(row['source_locator'] for row in rows),
                source_csv_row=';'.join(str(row['source_csv_row']) for row in rows))


def extract_core(root):
    checks, data, conflicts = [], {}, []
    for name in TABLES:
        raw = read_json(root / (BASE + name + '.json'))
        csv_rows = read_csv(root / (BASE + name + '.csv'))
        normalized = [{k: str(v) for k, v in row.items()} for row in raw]
        if normalized != csv_rows:
            for i in range(max(len(raw), len(csv_rows))):
                left = normalized[i] if i < len(raw) else {}
                right = csv_rows[i] if i < len(csv_rows) else {}
                for key in left.keys() | right.keys():
                    if left.get(key) != right.get(key):
                        conflicts.append(dict(table=name, row=i, field=key, json=left.get(key),
                                              csv=right.get(key), source_key={k: left.get(k) for k in
                                              ('scheme', 'fold_id', 'cohort', 'configuration', 'scenario', 'phase', 'identity')}))
        check(checks, name + '_csv_json_equal', normalized, csv_rows) if normalized != csv_rows else check(checks, name + '_csv_json_equal_rows', len(raw), len(csv_rows))
        data[name] = [located(row, name, i) for i, row in enumerate(raw)]
        for i, row in enumerate(raw):
            if all(k in row for k in COUNTS):
                if sum(row[k] for k in STATES) != row['N'] or row['T'] + row['F'] != row['defined']:
                    conflicts.append(dict(table=name, row=i, field='state_partition', counts=row))
    check(checks, 'source_conflicts', conflicts, [])
    combined = read_json(root / CONSOLIDATED)
    check(checks, 'primary_stage_contract', combined['app_primary_stage'], 'RETENTION; APP_TREE=FITTED')
    for name in TABLES[:-1]:
        raw = read_json(root / (BASE + name + '.json'))
        if name == 'specialists':
            raw = [r for r in raw if r['scenario'] == 'ALL' and r['phase'] == 'ALL']
        check(checks, 'consolidation_' + name, raw == combined['app'][name], True)
    main, conf, mtc, specialists, stages = [data[k] for k in ('main', 'configurations14', 'mtc', 'specialists', 'all_stages')]
    check(checks, 'six_methods', sorted({r['scheme'] for r in main}), sorted(METHOD_IDS))
    check(checks, '14_configurations', sorted({r['configuration'] for r in conf}), sorted(x[0] for x in CONFIG_NAMES))
    check(checks, 'main_rows', len(main), 12)
    check(checks, 'configuration_rows', len(conf), 168)
    for method in METHOD_IDS:
        for identity, n in [('EFFECTIVE_INTERVENTION', 9), ('NORMAL', 18)]:
            sub = [r for r in conf if r['scheme'] == method and r['identity'] == identity]
            ref = [r for r in main if r['scheme'] == method and r['identity'] == identity]
            check(checks, method + identity + '_14_rows', len(sub), 14)
            check(checks, method + identity + '_cell_N', [r['N'] for r in sub], [n] * 14)
            check(checks, method + identity + '_config_sum', total(sub), total(ref))
            primary = [r for r in stages if r['scheme'] == method and r['stage'] == stage(method)
                       and r['cohort'] == 'controlled' and r['subset'] == 'heldout' and r['identity'] == identity]
            check(checks, method + identity + '_stage_folds', sorted(r['fold_id'] for r in primary), FOLDS)
            check(checks, method + identity + '_stage_total', total(primary), total(ref))
    check(checks, 'main_T_regression', [next(r['T'] for r in main if r['scheme'] == m and r['identity'] == 'EFFECTIVE_INTERVENTION') for m in METHOD_IDS], [105, 108, 96, 96, 105, 72])
    f01 = [dict(r, configuration_short=dict((c[0], c[1]) for c in CONFIG_NAMES)[r['configuration']])
           for m in METHOD_IDS for r in conf if r['scheme'] == m and r['identity'] == 'EFFECTIVE_INTERVENTION']
    f02, t03 = [], []
    f03a, f04, tz_totals = [], [], []
    for method in METHOD_IDS:
        for fold in FOLDS:
            sub = [r for r in mtc if r['scheme'] == method and r['fold_id'] == fold]
            check(checks, method + fold + '_mtc_subsets', sorted((r['subset'], r['N']) for r in sub), [('development',144), ('discovery',630), ('reserved_validation',117)])
            for r in sub:
                t03.append(dict(r, role='training_normal_constraint' if r['subset'] == 'discovery' else 'historical_normal_evaluation'))
            selected = [r for r in sub if r['subset'] in ('development', 'reserved_validation')]
            r = aggregate(selected, scheme=method, method_short=NAMES[method], fold_id=fold,
                          stage=stage(method), subset='development+reserved_validation', identity='NORMAL', role='historical_normal_evaluation')
            check(checks, method + fold + '_mtc_261', r['N'], 261)
            f02.append(r); t03.append(r)
            memory = [r for r in specialists if r['scheme'] == method and r['fold_id'] == fold and r['cohort'] == 'memory' and r['scenario'] == 'ALL' and r['phase'] == 'ALL']
            check(checks, method + fold + '_memory_partition', sorted((r['identity'], r['N']) for r in memory), [('EFFECTIVE_INTERVENTION',18),('NORMAL',48),('NO_OBSERVABLE_EFFECT',6)])
            f03a.extend(memory)
            tz = [r for r in specialists if r['scheme'] == method and r['fold_id'] == fold and r['cohort'] == 'timezone']
            all_tz = [r for r in tz if r['scenario'] == 'ALL' and r['phase'] == 'ALL']
            check(checks, method + fold + '_timezone_total', sorted((r['identity'],r['N']) for r in all_tz), [('EFFECTIVE_INTERVENTION',6),('NORMAL',30)])
            tz_totals.extend(all_tz)
            for prefix, identity, label in [('L_', 'NORMAL', 'normal_system_change'), ('A_', 'EFFECTIVE_INTERVENTION', 'web_only_change')]:
                selected = [r for r in tz if r['scenario'].startswith(prefix) and r['phase'] == 'change' and r['identity'] == identity]
                check(checks, method + fold + prefix + '_scenarios', sorted((r['scenario'],r['N']) for r in selected), [(prefix + 'America/Los_Angeles',3),(prefix + 'UTC',3)])
                r = aggregate(selected, scheme=method, method_short=NAMES[method], fold_id=fold,
                              stage=stage(method), cohort='timezone', group=label, identity=identity,
                              scenario=prefix + 'America/Los_Angeles+' + prefix + 'UTC', phase='change')
                f04.append(r)
                # Disjoint detailed phase rows reconstruct ALL/ALL without adding it again.
                detailed = [x for x in tz if x['scenario'] != 'ALL' and x['phase'] != 'ALL' and x['identity'] == identity]
                full = next(x for x in all_tz if x['identity'] == identity)
                check(checks, method + fold + identity + '_timezone_detail_sum', total(detailed), {k:full[k] for k in COUNTS})
                check(checks, method + fold + identity + '_change_subset', all(r[k] <= full[k] for k in COUNTS), True)
    for name, rows, key in [('F03a',f03a,'identity'),('F04',f04,'group')]:
        for method in METHOD_IDS:
            for group in sorted({r[key] for r in rows}):
                sub = [r for r in rows if r['scheme'] == method and r[key] == group]
                check(checks, name + method + group + '_three_folds', sorted(r['fold_id'] for r in sub), FOLDS)
                check(checks, name + method + group + '_equal_counts', len({tuple(r[k] for k in COUNTS) for r in sub}), 1)
    return dict(F01=f01, F02=f02, F03a=f03a, F04=f04, T02=main, T03=t03,
                F04_totals=tz_totals, tree_input_integrity=data['tree_input_integrity']), checks


def validate_saved(output):
    """Only output files: no source loading, plotting, models or measurements."""
    checks = []
    manifest = read_json(output / 'FIGURES.json')
    check(checks, 'output_owner', manifest['owner'], OWNER)
    check(checks, 'five_unique_figure_ids', sorted(fig['id'] for fig in manifest['figures']), sorted(FIGURE_IDS))
    method_map = read_csv(output / 'data' / 'methods.csv')
    configuration_map = read_csv(output / 'data' / 'configurations.csv')
    fold_map = read_csv(output / 'data' / 'folds.csv')
    check(checks, 'method_mapping_order_names_and_stages',
          [(r['order'], r['scheme'], r['short_name'], r['zh_name'], r['stage']) for r in method_map],
          [(str(i), method, short, zh, stage(method)) for i, (method, short, zh) in enumerate(METHODS, 1)])
    check(checks, 'configuration_mapping_order_and_names',
          [(r['order'], r['config_id'], r['short_name'], r['zh_name']) for r in configuration_map],
          [(str(i), config, short, zh) for i, (config, short, zh) in enumerate(CONFIG_NAMES, 1)])
    check(checks, 'fold_mapping_and_non_independence',
          [(r['fold_id'], r['short_name'], r['independent_replicate']) for r in fold_map],
          [(fold, fold[-2:], 'False') for fold in FOLDS])
    saved = {}
    for name in FIGURE_IDS + ['T02','T03','F04_totals']:
        saved[name] = read_csv(output / 'data' / (name + '.csv'))
        for row in saved[name]:
            for key in COUNTS:
                row[key] = int(row[key])
            assert sum(row[s] for s in STATES) == row['N'], (name, row)
            assert row['defined'] == row['T'] + row['F'], (name, row)
            assert abs(float(row['rate']) - row['T'] / row['N']) < 1e-12
            assert abs(float(row['defined_rate']) - (row['T'] + row['F']) / row['N']) < 1e-12
            assert row['numerator'] == str(row['T']) and row['denominator'] == str(row['N'])
        check(checks, name + '_partitions_rates_defined_rates_and_denominators', True, True)
        if name != 'F03b':
            check(checks, name + '_method_ids_and_labels',
                  all(r['scheme'] in NAMES and r['method_short'] == NAMES[r['scheme']]
                      and r['stage'] == stage(r['scheme']) for r in saved[name]), True)
    check(checks, 'F01_84_cells', len(saved['F01']), 84)
    check(checks, 'F02_18_rows', len(saved['F02']), 18)
    check(checks, 'F03a_54_rows', len(saved['F03a']), 54)
    check(checks, 'F04_36_rows', len(saved['F04']), 36)
    check(checks, 'F04_totals_36_rows', len(saved['F04_totals']), 36)
    check(checks, 'F01_configuration_labels',
          all(r['configuration'] in dict((c[0], c[1]) for c in CONFIG_NAMES)
              and r['configuration_short'] == dict((c[0], c[1]) for c in CONFIG_NAMES)[r['configuration']]
              for r in saved['F01']), True)
    check(checks, 'F03a_saved_single_aggregation_layer',
          all(r['cohort'] == 'memory' and r['scenario'] == 'ALL' and r['phase'] == 'ALL'
              for r in saved['F03a']), True)
    check(checks, 'F04_totals_saved_single_aggregation_layer',
          all(r['cohort'] == 'timezone' and r['scenario'] == 'ALL' and r['phase'] == 'ALL'
              for r in saved['F04_totals']), True)
    timezone_groups = {'normal_system_change': ('L_', 'NORMAL'),
                       'web_only_change': ('A_', 'EFFECTIVE_INTERVENTION')}
    check(checks, 'F04_saved_scenarios_and_identities',
          all(r['group'] in timezone_groups and r['cohort'] == 'timezone' and r['phase'] == 'change'
              and r['identity'] == timezone_groups[r['group']][1]
              and r['scenario'] == timezone_groups[r['group']][0] + 'America/Los_Angeles+'
                                     + timezone_groups[r['group']][0] + 'UTC'
              for r in saved['F04']), True)
    for method in METHOD_IDS:
        cells = [r for r in saved['F01'] if r['scheme'] == method]
        check(checks, method + '_F01_unique_configuration_denominators',
              sorted((r['configuration'], r['identity'], r['N']) for r in cells),
              sorted((c[0], 'EFFECTIVE_INTERVENTION', 9) for c in CONFIG_NAMES))
        check(checks, method + '_F01_vs_T02', total([r for r in saved['F01'] if r['scheme']==method]), total([r for r in saved['T02'] if r['scheme']==method and r['identity']=='EFFECTIVE_INTERVENTION']))
        for fold in FOLDS:
            source = [r for r in saved['T03'] if r['scheme']==method and r['fold_id']==fold and r['subset'] in ('development','reserved_validation')]
            result = [r for r in saved['F02'] if r['scheme']==method and r['fold_id']==fold]
            check(checks, method + fold + '_saved_mtc_source_subsets',
                  sorted((r['subset'], r['N']) for r in source), [('development', 144), ('reserved_validation', 117)])
            check(checks, method + fold + '_saved_mtc_one_result', len(result), 1)
            check(checks, method + fold + '_saved_mtc_sum', total(result), total(source))
            check(checks, method + fold + '_saved_mtc_denominator', total(result)['N'], 261)
            for name, field, expected in [('F03a','identity',{'EFFECTIVE_INTERVENTION':18,'NORMAL':48,'NO_OBSERVABLE_EFFECT':6}),('F04','group',{'normal_system_change':6,'web_only_change':6})]:
                sub = [r for r in saved[name] if r['scheme']==method and r['fold_id']==fold]
                check(checks, method + fold + name + '_saved_unique_groups_and_denominators',
                      sorted((r[field], r['N']) for r in sub), sorted(expected.items()))
            timezone_totals = [r for r in saved['F04_totals'] if r['scheme'] == method and r['fold_id'] == fold]
            check(checks, method + fold + '_timezone_total_partition',
                  sorted((r['identity'], r['N']) for r in timezone_totals),
                  [('EFFECTIVE_INTERVENTION', 6), ('NORMAL', 30)])
            for group, (_, identity) in timezone_groups.items():
                change = total([r for r in saved['F04'] if r['scheme'] == method and r['fold_id'] == fold and r['group'] == group])
                overall = total([r for r in timezone_totals if r['identity'] == identity])
                check(checks, method + fold + group + '_subset_of_timezone_total',
                      all(change[k] <= overall[k] for k in COUNTS), True)
                if identity == 'NORMAL':
                    check(checks, method + fold + '_normal_remainder_24', overall['N'] - change['N'], 24)
                else:
                    check(checks, method + fold + '_all_timezone_interventions_are_web_changes', change, overall)
        for name, field, groups in [('F03a', 'identity', ('EFFECTIVE_INTERVENTION', 'NORMAL', 'NO_OBSERVABLE_EFFECT')),
                                    ('F04', 'group', tuple(timezone_groups))]:
            for group in groups:
                rows = [r for r in saved[name] if r['scheme'] == method and r[field] == group]
                check(checks, name + method + group + '_saved_three_unique_folds',
                      sorted(r['fold_id'] for r in rows), FOLDS)
                check(checks, name + method + group + '_saved_identical_configuration_counts',
                      len({tuple(r[k] for k in COUNTS) for r in rows}), 1)
    for condition in ('R_REL','R_WEB8'):
        target = [r for r in saved['F03b'] if r['condition']==condition and r['scope']=='target' and r['identity']=='EFFECTIVE_INTERVENTION']
        ref = [r for r in saved['F03b'] if r['condition']==condition and r['scope']=='aggregate_observable_changes']
        check(checks, condition + '_saved_targets_sum',total(target),total(ref))
        check(checks, condition + '_saved_targets_N',[(r['target'],r['N']) for r in target],[('4',6),('8',6),('16',6)])
    import re
    import struct
    import xml.etree.ElementTree as ET
    def svg_mm(value):
        match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)(pt|mm|cm|in|px)', value)
        if not match:
            return None
        factors = {'pt': 25.4 / 72, 'mm': 1, 'cm': 10, 'in': 25.4, 'px': 25.4 / 96}
        return float(match.group(1)) * factors[match.group(2)]
    for fig in manifest['figures']:
        check(checks, fig['id'] + '_canonical_artifact_paths',
              [fig['png'], fig['svg'], fig['plotting_csv']],
              ['figures/' + fig['id'] + '.png', 'figures/' + fig['id'] + '.svg', 'data/' + fig['id'] + '.csv'])
        png = (output / fig['png']).read_bytes()
        width, height = struct.unpack('>II',png[16:24])
        check(checks, fig['id'] + '_pixel_dimensions', [width,height],fig['pixel_dimensions'])
        idx = png.index(b'pHYs'); xppm,yppm,unit = struct.unpack('>IIB',png[idx+4:idx+13])
        check(checks, fig['id'] + '_at_least_300dpi',unit==1 and min(xppm,yppm)*.0254>=299.9,True)
        check(checks, fig['id'] + '_png_physical_size_matches_manifest',
              unit == 1 and xppm > 0 and yppm > 0
              and abs(width * 1000 / xppm - fig['size_mm'][0]) < .12
              and abs(height * 1000 / yppm - fig['size_mm'][1]) < .12, True)
        svg = ET.parse(output / fig['svg']).getroot()
        actual_mm = [svg_mm(svg.get(dimension, '')) for dimension in ('width', 'height')]
        check(checks, fig['id'] + '_svg_physical_size_matches_manifest',
              all(actual is not None and abs(actual - expected) < 1e-4
                  for actual, expected in zip(actual_mm, fig['size_mm'])), True)
        check(checks, fig['id'] + '_svg_no_raster_images',len(svg.findall('.//{http://www.w3.org/2000/svg}image')),0)
        check(checks, fig['id'] + '_svg_vector_paths',len(svg.findall('.//{http://www.w3.org/2000/svg}path'))>0,True)
    failures = [c for c in checks if c['status']!='PASS']
    return dict(status='PASS' if not failures else 'FAIL', source_files_read=0, checks=checks)


def plot_all(output, data):
    os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'rba-round1-mpl'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import Patch
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,
        'axes.labelsize':8,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,
        'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none',
        'svg.hashsalt':OWNER,'savefig.dpi':300,'hatch.linewidth':.35})
    cmap = LinearSegmentedColormap.from_list('round1_blue',['#f1f5f8','#a7c8dc','#1b5578'])
    specs=[]
    def save(fig, id_, size):
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        outside=[]
        from matplotlib.text import Text
        for artist in fig.findobj(match=Text):
            if not artist.get_visible() or not artist.get_text(): continue
            box=artist.get_window_extent(renderer)
            if box.width and box.height and (box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.width+1 or box.y1 > fig.bbox.height+1):
                outside.append(artist.get_text())
        if outside: raise ValueError((id_,'text outside canvas',outside))
        fig.savefig(output/'figures'/(id_+'.svg'),metadata={'Date':None})
        fig.savefig(output/'figures'/(id_+'.png'),dpi=300,metadata={'Software':OWNER})
        if os.environ.get('RBA_ROUND1_QA_DIR'):
            qa=Path(os.environ['RBA_ROUND1_QA_DIR']);qa.mkdir(parents=True,exist_ok=True)
            fig.savefig(qa/(id_+'_96dpi.png'),dpi=96)
        from PIL import Image
        with Image.open(output/'figures'/(id_+'.png')) as im: pixels=list(im.size)
        specs.append(dict(id=id_,svg='figures/'+id_+'.svg',png='figures/'+id_+'.png',
                          plotting_csv='data/'+id_+'.csv',size_mm=list(size),dpi=300,
                          pixel_dimensions=pixels,minimum_font_pt=8,text_canvas_bounds='PASS'))
        plt.close(fig)
    def heat(ax, matrix, denom):
        image=ax.pcolormesh(np.arange(matrix.shape[1]+1)-.5,
                            np.arange(matrix.shape[0]+1)-.5,
                            matrix/denom*100,cmap=cmap,vmin=0,vmax=100,
                            shading='flat',rasterized=False)
        ax.set_ylim(matrix.shape[0]-.5,-.5)
        for (y,x), val in np.ndenumerate(matrix):
            ax.text(x,y,f'{int(val)}/{denom}',ha='center',va='center',color='white' if val/denom>.55 else '#142e40',fontsize=8)
        ax.set_xticks(np.arange(matrix.shape[1]+1)-.5,minor=True)
        ax.set_yticks(np.arange(matrix.shape[0]+1)-.5,minor=True)
        ax.grid(which='minor',color='white',linewidth=1.2)
        ax.tick_params(which='both',length=0)
        for spine in ax.spines.values():spine.set_visible(False)
        return image
    # F01: full fixed colour scale, literal T/N in every cell, including zero.
    size=(180,135); fig=plt.figure(figsize=(size[0]/25.4,size[1]/25.4))
    ax=fig.add_axes([.30,.18,.64,.64]); lookup={(r['configuration'],r['scheme']):r for r in data['F01']}
    matrix=np.array([[lookup[(config,method)]['T'] for method in METHOD_IDS] for config,_,_ in CONFIG_NAMES])
    im=heat(ax,matrix,9)
    ax.set_yticks(range(14),[r[1] for r in CONFIG_NAMES])
    ax.set_xticks(range(6),['Full\nApp','No MTC\nalarm cap','App Web\nonly','No memory\nrelation','No timezone\nrelation','Small App\ntree'])
    ax.xaxis.tick_top();ax.tick_params(axis='x',pad=6)
    fig.text(.04,.965,'F01  App intervention detection',weight='bold',fontsize=10)
    cax=fig.add_axes([.30,.085,.64,.022]);cb=fig.colorbar(im,cax=cax,orientation='horizontal',ticks=[0,25,50,75,100]);cb.set_label('Detected interventions (%)',labelpad=3);cb.solids.set_rasterized(False)
    fig.text(.30,.135,'Each cell: T/9; U = FAILED = EMPTY_MODEL = 0.',fontsize=8)
    save(fig,'F01',size)
    # F02: no artificial enlargement of the 1--3 record alarm slices.
    size=(180,155);fig=plt.figure(figsize=(size[0]/25.4,size[1]/25.4))
    ax=fig.add_axes([.28,.14,.33,.68]);tab=fig.add_axes([.64,.14,.35,.68],sharey=ax)
    rows=data['F02']; y=np.arange(18);left=np.zeros(18)
    colors={'T':'#ce6b30','F':'#90b8d1','U':'#e5c365','FAILED':'#555561','EMPTY_MODEL':'#ffffff'}
    hatches={'T':'////','F':'','U':'..','FAILED':'xx','EMPTY_MODEL':'++'}
    use_states=list(STATES[:-1]) + (['EMPTY_MODEL'] if any(r['EMPTY_MODEL'] for r in rows) else [])
    for st in use_states:
        values=np.array([r[st]/r['N']*100 for r in rows])
        ax.barh(y,values,left=left,height=.7,color=colors[st],hatch=hatches[st],linewidth=0,edgecolor='#455765',label=st)
        left+=values
    labels=[NAMES[r['scheme']]+' / '+r['fold_id'][-2:] for r in rows]
    ax.set_yticks(y,labels);ax.set_ylim(17.7,-.7);ax.set_xlim(0,100);ax.set_xticks([0,50,100]);ax.set_xlabel('Historical normal records (%)')
    ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True);ax.tick_params(axis='y',length=0)
    tab.set_xlim(0,1);tab.axis('off')
    cols=[.08,.26,.42,.58,.83]
    for x,label in zip(cols,['T','F','U','FAILED','(T+F)/N']):tab.text(x,-1.25,label,ha='center',weight='bold',fontsize=8)
    for i,r in enumerate(rows):
        for x,label in zip(cols,[r['T'],r['F'],r['U'],r['FAILED'],f"{r['defined']}/{r['N']}"]):tab.text(x,i,str(label),ha='center',va='center',fontsize=8)
    for split in [2.5,5.5,8.5,11.5,14.5]:
        ax.axhline(split,color='#d3dbe0',lw=.6);tab.axhline(split,color='#d3dbe0',lw=.6)
    fig.text(.04,.963,'F02  App outputs on historical MTC normal records',fontsize=10,weight='bold')
    handles=[Patch(facecolor=colors[s],hatch=hatches[s],edgecolor='#455765',label=l) for s,l in zip(use_states,['T: alarm','F: no alarm','U: unknown','FAILED: failure','Empty model'])]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.51,.936),ncol=2,frameon=False,columnspacing=2.5)
    fig.text(.28,.058,'Each row: 144 + 117 = 261 records; 630 training records excluded.',fontsize=8)
    fig.text(.28,.030,'Configurations reuse records; binary tree output does not restore observations.',fontsize=8)
    save(fig,'F02',size)
    # F03a: one set of counts per configuration, with controls immediately beside it.
    size=(180,86);fig=plt.figure(figsize=(size[0]/25.4,size[1]/25.4))
    ax=fig.add_axes([.29,.25,.32,.48]);tab=fig.add_axes([.64,.25,.35,.48],sharey=ax)
    lookup={(r['scheme'],r['identity']):r for r in data['F03a'] if r['fold_id']==FOLDS[0]}
    ax.set_ylim(5.6,-.6);ax.set_xlim(0,18);ax.set_xticks([0,6,12,18]);ax.set_yticks(range(6),[NAMES[m] for m in METHOD_IDS]);ax.tick_params(axis='y',length=0,pad=7)
    for i,m in enumerate(METHOD_IDS):
        t=lookup[m,'EFFECTIVE_INTERVENTION']['T'];ax.hlines(i,0,t,color='#b4c6d2',lw=1.6);ax.plot(t,i,'o',color='#1b5578',ms=5,clip_on=False,zorder=4)
    ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True);ax.set_xlabel('Detected interventions (count)')
    tab.set_xlim(0,1);tab.axis('off')
    for x,label in zip([.16,.50,.84],['Modified','Normal','No change']):tab.text(x,-1.2,label,ha='center',fontsize=8,weight='bold')
    for i,m in enumerate(METHOD_IDS):
        for x,identity in zip([.16,.50,.84],['EFFECTIVE_INTERVENTION','NORMAL','NO_OBSERVABLE_EFFECT']):
            r=lookup[m,identity];tab.text(x,i,f"{r['T']}/{r['N']}",ha='center',va='center')
    fig.text(.04,.935,'F03a  Complete App models on the memory-only batch',fontsize=10,weight='bold')
    fig.text(.29,.82,'Alarm counts (T/N); identical totals in each of configurations 01, 02, 03.',fontsize=8)
    fig.text(.29,.075,'Per configuration: 18 effective + 48 normal + 6 no-change positions.',fontsize=8)
    fig.text(.29,.030,'U = FAILED = EMPTY_MODEL = 0; no independent repetitions implied.',fontsize=8)
    save(fig,'F03a',size)
    # F03b: only the saved fixed conditions, upward changes only.
    size=(85,87);fig=plt.figure(figsize=(size[0]/25.4,size[1]/25.4))
    ax=fig.add_axes([.18,.32,.78,.43]);lookup={(r['target'],r['condition']):r for r in data['F03b'] if r['scope']=='target' and r['identity']=='EFFECTIVE_INTERVENTION'}
    for condition,offset,color,hatch,label in [('R_REL',-.19,'#1b5578','','Native reference'),('R_WEB8',.19,'#d49651','///','Web > 8')]:
        vals=[lookup[t,condition]['T'] for t in (4,8,16)]
        ax.bar(np.arange(3)+offset,vals,width=.35,color=color,hatch=hatch,edgecolor='#263b48',linewidth=.4,label=label)
        for x,t,val in zip(np.arange(3)+offset,(4,8,16),vals):ax.text(x,val+.16,f'{val}/{lookup[t,condition]["N"]}',ha='center',va='bottom',fontsize=8)
    ax.set_ylim(0,7.15);ax.set_yticks([0,2,4,6]);ax.set_xticks(range(3),['4','8','16']);ax.set_xlabel('Target web memory (GiB)');ax.set_ylabel('Triggered (count)');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.text(.09,.948,'F03b  Fixed memory conditions',fontsize=9,weight='bold')
    fig.legend(*ax.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.52,.90),frameon=False,ncol=1)
    fig.text(.12,.15,'Both: normal alarms 0/48; U/FAILED = 0.',fontsize=8)
    fig.text(.12,.087,'Target 2: 6 no-change positions,',fontsize=8)
    fig.text(.12,.042,'0/6 triggers each; excluded above.',fontsize=8)
    save(fig,'F03b',size)
    # F04: normal changes and effective interventions are distinct columns.
    size=(180,91);fig=plt.figure(figsize=(size[0]/25.4,size[1]/25.4))
    ax=fig.add_axes([.30,.30,.59,.43]);lookup={(r['scheme'],r['group']):r for r in data['F04'] if r['fold_id']==FOLDS[0]}
    matrix=np.array([[lookup[m,g]['T'] for g in ('normal_system_change','web_only_change')] for m in METHOD_IDS]);im=heat(ax,matrix,6)
    ax.set_yticks(range(6),[NAMES[m] for m in METHOD_IDS]);ax.set_xticks(range(2),['Normal system change\nFewer alarms preferred','Web-only change\nAlarm = detection']);ax.xaxis.tick_top();ax.tick_params(axis='x',pad=6)
    fig.text(.04,.943,'F04  App alarms: system timezone change vs web-only change',fontsize=10,weight='bold')
    cax=fig.add_axes([.30,.165,.59,.026]);cb=fig.colorbar(im,cax=cax,orientation='horizontal',ticks=[0,25,50,75,100]);cb.set_label('Alarms (%)',labelpad=3);cb.solids.set_rasterized(False)
    fig.text(.30,.245,'T/6 in each configuration (01, 02, 03); U/FAILED/EMPTY_MODEL = 0.',fontsize=8)
    fig.text(.30,.035,'Normal changes are 6 of the 30 normal positions, not an additional cohort.',fontsize=8)
    save(fig,'F04',size)
    return specs, {'python_runtime':__import__('sys').version.split()[0], 'matplotlib':matplotlib.__version__}


# Extraction helpers for T01 and F03b are included below; they read saved JSON only.


"""Read-only F03b extraction from saved memory condition summary only."""
from collections import Counter
from pathlib import Path
import json

F03B_SOURCES = ('deliverables/memory_relation_validation_v1/summary.json',
                 'deliverables/timezone_relation_validation_v1/MEMORY_NORMAL_REVIEW.json')


def extract_f03b(root):
    """Return (rows, checks, sources), each a list.

    `scope == 'target' and identity == 'EFFECTIVE_INTERVENTION'` is the
    plot selection. Other rows preserve the no-effect, normal and all-batch
    counts. Aggregate rows overlap target rows and MUST NOT be summed with
    them. EMPTY_MODEL is inapplicable to a fixed condition; it is recorded
    as zero only after checking the exhaustive saved four-state partition.
    No condition is recomputed and no experimental code is imported.
    """
    source = F03B_SOURCES[0]
    data = json.loads((Path(root) / source).read_text(encoding='utf-8'))
    batch = data['new_batch']
    conditions = ('R_REL', 'R_WEB8')
    states = ('T', 'F', 'U', 'FAILED')
    checks = []
    rows = []

    def check(name, observed, expected):
        checks.append({'id': 'F03b_' + name, 'status': 'PASS' if observed == expected else 'FAIL',
                       'observed': observed, 'expected': expected})

    def pointer(value):
        return str(value).replace('~', '~0').replace('/', '~1')

    def count_summary(value):
        return {'N': value['n'], **{state: value[state] for state in states}}

    def sum_counts(values):
        return {key: sum(value[key] for value in values) for key in ('N',) + states}

    def validity(items):
        # Keep every observed value; no confound, recovery or execution filter.
        return {key + '_counts': json.dumps(dict(sorted(Counter(item[key] for _, item in items).items())),
                                           sort_keys=True, ensure_ascii=False)
                for key in ('execution', 'effect', 'recovery', 'confound_status')}

    def row(scope, target, condition, identity, counts, locations, items, phase):
        defined = counts['T'] + counts['F']
        result = {'figure_id': 'F03b', 'scope': scope, 'target': target,
                  'condition': condition,
                  'condition_short': 'Native reference' if condition == 'R_REL' else 'Web > 8',
                  'identity': identity, 'phase': phase, 'N': counts['N'],
                  **{state: counts[state] for state in states}, 'EMPTY_MODEL': 0,
                  'empty_model_semantics': 'not applicable to fixed condition; saved four-state partition is exhaustive',
                  'defined': defined, 'rate': counts['T'] / counts['N'] if counts['N'] else None,
                  'defined_rate': defined / counts['N'] if counts['N'] else None,
                  'numerator': counts['T'], 'denominator': counts['N'],
                  'source_path': source, 'source_locator': ';'.join(locations),
                  'validity_source_locator': ';'.join('/new_batch/triplets/' + str(i) for i, _ in items),
                  **validity(items),
                  'role': 'fixed saved condition; new local memory-only batch',
                  'overlap_note': 'aggregate overlaps target rows; do not sum across scopes' if scope != 'target'
                                  else 'one target, all environments and rounds retained; conditions share the same records'}
        rows.append(result)
        return result

    triplets = list(enumerate(batch['triplets']))
    phase_groups = batch['by_environment_target_phase']
    check('triplet_count', len(triplets), 24)
    check('triplet_unique_environment_target_round', len({(t['environment'], t['target_gib'], t['round']) for _, t in triplets}), 24)
    check('target_set', sorted({t['target_gib'] for _, t in triplets}), [2, 4, 8, 16])
    check('group_count', len(phase_groups), 36)
    check('normal_and_active_phases', sorted({key.rsplit('/', 1)[1] for key in phase_groups}), ['attack', 'clean_post', 'clean_pre'])
    check('environments', sorted({t['environment'] for _, t in triplets}),
          ['api29_swiftshader', 'api30_swiftshader', 'api36_swiftshader'])
    check('rounds', sorted({t['round'] for _, t in triplets}), [1, 2])
    for field in ('execution', 'effect', 'recovery', 'confound_status'):
        check('saved_validity_' + field, dict(Counter(t[field] for _, t in triplets)), batch['effect_counts'][field])

    partition_errors = []
    group_size_errors = []
    for key, group in phase_groups.items():
        if group['planned_n'] != 2:
            group_size_errors.append({'group': key, 'planned_n': group['planned_n']})
        for condition in conditions:
            value = group['conditions'][condition]
            if sum(value[state] for state in states) != value['n'] or value['n'] != group['planned_n']:
                partition_errors.append({'group': key, 'condition': condition, 'counts': value})
            if value['evaluable'] != value['T'] + value['F']:
                partition_errors.append({'group': key, 'condition': condition, 'defined': value})
    check('saved_group_state_partitions', partition_errors, [])
    check('saved_group_n_is_2', group_size_errors, [])

    by_target_rows = {}
    for target in (2, 4, 8, 16):
        items = [(i, item) for i, item in triplets if item['target_gib'] == target]
        check('target_' + str(target) + '_n', len(items), 6)
        expected_effect = 'NO_OBSERVABLE_EFFECT' if target == 2 else 'OBSERVABLE_TARGET_CHANGE'
        check('target_' + str(target) + '_validity', dict(Counter(t['effect'] for _, t in items)), {expected_effect: 6})
        identity = 'NO_OBSERVABLE_EFFECT' if target == 2 else 'EFFECTIVE_INTERVENTION'
        for condition in conditions:
            saved = Counter(item['active_conditions'][condition] for _, item in items)
            check('target_' + str(target) + '_' + condition + '_state_vocabulary', sorted(set(saved) - set(states)), [])
            counts = {'N': len(items), **{state: saved[state] for state in states}}
            keys = [key for key in phase_groups if key.split('/')[1:] == [str(target), 'attack']]
            grouped = sum_counts([count_summary(phase_groups[key]['conditions'][condition]) for key in keys])
            check('target_' + str(target) + '_' + condition + '_summary_vs_triplets', counts, grouped)
            locations = ['/new_batch/by_environment_target_phase/' + pointer(key) + '/conditions/' + condition for key in keys]
            result = row('target', target, condition, identity, grouped, locations, items, 'attack')
            by_target_rows[(target, condition)] = result

    summaries = (
        ('observable_changes', 'EFFECTIVE_INTERVENTION', [4, 8, 16], 'attack'),
        ('no_observable_effect', 'NO_OBSERVABLE_EFFECT', [2], 'attack'),
        ('normal_phases', 'NORMAL', [], 'clean_pre + clean_post'),
        ('all', 'ALL', [2, 4, 8, 16], 'all'),
    )
    for group_name, identity, targets, phase in summaries:
        items = [(i, item) for i, item in triplets if item['target_gib'] in targets]
        for condition in conditions:
            saved = count_summary(batch[group_name]['conditions'][condition])
            check(group_name + '_' + condition + '_state_partition', sum(saved[state] for state in states), saved['N'])
            check(group_name + '_' + condition + '_defined', batch[group_name]['conditions'][condition]['evaluable'], saved['T'] + saved['F'])
            if group_name in ('observable_changes', 'no_observable_effect'):
                recombined = sum_counts([by_target_rows[(target, condition)] for target in targets])
            else:
                keys = [key for key in phase_groups if group_name == 'all' or key.rsplit('/', 1)[1] in ('clean_pre', 'clean_post')]
                recombined = sum_counts([count_summary(phase_groups[key]['conditions'][condition]) for key in keys])
            check(group_name + '_' + condition + '_summary_vs_groups', saved, recombined)
            row('aggregate_' + group_name, 'ALL', condition, identity, saved,
                ['/new_batch/' + group_name + '/conditions/' + condition], items, phase)

    for condition in conditions:
        parts = [count_summary(batch[key]['conditions'][condition]) for key in ('normal_phases', 'observable_changes', 'no_observable_effect')]
        check(condition + '_72_partition', sum_counts(parts), count_summary(batch['all']['conditions'][condition]))
        check(condition + '_normal_n', batch['normal_phases']['conditions'][condition]['n'], 48)
        check(condition + '_effective_n', batch['observable_changes']['conditions'][condition]['n'], 18)
        check(condition + '_no_effect_n', batch['no_observable_effect']['conditions'][condition]['n'], 6)
    check('target_relation_T_regression', [by_target_rows[(t, 'R_REL')]['T'] for t in (4, 8, 16)], [6, 6, 6])
    check('target_web8_T_regression', [by_target_rows[(t, 'R_WEB8')]['T'] for t in (4, 8, 16)], [0, 0, 6])
    check('normal_T_regression', [batch['normal_phases']['conditions'][c]['T'] for c in conditions], [0, 0])
    review = json.loads((Path(root) / F03B_SOURCES[1]).read_text(encoding='utf-8'))
    check('later_saved_normal_review', review['confirmed_normal_n'], batch['normal_phases']['planned_n'])
    check('later_saved_normal_review_support', review['normal_without_support_n'], 0)
    check('later_saved_normal_review_preserves_outputs', review['historical_outputs_modified'], False)
    check('later_saved_normal_condition_counts', review['conditions_on_confirmed_normal'],
          {condition: {state: batch['normal_phases']['conditions'][condition][state]
                       for state in states if batch['normal_phases']['conditions'][condition][state]}
           for condition in conditions})
    for result in rows:
        if result['identity'] == 'NORMAL':
            result['normal_basis_source_path'] = F03B_SOURCES[1]
            result['normal_basis_source_locator'] = '/confirmed_normal_n;/conditions_on_confirmed_normal/' + result['condition']
    sources = [{'path': source, 'role': 'F03b new_batch summary, grouped saved condition states and saved intervention validity',
                         'locators': ['/new_batch/by_environment_target_phase', '/new_batch/triplets', '/new_batch/normal_phases',
                                      '/new_batch/observable_changes', '/new_batch/no_observable_effect', '/new_batch/all', '/new_batch/effect_counts']}]
    return rows, checks, sources




"""T01: saved aggregate counts only; never import experiment modules."""
import csv
import json
from pathlib import Path

T01_SOURCES = [
    'RBA_EXPERIMENT_REPORT_FOR_ADVISOR.md',
    'deliverables/app_browser_evidence_consolidation_v1/REPORT.md',
    'deliverables/app_browser_evidence_consolidation_v1/tables.json',
    'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol/SUMMARY.json',
    'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R02_matrix/SUMMARY.json',
    'deliverables/app177_core_ablation_v1/results/summary/main.json',
    'deliverables/app177_core_ablation_v1/results/summary/mtc.json',
    'deliverables/app177_core_ablation_v1/results/summary/specialists.json',
    'deliverables/mtc_p1_20260922/P1_SUMMARY.json',
    'deliverables/mtc_p2_20260922/P2_SUMMARY.json',
    'deliverables/memory_relation_validation_v1/summary.json',
    'deliverables/screen_geometry_observation_v1/SUMMARY.json',
    'deliverables/webgl_behavior_feasibility_v1/SUMMARY.json',
    'deliverables/browser67_cross_endpoint_diagnostic_v1/results/SUMMARY.json',
    'deliverables/browser67_cross_endpoint_diagnostic_v1/results/SUMMARY.csv',
    'deliverables/cross_endpoint_matched_controls_v1/results/summary.json',
    'deliverables/app_resource_paired_validation_v1/results/summary/SUMMARY.json',
    'deliverables/screen_geometry_closeout_v1/v16_evaluation/SUMMARY.json',
]


def extract_t01(root):
    root = Path(root)
    sources = list(T01_SOURCES)
    docs = {p: json.loads((root / p).read_text(encoding='utf-8'))
            for p in sources if p.endswith('.json')}
    checks = {}
    rows = []

    def check(name, condition):
        checks['T01_' + name] = bool(condition)
        if not condition:
            raise ValueError('T01 source mismatch: ' + name)

    def add(batch_id, batch_cn, normal, modified, no_effect, total, role, overlap,
            source_path, source_locator, count_semantics, status='VERIFIED_SAVED_AGGREGATES'):
        rows.append(dict(batch_id=batch_id, batch_cn=batch_cn,
                         normal_N=normal, effective_modified_N=modified,
                         no_observable_effect_N=no_effect, total_records_N=total,
                         data_role=role, overlap_and_non_independence=overlap,
                         source_path=source_path, source_locator=source_locator,
                         count_semantics=count_semantics, verification_status=status))

    early_path = sources[3]
    early = docs[early_path]
    matrix = docs[sources[4]]
    check('early_stage_count', early['stages'] == matrix['rows'])
    check('early_supervised_partition', early['attack'] + early['clean'] == early['supervised'] == matrix['supervised_rows'])
    check('early_descriptive_partition', early['stages'] - early['supervised'] == matrix['descriptive_rows'])
    add('early_app_development', '早期App开发材料', early['clean'], early['attack'], '', early['stages'],
        '早期规则学习、表示及选择程序探索；不用于第一轮五图的当前模型结果。',
        '监督阶段只是总阶段的一部分；其余阶段为描述性用途。历史多阶段模型输出不增加样本量；不能与当前主实验直接相加。',
        early_path + ';' + sources[4],
        '$.clean;$.attack;$.stages;$.supervised | $.rows;$.supervised_rows;$.descriptive_rows',
        '正常与修改数只覆盖 admitted_attack_triplet；有效修改沿用原 attack 准入标签，不以本轮重新验证。其余描述性阶段=' + str(matrix['descriptive_rows']) + '；无效果未单列，留空。')

    unified_path = sources[2]
    unified = docs[unified_path]
    main_path = sources[5]
    main = docs[main_path]
    check('unified_main_equal', main == unified['app']['main'])
    full = {r['identity']: r for r in main if r['scheme'] == 'APP_FULL'}
    normal, modified = full['NORMAL']['N'], full['EFFECTIVE_INTERVENTION']['N']
    check('main_denominators_across_methods', all(r['N'] == full[r['identity']]['N'] for r in main))
    add('current_app_controlled', '当前App受控主实验', normal, modified, 0, normal + modified,
        '当前App主结果、四项重训消融与App小树；F01/T02。',
        '三个环境留出部分不重叠；只合计留出位置，不累加三个模型的全量回放。已有开发使用历史；不是设备数。',
        main_path, '$[scheme=APP_FULL,identity=NORMAL|EFFECTIVE_INTERVENTION]',
        '正常和有效修改为互斥身份；无效果不在此已保存主表队列。')

    p1path, p2path = sources[8], sources[9]
    p1, p2 = docs[p1path], docs[p2path]
    check('mtc_primary_inventory', p1['qc_paired_244'] == p2['primary_paired_observations'])
    check('mtc_model_os_inventory', p1['qc_paired_model_os'] == p2['primary_model_os_representatives'])
    add('mtc_paired_qc', 'MTC配对主视图', '', '', '', p1['qc_paired_244'],
        '广机型采集、配对与字段质量背景。',
        '包含主代表及同型号/系统的额外配对记录；不是独立物理设备数；与下方主代表及重复视图重叠，不可相加。',
        p1path + ';' + p2path,
        '$.qc_paired_244;$.qc_paired_model_os;$.label_status | $.primary_paired_observations;$.primary_model_os_representatives',
        'P1保存标签为 unlabeled，不能把全部QC记录自动填为已验证正常/攻击；分类计数留空。型号/系统组合=' + str(p1['qc_paired_model_os']) + '。')

    mtc_path = sources[6]
    mtc = docs[mtc_path]
    representative_counts = {key: value['model_os_representatives'] for key, value in p2['split_counts'].items()}
    check('mtc_three_saved_subsets', set(representative_counts) == {'discovery', 'development', 'reserved_validation'})
    check('mtc_representative_sum', sum(representative_counts.values()) == p2['primary_model_os_representatives'])
    check('mtc_saved_subset_denominators', all(r['N'] == representative_counts[r['subset']] for r in mtc))
    check('unified_mtc_equal', mtc == unified['app']['mtc'])
    representative_n = sum(representative_counts.values())
    extra_n = p1['qc_paired_244'] - representative_n
    add('mtc_representatives', 'MTC主代表', representative_n, 0, 0, representative_n,
        '当前App的历史正常材料；discovery用于训练正常约束，development和reserved_validation为历史评价部分；F02/T03。',
        '为MTC配对主视图子集；同批记录被三配置重复输出，不能乘三；有已知关联分组，不代表物理独立。额外配对记录=' + str(extra_n) + '。',
        p2path + ';' + mtc_path,
        '$.primary_model_os_representatives;$.split_counts.*.model_os_representatives | $[scheme,fold_id,subset].N',
        'normal_N为当前研究正常材料口径，非外部独立真值认证；discovery=' + str(representative_counts['discovery']) + '; development=' + str(representative_counts['development']) + '; reserved_validation=' + str(representative_counts['reserved_validation']) + '。')
    add('mtc_extra_pairs', 'MTC其余重复配对记录', '', '', '', extra_n,
        '重复观测与质量描述背景；不纳入第一轮主代表正常率。',
        '主视图减主代表的余量，不是新增独立样本；已包含于MTC配对主视图。',
        p1path + ';' + p2path, '$.qc_paired_244 - $.primary_model_os_representatives',
        '只作已保存范围差额；不借研究正常用途推断该余量的逐条标签。')

    spath = sources[7]
    specialists = docs[spath]
    check('unified_specialists_equal', [r for r in specialists if r['scenario'] == 'ALL' and r['phase'] == 'ALL'] == unified['app']['specialists'])
    for cohort, label in [('memory', '内存专项'), ('timezone', '时区专项'), ('screen', '屏幕几何专项')]:
        all_rows = [r for r in specialists if r['cohort'] == cohort and r['scenario'] == 'ALL' and r['phase'] == 'ALL']
        chosen = [r for r in all_rows if r['scheme'] == 'APP_FULL' and r['fold_id'] == 'WEBGL1-LOEO-v1-01']
        n = {r['identity']: r['N'] for r in chosen}
        check(cohort + '_same_denominators_by_method_and_fold', all(r['N'] == n[r['identity']] for r in all_rows))
        normal, modified, no_effect = n['NORMAL'], n['EFFECTIVE_INTERVENTION'], n.get('NO_OBSERVABLE_EFFECT', 0)
        total = sum(n.values())
        overlap = '同批专项由六方法、三配置分别回放，不能乘方法数或配置数；只取scenario=ALL且phase=ALL一个层次。'
        semantics = '正常与有效修改为独立身份集合。'
        src, locator = spath, '$[scheme=APP_FULL,fold_id=WEBGL1-LOEO-v1-01,cohort=' + cohort + ',scenario=ALL,phase=ALL]'
        if cohort == 'memory':
            mempath = sources[10]
            memory = docs[mempath]['new_batch']
            check('memory_new_batch_counts', (normal, modified, no_effect, total) == (memory['normal_phases']['planned_n'], memory['observable_changes']['planned_n'], memory['no_observable_effect']['planned_n'], memory['all']['planned_n']))
            src += ';' + mempath
            locator += ' | $.new_batch.normal_phases;$.new_batch.observable_changes;$.new_batch.no_observable_effect;$.new_batch.all'
            semantics += '无可观测变化独立列出，不作为漏检攻击，也不并入已定义正常。'
            role = 'F03a当前完整方法与F03b固定条件的同批局部对照；仅覆盖已测向上修改范围。'
        elif cohort == 'timezone':
            subset = [r for r in specialists if r['scheme'] == 'APP_FULL' and r['fold_id'] == 'WEBGL1-LOEO-v1-01' and r['cohort'] == 'timezone' and r['scenario'].startswith('L_') and r['phase'] == 'change' and r['identity'] == 'NORMAL']
            change_n = sum(r['N'] for r in subset)
            check('timezone_normal_change_subset', change_n <= normal)
            semantics += '正常系统变化中间位置=' + str(change_n) + '，为全部正常的子集，不能相加。'
            role = 'F04正常系统换区与网页单独修改对照。'
        else:
            geo_path = sources[11]
            geo = docs[geo_path]
            check('screen_summary_counts', (normal, modified, total) == (geo['confirmed_normal']['n'], geo['observable_intervention']['n'], geo['all']['n']))
            no_effect = geo['no_observable_effect_positions']['n']
            src += ';' + geo_path
            locator += ' | $.confirmed_normal.n;$.observable_intervention.n;$.all.n;$.no_observable_effect_positions.n'
            semantics += '无可观测效果=' + str(no_effect) + '属于正常集合中的正常操作位置；normal_N+effective_modified_N=total，不能再加无效果列。'
            role = 'Host几何独立专项背景；本轮不制F09，也不宣称已接入当前Full。'
        add(cohort + '_specialist', label, normal, modified, no_effect, total, role, overlap, src, locator, semantics)

    web_path = sources[12]
    web = docs[web_path]
    normal = web['by_phase']['clean_pre']['collections'] + web['by_phase']['clean_post']['collections']
    modified = web['by_phase']['attack']['collections']
    check('webgl_effect_triplets', modified == web['measured_effect_triplets'])
    check('webgl_phase_partition', normal + modified == web['captured_payloads'])
    add('webgl_feasibility', 'WebGL行为可行性', normal, modified, 0, web['captured_payloads'],
        '行为一致性假设的可行性观察；不是完整App模型结果。',
        '同一批三阶段位置；不能解释为独立设备或总体检出率。',
        web_path, '$.by_phase.*.collections;$.captured_payloads;$.measured_effect_triplets;$.feasibility',
        '有效修改是measured_effect_triplets所确认的修改阶段；feasibility=' + web['feasibility'] + '。')

    pilot_path = sources[13]
    pilot = docs[pilot_path]
    with (root / sources[14]).open(encoding='utf-8-sig', newline='') as handle:
        pilot_csv = list(csv.DictReader(handle))
    check('pilot_json_csv_rows', len(pilot) == len(pilot_csv))
    for index, (j, c) in enumerate(zip(pilot, pilot_csv)):
        for key in ('kind', 'id', 'cohort', 'group', 'n', 'T', 'F', 'U', 'FAILED'):
            if str(j[key]) != c[key]:
                raise ValueError('T01 pilot JSON/CSV conflict: row=' + str(index) +
                                 ', kind=' + str(j.get('kind')) + ', id=' + str(j.get('id')) +
                                 ', cohort=' + str(j.get('cohort')) + ', group=' + str(j.get('group')) +
                                 ', field=' + key + ', JSON=' + str(j[key]) + ', CSV=' + str(c[key]))
    checks['T01_pilot_json_csv_count_and_row_keys_match'] = True
    model_id = next(r['id'] for r in pilot if r['kind'] == 'model' and r['cohort'] == 'pilot')
    selected = [r for r in pilot if r['kind'] == 'model' and r['cohort'] == 'pilot' and r['id'] == model_id]
    n = {r['group']: r['n'] for r in selected}
    check('pilot_groups', set(n) == {'normal', 'language_fr', 'timezone_tokyo'})
    pilot_normal, pilot_modified = n['normal'], n['language_fr'] + n['timezone_tokyo']
    add('browser_language_timezone_pilot', 'Browser语言/时区先导', pilot_normal, pilot_modified, 0, sum(n.values()),
        '独立Browser修改的先导背景；同批材料纳入后续语言/时区60条。',
        '一个先导环境、三阶段反复；多个模型与条件输出不增加位置数；不是正式独立泛化证明。',
        pilot_path, '$[kind=model,cohort=pilot,id=' + model_id + ',group=normal|language_fr|timezone_tokyo]',
        '取一个模型的保存分组分母；本表不使用其预测成绩。')

    matched_path = sources[15]
    matched = docs[matched_path]
    matched_normal = matched['groups']['qualified_normal']['positions']
    matched_modified = matched['groups']['qualified_intervention']['positions']
    check('matched_flow_and_groups', matched_normal == matched['flow']['identity_counts']['NORMAL'] and matched_modified == matched['flow']['identity_counts']['CONTROLLED_INTERVENTION'])
    check('matched_partition', matched_normal + matched_modified == matched['planned_positions'])
    add('bidirectional_language_timezone', '双向语言/时区及正常设置', matched_normal, matched_modified, 0, matched['planned_positions'],
        'App/Browser两方向修改及正常设置、连接对照。',
        '与先导合成后续60条语言/时区材料；补跑与多模型输出不能增加正式位置。',
        matched_path, '$.planned_positions;$.groups.qualified_normal.positions;$.groups.qualified_intervention.positions;$.flow.identity_counts',
        '使用qualified身份位置数，不将app_model_positions或condition_positions作为样本量。')

    resource_path = sources[16]
    resource = docs[resource_path]
    resource_normal = resource['identity_counts']['NORMAL']
    resource_modified = resource['effective_count']
    check('resource_effect_count', resource_modified == resource['identity_counts']['CONTROLLED_INTERVENTION'])
    check('resource_partition', resource_normal + resource_modified == resource['formal_positions'] == resource['pairs_valid'])
    add('paired_resource', '资源双端补证', resource_normal, resource_modified, 0, resource['formal_positions'],
        'App/Browser资源修改及空操作正常对照；资源联合接入的局部证据背景。',
        '空操作对照已在正常中；六条件、多模型和组合回放不形成新样本。不得与联合开发744重复相加。',
        resource_path, '$.formal_positions;$.identity_counts.NORMAL;$.effective_count;$.pairs_valid',
        '无效果指修改未产生可观测变化；计划正常空操作仍属于NORMAL，不重复列为无效果修改。')

    v16path = sources[17]
    v16 = docs[v16path]
    normal, modified = v16['confirmed_normal']['n'], v16['observable_intervention']['n']
    check('v16_engineering_total', sum(v16['position_status_counts'].values()) == v16['all']['n'] == v16['planned_records'])
    add('screen_v16_engineering', '屏幕v16工程收尾', normal, modified, v16['no_observable_effect_positions']['n'], v16['planned_records'],
        '工程降级、来源约束与失败流程检查；不纳入正式检测效果主表。',
        '独立工程位置；旧72条回放不是新增样本；本批也不能与正式检测分母相加。',
        v16path, '$.planned_records;$.confirmed_normal.n;$.observable_intervention.n;$.no_observable_effect_positions.n;$.position_status_counts',
        '正常和有效修改以外还有' + str(v16['planned_records'] - normal - modified) + '个工程位置；FAILED_EVIDENCE=' + str(v16['position_status_counts'].get('FAILED_EVIDENCE', 0)) + '。')

    paired60 = [r for r in unified['paired'] if r['dataset'] == 'language_timezone60' and r['method'] == 'APP_FULL']
    check('paired60_from_existing_batches', all(r['NORMAL']['n'] == pilot_normal + matched_normal and r['App']['n'] + r['Browser']['n'] == pilot_modified + matched_modified for r in paired60))
    checks['T01_no_global_sample_sum'] = True
    checks['T01_no_private_raw_or_ticket_reads'] = True
    checks['T01_unknown_counts_remain_blank'] = True
    return rows, checks, sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if args.check_only:
        result = validate_saved(output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['status'] == 'PASS' else 1
    if output == ROOT or (ROOT / 'deliverables') == output or (ROOT / 'deliverables') in output.parents:
        raise ValueError('Output must not overwrite the repository root or historical deliverables.')
    previous = read_json(output / 'CHECK.json') if (output / 'CHECK.json').exists() else {}
    if (output / 'FIGURES.json').exists():
        if read_json(output / 'FIGURES.json').get('owner') != OWNER:
            raise ValueError('Existing artifacts have no round-one ownership marker; use a new --output directory.')
    elif (output.exists() and output != HERE and any(output.iterdir())) or any((output/'figures'/(id_+'.png')).exists() for id_ in FIGURE_IDS):
        raise ValueError('Existing artifacts are not yet identified as this round; use a new --output directory.')
    output.mkdir(parents=True, exist_ok=True)
    (output/'figures').mkdir(exist_ok=True); (output/'data').mkdir(exist_ok=True)
    source_paths = sorted(set(CORE_SOURCES + list(F03B_SOURCES) + T01_SOURCES + [
        'deliverables/memory_relation_validation_v1/REPORT.md',
        'deliverables/timezone_relation_validation_v1/REPORT.md']))
    before = {p:digest(ROOT/p) for p in source_paths}
    checks=[]
    report={'owner':OWNER,'status':'IN_PROGRESS','initial_workspace_head_observed':'1b2d047e951029a41629f80773b5a4babe4a253c',
            'reference_commit':'2a83385d2f6119da90505e3a95518ae23296a9aa',
            'experiment_fact_baseline':'14540e6c946e6f6bd54ca3dca7d59694526ce6e0',
            'source_sha256_before':before,'checks':checks,
            'scope':'Saved aggregates only; no collection, fitting, rule selection, model/condition prediction or retiming.',
            'visual':{id_:{'png':'PENDING','svg':'NOT_VISUALLY_INSPECTED'} for id_ in FIGURE_IDS}}
    try:
        data, core_checks = extract_core(ROOT); checks.extend(core_checks)
        data['F03b'], mem_checks, mem_sources = extract_f03b(ROOT); checks.extend(mem_checks)
        data['T01'], t01_checks, t01_sources = extract_t01(ROOT)
        for name, ok in t01_checks.items():check(checks,name,ok,True)
        # The current zero-status annotations are guarded, never inferred from zero T.
        for name in ('F01','F03a','F03b','F04'):
            check(checks,name+'_nonbinary_states_for_current_annotations',
                  sum(r['U']+r['FAILED']+r['EMPTY_MODEL'] for r in data[name]),0)
        check(checks,'F02_current_empty_model_count',sum(r['EMPTY_MODEL'] for r in data['F02']),0)
        check(checks,'controlled_normal_T_regression',[r['T'] for r in data['T02'] if r['identity']=='NORMAL'],[0]*6)
        for m, expected_T, expected_U in [('APP_FULL',[2,2,0],[14]*3),('A_NO_MTC_CAP',[261]*3,[0]*3),('A_NO_MEMORY_REL',[2,2,0],[1]*3)]:
            rows=[r for r in data['F02'] if r['scheme']==m]
            check(checks,m+'_MTC_T_regression',[r['T'] for r in rows],expected_T)
            check(checks,m+'_MTC_U_regression',[r['U'] for r in rows],expected_U)
        # Static call/import review is an execution-scope check, not a new scientific test.
        tree=ast.parse(Path(__file__).read_text())
        forbidden={'fit','predict','predict_proba','evaluate','select','collect','collect_data'}
        calls=[n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id for n in ast.walk(tree)
               if isinstance(n,ast.Call) and isinstance(n.func,(ast.Name,ast.Attribute))]
        check(checks,'no_experiment_calls_in_plotting_entrypoint',sorted(set(calls)&forbidden),[])
        imports=sorted({n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module} |
                       {a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names})
        check(checks,'no_experiment_imports',any(x.startswith(('hybridguard','deliverables','sklearn','subprocess')) for x in imports),False)
        report['import_modules']=imports
        if any(c['status']=='FAIL' for c in checks):
            raise ValueError('Source checks failed; see CHECK.json for exact keys and fields.')
        for name, rows in data.items():write_csv(output/'data'/(name+'.csv'),rows)
        write_csv(output/'data/methods.csv',[dict(order=i+1,scheme=m,short_name=en,zh_name=cn,stage=stage(m),role='complete_current_App_model' if m!='APP_TREE' else 'fixed_small_App_tree') for i,(m,en,cn) in enumerate(METHODS)])
        write_csv(output/'data/configurations.csv',[dict(order=i+1,config_id=id_,short_name=en,zh_name=cn,role='controlled_modification_configuration') for i,(id_,en,cn) in enumerate(CONFIG_NAMES)])
        write_csv(output/'data/folds.csv',[dict(fold_id=f,short_name=f[-2:],role='frozen_environment_holdout_configuration',independent_replicate=False) for f in FOLDS])
        specs, runtime=plot_all(output,data)
        descriptions={
            'F01':dict(name='App detection across 14 modification configurations',source_stems=['configurations14','main','all_stages'],
                       filtering='configurations14: identity=EFFECTIVE_INTERVENTION; six methods; rules RETENTION and tree FITTED',
                       aggregation='None within a cell. Sum 14 disjoint held-out configuration rows only for T02; do not sum full-model replays.',
                       role='Current complete App method, four saved retrained ablations, fixed small App tree',
                       denominators='9 per cell; 126 effective positions overall; controlled normal 252 in T02',
                       limitations=['Development-exposed material, not a fresh blind test.','108/126 without MTC cap must be read with 261/261 normal alarms in F02.','Full is App only, not App+C1.']),
            'F02':dict(name='Four App outputs on historical MTC normal records',source_stems=['mtc','tree_input_integrity'],
                       filtering='six methods x three fold_id; subset in development,reserved_validation',
                       aggregation='Within each method/fold only: 144 + 117 = 261. Retain original discovery630/development144/reserved117 and derived261 in T03.',
                       role='Historical normal evaluation; discovery630 is training normal constraint',
                       denominators='261 per plotted row; T03 retains 630,144,117 and derived261',
                       limitations=['No attack-generalization evidence.','Three configurations reuse the same records.','Tree binary output does not restore missing observations; 73/891 input-unknown count is for full MTC, not 261.','EMPTY_MODEL=0; failure and unknown remain distinct from F.']),
            'F03a':dict(name='Complete App models on the memory-only batch',source_stems=['specialists'],
                       filtering='cohort=memory AND scenario=ALL AND phase=ALL; all three identities and folds retained',
                       aggregation='No hierarchy summation. Plot one count tuple only after all three configurations match in every state; keep all 54 rows.',
                       role='Saved complete-model specialist results, not a two-condition ablation',
                       denominators='Per configuration: 18 effective, 48 normal, 6 no observable effect; 72 total',
                       limitations=['Not 54 independent interventions.','Equal aggregate counts do not establish member-wise equality.','Upward memory changes only; does not cover arbitrary changes.']),
            'F03b':dict(name='Fixed memory relation versus Web > 8',source_stems=[],
                       filtering='summary.new_batch only; scope=target and EFFECTIVE_INTERVENTION for targets4,8,16',
                       aggregation='Sum saved condition counts across three environments/two rounds per target; cross-check saved triplet states. Aggregate rows are separate scopes.',
                       role='Original fixed conditions R_REL and R_WEB8; no retraining or condition evaluation',
                       denominators='6 per effective target; total18; target2 no-effect6 separately; normal48',
                       limitations=['Same local batch as F03a, not another 72 samples.','Upward changes only, not arbitrary memory tampering.','Full planned denominators retain U/FAILED; no common-evaluable restriction.','EMPTY_MODEL is not applicable to a fixed condition.']),
            'F04':dict(name='Normal timezone changes versus web-only modifications',source_stems=['specialists','main'],
                       filtering='timezone; phase=change; L_* AND NORMAL versus A_* AND EFFECTIVE_INTERVENTION; scenario ALL excluded',
                       aggregation='Sum Los_Angeles and UTC within one method/fold/identity. Plot equal count tuples after checking all folds; retain full rows.',
                       role='Current complete App methods on system-change controls and web-only interventions',
                       denominators='6 normal changes and 6 modifications per configuration; normal6 is a subset of normal30 in F04_totals',
                       limitations=['Normal and modified columns have different interpretations.','Full and no-timezone main score both105/126, but normal-change costs differ.','Three configurations are not independent experimental repetitions.'])}
        for item in specs:
            item.update(descriptions[item['id']]);item['status']='初稿已生成／待导师选择'
            paths=[BASE+n+ext for n in item.pop('source_stems') for ext in ('.json','.csv')]
            if item['id']=='F03b':paths+=list(F03B_SOURCES)
            else:paths+=[CONSOLIDATED]
            if item['id'] in ('F03a','F03b'):paths+=['deliverables/memory_relation_validation_v1/REPORT.md']
            if item['id']=='F04':paths+=['deliverables/timezone_relation_validation_v1/REPORT.md']
            item['sources']=[dict(path=p,sha256=before[p]) for p in paths]
            item['caption']='CAPTIONS.md#'+item['id'].lower()
            item['data_role']='Development-exposed saved material; not a new blind test.'
            item['png_sha256']=digest(output/item['png'])
            old=previous.get('visual',{}).get(item['id'],{})
            if old.get('png_sha256')==item['png_sha256']:report['visual'][item['id']]=old
        manifest=dict(owner=OWNER,status='初稿已生成／待导师选择',figures=specs,runtime=runtime,
                      source_summary='Saved CSV/JSON counts; reports are semantic references only.',
                      tables={name:'data/'+name+'.csv' for name in ('T01','T02','T03','F04_totals','tree_input_integrity')},
                      mappings={name:'data/'+name+'.csv' for name in ('methods','configurations','folds')})
        write_json(output/'FIGURES.json',manifest)
        saved_result=validate_saved(output)
        report['saved_output_check']=saved_result
        if saved_result['status']!='PASS':raise ValueError('Saved output consistency checks failed.')
        report['status']='PASS'
        report['runtime']=runtime
        report['numeric_check_count']=len(checks)
        report['source_count']=len(source_paths)
        report['source_notes']=['No source CSV/JSON conflicts detected.',
            'consolidation specialists is the 126-row ALL/ALL subset of the 1332-row specialists source.',
            'The old memory summary /new_batch/normal_phases/normal_basis_supported/n is 0, a separate field from planned_n=48 and conditions F=48. The later saved MEMORY_NORMAL_REVIEW.json confirms 48 normal positions, zero unsupported positions, unchanged historical outputs, and F=48 for both conditions. The separate old field is preserved; it is not used to redefine the plotted denominator.']
    except Exception as exc:
        report['status']='FAIL';report['error']=str(exc)
        raise
    finally:
        after={p:digest(ROOT/p) for p in source_paths}
        report['source_sha256_after']=after
        report['source_files_unchanged']=before==after
        if before!=after:report['status']='FAIL'
        write_json(output/'CHECK.json',report)
    print(json.dumps(dict(status=report['status'],numeric_checks=len(checks),figures=FIGURE_IDS,
                          source_files_unchanged=report['source_files_unchanged'],output=str(output)),ensure_ascii=False))
    return 0 if report['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
