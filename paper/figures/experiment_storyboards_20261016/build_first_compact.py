"""Compact first discussion figure only; no import of the four-figure entrypoint."""
import csv
import json
import os
from collections import OrderedDict
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
plt.rcParams.update({'font.family':'Heiti TC','font.size':12,'axes.unicode_minus':False,
                     'svg.fonttype':'none','figure.facecolor':'white','savefig.facecolor':'white'})
C={'ink':'#24323D','muted':'#586775','blue':'#35648C','red':'#B85045',
   'green':'#287B65','gray':'#F1F4F6','loss':'#F6E5E1','gain':'#E0F1E9','line':'#DCE2E7'}
METHODS=['APP_FULL','A_NO_MTC_CAP','A_APP_WEB_ONLY','A_NO_MEMORY_REL','A_NO_TIMEZONE_REL','APP_TREE']
LABELS=['完整App','去MTC\n报警上限','仅App网页','去内存关系','去时区关系','App小树']
STATES=['N','T','F','U','FAILED','EMPTY_MODEL']

def read(rel):
    rows=list(csv.DictReader((ROOT/rel).open()))
    for i,r in enumerate(rows,2):
        r['_csv_line']=i
        for k in STATES:r[k]=int(r[k])
        assert r['N']==sum(r[k] for k in STATES[1:])
    return rows

rows=read('paper/figures/round1_app/data/F01.csv')
totals=read('paper/figures/round1_app/data/T02.csv')
assert len(rows)==84
by={(r['configuration'],r['scheme']):r for r in rows}
assert len(by)==84
configs=[r['configuration'] for r in rows if r['scheme']=='APP_FULL']
groups=OrderedDict()
for cfg in configs:
    signature=tuple(tuple(by[cfg,m][k] for k in STATES) for m in METHODS)
    assert all(s[0]==9 and s[3:]==(0,0,0) for s in signature)
    groups.setdefault(signature,[]).append(cfg)
assert len(groups)==5 and sum(map(len,groups.values()))==14

# Arrange by explanatory role, not by ranking methods or selecting best outcomes.
anchors=[
 ('w9-rule-boundary-cdp-resource-pair-v1','CPU＋内存','网页单层、去内存关系\n均少检出9次'),
 ('w10-cdp-emulation-screen-metrics-only-v1','屏幕参数','去MTC上限多检出3次\n正常代价见图03'),
 ('w10-cdp-emulation-timezone-only-v1','时区、Plugins / MIME','小树每类少检出9次'),
 ('w6-tool-054-legacy-default-v1','共同检出配置*','8类配置，各方法均检出'),
 ('w9-rule-boundary-cdp-webdriver-only-v1','Webdriver、WebGL标识','2类配置，各方法均漏检'),
]
ordered=[]
for anchor,label,annotation in anchors:
    sig,members=next((sig,cs) for sig,cs in groups.items() if anchor in cs)
    ordered.append({'label':label,'annotation':annotation,'configuration_count':len(members),
                    'members':members,'states_by_method':dict(zip(METHODS,sig)),
                    'counts':[s[1] for s in sig]})
assert len({c for g in ordered for c in g['members']})==14
weighted=[sum(g['configuration_count']*g['counts'][j] for g in ordered) for j in range(6)]
saved=[next(r['T'] for r in totals if r['scheme']==m and r['identity']=='EFFECTIVE_INTERVENTION') for m in METHODS]
assert weighted==saved==[105,108,96,96,105,72]
for r in totals:
    if r['identity']=='NORMAL':assert r['N']==252 and r['T']==0

fig=plt.figure(figsize=(12.8,6.15))
fig.text(.035,.955,'内存参照补充资源检出，两类修改仍全部漏检',fontsize=20,color=C['ink'],va='top')
fig.text(.035,.882,'14类配置合并为5组；格内为每类配置的检出数，每类均有9次有效修改。',fontsize=12,color=C['muted'],va='top')
ax=fig.add_axes([.035,.29,.93,.50])
ax.set_xlim(-3.25,8.55);ax.set_ylim(-1.9,5.15);ax.invert_yaxis();ax.axis('off')

def text(x,y,s,fs=12,**kw):
    ax.text(x,y,s,fontsize=fs,color=kw.pop('color',C['ink']),ha=kw.pop('ha','center'),va='center',**kw)

text(-3.2,-1.1,'修改配置组',ha='left')
text(-.48,-1.1,'配置数',fs=11)
text(-3.2,-.48,'总检出（126次修改）',fs=11,ha='left',color=C['muted'])
for j,(lbl,total) in enumerate(zip(LABELS,weighted)):
    text(j+.49,-1.33,lbl,12.2,fontweight='bold' if j==0 else 'normal')
    text(j+.49,-.48,f'{total}/126',12,color=C['blue'] if j==0 else C['muted'])
for i,g in enumerate(ordered):
    text(-3.2,i+.47,g['label'],11.8,ha='left')
    text(-.48,i+.47,str(g['configuration_count']),12.5)
    vals=g['counts'];baseline=vals[0];spans=[];start=0
    # Only merge adjacent method cells with identical complete state vectors.
    signatures=list(g['states_by_method'].values())
    while start<6:
        end=start+1
        while end<6 and signatures[end]==signatures[start]:end+=1
        value=vals[start];delta=value-baseline
        color=C['gain'] if delta>0 else C['loss'] if delta<0 else C['gray']
        ax.add_patch(Rectangle((start,i+.04),end-start-.045,.84,facecolor=color,edgecolor='none'))
        s=str(value)
        if delta:s+=f'  ({delta:+d})'
        if end-start==6:s+='  全部检出' if value==9 else '  均未检出'
        text((start+end-.045)/2,i+.46,s,13.5)
        spans.append({'method_start':start,'method_end_exclusive':end,'T':value,'delta_vs_full':delta})
        start=end
    g['merged_cells']=spans
    text(6.25,i+.47,g['annotation'],11,ha='left',color=C['red'] if i==4 else C['ink'],linespacing=1.4)

fig.text(.035,.228,'灰：与完整App检出数相同    绿：更多    红：更少    括号：每类配置相对完整App的检出差值',fontsize=10.5,color=C['muted'])
fig.text(.035,.172,'横向合并表示相邻方法结果相同；配置数是组内原配置数量。总计仍按14类配置加权，分母为126。',fontsize=10.5,color=C['muted'])
fig.text(.035,.116,'* 8类：Playwright、Puppeteer、CDP多字段、Stealth四种预设，以及平台、UA、UA＋平台、语言列表。',fontsize=10.5,color=C['muted'])
fig.text(.035,.060,'受控正常：全部方法均0/252报警；未知/失败/空模型均0。规则取RETENTION，小树取FITTED。',fontsize=10.5,color=C['muted'])

fig.canvas.draw()
renderer=fig.canvas.get_renderer()
outside=[]
for obj in fig.findobj(match=matplotlib.text.Text):
    if not obj.get_visible() or not obj.get_text():continue
    bb=obj.get_window_extent(renderer)
    if bb.x0<0 or bb.y0<0 or bb.x1>fig.bbox.width or bb.y1>fig.bbox.height:outside.append(obj.get_text())
assert not outside,outside
for ext in ('png','svg'):fig.savefig(OUT/f'01_app_contribution_compact.{ext}',dpi=180)
plt.close(fig)
(OUT/'01_compact_groups.json').write_text(json.dumps({'grouping_keys':STATES,'methods':METHODS,
    'grouping_rule':'Equal full six-method state vectors; descriptive compression only.',
    'source':'paper/figures/round1_app/data/F01.csv','groups':ordered,
    'weighted_totals':dict(zip(METHODS,weighted))},ensure_ascii=False,indent=2)+'\n')
(OUT/'01_COMPACT_CHECK.json').write_text(json.dumps({'saved_sources_only':True,'new_experiment_calls':0,
    'source_configurations':14,'source_cells':84,'display_groups':5,'display_value_cells':sum(len(g['merged_cells']) for g in ordered),
    'all_configurations_retained':True,'totals_match_saved_results':True,'text_within_canvas':True,
    'visual_review':'PENDING','paper_scale_review':'NOT_PERFORMED_DISCUSSION_DRAFT_ONLY'},ensure_ascii=False,indent=2)+'\n')
print('Grouped 14 configurations into 5 rows and',sum(len(g['merged_cells']) for g in ordered),'merged value cells.')
