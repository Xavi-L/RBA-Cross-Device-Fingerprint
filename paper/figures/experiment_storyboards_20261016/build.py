"""Four discussion drafts, rendered only from saved results. No experiment imports."""
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

FONT = '/System/Library/Fonts/STHeiti Medium.ttc'
font_manager.fontManager.addfont(FONT)
plt.rcParams.update({'font.family': font_manager.FontProperties(fname=FONT).get_name(),
                     'font.size': 12, 'axes.unicode_minus': False, 'svg.fonttype': 'none',
                     'figure.facecolor': 'white', 'savefig.facecolor': 'white'})
C = {'ink':'#24323D','muted':'#586775','line':'#DCE2E7','blue':'#35648C',
     'green':'#287B65','red':'#B85045','yellow':'#D2A447',
     'lightblue':'#E6EEF5','lightgreen':'#E0F1E9','lightred':'#F6E5E1',
     'light':'#F4F6F8','gray':'#BAC6D0'}
SOURCES = {}
CHECKS = []

def read_csv(rel):
    rows = list(csv.DictReader((ROOT / rel).open()))
    SOURCES[rel] = {'kind':'saved_csv', 'rows':len(rows)}
    for i, r in enumerate(rows, 2):
        r['_csv_line'] = i
        for k in ('N','T','F','U','FAILED','EMPTY_MODEL','defined'):
            if k in r:
                r[k] = int(r[k])
        if all(k in r for k in ('N','T','F','U','FAILED')):
            assert r['N'] == sum(r[k] for k in ('T','F','U','FAILED')) + r.get('EMPTY_MODEL', 0)
    return rows

def read_json(rel):
    SOURCES[rel] = {'kind':'saved_json'}
    return json.loads((ROOT / rel).read_text())

def one(rows, **keys):
    hits = [r for r in rows if all(r.get(k) == v for k,v in keys.items())]
    assert len(hits) == 1, (keys, len(hits))
    return hits[0]

def canvas(title, subtitle, size=(12.3,7.1)):
    fig = plt.figure(figsize=size)
    fig.text(.035,.955,title,fontsize=20,color=C['ink'],va='top')
    fig.text(.035,.897,subtitle,fontsize=11.5,color=C['muted'],va='top')
    return fig

def panel(fig, rect):
    ax=fig.add_axes(rect);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off');return ax

def t(ax,x,y,s,fs=12,**kw):
    return ax.text(x,y,s,fontsize=fs,color=kw.pop('color',C['ink']),va=kw.pop('va','center'),**kw)

def foot(fig, lines):
    fig.text(.035,.035,'\n'.join(lines),fontsize=10,color=C['muted'],va='bottom',linespacing=1.6)

def save(fig, name):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    outside=[]
    for obj in fig.findobj(match=matplotlib.text.Text):
        if not obj.get_visible() or not obj.get_text(): continue
        bb=obj.get_window_extent(renderer)
        if bb.x0 < -1 or bb.y0 < -1 or bb.x1 > fig.bbox.width+1 or bb.y1 > fig.bbox.height+1:
            outside.append(obj.get_text())
    assert not outside, (name, outside)
    for ext in ('png','svg'):
        fig.savefig(OUT / f'{name}.{ext}',dpi=180)
    CHECKS.append({'figure':name,'text_within_canvas':True})
    plt.close(fig)

F01 = read_csv('paper/figures/round1_app/data/F01.csv')
T02 = read_csv('paper/figures/round1_app/data/T02.csv')
F02 = read_csv('paper/figures/round1_app/data/F02.csv')
MEM = read_csv('paper/figures/round1_app/data/F03b.csv')
MTC = read_json('deliverables/app177_core_ablation_v1/results/summary/mtc.json')
TZ = read_json('deliverables/timezone_relation_validation_v1/summary.json')['local']
SCREEN = read_json('deliverables/screen_geometry_observation_v1/SUMMARY.json')
PAIR = read_csv('paper/figures/round2_paired/data/F05a.csv')
TABLES = read_json('deliverables/app_browser_evidence_consolidation_v1/tables.json')

# Validate the side notes against saved outputs as well as the visible chart cells.
for fold in ('01','02','03'):
    fid='WEBGL1-LOEO-v1-'+fold
    full=one(F02,scheme='APP_FULL',fold_id=fid)
    assert full['N']==261 and full['U']==14
    paired=[r for r in TABLES['historical_mtc'] if r['fold']==fid and r['set_id']=='S0']
    assert len(paired)==2 and sum(r['n'] for r in paired)==261
    assert sum(r['U'] for r in paired)==17
    discovery=one(MTC,scheme='APP_FULL',fold_id=fid,subset='discovery')
    assert discovery['N']==630 and discovery['U']==51
    assert discovery['T']==(0 if fold=='03' else 6)
    no_cap=one(MTC,scheme='A_NO_MTC_CAP',fold_id=fid,subset='discovery')
    assert no_cap['T']==no_cap['N']==630
    for method in ('APP_FULL','PAIRED_BASE'):
        normal=one(PAIR,method=method,configuration=fold,identity='NORMAL')
        assert normal['N']==46 and all(normal[k]==0 for k in ('T','U','FAILED'))
        attack=[r for r in PAIR if r['method']==method and r['configuration']==fold and r['identity']=='EFFECTIVE_INTERVENTION']
        assert sum(r['N'] for r in attack)==14
        assert sum(r['T'] for r in attack)==(2 if method=='APP_FULL' else 7)
        assert all(r['U']==r['FAILED']==0 for r in attack)
for cond in ('R_REL','R_WEB8'):
    for scope,n in (('aggregate_normal_phases',48),('aggregate_no_observable_effect',6)):
        r=one(MEM,condition=cond,scope=scope)
        assert r['N']==n and all(r[k]==0 for k in ('T','U','FAILED'))
CHECKS.append({'side_notes_verified_against_saved_sources':True,
               'three_configurations_kept_separate':True,'paired_display_compresses_equal_counts_only':True})

methods=['APP_FULL','A_NO_MTC_CAP','A_APP_WEB_ONLY','A_NO_MEMORY_REL','A_NO_TIMEZONE_REL','APP_TREE']
labels=['完整App','去MTC\n报警上限','仅App网页','去内存关系','去时区关系','App小树']
configs=[r['configuration'] for r in F01 if r['scheme']=='APP_FULL']
clabels=['屏幕参数','时区','Playwright预设','Puppeteer预设','CDP多字段预设','Stealth预设','平台字段',
         'CPU＋内存','User-Agent','UA＋平台','Webdriver','语言列表','Plugins / MIME','WebGL标识']
assert len(configs)==14
totals=[one(T02,scheme=m,identity='EFFECTIVE_INTERVENTION')['T'] for m in methods]
assert totals==[105,108,96,96,105,72]
for m in methods:
    assert one(T02,scheme=m,identity='NORMAL')['T']==0
    assert one(T02,scheme=m,identity='NORMAL')['N']==252

# 1. Preserve every cell; use color for the difference from Full, not score saturation.
fig=canvas('01  内存参照补充资源检出，部分修改仍全部漏检',
           '设计：完整方法作参照；只给发生变化的格子着色，让读者先看到组件贡献与共同漏检。',size=(12.3,8.5))
ax=panel(fig,[.035,.155,.93,.67])
ax.set_xlim(-2.65,8.8);ax.set_ylim(-2.6,14.4);ax.invert_yaxis()
for j,(m,lbl,total) in enumerate(zip(methods,labels,totals)):
    t(ax,j+.5,-1.94,lbl,12,ha='center')
    delta=total-totals[0]
    txt=f'{total}/126' + (f'  ({delta:+d})' if j else '')
    t(ax,j+.5,-.93,txt,11,ha='center',color=C['blue'] if j==0 else C['ink'])
t(ax,-.15,-1.3,'修改配置',12,ha='right')
for i,(cfg,lbl) in enumerate(zip(configs,clabels)):
    t(ax,-.16,i+.5,lbl,11.5,ha='right')
    baseline=one(F01,scheme='APP_FULL',configuration=cfg)['T']
    for j,m in enumerate(methods):
        r=one(F01,scheme=m,configuration=cfg); delta=r['T']-baseline
        bg=C['lightblue'] if j==0 else C['lightgreen'] if delta>0 else C['lightred'] if delta<0 else C['light']
        ax.add_patch(Rectangle((j,i),.98,.95,facecolor=bg,edgecolor='white'))
        txt=f"{r['T']}/9"
        if j and delta: txt+=f' ({delta:+d})'
        t(ax,j+.49,i+.48,txt,11.4,ha='center')
    if i in (0,7,10,13):
        ax.plot([6.08,6.25],[i+.48,i+.48],color=C['muted'],lw=1)
        msg={0:'多检出3次，代价见图03',7:'移除内存参照后损失9次',10:'所有方法均未检出',13:'所有方法均未检出'}[i]
        t(ax,6.36,i+.48,msg,11,color=C['red'] if i in (10,13) else C['ink'])
fig.text(.035,.115,'蓝底：完整App参照    绿底：相对参照多检出    红底：相对参照少检出    灰底：检出数不变',fontsize=10.5,color=C['muted'])
foot(fig,['全部14配置、6方法均保留；每格为检出数/9，总计为126次有效修改。所有方法在受控正常中均0/252报警。',
          '规则取RETENTION，小树取FITTED；本图未知/失败均0。颜色表示差值，不表示已判定哪种方法更好。'])
save(fig,'01_app_contribution')

# 2. Fixed-condition mechanism comparisons, explicitly separate from whole models.
fig=canvas('02  设备参照既能补漏检，也能容忍正常变化',
           '设计：三组有明确含义的场景对照。这里比较的是固定单条检查，不是三个完整模型。',size=(12.3,6.7))
panels=[panel(fig,[.035+i*.325,.24,.302,.58]) for i in range(3)]

def cell(ax,x,y,w,alarm,n,normal=False):
    good=(alarm==0) if normal else (alarm==n)
    bg=C['lightgreen'] if good else C['lightred']
    ax.add_patch(Rectangle((x,y-.045),w,.09,facecolor=bg,edgecolor='none'))
    prefix='误报' if normal else '检出'
    t(ax,x+w/2,y,f'{prefix} {alarm}/{n}',11.5,ha='center')

a=panels[0]
t(a,0,.98,'(a) 内存：补上阈值的漏检',14)
t(a,.51,.83,'网页 > 8',11,ha='center');t(a,.83,.83,'系统参照',11,ha='center')
for y,target in zip((.67,.51,.35),(4,8,16)):
    t(a,0,y,f'上报 {target} GiB',11)
    for x,cond in ((.36,'R_WEB8'),(.68,'R_REL')):
        r=one(MEM,scope='target',target=str(target),condition=cond)
        cell(a,x,y,.30,r['T'],r['N'])
t(a,0,.15,'额外12次检出来自4与8',12,color=C['blue'])
t(a,0,.025,'两条件：正常均0/48报警\n另6次无效果操作均0/6报警',10.5,va='bottom',linespacing=1.7)

a=panels[1]
t(a,0,.98,'(b) 时区：保留检出，减少误报',14)
t(a,.51,.83,'绝对偏移',11,ha='center');t(a,.83,.83,'系统参照',11,ha='center')
for y,key,lbl,normal in ((.65,'L_system_change','正常系统\n换时区',True),(.42,'A_observable','仅网页\n改时区',False)):
    t(a,0,y,lbl,11)
    for x,cond in ((.36,'R_ABSOLUTE'),(.68,'R_TZ')):
        cell(a,x,y,.30,TZ[key]['conditions'][cond].get('T',0),TZ[key]['positions'],normal)
t(a,0,.19,'6次正常换区：6次误报 → 0',12,color=C['blue'])
t(a,0,.025,'正常换区6条属于全部正常30条\n全部正常报警：6/30 → 0/30',10.5,va='bottom',linespacing=1.7)

a=panels[2]
t(a,0,.98,'(c) 屏幕：正常布局不应报警',14)
t(a,.53,.83,'正常布局\n扩大',10.5,ha='center');t(a,.84,.83,'屏幕参数\n修改',10.5,ha='center')
for y,cond,lbl in ((.65,'R_HEIGHT710','固定高度'),(.49,'R_SAME_WEB','网页内视口'),(.33,'R_HOST_GEOMETRY','宿主几何')):
    t(a,0,y,lbl,11)
    norm=SCREEN['normal_change_by_process']['L2'];attack=SCREEN['observable_intervention']
    cell(a,.38,y,.29,norm['conditions'][cond]['T'],norm['n'],True)
    cell(a,.70,y,.29,attack['conditions'][cond]['T'],attack['n'])
t(a,0,.15,'宿主几何：保留6次检出，减少6次误报',11.5,color=C['blue'])
t(a,0,.025,'几何条件在全部正常中0/66报警\n该新条件尚未进入完整App模型',10.5,va='bottom',linespacing=1.7)
foot(fig,['绿底：所示场景下检出有效修改或未报正常；红底：漏检或正常报警。各组为不同材料，不合并成一个分数。',
          '各组固定条件的未知/失败均0；内存结论限于已测向上修改，屏幕结论限于该专项环境。'])
save(fig,'02_reference_mechanisms')

# 3. Display a small benefit next to the full historical normal-state cost.
fig=canvas('03  取消正常报警上限：仅多检出3次，历史正常却全部报警',
           '设计：取消MTC报警上限的收益与代价放在同一张图；未知单独保留。',size=(12.3,7.1))
a=panel(fig,[.035,.69,.93,.14])
t(a,0,.83,'受控修改：105/126 → 108/126',16,color=C['blue'])
t(a,0,.35,'只增加3次检出；受控正常仍都是0/252报警',11.5)
t(a,.59,.83,'历史正常：低报警 → 每条都报警',16,color=C['red'])
t(a,.59,.35,'仅看受控正常，会完全看不到这一代价',11.5)

ys=[.83,.69,.55,.36,.22,.08]
for pidx,(subset,title,n) in enumerate((('development','历史评价144条',144),('reserved_validation','历史保留评价117条',117))):
    a=panel(fig,[.035+pidx*.49,.25,.455,.40])
    t(a,0,1.04,title,14)
    for i,(method,fold) in enumerate((('APP_FULL','01'),('APP_FULL','02'),('APP_FULL','03'),('A_NO_MTC_CAP','01'),('A_NO_MTC_CAP','02'),('A_NO_MTC_CAP','03'))):
        r=one(MTC,scheme=method,fold_id='WEBGL1-LOEO-v1-'+fold,subset=subset)
        assert r['N']==n and r['FAILED']==0
        y=ys[i]
        t(a,0,y,('有上限 ' if i<3 else '无上限 ')+fold,10.5)
        left=.24; width=.44
        for state,col,hatch in (('F',C['gray'],None),('U',C['yellow'],'///'),('T',C['red'],None)):
            w=width*r[state]/n
            if w: a.add_patch(Rectangle((left,y-.037),w,.074,facecolor=col,edgecolor='white',lw=.3,hatch=hatch))
            left+=w
        t(a,.705,y,f"{r['T']} / {r['F']} / {r['U']}",10.5)
    t(a,.705,.96,'报警 / 未报 / 未知',9.2)

fig.text(.035,.175,'灰：不报警    黄斜线：未知    红：正常报警。每条堆叠条的完整长度为该历史集合的100%。',fontsize=10.5,color=C['muted'])
foot(fig,['630条正常约束训练记录另计：有上限三配置报警6 / 6 / 0条、各51条未知；无上限均630/630报警。',
          '01/02/03是三个模型分别作用于同一批记录，不合并分母。144＋117是历史评价材料，不是新的盲测。'])
save(fig,'03_normal_constraint_cost')

# 4. Dots encode actual evaluation positions in each family, not model repeats.
fig=canvas('04  双端新增的检出，明确来自Browser时区',
           '设计：按“修改发生在哪一端 × 修改类型”排成四格；直接显示保留、新增与仍然漏检的位置。',size=(12.3,6.8))
families=[('App_timezone','App时区',0,0),('App_language','App语言',0,1),
          ('Browser_timezone','Browser时区',1,0),('Browser_language','Browser语言',1,1)]
for fam,label,row,col in families:
    a=panel(fig,[.035+col*.49,.39-row*.235,.455,.21])
    if row==0: t(a,0,1.24,'时区修改' if col==0 else '语言修改',15,color=C['blue'])
    t(a,0,.94,label,14)
    values=[]
    for y,m,lbl in ((.57,'APP_FULL','完整App'),(.19,'PAIRED_BASE','App＋跨端C1')):
        rs=[one(PAIR,method=m,family=fam,configuration=f) for f in ('01','02','03')]
        assert len({tuple(r[k] for k in ('N','T','F','U','FAILED')) for r in rs})==1
        r=rs[0];values.append(r['T'])
        t(a,0,y,lbl,11)
        for i in range(r['N']):
            a.scatter(.36+i*.065,y,s=105,facecolor=C['green'] if i<r['T'] else 'white',
                      edgecolor=C['green'] if i<r['T'] else C['gray'],linewidth=1.7,zorder=3)
        t(a,.74,y,f"{r['T']}/{r['N']}",13)
    msg={'App_timezone':'保留2次检出','App_language':'仍漏检2次','Browser_timezone':'新增5次检出','Browser_language':'仍漏检5次'}[fam]
    t(a,.98,.94,msg,12,ha='right',color=C['green'] if col==0 else C['red'])
    if row==0:a.plot([0,1],[-.05,-.05],color=C['line'],lw=.8,clip_on=False)
fig.text(.035,.795,'● 检出     ○ 未检出     每点表示一个修改评价位置',fontsize=11,color=C['muted'])
fig.text(.035,.735,'总计 2/14 → 7/14；5次新增均为Browser时区，7次语言修改仍未检出。',fontsize=15,color=C['ink'])
foot(fig,['同批46条配对正常：两方法均0/46报警，未知/失败均0；01/02/03汇总相同，图中不叠加为三倍样本。',
          '更广正常侧代价：历史MTC 261条的未知由14增至17（各配置）；本图14次修改有开发使用历史。'])
save(fig,'04_cross_endpoint_gain')

data={'app_cells':F01,'app_totals':T02,'app_historical_normals':F02,
      'mtc_constraint_split_rows':[r for r in MTC if r['scheme'] in ('APP_FULL','A_NO_MTC_CAP')],
      'paired_base_historical_normals':[r for r in TABLES['historical_mtc'] if r['set_id']=='S0'],
      'memory_fixed_conditions':MEM,
      'timezone_fixed_conditions':{k:{'N':v['positions'],'conditions':v['conditions']} for k,v in TZ.items()},
      'screen_fixed_conditions':{k:SCREEN[k] for k in ('confirmed_normal','observable_intervention','normal_change_by_process')},
      'paired_families_all_configurations':PAIR}
(OUT/'plotted_data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
(OUT/'SOURCES.json').write_text(json.dumps(SOURCES,ensure_ascii=False,indent=2)+'\n')
(OUT/'CHECK.json').write_text(json.dumps({'saved_sources_only':True,'new_experiment_calls':0,
    'figure_count':4,'checks':CHECKS,'visual_review':'PENDING'},ensure_ascii=False,indent=2)+'\n')
print('Saved four PNG/SVG design drafts and source data to',OUT)
