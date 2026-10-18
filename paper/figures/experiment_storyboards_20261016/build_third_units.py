"""Experiment 03: equal-area unit charts from saved summaries only."""
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
from matplotlib.patches import Rectangle

font_manager.fontManager.addfont('/System/Library/Fonts/STHeiti Medium.ttc')
plt.rcParams.update({'font.family': 'Heiti TC', 'font.size': 12,
                     'svg.fonttype': 'none', 'figure.facecolor': 'white',
                     'savefig.facecolor': 'white', 'hatch.linewidth': .8})
SOURCES = {
    'mtc': 'deliverables/app177_core_ablation_v1/results/summary/mtc.json',
    'main': 'deliverables/app177_core_ablation_v1/results/summary/main.json',
}
saved = {k: json.loads((ROOT / p).read_text()) for k, p in SOURCES.items()}

def one(rows, **keys):
    matches = [r for r in rows if all(r.get(k) == v for k, v in keys.items())]
    assert len(matches) == 1, keys
    r = matches[0]
    assert r['N'] == sum(r[k] for k in ('T', 'F', 'U', 'FAILED', 'EMPTY_MODEL'))
    assert r['FAILED'] == r['EMPTY_MODEL'] == 0
    return r

specs = [('APP_FULL', ['01', '02']), ('APP_FULL', ['03']),
         ('A_NO_MTC_CAP', ['01', '02', '03'])]
cohorts = [('development', '历史评价', 144, 12, 12),
           ('reserved_validation', '历史保留评价', 117, 13, 9)]
panels = []
for subset, label, n, cols, rows in cohorts:
    for scheme, folds in specs:
        members = [one(saved['mtc'], scheme=scheme,
                       fold_id='WEBGL1-LOEO-v1-' + f, subset=subset) for f in folds]
        fields = ('N', 'T', 'F', 'U', 'FAILED', 'EMPTY_MODEL', 'defined')
        assert len({tuple(r[k] for k in fields) for r in members}) == 1
        r = members[0]
        assert r['N'] == n == cols * rows
        panels.append({'subset': subset, 'label': label, 'scheme': scheme,
                       'configurations': folds, 'cols': cols, 'rows': rows,
                       **{k: r[k] for k in fields}, 'source_rows': members})

assert [(r['T'], r['F'], r['U']) for r in panels] == [
    (1, 135, 8), (0, 136, 8), (144, 0, 0),
    (1, 110, 6), (0, 111, 6), (117, 0, 0)]
attacks = [one(saved['main'], scheme=s, identity='EFFECTIVE_INTERVENTION')
           for s in ('APP_FULL', 'A_NO_MTC_CAP')]
normals = [one(saved['main'], scheme=s, identity='NORMAL')
           for s in ('APP_FULL', 'A_NO_MTC_CAP')]
assert [(r['T'], r['N']) for r in attacks] == [(105, 126), (108, 126)]
assert all(r['N'] == 252 and r['T'] == r['U'] == 0 for r in normals)
training = [one(saved['mtc'], scheme=s, fold_id='WEBGL1-LOEO-v1-' + f,
                subset='discovery')
            for s in ('APP_FULL', 'A_NO_MTC_CAP') for f in ('01', '02', '03')]
assert [r['T'] for r in training] == [6, 6, 0, 630, 630, 630]
assert [r['U'] for r in training] == [51, 51, 51, 0, 0, 0]

W, H = 12.6, 8.6
fig = plt.figure(figsize=(W, H))
ax = fig.add_axes([0, 0, 1, 1])
ax.set(xlim=(0, W), ylim=(0, H))
ax.axis('off')
INK, MUTED = '#22313B', '#53636D'
STYLES = {
    'T': dict(facecolor='#AF3E35', edgecolor='#922D26', linewidth=.65),
    'F': dict(facecolor='#E1E6EA', edgecolor='#B4BEC6', linewidth=.45),
    'U': dict(facecolor='#F6DF99', edgecolor='#9B751C', linewidth=.65, hatch='///'),
}

def text(x, y, s, size=12, color=INK, ha='left', **kw):
    return ax.text(x, y, s, fontsize=size, color=color,
                   ha=ha, va='center', **kw)

text(.42, 8.18, '03　取消正常报警上限：多检出3次，历史正常却全部报警', 19)
text(.42, 7.71, '受控修改检出 105/126 → 108/126；受控正常报警均为 0/252。', 12.5)
text(.42, 7.24, '每格 = 1条正常记录', 11)
for x, state, label in [(3.10, 'T', '报警'), (4.53, 'F', '未报'), (5.96, 'U', '未知')]:
    ax.add_patch(Rectangle((x, 7.16), .15, .15, **STYLES[state]))
    text(x + .24, 7.24, label, 11)

starts = [2.66, 6.03, 9.40]
centers = [x + 1.01 for x in starts]
for cx, (label, folds) in zip(centers, [
        ('保留上限', '配置01、02'), ('保留上限', '配置03'),
        ('取消上限', '配置01、02、03')]):
    text(cx, 6.76, label, 15, ha='center')
    text(cx, 6.42, folds, 10.5, color=MUTED, ha='center')

pitch, side = .17, .145  # Identical physical area in every panel.
for row_index, (_, label, n, cols, rows) in enumerate(cohorts):
    top = [6.12, 3.30][row_index]
    cy = top - (rows * pitch) / 2
    text(.42, cy + .16, label, 13)
    text(.42, cy - .17, f'{n}条正常记录', 11, color=MUTED)
    for col_index in range(3):
        p = panels[row_index * 3 + col_index]
        x0 = starts[col_index]
        # Order is an illustrative count layout, never record-level matching.
        states = ['T'] * p['T'] + ['F'] * p['F'] + ['U'] * p['U']
        assert len(states) == p['N']
        for i, state in enumerate(states):
            x = x0 + (i % cols) * pitch
            y = top - (i // cols + 1) * pitch
            ax.add_patch(Rectangle((x, y), side, side, **STYLES[state]))
        bottom = top - rows * pitch
        center = x0 + (cols * pitch - (pitch - side)) / 2
        text(center, bottom - .24, f"报警 {p['T']} / {p['N']}", 13,
             color=STYLES['T']['facecolor'], ha='center')
        text(center, bottom - .53, f"未报 {p['F']}　·　未知 {p['U']}", 10.5,
             color=MUTED, ha='center')

notes = [
    '注：方格仅表示计数，位置不代表记录顺序或逐条对应；合并配置仅因所列计数相同，各配置不合并分母。',
    '144条与117条均为历史评价材料，并非新的独立盲测；失败和空模型均为0，未知未计为未报。',
    '630条约束训练记录另计：保留上限三配置报警6/6/0条、各51条未知；取消上限均为630条报警。',
]
for y, note in zip([.82, .49, .16], notes):
    text(.42, y, note, 9.4, color=MUTED)

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
    fig.savefig(OUT / f'03_normal_constraint_units.{ext}', dpi=180)
plt.close(fig)
(OUT / '03_units_data.json').write_text(json.dumps({
    'sources': SOURCES, 'panels': panels, 'controlled_interventions': attacks,
    'controlled_normals': normals, 'constraint_training': training,
    'layout_is_record_alignment': False,
}, ensure_ascii=False, indent=2) + '\n')
with (OUT / '03_units_data.csv').open('w', newline='') as f:
    fields = ['subset', 'scheme', 'configurations', 'N', 'T', 'F', 'U', 'FAILED', 'EMPTY_MODEL']
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for p in panels:
        writer.writerow({k: ','.join(p[k]) if k == 'configurations' else p[k] for k in fields})
(OUT / '03_UNITS_CHECK.json').write_text(json.dumps({
    'saved_sources_only': True, 'new_experiment_calls': 0,
    'source_counts_verified': True, 'equal_unit_area': True,
    'one_unit_per_record': True, 'panel_records': [p['N'] for p in panels],
    'grouping_uses_equal_counts_only': True, 'text_within_canvas': True,
    'visual_review': 'PENDING',
    'paper_scale_review': 'NOT_PERFORMED_DISCUSSION_DRAFT_ONLY',
}, ensure_ascii=False, indent=2) + '\n')
print('Rendered only experiment 03: six equal-area unit charts from saved counts.')
