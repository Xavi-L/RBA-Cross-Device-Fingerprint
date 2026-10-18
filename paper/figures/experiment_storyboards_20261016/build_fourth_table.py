"""Experiment 04 grouped comparison table; render saved results only."""
import csv
import json
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
os.environ.setdefault('MPLCONFIGDIR', '/tmp/hybridguard-storyboard-mpl')
os.environ.setdefault('XDG_CACHE_HOME', '/tmp/hybridguard-storyboard-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

font_manager.fontManager.addfont('/System/Library/Fonts/STHeiti Medium.ttc')
plt.rcParams.update({'font.family': 'Heiti TC', 'font.size': 12,
                     'svg.fonttype': 'none', 'figure.facecolor': 'white',
                     'savefig.facecolor': 'white'})
SOURCES = {
    'paired': 'paper/figures/round2_paired/data/F05a.csv',
    'app_historical': 'paper/figures/round1_app/data/F02.csv',
    'paired_historical': 'deliverables/app_browser_evidence_consolidation_v1/tables.json',
}
FIELDS = ('N', 'T', 'F', 'U', 'FAILED', 'defined')

def read_csv(rel):
    rows = list(csv.DictReader((ROOT / rel).open()))
    for line, r in enumerate(rows, 2):
        r['_csv_line'] = line
        for k in (*FIELDS, 'EMPTY_MODEL'):
            if k in r:
                r[k] = int(r[k])
        assert r['N'] == r['T'] + r['F'] + r['U'] + r['FAILED'] + r.get('EMPTY_MODEL', 0)
    return rows

def one(rows, **keys):
    hits = [r for r in rows if all(r.get(k) == v for k, v in keys.items())]
    assert len(hits) == 1, keys
    return hits[0]

paired = read_csv(SOURCES['paired'])
app_mtc = read_csv(SOURCES['app_historical'])
tables = json.loads((ROOT / SOURCES['paired_historical']).read_text())
families = ['App_timezone', 'App_language', 'Browser_timezone', 'Browser_language']
methods = [('APP_FULL', '完整App'), ('PAIRED_BASE', '完整App + 跨端时区C1')]
rows = []
for method, label in methods:
    common = []
    for family in families + ['NORMAL']:
        source = [one(paired, method=method, family=family, configuration=f)
                  for f in ('01', '02', '03')]
        assert len({tuple(r[k] for k in FIELDS) for r in source}) == 1
        assert all(r['U'] == r['FAILED'] == 0 for r in source)
        common.append({'family': family, **{k: source[0][k] for k in FIELDS},
                       'source_rows': source})
    totals = {k: sum(r[k] for r in common[:4]) for k in FIELDS}
    rows.append({'method': method, 'label': label, 'families': common[:4],
                 'total_modifications': totals, 'normal': common[4]})
assert [[(r['T'], r['N']) for r in row['families']] for row in rows] == [
    [(2, 2), (0, 2), (0, 5), (0, 5)], [(2, 2), (0, 2), (5, 5), (0, 5)]]
assert [(r['total_modifications']['T'], r['total_modifications']['N']) for r in rows] == [(2, 14), (7, 14)]
assert all(r['normal']['N'] == 46 and r['normal']['T'] == 0 for r in rows)
display_rows = [r['families'] + [r['total_modifications'], r['normal']] for r in rows]
deltas = [new['T'] - old['T'] for old, new in zip(*display_rows)]
assert deltas == [0, 0, 5, 0, 5, 0]

historical = []
for fold in ('01', '02', '03'):
    fid = 'WEBGL1-LOEO-v1-' + fold
    old = one(app_mtc, scheme='APP_FULL', fold_id=fid)
    split = [r for r in tables['historical_mtc'] if r['set_id'] == 'S0' and r['fold'] == fid]
    assert sorted(r['n'] for r in split) == [117, 144]
    new = {'N': sum(r['n'] for r in split),
           **{k: sum(r[k] for r in split) for k in ('T', 'F', 'U', 'FAILED', 'defined')}}
    assert old['N'] == new['N'] == 261
    assert old['T'] == new['T'] == (0 if fold == '03' else 2)
    assert old['U'] == 14 and new['U'] == 17
    assert old['FAILED'] == new['FAILED'] == 0
    historical.append({'configuration': fold, 'app': old, 'paired': new,
                       'paired_original_groups': split})

fig = plt.figure(figsize=(12.2, 4.8))
ax = fig.add_axes([0, 0, 1, 1])
ax.set(xlim=(0, 1), ylim=(0, 1))
ax.axis('off')

def text(x, y, s, size=12, ha='center', bold=False, numeric=False):
    kw = {'fontfamily': 'DejaVu Sans'} if numeric else {}
    return ax.text(x, y, s, fontsize=size, color='black', ha=ha, va='center',
                   fontweight='bold' if bold else 'normal', **kw)

def line(y, x0=.035, x1=.965, lw=.8):
    ax.plot([x0, x1], [y, y], color='black', lw=lw)

text(.035, .941, '表4　跨端时区关系的分类型检出增益', 16, ha='left')
line(.867, lw=1.3)
text(.035, .788, '方法', 12, ha='left')
text(.3975, .826, 'App侧修改', 12)
text(.6125, .826, '独立Browser侧修改', 12)
line(.791, .315, .480, .6)
line(.791, .530, .695, .6)
xs = [.345, .450, .560, .665, .795, .925]
for x, label in zip(xs[:4], ['时区', '语言', '时区', '语言']):
    text(x, .748, label, 11)
text(xs[4], .788, '总检出 ↑', 12)
text(xs[5], .788, '正常报警 ↓', 12)
line(.701, lw=.8)

for row, values, y in zip(rows, display_rows, [.635, .528]):
    text(.035, y, row['label'], 11.5, ha='left')
    for index, (x, r) in enumerate(zip(xs, values)):
        changed = row['method'] == 'PAIRED_BASE' and deltas[index] != 0
        text(x, y, f"{r['T']}/{r['N']}", 13, bold=changed, numeric=True)
line(.470, lw=.45)
text(.035, .412, '增加条数', 11.5, ha='left')
for x, value in zip(xs, deltas):
    text(x, .412, f'+{value}' if value else '0', 13, bold=value != 0, numeric=True)
line(.350, lw=1.3)

notes = [
    '新增5次检出全部来自Browser时区；App时区检出保留，两端语言修改仍未检出。',
    '注：前两行为检出数/修改数或报警数/正常数；末行为计数差。C1为跨端时区关系。',
    '本批60条已用于开发：14次修改、46条正常，未知与失败均为0；三配置计数相同，合并展示但不叠加样本。',
    '历史MTC 261条（144+117）：各配置报警数不变，未知由14增至17；本图不是新的独立盲测。',
]
for y, note in zip([.286, .217, .148, .079], notes):
    text(.035, y, note, 10 if y == .286 else 9.2, ha='left')

fig.canvas.draw()
renderer = fig.canvas.get_renderer()
outside = []
for item in fig.findobj(match=matplotlib.text.Text):
    if not item.get_visible() or not item.get_text():
        continue
    b = item.get_window_extent(renderer)
    if b.x0 < 0 or b.y0 < 0 or b.x1 > fig.bbox.width or b.y1 > fig.bbox.height:
        outside.append(item.get_text())
assert not outside, outside
for ext in ('png', 'svg'):
    fig.savefig(OUT / f'04_cross_endpoint_table.{ext}', dpi=180)
plt.close(fig)
(OUT / '04_table_data.json').write_text(json.dumps({
    'sources': SOURCES, 'rows': rows, 'delta_counts': dict(zip(families + ['TOTAL', 'NORMAL'], deltas)),
    'historical_normal_context': historical, 'configuration_count_multiplier': 1,
    'merged_counts_imply_equal_record_states': False,
}, ensure_ascii=False, indent=2) + '\n')
with (OUT / '04_table_data.csv').open('w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['method', 'configurations', 'family', *FIELDS])
    writer.writeheader()
    for row in rows:
        for family, r in zip(families + ['TOTAL', 'NORMAL'], row['families'] + [row['total_modifications'], row['normal']]):
            writer.writerow({'method': row['method'], 'configurations': '01,02,03',
                             'family': family, **{k: r[k] for k in FIELDS}})
(OUT / '04_TABLE_CHECK.json').write_text(json.dumps({
    'saved_sources_only': True, 'new_experiment_calls': 0,
    'source_counts_verified': True, 'three_configuration_counts_match': True,
    'historical_unknown_increase_preserved': True, 'normal_denominator': 46,
    'display_method_rows': 2, 'delta_rows': 1, 'columns': 7,
    'text_within_canvas': True, 'visual_review': 'PENDING',
    'paper_scale_review': 'NOT_PERFORMED_DISCUSSION_DRAFT_ONLY',
}, ensure_ascii=False, indent=2) + '\n')
print('Rendered only experiment 04: grouped comparison table, 2 method rows plus count changes.')
