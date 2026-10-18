"""A monochrome academic table for experiment 02; only reads saved results."""
import json
import os
from pathlib import Path

OUT=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR','/tmp/hybridguard-storyboard-mpl')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/hybridguard-storyboard-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

font_manager.fontManager.addfont('/System/Library/Fonts/STHeiti Medium.ttc')
plt.rcParams.update({'font.family':'Heiti TC','font.size':12,'svg.fonttype':'none',
                    'figure.facecolor':'white','savefig.facecolor':'white'})
data=json.loads((OUT/'02_clear_data.json').read_text())
labels=[['网页内存 > 8 GiB','系统内存上界'],['绝对时区偏移','系统时区参照'],['固定网页高度','宿主几何上界']]
groups=[]
for source,names in zip(data['rows'],labels):
    rows=[]
    for i,name in enumerate(names):
        attack,normal=source['attack'][i],source['normal'][i]
        for r in (attack,normal):
            assert r['N']==r['T']+r['F']+r['U']+r['FAILED']
            assert r['U']==r['FAILED']==0
        rows.append({'condition':name,'condition_id':source['condition_ids'][i],
                     'reference':i==1,'detected':attack['T'],'false_alarms':normal['T']})
    if source['name']=='屏幕':
        other=data['screen_same_web_comparison']
        assert other['attack']['N']==6 and other['normal']['N']==66
        rows.insert(1,{'condition':'同网页视口关系','condition_id':'R_SAME_WEB','reference':False,
                       'detected':other['attack']['T'],'false_alarms':other['normal']['T']})
    groups.append({'specialist':source['name'],'attack_N':source['attack'][0]['N'],
                   'normal_N':source['normal'][0]['N'],'rows':rows})
assert [(g['attack_N'],g['normal_N']) for g in groups]==[(18,48),(6,30),(6,66)]
assert [(r['detected'],r['false_alarms']) for g in groups for r in g['rows']]==[(6,0),(18,0),(6,6),(6,0),(6,6),(0,0),(6,0)]

fig=plt.figure(figsize=(10.8,5.5))
ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
def text(x,y,s,size=12,bold=False,ha='left'):
    return ax.text(x,y,s,fontsize=size,color='black',ha=ha,va='center',fontweight='bold' if bold else 'normal')
def line(y,width=1):ax.plot([.035,.965],[y,y],color='black',lw=width)

text(.035,.934,'表2　设备参照与对照条件的专项结果',16)
line(.856,1.3)
text(.153,.812,'专项与样本量',12,ha='center')
text(.360,.812,'单条检查条件',12)
text(.735,.812,'修改检出数 ↑',12,ha='center')
text(.910,.812,'正常误报数 ↓',12,ha='center')
line(.771,.8)
centers=[(.714,.644),(.544,.474),(.374,.304,.234)]
for group,ys in zip(groups,centers):
    cy=sum(ys)/len(ys)
    text(.153,cy+.022,group['specialist'],13,ha='center')
    text(.153,cy-.022,f"有效修改 {group['attack_N']}；正常 {group['normal_N']}",10.6,ha='center')
    for row,y in zip(group['rows'],ys):
        text(.360,y,row['condition']+('*' if row['reference'] else ''),12)
        text(.735,y,str(row['detected']),13,ha='center')
        text(.910,y,str(row['false_alarms']),13,ha='center')
line(.594,.45);line(.424,.45);line(.183,1.3)
text(.035,.137,'注：数值为记录计数；↑越多越好，↓越少越好。* 为设备参照条件。各专项分别比较，不合并分母。',9.6)
text(.035,.095,'内存另有6次无可观察效果的操作，两条件均未报警，未计入18次有效修改；表内未知与失败均为0。',9.6)
text(.035,.053,'宿主几何上界仍是独立专项条件，尚未接入完整App模型。',9.6)

fig.canvas.draw();renderer=fig.canvas.get_renderer();outside=[]
for item in fig.findobj(match=matplotlib.text.Text):
    if not item.get_visible() or not item.get_text():continue
    b=item.get_window_extent(renderer)
    if b.x0<0 or b.y0<0 or b.x1>fig.bbox.width or b.y1>fig.bbox.height:outside.append(item.get_text())
assert not outside,outside
for ext in ('png','svg'):fig.savefig(OUT/f'02_reference_mechanisms_table.{ext}',dpi=180)
plt.close(fig)
(OUT/'02_table_data.json').write_text(json.dumps({'source':'02_clear_data.json',
    'original_sources':data['sources'],'groups':groups},ensure_ascii=False,indent=2)+'\n')
(OUT/'02_TABLE_CHECK.json').write_text(json.dumps({'saved_sources_only':True,'new_experiment_calls':0,
    'rows':7,'columns':4,'source_counts_verified':True,'text_within_canvas':True,
    'visual_review':'PENDING','paper_scale_review':'NOT_PERFORMED_DISCUSSION_DRAFT_ONLY'},ensure_ascii=False,indent=2)+'\n')
print('Rendered only experiment 02 as a monochrome table: 7 rows, 4 columns.')
