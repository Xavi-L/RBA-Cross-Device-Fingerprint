"""Render only the simplified second figure from saved fixed-condition results."""
import csv
import json
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
os.environ.setdefault('MPLCONFIGDIR','/tmp/hybridguard-storyboard-mpl')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/hybridguard-storyboard-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle

font_manager.fontManager.addfont('/System/Library/Fonts/STHeiti Medium.ttc')
plt.rcParams.update({'font.family':'Heiti TC','font.size':12,'axes.unicode_minus':False,
                    'svg.fonttype':'none','figure.facecolor':'white','savefig.facecolor':'white'})
C={'ink':'#24323D','muted':'#586775','line':'#DCE2E7','blue':'#35648C',
   'green':'#287B65','lightgreen':'#E8F3EE','light':'#F4F6F8'}
M_PATH='paper/figures/round1_app/data/F03b.csv'
TZ_PATH='deliverables/timezone_relation_validation_v1/summary.json'
S_PATH='deliverables/screen_geometry_observation_v1/SUMMARY.json'
memory=list(csv.DictReader((ROOT/M_PATH).open()))
tz=json.loads((ROOT/TZ_PATH).read_text())['local']
screen=json.loads((ROOT/S_PATH).read_text())

def mem(scope,condition,target=None):
    hits=[r for r in memory if r['scope']==scope and r['condition']==condition
          and (target is None or r['target']==str(target))]
    assert len(hits)==1
    r=hits[0]
    return {k:int(r[k]) for k in ('N','T','F','U','FAILED')}

def local_tz(group,condition):
    r=tz[group]
    return {'N':r['positions'],**{s:r['conditions'][condition].get(s,0) for s in ('T','F','U','FAILED')}}

def local_screen(group,condition):
    r=screen[group]
    return {'N':r['n'],**{s:r['conditions'][condition][s] for s in ('T','F','U','FAILED')}}

rows=[
 {'name':'内存','comparison':'网页内存 > 8 GiB → 系统上界',
  'condition_ids':['R_WEB8','R_REL'],
  'attack':[mem('aggregate_observable_changes',c) for c in ('R_WEB8','R_REL')],
  'normal':[mem('aggregate_normal_phases',c) for c in ('R_WEB8','R_REL')],
  'source':M_PATH},
 {'name':'时区','comparison':'绝对偏移 → 系统时区参照',
  'condition_ids':['R_ABSOLUTE','R_TZ'],
  'attack':[local_tz('A_observable',c) for c in ('R_ABSOLUTE','R_TZ')],
  'normal':[local_tz('confirmed_normal',c) for c in ('R_ABSOLUTE','R_TZ')],
  'source':TZ_PATH},
 {'name':'屏幕','comparison':'固定高度 → 宿主几何上界',
  'condition_ids':['R_HEIGHT710','R_HOST_GEOMETRY'],
  'attack':[local_screen('observable_intervention',c) for c in ('R_HEIGHT710','R_HOST_GEOMETRY')],
  'normal':[local_screen('confirmed_normal',c) for c in ('R_HEIGHT710','R_HOST_GEOMETRY')],
  'source':S_PATH},
]
for r in rows:
    for kind in ('attack','normal'):
        assert r[kind][0]['N']==r[kind][1]['N']
        for s in r[kind]:
            assert s['N']==sum(s[k] for k in ('T','F','U','FAILED'))
            assert s['U']==s['FAILED']==0
assert [(r['attack'][0]['T'],r['attack'][1]['T'],r['attack'][0]['N']) for r in rows]==[(6,18,18),(6,6,6),(6,6,6)]
assert [(r['normal'][0]['T'],r['normal'][1]['T'],r['normal'][0]['N']) for r in rows]==[(0,0,48),(6,0,30),(6,0,66)]
for target in (4,8):
    assert mem('target','R_REL',target)['T']==6 and mem('target','R_WEB8',target)['T']==0
no_effect=[mem('aggregate_no_observable_effect',c) for c in ('R_WEB8','R_REL')]
assert all(r['N']==6 and r['T']==0 for r in no_effect)
same_web={'attack':local_screen('observable_intervention','R_SAME_WEB'),
          'normal':local_screen('confirmed_normal','R_SAME_WEB')}
assert same_web['attack']['N']==6 and same_web['attack']['T']==0
assert same_web['normal']['N']==66 and same_web['normal']['T']==0

fig=plt.figure(figsize=(12.3,6.35))
ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
def text(x,y,s,size=12,color=None,**kw):
    return ax.text(x,y,s,fontsize=size,color=color or C['ink'],va='center',**kw)

text(.035,.945,'设备参照的作用：补上漏检，减少误报',21)
text(.035,.886,'固定单条检查对照：每行比较“旧阈值条件 → 本机参照条件”，两列分别回答两个问题。',11.7,C['muted'])
text(.035,.800,'专项与比较条件',12,C['muted'])
text(.325,.813,'有效修改：有没有发现？',16,C['blue'])
text(.325,.772,'这一列只看检出',11,C['muted'])
text(.655,.813,'正常记录：有没有误报？',16,C['blue'])
text(.655,.772,'这一列只看误报',11,C['muted'])
ax.plot([.035,.965],[.745,.745],color=C['line'],lw=1)

for i,(y,row) in enumerate(zip((.657,.481,.305),rows)):
    text(.035,y+.029,row['name'],18)
    text(.035,y-.025,row['comparison'],11,C['muted'])
    for x,kind in ((.305,'attack'),(.635,'normal')):
        before,after=row[kind]
        improves=after['T']>before['T'] if kind=='attack' else after['T']<before['T']
        ax.add_patch(Rectangle((x,y-.061),.328,.133,facecolor=C['lightgreen'] if improves else C['light'],edgecolor='none'))
        color=C['green'] if improves else C['ink']
        if kind=='attack' and improves:
            headline='多发现12次修改'
            detail='检出 6/18 → 18/18；新增来自4、8 GiB'
        elif kind=='attack':
            headline='两种检查均全部发现'
            detail='同一批6次有效修改，均检出6次'
        elif before['T']==after['T']==0:
            headline='两种检查均无误报'
            detail=f"同一批{before['N']}条正常记录，均未报警"
        else:
            headline='减少6次误报'
            scenario='正常系统换时区' if i==1 else '正常扩大布局'
            detail=f"{before['N']}条正常中：{scenario}的6次误报 → 0"
        text(x+.018,y+.028,headline,17,color)
        text(x+.018,y-.025,detail,10.6,C['muted'])
    if i<2:ax.plot([.035,.965],[y-.088,y-.088],color=C['line'],lw=.65)

text(.035,.171,'补充对照：只比较网页内视口，虽然66条正常均未误报，但6次屏幕修改也全部漏检。',11,C['muted'])
text(.035,.116,'口径：各行使用不同专项数据，不合并为总体分数；另6次内存无效果操作均未报警，不计入18次有效修改。',10.4,C['muted'])
text(.035,.064,'边界：屏幕新几何条件尚未进入完整App模型；内存仅覆盖所测向上修改。以上未知与失败均为0。',10.4,C['muted'])

fig.canvas.draw();renderer=fig.canvas.get_renderer()
outside=[]
for item in fig.findobj(match=matplotlib.text.Text):
    if not item.get_visible() or not item.get_text():continue
    b=item.get_window_extent(renderer)
    if b.x0<0 or b.y0<0 or b.x1>fig.bbox.width or b.y1>fig.bbox.height:outside.append(item.get_text())
assert not outside,outside
for ext in ('png','svg'):fig.savefig(OUT/f'02_reference_mechanisms_clear.{ext}',dpi=180)
plt.close(fig)
(OUT/'02_clear_data.json').write_text(json.dumps({'rows':rows,'memory_no_effect':no_effect,
    'screen_same_web_comparison':same_web,'sources':[M_PATH,TZ_PATH,S_PATH]},ensure_ascii=False,indent=2)+'\n')
(OUT/'02_CLEAR_CHECK.json').write_text(json.dumps({'saved_sources_only':True,'new_experiment_calls':0,
    'attack_and_normal_columns_separate':True,'source_counts_verified':True,'text_within_canvas':True,
    'visual_review':'PENDING','paper_scale_review':'NOT_PERFORMED_DISCUSSION_DRAFT_ONLY'},ensure_ascii=False,indent=2)+'\n')
print('Rendered the second figure only: three comparisons, two fixed outcome columns.')
