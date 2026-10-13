"""Render one compact three-value table revision from the already verified, unchanged F01 CSV.

No collection, fitting, evaluation, experiment summary, or original plot entrypoint
is called. The previous revision's artifacts and scripts are never overwritten.
"""
from collections import Counter
from html import escape
from pathlib import Path
import csv
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
W, H = 1800, 625
X, Y, CW, RH = 458, 124, 220, 35
INK = '#343434'
PALETTE = {'9/9': '#DCE9D8', '6/9': '#E4EDF7', '0/9': 'none'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def luminance(color):
    color = '#ffffff' if color == 'none' else color
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(v * k for v, k in zip(linear, (.2126, .7152, .0722)))


def saved_data():
    with (HERE / 'F01_plot_data.csv').open(newline='') as stream:
        cells = list(csv.DictReader(stream))
    aliases = json.loads((HERE / 'ALIASES.json').read_text())
    old = json.loads((HERE / 'rev3_snapshot/CHECK.json').read_text())
    expected_methods = ['APP_FULL', 'A_NO_MTC_CAP', 'A_APP_WEB_ONLY',
                        'A_NO_MEMORY_REL', 'A_NO_TIMEZONE_REL', 'APP_TREE']
    require([m['scheme'] for m in aliases['methods']] == expected_methods, 'Method order changed')
    require(len(aliases['configurations']) == 14 and len(cells) == 84, 'Matrix dimensions changed')
    require(len({(c['row_order'], c['column_order']) for c in cells}) == 84, 'Duplicate cell')
    count_fields = ['N', 'T', 'F', 'U', 'FAILED', 'EMPTY_MODEL', 'defined']
    for cell in cells:
        i, j = int(cell['row_order']) - 1, int(cell['column_order']) - 1
        require(cell['scheme'] == aliases['methods'][j]['scheme'] and
                cell['configuration'] == aliases['configurations'][i]['config_id'], 'Alias/order mismatch')
        require(cell['N'] == '9' and cell['display'] == f"{cell['T']}/9", 'Count display mismatch')
    # Arithmetic consistency only; the recorded evaluation results are not rerun.
    for method in old['data']['methods']:
        subset = [c for c in cells if c['scheme'] == method['scheme']]
        require({k: sum(int(c[k]) for c in subset) for k in count_fields} ==
                method['EFFECTIVE_INTERVENTION'], 'Saved totals changed')
    require(dict(Counter(c['display'] for c in cells)) == old['data']['input_count_distribution'],
            'Saved cell distribution changed')
    data = old['data'].copy()
    data['revision_verification'] = {
        'source': 'Unmodified F01_plot_data.csv and ALIASES.json from rev1',
        'original_source_checks': 'Inherited from rev3_snapshot/CHECK.json; source files retained unchanged',
        'new_checks': '84 unique cells, aliases, display counts, and arithmetic equality with saved totals',
        'experiment_or_evaluation_entrypoints_called': False,
        'row_grouping_or_reordering': False,
    }
    return cells, aliases, data, old


def draw(cells, aliases):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="62.5mm" viewBox="0 0 {W} {H}">',
             '<title>Detection across 14 App intervention configurations</title>',
             '<desc>A fourteen by six table of saved alarm counts T/9 in the original order. '
             'Discrete styles show 9/9 in pale green, 6/9 in pale blue and 0/9 without a cell fill. '
             'Numbers carry all values. No continuous color scale is used.</desc>',
             '<g font-family="Times New Roman" fill="#343434">',
             f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    def text(x, y, label, anchor='start', weight='normal', extra=''):
        parts.append(f'<text x="{x}" y="{y}" font-size="31" text-anchor="{anchor}" '
                     f'font-weight="{weight}" {extra}>{escape(label)}</text>')

    text(18, 30, 'Detection across 14 App intervention configurations',
         weight='bold', extra='data-role="title"')
    text(18, 88.5, 'Configuration', extra='data-role="row-heading"')
    for j, method in enumerate(aliases['methods']):
        lines = method['display_lines']
        for k, line in enumerate(lines):
            text(X + (j + .5) * CW, 88.5 if len(lines) == 1 else 71 + 35 * k, line,
                 anchor='middle', weight='bold' if j == 0 else 'normal',
                 extra=f'data-role="method" data-method="{method["scheme"]}"')
    for i, config in enumerate(aliases['configurations']):
        text(18, Y + i * RH + 28, config['short_name'],
             extra=f'data-role="configuration" data-config="{config["config_id"]}"')
    for cell in cells:
        i, j = int(cell['row_order']) - 1, int(cell['column_order']) - 1
        fill = PALETTE[cell['display']]
        attrs = (f'data-cell="{i + 1}-{j + 1}" data-method="{cell["scheme"]}" '
                 f'data-config="{cell["configuration"]}"')
        parts.append(f'<rect x="{X + j * CW}" y="{Y + i * RH}" width="{CW}" '
                     f'height="{RH}" fill="{fill}" {attrs}/>')
        text(X + (j + .5) * CW, Y + i * RH + 28, cell['display'], anchor='middle',
             extra=attrs + ' data-role="count"')
    # Fine white rules separate pale fills without changing cells or typography.
    for j in range(1, 6):
        parts.append(f'<path d="M{X+j*CW} {Y}V{Y+14*RH}" fill="none" '
                     'stroke="#ffffff" stroke-width="1.5" data-role="cell-separator"/>')
    for i in range(1, 14):
        parts.append(f'<path d="M{X} {Y+i*RH}H{X+6*CW}" fill="none" '
                     'stroke="#ffffff" stroke-width="1.5" data-role="cell-separator"/>')
    # The legend occupies unused space on the existing title row: zero new height.
    for k, value in enumerate(['9/9', '6/9', '0/9']):
        x = 1452 + 112*k
        outline = ' stroke="#B9C0C8" stroke-width="1"' if value == '0/9' else ''
        parts.append(f'<rect x="{x}" y="8" width="22" height="22" '
                     f'fill="{PALETTE[value]}" data-role="legend-swatch" data-value="{value}"{outline}/>')
        text(x+32, 30, value, extra=f'data-role="legend" data-value="{value}"')
    for y, width, ink in [(41, 2, '#666666'), (120, 1.5, '#B9C0C8'), (617, 2, '#666666')]:
        parts.append(f'<path d="M18 {y}H1778" fill="none" stroke="{ink}" '
                     f'stroke-width="{width}" data-role="table-rule"/>')
    parts.append('</g></svg>')
    (HERE / 'F01_main_rev4.svg').write_text('\n'.join(parts) + '\n')
    return {
        'size_mm': [180, 62.5], 'viewbox': [W, H], 'grid': [X, Y, CW, RH],
        'font': 'Times New Roman', 'minimum_font_units': 31, 'body_font_unchanged_from_rev3': True,
        'colors': {'ink': INK, 'canvas': '#ffffff', 'discrete_cell_fills': PALETTE,
                   'top_bottom_rule': '#666666', 'header_rule': '#B9C0C8', 'cell_separator': '#ffffff'},
        'cell_contrast_by_value': {v: (luminance(c)+.05)/(luminance(INK)+.05) for v,c in PALETTE.items()},
        'cell_contrast_min': min((luminance(c)+.05)/(luminance(INK)+.05) for c in PALETTE.values()),
        'encoding': {'9/9': 'pale green', '6/9': 'pale blue', '0/9': 'no fill (white page shows through)'},
        'encoding_note': 'Exact dictionary lookup for three values; no proportional interpolation.',
        'traditional_heatmap': False, 'continuous_scale': False, 'colorbar': False,
        'figure_legend': True, 'legend_location': 'Existing title row, right aligned',
        'legend_height_added_mm': 0, 'summary_row': False, 'title_lines': 1,
        'horizontal_table_rules': 3, 'white_cell_separators': 18, 'separator_stroke_units': 1.5,
        'row_grouping': False, 'tinted_cells': 66, 'unfilled_zero_cells': 18,
        'cell_fill_counts': {v: sum(c['display']==v for c in cells) for v in PALETTE},
        'full_app_emphasis': 'Bold column header only; cell fills use the same mapping as every other column.',
    }



def main():
    cells, aliases, data, old = saved_data()
    layout = draw(cells, aliases)
    dump(HERE / 'layout_rev4.json', layout)
    dump(HERE / 'CHECK.json', {'revision': 'rev4', 'data': data, 'layout': layout,
         'previous_revision': {'revision': 'rev3', 'committed': False,
                               'base_commit': 'e8c01e469400dab0065c173b7448a96d9ec127ee',
                               'check': 'rev3_snapshot/CHECK.json', 'layout': old['layout']},
         'visual_review': {'status': 'PENDING'}})
    node = os.environ.get('RBA_NODE', str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'))
    subprocess.run([node, str(HERE / 'render_rev4.cjs')], check=True, cwd=HERE)
    subprocess.run([sys.executable, '-B', str(HERE / 'check_rev4.py')], check=True, cwd=HERE)


if __name__ == '__main__':
    main()
