"""Render only experiment 03 as a monochrome comparison table, from saved results."""
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
SOURCES = {name: f'deliverables/app177_core_ablation_v1/results/summary/{name}.json'
           for name in ('mtc', 'main')}
saved = {name: json.loads((ROOT / path).read_text()) for name, path in SOURCES.items()}
FIELDS = ('N', 'T', 'F', 'U', 'FAILED', 'EMPTY_MODEL', 'defined')

def one(name, **keys):
    hits = [r for r in saved[name] if all(r.get(k) == v for k, v in keys.items())]
    assert len(hits) == 1, keys
    r = hits[0]
    assert r['N'] == sum(r[k] for k in ('T', 'F', 'U', 'FAILED', 'EMPTY_MODEL'))
    assert r['FAILED'] == r['EMPTY_MODEL'] == 0
    return r

def grouped(subset, scheme, folds):
    rows = [one('mtc', subset=subset, scheme=scheme,
                fold_id='WEBGL1-LOEO-v1-' + fold) for fold in folds]
    assert len({tuple(r[k] for k in FIELDS) for r in rows}) == 1
    return {'configurations': folds, 'scheme': scheme,
            **{k: rows[0][k] for k in FIELDS}, 'source_rows': rows}

groups = []
for subset, label, n in [('development', '历史评价', 144),
                         ('reserved_validation', '历史保留评价', 117)]:
    cap = [grouped(subset, 'APP_FULL', ['01', '02']),
           grouped(subset, 'APP_FULL', ['03'])]
    no_cap = grouped(subset, 'A_NO_MTC_CAP', ['01', '02', '03'])
    assert all(r['N'] == n for r in cap + [no_cap])
    groups.append({'subset': subset, 'label': label, 'N': n,
                   'with_cap': cap, 'without_cap': no_cap})
assert [[tuple(r[k] for k in ('T', 'F', 'U')) for r in g['with_cap']] for g in groups] == [
    [(1, 135, 8), (0, 136, 8)], [(1, 110, 6), (0, 111, 6)]]
assert [tuple(g['without_cap'][k] for k in ('T', 'F', 'U')) for g in groups] == [
    (144, 0, 0), (117, 0, 0)]
attacks = [one('main', scheme=s, identity='EFFECTIVE_INTERVENTION')
           for s in ('APP_FULL', 'A_NO_MTC_CAP')]
normals = [one('main', scheme=s, identity='NORMAL')
           for s in ('APP_FULL', 'A_NO_MTC_CAP')]
assert [(r['T'], r['N'], r['U']) for r in attacks] == [(105, 126, 0), (108, 126, 0)]
assert all(r['N'] == 252 and r['T'] == r['U'] == 0 for r in normals)
training = [one('mtc', subset='discovery', scheme=s, fold_id='WEBGL1-LOEO-v1-' + f)
            for s in ('APP_FULL', 'A_NO_MTC_CAP') for f in ('01', '02', '03')]
assert [(r['T'], r['U'], r['N']) for r in training] == [
    (6, 51, 630), (6, 51, 630), (0, 51, 630),
    (630, 0, 630), (630, 0, 630), (630, 0, 630)]

fig = plt.figure(figsize=(11.7, 5.2))
ax = fig.add_axes([0, 0, 1, 1])
ax.set(xlim=(0, 1), ylim=(0, 1))
ax.axis('off')

def text(x, y, s, size=12, ha='center', bold=False, numeric=False):
    kw = {'fontfamily': 'DejaVu Sans'} if numeric else {}
    return ax.text(x, y, s, fontsize=size, color='black', ha=ha, va='center',
                   fontweight='bold' if bold else 'normal', **kw)

def line(y, x0=.035, x1=.965, lw=.8):
    ax.plot([x0, x1], [y, y], color='black', lw=lw)

text(.035, .947, '表3　MTC正常报警上限的作用', 16, ha='left')
line(.881, lw=1.3)
text(.142, .808, '历史正常材料', 12)
text(.300, .808, '配置', 12)
text(.495, .837, '保留报警上限', 13)
text(.830, .837, '取消报警上限', 13)
line(.801, .380, .610, .6)
line(.801, .715, .945, .6)
left_xs, right_xs = [.395, .495, .595], [.730, .830, .930]
for xs in (left_xs, right_xs):
    for x, label in zip(xs, ['报警 ↓', '未报', '未知']):
        text(x, .762, label, 11)
line(.719, lw=.8)

for group, ys in zip(groups, [(.653, .558), (.416, .321)]):
    cy = sum(ys) / 2
    text(.142, cy + .024, group['label'], 12)
    text(.142, cy - .028, f"N = {group['N']}", 11, numeric=True)
    for r, y in zip(group['with_cap'], ys):
        text(.300, y, '、'.join(r['configurations']), 11)
        for x, key in zip(left_xs, ('T', 'F', 'U')):
            text(x, y, str(r[key]), 13, bold=key == 'T', numeric=True)
    for x, key in zip(right_xs, ('T', 'F', 'U')):
        text(x, cy, str(group['without_cap'][key]), 13, bold=key == 'T', numeric=True)
line(.489, lw=.45)
line(.255, lw=1.3)

notes = [
    '取消上限后：受控修改检出由105/126增至108/126（仅+3）；受控正常报警均为0/252。',
    '注：数值均为正常记录数。相同计数合并展示；三个配置分别作用于同批记录，不合并分母。',
    '两批均为历史评价材料，并非新的独立盲测；未知单列，失败与空模型均为0。',
    '630条约束训练记录另计：保留上限报警6/6/0条、各51条未知；取消上限三配置均全部报警。',
]
for y, note in zip([.204, .151, .098, .045], notes):
    text(.035, y, note, 10 if y == .204 else 9.4, ha='left')

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
    fig.savefig(OUT / f'03_normal_constraint_table.{ext}', dpi=180)
plt.close(fig)
(OUT / '03_table_data.json').write_text(json.dumps({
    'sources': SOURCES, 'groups': groups, 'controlled_interventions': attacks,
    'controlled_normals': normals, 'constraint_training': training,
    'merged_counts_imply_equal_record_states': False,
}, ensure_ascii=False, indent=2) + '\n')
with (OUT / '03_table_data.csv').open('w', newline='') as f:
    keys = ['subset', 'scheme', 'configurations', *FIELDS]
    writer = csv.DictWriter(f, fieldnames=keys)
    writer.writeheader()
    for g in groups:
        for r in g['with_cap'] + [g['without_cap']]:
            writer.writerow({'subset': g['subset'], 'scheme': r['scheme'],
                             'configurations': ','.join(r['configurations']),
                             **{k: r[k] for k in FIELDS}})
(OUT / '03_TABLE_CHECK.json').write_text(json.dumps({
    'saved_sources_only': True, 'new_experiment_calls': 0,
    'source_counts_verified': True, 'same_count_groups_verified': True,
    'rows': 4, 'columns': 8, 'text_within_canvas': True,
    'visual_review': 'PENDING',
    'paper_scale_review': 'NOT_PERFORMED_DISCUSSION_DRAFT_ONLY',
}, ensure_ascii=False, indent=2) + '\n')
print('Rendered only experiment 03 as a monochrome table: 4 rows, 8 columns.')
