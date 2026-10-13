"""Build only this saved-result F03a/F04 candidate; no research entrypoints.

Read saved CSV/JSON, verify row locators and counts, and draw editable SVG.
Browser rendering and isolated ACM validation are local to this directory.
"""
from pathlib import Path
from collections import Counter
from html import escape
import argparse
import csv
import itertools
import json
import os
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SAVED = ROOT / 'paper/figures/round1_app'
SUMMARY = ROOT / 'deliverables/app177_core_ablation_v1/results/summary'
DATA = HERE / 'data'
COUNTS = ['N', 'T', 'F', 'U', 'FAILED', 'EMPTY_MODEL', 'defined']
KEYS = ['scheme', 'fold_id', 'cohort', 'scenario', 'phase', 'identity']
METHODS = ['APP_FULL', 'A_NO_MTC_CAP', 'A_APP_WEB_ONLY', 'A_NO_MEMORY_REL',
           'A_NO_TIMEZONE_REL', 'APP_TREE']
ALIASES = ['Full App', 'No MTC alarm cap', 'App Web only', 'No memory relation',
           'No timezone relation', 'Small App tree']
FOLDS = ['WEBGL1-LOEO-v1-01', 'WEBGL1-LOEO-v1-02', 'WEBGL1-LOEO-v1-03']
W, H = 1800, 572
FONT_SIZE = 31
INK, GREEN, BLUE = '#343434', '#5B8574', '#6B8299'
PANELS = {'memory': {'x0': 520, 'x1': 1055, 'title': '(a) Memory reference'},
          'timezone': {'x0': 1230, 'x1': 1765, 'title': '(b) Timezone reference'}}
FIRST_ROW, ROW_PITCH, OFFSET = 110, 70, 17.5


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def capture_generation_baseline():
    """Protect this run against changes, independent of the historical HEAD."""
    historical = json.loads((HERE/'SOURCE_MANIFEST.json').read_text())['baseline']
    stats = {}
    for name in historical['protected_file_stats']:
        stat = (ROOT/name).stat()
        # CHECK.json also passes through Node: preserve nanoseconds beyond 2**53.
        stats[name] = {'size': stat.st_size, 'mtime_ns': str(stat.st_mtime_ns)}
    return {
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'status_porcelain_v1_z': subprocess.check_output(
            ['git', 'status', '--porcelain=v1', '-z', '--untracked-files=all'], cwd=ROOT).decode(),
        'index_status': subprocess.check_output(['git', 'diff', '--cached', '--name-status'], cwd=ROOT, text=True),
        'protected_file_stats': stats,
    }


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def clean_source(row):
    return {key: int(row[key]) if key in COUNTS else row[key] for key in KEYS + COUNTS}


def verify_and_extract():
    DATA.mkdir(exist_ok=True)
    methods, folds = read_csv(SAVED/'data/methods.csv'), read_csv(SAVED/'data/folds.csv')
    require([m['scheme'] for m in methods] == METHODS, 'Method ID/order changed')
    require([m['short_name'] for m in methods] == ALIASES, 'Method aliases changed')
    require([int(m['order']) for m in methods] == list(range(1, 7)), 'Method order field')
    require([f['fold_id'] for f in folds] == FOLDS, 'Frozen configuration IDs changed')
    require(all(f['independent_replicate'] == 'False' for f in folds), 'Configurations are not independent replicates')
    stage = {m['scheme']: m['stage'] for m in methods}
    require(all(stage[m] == ('FITTED' if m == 'APP_TREE' else 'RETENTION') for m in METHODS), 'Wrong model stage')
    source_csv = read_csv(SUMMARY/'specialists.csv')
    source_json = json.loads((SUMMARY/'specialists.json').read_text())
    require(len(source_csv) == len(source_json), 'Saved CSV/JSON length mismatch')
    source_keys = [tuple(r[k] for k in KEYS) for r in source_json]
    require(len(source_keys) == len(set(source_keys)), 'Ambiguous saved source keys')
    expected_sets = {
        'F03a': set(itertools.product(METHODS, FOLDS, ['NORMAL', 'EFFECTIVE_INTERVENTION', 'NO_OBSERVABLE_EFFECT'])),
        'F04': set(itertools.product(METHODS, FOLDS, ['normal_system_change', 'web_only_change'])),
        'F04_totals': set(itertools.product(METHODS, FOLDS, ['NORMAL', 'EFFECTIVE_INTERVENTION'])),
    }
    normalized, mappings, tables = [], [], {}
    for name in ('F03a', 'F04', 'F04_totals'):
        path = SAVED/f'data/{name}.csv'
        rows = read_csv(path)
        tables[name] = rows
        identity_key = 'group' if name == 'F04' else 'identity'
        observed = [(r['scheme'], r['fold_id'], r[identity_key]) for r in rows]
        require(len(observed) == len(set(observed)) and set(observed) == expected_sets[name], (name, 'Missing or duplicate groups'))
        for number, row in enumerate(rows, start=2):
            require(row['source_path'] == str((SUMMARY/'specialists.json').relative_to(ROOT)), 'Unexpected source file')
            require(row['stage'] == stage[row['scheme']], 'Stage mismatch')
            require(row['method_short'] == ALIASES[METHODS.index(row['scheme'])], 'Alias mismatch')
            locators = row['source_locator'].split(';')
            csv_lines = [int(s) for s in row['source_csv_row'].split(';')]
            require(len(locators) == len(csv_lines) == len(set(locators)), 'Bad or repeated locators')
            records = []
            for loc, line in zip(locators, csv_lines):
                require(loc.startswith('/') and loc[1:].isdigit(), 'Unsupported JSON locator')
                index = int(loc[1:])
                require(line == index + 2, 'CSV line and JSON index differ')
                item = source_json[index]
                require(clean_source(source_csv[line-2]) == item, ('CSV/JSON source disagreement', loc))
                require(all(item[k] == row[k] for k in ('scheme', 'fold_id', 'cohort', 'identity')), 'Source identity mismatch')
                records.append(item)
            if name == 'F04':
                normal = row['group'] == 'normal_system_change'
                scenarios = {'L_America/Los_Angeles', 'L_UTC'} if normal else {'A_America/Los_Angeles', 'A_UTC'}
                require(row['cohort'] == 'timezone' and row['phase'] == 'change', 'Timezone group/stage')
                require(row['identity'] == ('NORMAL' if normal else 'EFFECTIVE_INTERVENTION'), 'Timezone identity')
                require(set(row['scenario'].split('+')) == scenarios, 'Plot CSV scenario set')
                require(len(records) == 2 and {r['scenario'] for r in records} == scenarios, 'Wrong timezone scenarios')
                require(all(r['phase'] == 'change' and r['scenario'] != 'ALL' and r['N'] == 3 for r in records), 'ALL/phase double count or bad denominator')
                subset = row['group']
            else:
                require(len(records) == 1 and row['scenario'] == row['phase'] == 'ALL', 'Expected exactly one saved aggregate')
                require(records[0]['scenario'] == records[0]['phase'] == 'ALL', 'Wrong saved aggregate')
                require(row['cohort'] == ('memory' if name == 'F03a' else 'timezone'), 'Wrong cohort')
                subset = row['identity'] if name == 'F03a' else 'total_' + row['identity']
            counts = {key: sum(r[key] for r in records) for key in COUNTS}
            require(counts == {k: int(row[k]) for k in COUNTS}, (name, number, 'Saved counts disagree'))
            require(counts['N'] == sum(counts[k] for k in ['T', 'F', 'U', 'FAILED', 'EMPTY_MODEL']), 'State partition mismatch')
            require(counts['defined'] == counts['T'] + counts['F'], 'Defined count mismatch')
            require(int(row['numerator']) == counts['T'] and int(row['denominator']) == counts['N'], 'T/N mapping mismatch')
            require(abs(float(row['rate']) - counts['T']/counts['N']) < 1e-12, 'Rate mismatch')
            require(abs(float(row['defined_rate']) - counts['defined']/counts['N']) < 1e-12, 'Defined rate mismatch')
            require(all(counts[k] == 0 for k in ['U', 'FAILED', 'EMPTY_MODEL']), 'Nonzero status must remain visible')
            norm = {'source_id': name, 'plot_csv_row': number, 'scheme': row['scheme'],
                    'method': row['method_short'], 'fold_id': row['fold_id'], 'stage': row['stage'],
                    'panel': row['cohort'], 'subset': subset, 'identity': row['identity'], **counts,
                    'source_locator': row['source_locator'], 'source_csv_row': row['source_csv_row']}
            normalized.append(norm)
            mappings.append({**norm, 'source_path': row['source_path'], 'records': records})
        shutil.copy2(path, DATA/f'{name}_all_configurations.csv')
    for name in ('methods', 'folds'):
        shutil.copy2(SAVED/f'data/{name}.csv', DATA/f'{name}.csv')
    grouped = {}
    for r in normalized:
        grouped.setdefault((r['scheme'], r['panel'], r['subset']), []).append(r)
    equality = []
    for key, group in grouped.items():
        require({r['fold_id'] for r in group} == set(FOLDS), ('Incomplete configuration group', key))
        require(len({tuple(r[k] for k in COUNTS) for r in group}) == 1, ('Cannot compress unequal aggregates', key))
        require(len({r['stage'] for r in group}) == 1, 'Stage varies across configurations')
        equality.append({'scheme': key[0], 'panel': key[1], 'subset': key[2],
                         'counts': {k: group[0][k] for k in COUNTS}, 'configurations': FOLDS, 'equal': True})
    for method, fold in itertools.product(METHODS, FOLDS):
        records = [r for r in normalized if r['scheme'] == method and r['fold_id'] == fold]
        memory = {r['subset']: r for r in records if r['panel'] == 'memory'}
        require({k: r['N'] for k,r in memory.items()} == {'NORMAL': 48, 'EFFECTIVE_INTERVENTION': 18, 'NO_OBSERVABLE_EFFECT': 6}, 'Memory denominators')
        require(memory['NO_OBSERVABLE_EFFECT']['T'] == 0, 'No-change caption mismatch')
        timezone = {r['subset']: r for r in records if r['panel'] == 'timezone'}
        require(timezone['normal_system_change']['N'] == timezone['web_only_change']['N'] == 6, 'Timezone plotted denominators')
        require(timezone['total_NORMAL']['N'] == 30 and timezone['total_EFFECTIVE_INTERVENTION']['N'] == 6, 'Timezone full denominators')
        require(all(timezone['normal_system_change'][k] <= timezone['total_NORMAL'][k] for k in COUNTS), 'Normal changes not within total counts')
        require(all(timezone['web_only_change'][k] == timezone['total_EFFECTIVE_INTERVENTION'][k] for k in COUNTS), 'Intervention total mismatch')
    # The user-provided matrix is an acceptance assertion, never a plotting source.
    expected = [[18,0,6,0], [18,0,6,0], [0,0,6,6], [0,0,6,0], [18,0,6,6], [0,0,0,0]]
    plotted = []
    for order, method in enumerate(METHODS, 1):
        four = []
        for panel, subsets in [('memory', ['EFFECTIVE_INTERVENTION', 'NORMAL']),
                               ('timezone', ['web_only_change', 'normal_system_change'])]:
            for series, subset in zip(['intervention', 'normal'], subsets):
                group = sorted(grouped[(method, panel, subset)], key=lambda r: r['fold_id'])
                # The equal verified counts are represented once; no sum across folds.
                item = group[0]
                four.append(item['T'])
                plotted.append({'row_order': order, 'scheme': method, 'method': item['method'],
                                'panel': panel, 'series': series, 'identity': item['identity'],
                                'subset': subset, 'stage': item['stage'], **{k: item[k] for k in COUNTS},
                                'alarm_rate_pct': item['T']/item['N']*100,
                                'display': f"{item['T']}/{item['N']}", 'configurations': ';'.join(FOLDS),
                                'source_id': item['source_id'],
                                'plot_csv_rows': ';'.join(str(r['plot_csv_row']) for r in group),
                                'source_locators_by_configuration': json.dumps({r['fold_id']: r['source_locator'] for r in group}),
                                'source_csv_rows_by_configuration': json.dumps({r['fold_id']: r['source_csv_row'] for r in group})})
        require(four == expected[order-1], ('Acceptance matrix mismatch', method))
    require(len(plotted) == 24, '24 unique data markers required')
    timezone_refs = [loc for r in tables['F04'] for loc in r['source_locator'].split(';')]
    require(len(timezone_refs) == len(set(timezone_refs)) == 72, 'Duplicate timezone scenario records')
    write_csv(DATA/'plot_data.csv', plotted)
    write_csv(DATA/'counts_by_configuration.csv', normalized)
    write_csv(DATA/'memory_no_observable_change.csv', [r for r in normalized if r['subset'] == 'NO_OBSERVABLE_EFFECT'])
    dump(DATA/'source_mapping.json', mappings)
    dump(DATA/'configuration_equality.json', equality)
    report = {'pass': True, 'source': 'Saved specialists.csv/json and original F03a/F04 plotting CSVs',
              'original_rows': {k: len(v) for k,v in tables.items()}, 'normalized_rows': len(normalized),
              'method_ids': METHODS, 'method_aliases': ALIASES, 'frozen_configurations': FOLDS,
              'verified_state_fields': COUNTS, 'equal_configuration_groups': len(equality),
              'plotted_markers': len(plotted), 'unique_timezone_scenario_records': 72,
              'timezone_ALL_records_added_to_scenarios': False, 'denominators_pooled_across_configurations': False,
              'memory_no_change_separate': True, 'normal_timezone_change_is_subset_of_30': True,
              'all_shown_U_FAILED_EMPTY_MODEL_zero': True, 'record_level_prediction_equality_claimed': False,
              'expected_matrix_assertion_pass': True, 'experimental_entrypoints_called': False,
              'error_bars_or_significance_generated': False,
              'counts_by_method': {m: [r['display'] for r in plotted if r['scheme'] == m] for m in METHODS}}
    return plotted, methods, report


def draw(plotted, methods):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="{H/10:g}mm" viewBox="0 0 {W} {H}">',
             '<title>Native-App Web reference evaluations on saved specialist records</title>',
             '<desc>Shared method rows and two alarm-rate dot plots: memory and timezone. Filled green circles show intervention detection; hollow blue squares show normal false alarms. Higher detection and lower false alarms are preferred. Every point has an exact T/N label. The same counts hold separately for three frozen configurations, without pooling.</desc>',
             f'<g font-family="Times New Roman" fill="{INK}">',
             f'<rect width="{W}" height="{H}" fill="#ffffff" data-role="canvas"/>']
    def text(x, y, value, role, size=FONT_SIZE, anchor='start', bold=False, attrs=''):
        parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{700 if bold else 400}" '
                     f'text-anchor="{anchor}" data-role="{role}" {attrs}>{escape(value)}</text>')
    def line(x1,y1,x2,y2,color,width,role,attrs=''):
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" data-role="{role}" {attrs}/>')
    for panel, settings in PANELS.items():
        x0,x1 = settings['x0'],settings['x1']; mid=(x0+x1)/2
        text(mid, 30, settings['title'], 'panel-title', bold=True, anchor='middle', attrs=f'data-panel="{panel}"')
        for tick in [0,50,100]:
            x=x0+(x1-x0)*tick/100
            line(x,81,x,496,'#E1E4E7',1.25,'grid',f'data-panel="{panel}" data-rate="{tick}"')
            line(x,496,x,500,'#9BA2A8',1.5,'tick')
            text(x,528,str(tick),'tick-label',anchor='middle')
        line(x0,496,x1,496,'#9BA2A8',1.5,'axis',f'data-panel="{panel}"')
        text(mid,563,'Alarm rate (%)','axis-label',anchor='middle')
    # Shared legend uses words for direction, avoiding arrow-glyph fallback.
    parts.append(f'<circle cx="447" cy="56" r="8.5" fill="{GREEN}" data-role="legend-marker"/>')
    text(471,67,'Interventions: detection (higher is better)','legend')
    parts.append(f'<rect x="1130" y="48" width="16" height="16" fill="#ffffff" stroke="{BLUE}" stroke-width="3" data-role="legend-marker"/>')
    text(1162,67,'Normal records: false alarms (lower is better)','legend')
    for i,method in enumerate(methods):
        y=FIRST_ROW+i*ROW_PITCH
        text(18,y+10,method['short_name'],'method',bold=i==0,attrs=f'data-method="{method["scheme"]}" data-row="{i+1}"')
    mark_positions=[]
    for record in plotted:
        panel=record['panel']; settings=PANELS[panel]
        rate=record['alarm_rate_pct']; x=settings['x0']+(settings['x1']-settings['x0'])*rate/100
        center=FIRST_ROW+(record['row_order']-1)*ROW_PITCH
        y=center+(-OFFSET if record['series']=='intervention' else OFFSET)
        id_=f'{panel}-{record["scheme"]}-{record["series"]}'
        attrs=(f'data-point="{id_}" data-method="{record["scheme"]}" data-panel="{panel}" '
               f'data-series="{record["series"]}" data-rate="{rate:g}" data-count="{record["display"]}"')
        if record['series']=='intervention':
            parts.append(f'<circle cx="{x:g}" cy="{y:g}" r="8.5" fill="{GREEN}" data-role="data-marker" {attrs}/>')
        else:
            parts.append(f'<rect x="{x-8:g}" y="{y-8:g}" width="16" height="16" fill="#ffffff" stroke="{BLUE}" stroke-width="3" data-role="data-marker" {attrs}/>')
        label_x=x+23 if rate<=50 else x-23
        text(label_x,y+10,record['display'],'count',anchor='start' if rate<=50 else 'end',attrs=attrs)
        mark_positions.append({'id':id_, 'panel':panel,'series':record['series'],'scheme':record['scheme'],
                               'row':record['row_order'],'x':x,'y':y,'rate':rate,'display':record['display'],
                               'label_x':label_x,'label_y':y+10})
    parts.append('</g></svg>')
    (HERE/'F03a_F04_main.svg').write_text('\n'.join(parts)+'\n')
    return {'size_mm':[180,H/10], 'viewbox':[W,H], 'font':'Times New Roman', 'minimum_font_units':FONT_SIZE,
            'ink':INK, 'series_colors':{'intervention':GREEN,'normal':BLUE},
            'shapes':{'intervention':'filled circle','normal':'hollow square'},
            'panels':PANELS,'first_row_y':FIRST_ROW,'row_pitch':ROW_PITCH,'series_vertical_offset':OFFSET,
            'row_alignment_shared':True,'x_limits':[0,100],'ticks':[0,50,100],
            'horizontal_marker_jitter':0,'data_connectors':0,'colorbar':False,'error_bars':False,
            'method_background_fills':False,'main_title_visible':False,'markers':mark_positions}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--baseline',type=Path); args=parser.parse_args()
    if not (HERE/'SOURCE_MANIFEST.json').exists():
        require(args.baseline is not None,'First build requires a pre-edit workspace baseline')
        baseline=json.loads(args.baseline.read_text())
        sources=[SAVED/f'data/{name}.csv' for name in ['F03a','F04','F04_totals','methods','folds']]
        sources += [SUMMARY/'specialists.csv',SUMMARY/'specialists.json',SAVED/'CAPTIONS.md',
                    SAVED/'figures/F03a.svg',SAVED/'figures/F04.svg']
        dump(HERE/'SOURCE_MANIFEST.json',{'source_ids':['F03a','F04'],'candidate':'F03a_F04_main',
             'baseline':baseline,'source_files':[{ 'path':str(p.relative_to(ROOT)), 'bytes':p.stat().st_size } for p in sources],
             'reference_pdf':{'path':'_WWW__Lower_Barriers__Greater_Threat_.pdf','table_1_page':6,'figure_1_page':5},
             'accepted_F01':'paper/figures/f01_app_detection/style_www_v1/F01_main_rev4.pdf',
             'accepted_overview':'paper/figures/overview_triangle/style_full_v1/HybridGuard_overview_candidate.pdf',
             'scope':'Saved counts only; all candidate generation writes stay in this directory. No new evaluation.',
             'integrity_scope':'Targeted source key/count comparisons and pre-existing file size/mtime plus Git status; no hash scans.'})
    generation_baseline=capture_generation_baseline()
    plotted,methods,data=verify_and_extract()
    layout=draw(plotted,methods); dump(HERE/'layout.json',layout)
    dump(HERE/'CHECK.json',{'data':data,'layout':layout,'generation_baseline':generation_baseline,
                          'visual_review':{'status':'PENDING','actually_viewed':[]}})
    node=os.environ.get('RBA_NODE',str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'))
    subprocess.run([node,str(HERE/'render_candidate.cjs')],check=True,cwd=HERE)
    subprocess.run([sys.executable,'-B',str(HERE/'check_candidate.py')],check=True,cwd=HERE)


if __name__=='__main__':
    main()
