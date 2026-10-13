"""Rebuild only this F01 candidate from saved tables. No experiment imports.

Run with the bundled Python (pdfplumber, pypdf, Pillow), Node/Playwright,
local Chrome, Poppler and the existing TeX Live installation.
"""
from pathlib import Path
from html import escape
from collections import Counter
import csv
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OLD = ROOT / 'paper/figures/round1_app'
SOURCE = ROOT / 'deliverables/app177_core_ablation_v1/results/summary'
FIELDS = ['N', 'T', 'F', 'U', 'FAILED', 'EMPTY_MODEL', 'defined']
METHODS = ['APP_FULL', 'A_NO_MTC_CAP', 'A_APP_WEB_ONLY', 'A_NO_MEMORY_REL',
           'A_NO_TIMEZONE_REL', 'APP_TREE']
EXPECTED_TOTALS = [105, 108, 96, 96, 105, 72]  # Acceptance assertions, never plot input.
W, H = 1800, 780
X, Y, CW, RH = 458, 92, 220, 42
FONT = 'Times New Roman'


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def counts(row):
    return {k: int(row[k]) for k in FIELDS}


def total(rows):
    return {k: sum(int(r[k]) for r in rows) for k in FIELDS}


def require(condition, context):
    if not condition:
        raise ValueError(json.dumps(context, ensure_ascii=False))


def keyed(rows, fields, file):
    result = {}
    for index, row in enumerate(rows):
        key = tuple(row[k] for k in fields)
        require(key not in result, dict(file=str(file), duplicate_key=key, row=index+2))
        result[key] = (index, row)
    return result


def source_table(stem, keys):
    rows = json.loads((SOURCE / f'{stem}.json').read_text())
    csv_rows = read_csv(SOURCE / f'{stem}.csv')
    a = keyed(rows, keys, f'{stem}.json')
    b = keyed(csv_rows, keys, f'{stem}.csv')
    require(a.keys() == b.keys(), dict(table=stem, error='CSV/JSON key mismatch'))
    for key, (i, row) in a.items():
        j, other = b[key]
        for field, value in row.items():
            require(str(value) == other.get(field), dict(table=stem, key=key, field=field,
                    json_index=i, csv_row=j+2, json=value, csv=other.get(field)))
        require(sum(row[f] for f in ['T', 'F', 'U', 'FAILED', 'EMPTY_MODEL']) == row['N'],
                dict(table=stem, key=key, error='state partition'))
        require(row['defined'] == row['T']+row['F'], dict(table=stem, key=key, error='defined'))
    return rows, a, b


def data_and_aliases():
    methods = read_csv(OLD / 'data/methods.csv')
    configurations = read_csv(OLD / 'data/configurations.csv')
    require([r['scheme'] for r in methods] == METHODS, 'Method order or identity changed')
    require([int(r['order']) for r in methods] == list(range(1, 7)), 'Method order')
    require([int(r['order']) for r in configurations] == list(range(1, 15)), 'Row order')
    require(len({r['config_id'] for r in configurations}) == 14, '14 unique configurations')
    conf, confkeys, confcsv = source_table('configurations14', ['scheme', 'configuration', 'identity'])
    main, mainkeys, _ = source_table('main', ['scheme', 'identity'])
    stages, _, _ = source_table('all_stages', ['scheme', 'stage', 'fold_id', 'cohort', 'subset', 'identity'])
    old = keyed(read_csv(OLD/'data/F01.csv'), ['scheme', 'configuration', 'identity'], 'F01.csv')
    t02 = keyed(read_csv(OLD/'data/T02.csv'), ['scheme', 'identity'], 'T02.csv')
    expected_keys = {(m, c['config_id'], 'EFFECTIVE_INTERVENTION') for m in METHODS for c in configurations}
    require(set(old) == expected_keys and len(old) == 84, 'Old F01 keys')
    require({k for k in confkeys if k[2] == 'EFFECTIVE_INTERVENTION'} == expected_keys, 'Source configuration keys')
    require(len(conf) == 168 and len(main) == 12, 'Source table cardinality')
    cells, summary = [], []
    method_lines = [['Full App'], ['No MTC', 'alarm cap'], ['App Web', 'only'],
                    ['No memory', 'relation'], ['No timezone', 'relation'], ['Small App', 'tree']]
    for method, lines in zip(methods, method_lines):
        method['display_lines'] = lines
        require(' '.join(lines) == method['short_name'], dict(alias=method))
        require(method['stage'] == ('FITTED' if method['scheme'] == 'APP_TREE' else 'RETENTION'), method)
    for row_index, config in enumerate(configurations):
        for col_index, method in enumerate(methods):
            key = (method['scheme'], config['config_id'], 'EFFECTIVE_INTERVENTION')
            source_index, row = confkeys[key]
            csv_index, _ = confcsv[key]
            old_index, previous = old[key]
            for field in FIELDS:
                require(int(previous[field]) == row[field], dict(file='F01.csv', key=key,
                        field=field, old=previous[field], source=row[field]))
            require(row['N'] == 9, dict(key=key, N=row['N']))
            require(previous['stage'] == method['stage'] and previous['method_short'] == method['short_name']
                    and previous['configuration_short'] == config['short_name'], dict(key=key, error='alias/stage'))
            require(previous['source_locator'] == f'/{source_index}' and int(previous['source_csv_row']) == csv_index+2,
                    dict(key=key, error='source locator'))
            require(int(previous['numerator']) == row['T'] and int(previous['denominator']) == row['N']
                    and abs(float(previous['rate'])-row['T']/row['N']) < 1e-12, dict(key=key, error='rate'))
            cells.append(dict(row_order=row_index+1, column_order=col_index+1, **row,
                              stage=method['stage'], method_alias=method['short_name'],
                              configuration_alias=config['short_name'], display=f"{row['T']}/{row['N']}",
                              proportion=row['T']/row['N'], source_json=str((SOURCE/'configurations14.json').relative_to(ROOT)),
                              source_json_pointer=f'/{source_index}', source_csv_row=csv_index+2,
                              previous_F01_csv_row=old_index+2))
    for method, expected in zip(methods, EXPECTED_TOTALS):
        m = method['scheme']
        record = {'scheme': m, 'method_alias': method['short_name'], 'stage': method['stage']}
        for identity, n in [('EFFECTIVE_INTERVENTION', 126), ('NORMAL', 252)]:
            subset = [r for r in conf if r['scheme'] == m and r['identity'] == identity]
            computed = total(subset)
            reference = counts(mainkeys[(m, identity)][1])
            require(len(subset) == 14 and computed == reference == counts(t02[(m, identity)][1]),
                    dict(method=m, identity=identity, computed=computed, main=reference, error='Totals mismatch'))
            primary = [r for r in stages if r['scheme'] == m and r['stage'] == method['stage']
                       and r['cohort'] == 'controlled' and r['subset'] == 'heldout' and r['identity'] == identity]
            require(sorted(r['fold_id'] for r in primary) == [f'WEBGL1-LOEO-v1-0{i}' for i in (1,2,3)]
                    and total(primary) == computed, dict(method=m, identity=identity, error='Stage contract'))
            require(computed['N'] == n and all(computed[k] == 0 for k in ['U','FAILED','EMPTY_MODEL']),
                    dict(method=m, identity=identity, computed=computed))
            require(computed['T'] == (expected if identity == 'EFFECTIVE_INTERVENTION' else 0),
                    dict(method=m, identity=identity, computed=computed, error='Acceptance assertion'))
            record[identity] = computed
        summary.append(record)
    aliases = {'row_order_changed': False, 'column_order_changed': False,
               'methods_source': 'paper/figures/round1_app/data/methods.csv',
               'configurations_source': 'paper/figures/round1_app/data/configurations.csv',
               'methods': methods, 'configurations': configurations}
    dump(HERE/'ALIASES.json', aliases)
    with (HERE/'F01_plot_data.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(cells[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(cells)
    return cells, aliases, dict(pass_=True, unique_cells=len(cells), rows=14, columns=6,
                               methods=summary, csv_json_agree=True, source_fields_compared=FIELDS,
                               all_stages_verified=True, old_aliases_and_order_preserved=True,
                               input_count_distribution=dict(Counter(c['display'] for c in cells)),
                               normal_scope='Controlled normal only; these zeros do not describe MTC.')


def rgb(color):
    return tuple(int(color[i:i+2], 16) for i in (1,3,5))


def color(p):
    # A single monotone blue ramp derived from the approved overview palette.
    stops = [(0., '#e9f0f9'), (2/3, '#96afd8'), (1., '#4469a7')]
    for (lo, ca), (hi, cb) in zip(stops, stops[1:]):
        if lo <= p <= hi:
            a, b = rgb(ca), rgb(cb); f = (p-lo)/(hi-lo)
            return '#' + ''.join(f'{round(x+(y-x)*f):02x}' for x,y in zip(a,b))
    raise ValueError(p)


def luminance(c):
    def lin(v):
        v /= 255
        return v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4
    return sum(v*w for v,w in zip(map(lin, rgb(c)), [.2126,.7152,.0722]))


def contrast(a, b):
    x,y=sorted([luminance(a),luminance(b)])
    return (y+.05)/(x+.05)


def draw(cells, aliases):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="78mm" viewBox="0 0 {W} {H}">',
             '<title>App detection across 14 modification configurations and six methods</title>',
             '<desc>Each cell is the saved alarm count T/9. All cells share a fixed 0 to 100 percent blue scale.</desc>',
             '<defs><linearGradient id="detection-scale"><stop offset="0" stop-color="#e9f0f9"/><stop offset="66.6666667%" stop-color="#96afd8"/><stop offset="100%" stop-color="#4469a7"/></linearGradient></defs>',
             f'<g font-family="{FONT}" fill="#343434"><rect width="{W}" height="{H}" fill="white"/>']
    def text(x,y,s,size=31,anchor='start',fill='#343434',weight='normal',extra=''):
        parts.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" font-weight="{weight}" {extra}>{escape(s)}</text>')
    def rect(x,y,w,h,fill,extra=''):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" {extra}/>')
    text(18,60,'Modification',fill='#666666',extra='data-role="row-heading"')
    for j, method in enumerate(aliases['methods']):
        lines=method['display_lines']
        for k,line in enumerate(lines):
            text(X+(j+.5)*CW, 54.5 if len(lines)==1 else 36+37*k, line, size=32, anchor='middle',
                 weight='bold' if j == 0 else 'normal', extra=f'data-role="method" data-method="{method["scheme"]}"')
    for i, config in enumerate(aliases['configurations']):
        text(18,Y+i*RH+31,config['short_name'],extra=f'data-role="configuration" data-config="{config["config_id"]}"')
    contrast_values=[]
    for c in cells:
        i,j=c['row_order']-1,c['column_order']-1
        fill=color(c['proportion'])
        ink=max(['#343434','#ffffff'],key=lambda ink:contrast(ink,fill))
        cr=contrast(ink,fill); require(cr>=4.5,dict(cell=c['display'],contrast=cr))
        contrast_values.append(cr)
        extra=f'data-cell="{i+1}-{j+1}" data-method="{c["scheme"]}" data-config="{c["configuration"]}"'
        rect(X+j*CW,Y+i*RH,CW,RH,fill,extra)
        text(X+(j+.5)*CW,Y+i*RH+31,c['display'],anchor='middle',fill=ink,extra=extra+' data-role="count"')
    for j in range(1,6):
        parts.append(f'<path d="M{X+j*CW} {Y}V{Y+14*RH}" stroke="white" stroke-width="1.25"/>')
    for i in range(1,14):
        parts.append(f'<path d="M{X} {Y+i*RH}H{X+6*CW}" stroke="white" stroke-width="1.25"/>')
    rect(X,Y,6*CW,14*RH,'none','stroke="#B9C0C8" stroke-width="1.5"')
    text(18,745,'Detection (%)',fill='#666666',extra='data-role="legend"')
    rect(X,718,850,14,'url(#detection-scale)','data-role="colorbar" stroke="#B9C0C8" stroke-width="1.2"')
    for t in [0,.5,1]:
        x=X+850*t
        parts.append(f'<path d="M{x} 732v6" stroke="#666666" stroke-width="1.2"/>')
        text(x,768,str(round(100*t)),anchor='middle',fill='#666666',extra='data-role="legend"')
    text(1778,745,'Cells: T/9',anchor='end',fill='#666666',extra='data-role="legend"')
    parts.append('</g></svg>')
    (HERE/'F01_main.svg').write_text('\n'.join(parts)+'\n')
    ramp=[luminance(color(i/1000)) for i in range(1001)]
    require(all(a>=b for a,b in zip(ramp,ramp[1:])), 'Non-monotone luminance')
    return dict(size_mm=[180,78], viewbox=[W,H], grid=[X,Y,CW,RH], font=FONT,
                minimum_font_units=31, cell_contrast_min=min(contrast_values),
                fixed_scale=[0,1], luminance_monotone=True,
                colors={'ink':'#343434','muted':'#666666','boundary':'#B9C0C8',
                        'overview_blue':'#507cc4','ramp_stops':[[0,'#e9f0f9'],[2/3,'#96afd8'],[1,'#4469a7']]},
                palette_note='Pale/mid blue and a 15-percent darkened overview blue; same ramp in every column.')


def main():
    cells, aliases, data_check = data_and_aliases()
    data_check['pass'] = data_check.pop('pass_')
    layout=draw(cells,aliases)
    dump(HERE/'layout.json',layout)
    dump(HERE/'CHECK.json',{'data':data_check,'layout':layout,'visual_review':{'status':'PENDING'}})
    manifest=json.loads((HERE/'SOURCE_MANIFEST.json').read_text())
    manifest.update(selection={'cell_source':'configurations14.json',
        'key':['scheme','configuration','identity'], 'identity':'EFFECTIVE_INTERVENTION',
        'source_csv_json_crosscheck':True, 'rules_stage':'RETENTION', 'tree_stage':'FITTED',
        'stage_crosscheck':'all_stages: cohort=controlled, subset=heldout, original three folds; sum equals main',
        'denominator':'9 effective evaluation positions per configuration; 126 per method. Repeated predictions are not new independent samples.',
        'row_order':'Original configurations.csv order, unchanged','column_order':METHODS},
        external_reference={'file':'_WWW__Lower_Barriers__Greater_Threat_.pdf','page_one_based':5,
                            'figure':'Figure 1, upper figure','original_pdf_actually_opened':True,
                            'use':'Visual language only; no imported screenshot, icon or geometry.'},
        style_reference='paper/figures/overview_triangle/style_full_v1/HybridGuard_overview_candidate.svg')
    dump(HERE/'SOURCE_MANIFEST.json',manifest)
    node=os.environ.get('RBA_NODE',str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'))
    subprocess.run([node,str(HERE/'render_candidate.cjs')],check=True,cwd=HERE)
    subprocess.run([sys.executable,'-B',str(HERE/'check_candidate.py')],check=True,cwd=HERE)


if __name__ == '__main__':
    main()
