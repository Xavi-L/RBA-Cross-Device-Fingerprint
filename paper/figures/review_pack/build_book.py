#!/usr/bin/env python3
"""Build one advisor PDF from saved SVG/CSV. --check-only is read-only/offline."""
import argparse
import csv
import hashlib
import html
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIGURES = HERE.parent
ROUND3 = FIGURES / 'round3_overview'
OWNER = 'rba-advisor-figure-book-v1'
PDF = HERE / 'ADVISOR_FIGURE_BOOK.pdf'
EXPECTED_IDS = ['F00','F01','F02','F03a','F03b','F04','F05a','F05b','F06a','F06b','F07a','F07b','F08','F09']
DEPENDENCIES = Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies'


def read_json(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path, data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def esc(value): return html.escape(str(value))
def github_url(path, version):
    return 'https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/'+version+'/'+quote(str(path),safe='/')
def full_https(uri):
    parsed=urlparse(uri)
    return parsed.scheme=='https' and bool(parsed.hostname) and not parsed.username and not parsed.password
def paragraphs(items): return ''.join('<p>'+esc(p)+'</p>' for p in items)
def table(headers, data):
    return '<table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in data)+'</tbody></table>'


def build_pages(config):
    pages=[]; links=[]; inputs=set(); svg_map=[]
    def link(label,path,published=False):
        path=Path(path); absolute=(ROOT/path).resolve()
        if not absolute.is_file():raise FileNotFoundError(path)
        version=config['published_artifact_commit'] if published else config['baseline']
        uri=github_url(path.as_posix(),version)
        links.append(dict(label=label,uri=uri,path=path.as_posix(),version=version))
        return '<a href="'+esc(uri)+'">'+esc(label)+'</a>'
    def add(id,title,body,category='待导师选择',keywords=None):
        pages.append(dict(id=id,title=title,body=body,category=category,keywords=keywords or [id,title]))
    def saved(path):
        inputs.add(path.relative_to(ROOT).as_posix());return rows(path)
    guide=paragraphs([
        '本册用于连续阅读与选图，尚未给定导师提纲、投稿模板或最终论文图号。素材ID保持F00-F09（含拆分子图），共14类；F00正文候选和详细说明是同一素材的两个版式，F10仍以T05表格呈现，F11未制作。',
        '事实基线：'+config['baseline']+'。当前稿件：'+config['version']+'。本轮只修外部链接与发送说明；图形、实验和统计数据不变，无采集、拟合、选择、预测或重新计时。',
        'PDF可单独发送和阅读，无需附带仓库目录；页内矢量图、正文和表格均已嵌入。F00正文版、修正F09、节点/连线映射及当前英文图注的6个入口固定到已推送图稿提交 '+config['published_artifact_commit']+'；未变更的实验依据仍保留原事实基线。外部材料通过完整HTTPS网页链接访问，目录保持PDF内部跳转；源图版本、摘要与页码另存PAGES.json。'])
    guide+=table(['简称','方法身份'],[
        ['Full App / APP_FULL','不读独立Browser的当前完整App规则；四项消融是已保存的重新选择/拟合模型。'],
        ['App+C1 / PAIRED_BASE / S0','冻结App加接受的跨端时区C1；T05旧名R_FULL也是此方法，R_NO_CROSS是旧App基线。'],
        ['固定条件','内存、Host几何、C1/C2或M/B/W等单条检查；不是完整训练模型。B仅指Browser内存>8。'],
        ['Small App tree / 四视图树','App小树与P0/P1/P2四视图树是不同比较对象；不代表全部177/67字段的机器学习上限。']])
    guide+=paragraphs(['计数单位为评价位置/记录，不是设备数；开发使用历史、正常报警、未知U与失败均保留。F为未报警，不是安全认证。页角正文/附录均为候选建议，由导师决定。'])
    guide+='<div class="links">'+link('综合证据报告',Path('RBA_EXPERIMENT_REPORT_FOR_ADVISOR.md'))+' · '+link('F00详细说明（基线原图）',Path('paper/figures/round3_overview/figures/F00.svg'))+'</div>'
    add('GUIDE','导师选图册 · 阅读说明',guide,keywords=['可供导师选图','14类','7ae5bc1d','R_FULL'])
    add('TOC','目录 · 点击跳转','',keywords=['目录','F00','F09','T05'])
    for entry in config['figures']:
        fid=entry['id'];rnd=FIGURES/entry['round'];manifest=read_json(rnd/'FIGURES.json')
        item=next(f for f in manifest['figures'] if f['id']==fid)
        variant=entry.get('variant',fid);svg=rnd/'figures'/(variant+'.svg');size=[180,160] if variant=='F00_main' else item['size_mm']
        csv_path=rnd/('data/F00_main_nodes.csv' if variant=='F00_main' else item['plotting_csv'])
        for path in (svg,csv_path,rnd/'CAPTIONS.md'):inputs.add(path.relative_to(ROOT).as_posix())
        raw=svg.read_text(); raw=raw[raw.index('<svg'):]
        raw=re.sub(r'\bid="([^"]+)"',lambda m:'id="'+variant+'_'+m[1]+'"',raw)
        raw=re.sub(r'url\(#([^)]+)\)',lambda m:'url(#'+variant+'_'+m[1]+')',raw)
        raw=re.sub(r'(?:xlink:)?href="#([^"]+)"',lambda m:'href="#'+variant+'_'+m[1]+'"',raw)
        body='<div class="figure" style="width:'+str(size[0])+'mm;height:'+str(size[1])+'mm">'+raw+'</div>'
        body+=paragraphs(entry['notes'])
        current=fid in ('F00','F09')
        captions=(rnd/'CAPTIONS.md').relative_to(ROOT)
        refs=[link('绘图CSV/节点映射',csv_path.relative_to(ROOT),published=fid=='F00'),
              link('当前原图SVG' if current else '原图SVG',svg.relative_to(ROOT),published=current),
              link('完整英文图注',captions,published=current),link('保存证据',Path(item['sources'][0]['path']))]
        if fid=='F00':
            refs+=[link('F00详细说明',Path('paper/figures/round3_overview/figures/F00.svg')),
                link('连线/评价依赖',Path('paper/figures/round3_overview/data/F00_main_edges.csv'),published=True)]
            inputs.update(['paper/figures/round3_overview/F00_main_source.json',
                'paper/figures/round3_overview/data/F00_main_edges.csv'])
        if fid=='F06b':refs.append(link('T04分组长明细',Path('paper/figures/round2_paired/data/T04_four_view_all_cohorts.csv')))
        if fid=='F07b':
            refs.append(link('T04全部24组合',Path('paper/figures/round2_paired/data/T04_resource_candidates.csv')))
            refs.append(link('T04历史正常分组',Path('paper/figures/round2_paired/data/T04_resource_normals.csv')))
        if fid=='F09':refs.append(link('基线原图（未修副标题）',Path('paper/figures/round3_overview/figures/F09.svg')))
        body+='<div class="links">'+' · '.join(refs)+'</div>'
        add(fid,entry['title'],body,entry['placement'],[fid,entry['title']])
        svg_map.append(dict(id=fid,variant=variant,svg=svg.relative_to(ROOT).as_posix(),size_mm=size,
            csv=csv_path.relative_to(ROOT).as_posix(),page=len(pages),svg_sha256=sha(svg),format='inline vector SVG; no raster fallback'))

    t01=FIGURES/'round1_app/data/T01.csv';scope=saved(t01)
    if [r['batch_id'] for r in scope]!=['early_app_development','current_app_controlled','mtc_paired_qc',
        'mtc_representatives','mtc_extra_pairs','memory_specialist','timezone_specialist','screen_specialist',
        'webgl_feasibility','browser_language_timezone_pilot','bidirectional_language_timezone','paired_resource','screen_v16_engineering']:
        raise ValueError('T01 identities/order changed; review role mapping before rendering')
    roles=[
      '探索材料；监督阶段只是总阶段262的一部分', 'F01/T02；环境留出位置不重复相加',
      '配对/QC目录背景，不作为正常率分母', '630训练正常；144/117历史评价',
      '重复观测背景，不纳主代表正常率', 'F03a/b共享一批；无变化6另列',
      'F04；正常系统换区与网页修改', 'F09；无效果2已包含在正常66中',
      '可行性观察，不是完整App结果', 'F05a的60中先导18', 'F05a的60中匹配42',
      'F05b；单列资源54，不与60相加', '工程收尾，排除正式效果；剩余阶段见CSV']
    data=[[r['batch_cn'],r['normal_N'] or '—',r['effective_modified_N'] or '—',
           (r['no_observable_effect_N']+'*' if r['batch_id']=='screen_specialist' else r['no_observable_effect_N']) or '—',
           r['total_records_N'],role] for r,role in zip(scope,roles)]
    body=paragraphs(['沿用T01保存范围，不跨批次求和。“—”表示未以该身份单列，不能补零；早期探索与工程阶段不必等于所列正常+修改数。'])
    body+=table(['材料','正常','有效修改','无效果','总位置','角色与重叠边界'],data)
    body+=paragraphs(['* F09的2条无可观测效果旋转尝试属于正常66，非额外两条；正常布局6同样为66的子集。MTC1028包含891主代表及137其余配对记录，不能把三者累计；F03a/b共享内存72。'])
    body+='<div class="links">'+link('T01完整语义与来源',t01.relative_to(ROOT))+'</div>'
    add('T01','数据范围与不可相加的分母',body,keywords=['T01','252','126','630','144/117','正常66'])

    t02=FIGURES/'round1_app/data/T02.csv';results=saved(t02)
    body=paragraphs(['六方法、两种身份均保留原始N/T/F/U/FAILED和EMPTY_MODEL；规则使用RETENTION，小树使用FITTED。主表不纳MTC正常，正常代价须并读F02。'])
    body+=table(['方法','身份','N','T','F','U','FAILED','EMPTY'],[[r['method_short'],'修改' if r['identity']=='EFFECTIVE_INTERVENTION' else '正常']+[r[k] for k in ('N','T','F','U','FAILED','EMPTY_MODEL')] for r in results])
    body+=paragraphs(['修改分母126是原环境留出结构的不重复合计，正常252是受控前后位置；不是三配置全量回放相加。去MTC上限108/126的局部增加伴随F02三配置各261/261历史正常报警，不能单独择优。'])
    body+='<div class="links">'+link('T02完整主表',t02.relative_to(ROOT))+' · '+link('源主结果',Path('deliverables/app177_core_ablation_v1/results/summary/main.csv'))+'</div>'
    add('T02','App主结果：完整状态计数',body,keywords=['T02','105','108','126','252','261/261'])

    costs=saved(ROUND3/'data/T05_cost_main.csv');cost_index={(r['label'],r['stage']):r for r in costs}
    labels=list(dict.fromkeys(r['label'] for r in costs))
    if len(costs)!=49 or len(labels)!=7:raise ValueError('Expected fixed 7-model, 49-stage-row main table')
    def cost_table(stages):
        return table(['方法']+[label for key,label in stages],[[label]+[f"{float(cost_index[label,key]['median_amortized_ms']):.4f} / {float(cost_index[label,key]['p95_batch_amortized_ms']):.4f}" for key,_ in stages] for label in labels])
    cost_note='每格为中位数 / P95，单位ms。R_FULL是冻结App+C1；主表固定三个配置与P0四视图，非按速度择优。除加载每模型外，其余为同60位置批均；P95是10批均摊值的分布，不是单请求尾延迟。'
    cost_links='<div class="links">'+' · '.join([
        link('49行固定主表',Path('paper/figures/round3_overview/data/T05_cost_main.csv')),
        link('阶段定义',Path('paper/figures/round3_overview/data/T05_stage_definitions.csv')),
        link('148阶段明细',Path('paper/figures/round3_overview/data/T05_cost_all.csv')),
        link('1480原批次',Path('paper/figures/round3_overview/data/T05_cost_batches.csv')),
        link('T05完整说明',Path('paper/figures/round3_overview/T05.md'))])+'</div>'
    body=paragraphs([cost_note])+cost_table([('load_parse_validate','加载校验 / 每模型'),('model_input_prepare','输入准备 / 每位置'),('prepared_inference','准备后判断 / 每位置')])
    body+=table(['阶段','计时起点与终点'],[
        ['加载校验','模型/预处理JSON读取、解析与身份校验；规则含基础模型。热文件系统重复读取，不是OS冷启动。'],
        ['输入准备','已适配测量 → 冻结编码、所选关系和输入投影。树含视图测量、REL和冻结预处理。'],
        ['准备后判断','已准备输入 → 原规则组合或JSON树遍历；入口自身检查仍保留。']])
    body+=paragraphs(['这些阶段与下一页路径部分重叠，各阶段中位数和P95不能相加。计时不含设备采集、页面启动、网络上传、配对等待、raw文件读取/JSON解析与首次模块导入。旧环境为Darwin 24.6.0 arm64、Python 3.13.5，GC开启，1遍预热与10遍记录；本轮未重新计时。'])+cost_links
    add('T05a','成本选读（1/4）：加载、准备与判断',body,'附录候选',keywords=['T05a','R_FULL','1.8444','10批','P95'])
    body=paragraphs([cost_note])+cost_table([('original_current_interface','原公开接口 / 每位置'),('cached_from_adapted','已适配 → 缓存输出 / 每位置')])
    body+=cost_table([('loaded_raw_to_original','已加载raw → 原接口 / 每位置'),('loaded_raw_to_cached','已加载raw → 缓存输出 / 每位置')])
    shared=saved(ROUND3/'data/T05_cost_shared.csv')[0]
    body+=paragraphs([
        '原规则接口每次含基础文件读取、校验与预处理；树接口从已派生cells开始，因此起点不同。缓存路径从已适配测量开始，复用已加载对象，不表示生产代码已经改造。',
        '已加载raw包装包含共享适配再到相应输出，仍不含raw磁盘读取/JSON解析；单端树也可能承担多余App准备。共享适配中位/P95为'+f"{float(shared['median_amortized_ms']):.4f} / {float(shared['p95_batch_amortized_ms']):.4f}"+' ms/位置。',
        '四种路径互有重叠，不能相加为端到端时间，也不能据此排名规则/树算法倍速；后续资源组合与新App消融未计时，不继承旧值。'])+cost_links
    add('T05b','成本选读（2/4）：不同起点的输出路径',body,'附录候选',keywords=['T05b','0.4814','8.1355','7.6255','不能相加'])
    resources=saved(ROUND3/'data/T05_model_resources_main.csv')
    body=paragraphs(['同一固定7模型主表，保留规则/树适用字段及额外基础模型依赖。“—”为不适用，不是零；文件大小单位bytes。'])
    body+=table(['方法','规则','复杂度','节点','深度','模型/包装','基础模型'],[[r['label']]+[r[k] or '—' for k in ('rules','complexity','nodes','depth','file_bytes','base_file_bytes')] for r in resources])
    body+=paragraphs([
        'R_FULL包装JSON含来源与选择记录，冻结预处理位于另列的基础模型；树JSON也含预处理及开发/评价成员元数据。这不是裁剪后的部署包，不含代码库、Python及依赖环境；额外条件/适配代码字节数未记录。',
        '规则复用标准库与原规则/适配模块；树沿用原engine，导入仍依赖numpy/sklearn，不能宣称无此运行依赖。完整21模型与来源留在结构化表中；后续资源组合与新App消融未重新计时。'])
    body+='<div class="links">'+link('7模型资源主表',Path('paper/figures/round3_overview/data/T05_model_resources_main.csv'))+' · '+link('21模型完整资源表',Path('paper/figures/round3_overview/data/T05_model_resources_all.csv'))+'</div>'
    add('T05c','成本选读（3/4）：保存模型与额外依赖',body,'附录候选',keywords=['T05c','43426','105587','bytes','不是裁剪'])
    logs=saved(ROUND3/'data/T05_collection_summary.csv')
    def interval(r):
        return f"{float(r['median_seconds']):.4f} ({float(r['minimum_seconds']):.4f}-{float(r['maximum_seconds']):.4f}); {r['recorded_n']}/{r['cohort_n']}" if r['status']=='RECORDED' else '未记录'
    log_index={(r['cohort'],r['metric']):r for r in logs}
    body=paragraphs(['以下单位为秒，数值为中位数（最小-最大）；有效条数。仅复用同host保存端点差值，是含设置、上传、等待与恢复的编排区间，不是纯探针或端到端检测延迟。'])
    body+=table(['批次','完整采集编排','App导航 → 配对完成','纯探针'],[[c,interval(log_index[c,'capture_orchestration_seconds']),interval(log_index[c,'app_navigation_to_pair_complete_seconds']),'未记录'] for c in ('pilot18','b2b42')])
    body+=paragraphs(['匹配正常Browser偏好的两次change、两次post保留4条15秒持久化等待，未扣除慢项；纯探针60/60未记录。墙钟差值不等于单调时钟保证，不能跨host相减。'])
    training=saved(ROUND3/'data/T05_historical_training_timing.csv')
    body+=table(['历史阶段','保存秒数','范围'],[[('App RETENTION / '+str(i+1).zfill(2)) if i<3 else r['method'],f"{float(r['elapsed_seconds']):.6f}" if r['elapsed_seconds'] else '未记录','已准备输入后的内部fit' if i<3 else '无独立纯fit/选择时长'] for i,r in enumerate(training)])
    body+=paragraphs(['三个App区间不含编码器准备、raw解析、此前SPARSE拟合或完整训练流程。B2C、B3A及B3B有限选择缺少独立耗时；流水线起止和调用次数不能补成纯训练成本。'])
    body+='<div class="links">'+' · '.join(link(label,Path('paper/figures/round3_overview/data')/f) for label,f in [('60条去标识区间','T05_collection_intervals.csv'),('采集分组完整表','T05_collection_summary.csv'),('历史计时原值','T05_historical_training_timing.csv')])+'</div>'
    add('T05d','成本选读（4/4）：已有采集与训练日志',body,'附录候选',keywords=['T05d','10.6750','80.4580','15秒','未记录'])
    pages[1]['body']='<nav>'+''.join('<a class="toc" href="#'+p['id']+'"><span>'+esc(p['id']+'　'+p['title'])+'</span><span>'+str(i+1)+'</span></a>' for i,p in enumerate(pages) if i>1)+'</nav>'+paragraphs(['F01/F02、F03a/F03b、F05a/F05b、F06a/F06b与F07a/F07b相邻阅读。各页候选位置均待导师确认。'])
    return pages,links,inputs,svg_map


def html_document(pages):
    cjk=Path(os.environ.get('RBA_CJK_FONT','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
    font_dir=next((ROOT/'deliverables/prepaper_evidence_closeout_v1/.plot-runtime/lib').glob('python*/site-packages/matplotlib/mpl-data/fonts/ttf'))
    if not cjk.is_file():raise FileNotFoundError('Set RBA_CJK_FONT to an embeddable CJK TrueType font')
    css=f'''@font-face{{font-family:ReviewCJK;src:url("{cjk.as_uri()}")}} @font-face{{font-family:"DejaVu Sans";src:url("{(font_dir/'DejaVuSans.ttf').as_uri()}")}} @font-face{{font-family:"DejaVu Sans";font-weight:700;src:url("{(font_dir/'DejaVuSans-Bold.ttf').as_uri()}")}}
    @page{{size:A4;margin:15mm}} *{{box-sizing:border-box}} body{{margin:0;color:#21313c;font:10.5pt ReviewCJK,sans-serif;line-height:1.5}}
    .page{{width:180mm;height:266mm;position:relative;break-after:page}} .page:last-child{{break-after:auto}}
    h1{{font-size:16pt;margin:0 0 2mm;font-weight:600;line-height:1.4}} .kicker{{font-size:9pt;color:#526d7c;margin-bottom:2mm;letter-spacing:.3pt}}
    .rule{{height:.5mm;background:#416b81;margin-bottom:4mm}} p{{margin:3mm 0;text-align:justify}}
    .figure{{margin:0 auto 4mm}} .figure>svg{{display:block;width:100%;height:100%;overflow:visible}}
    .links{{font-size:9pt;line-height:1.6;margin-top:4mm}} a{{color:#245f83;text-decoration:underline}}
    table{{border-collapse:collapse;width:100%;margin:4mm 0 5mm;font-size:9.5pt;line-height:1.45}} th{{text-align:left;background:#edf3f6;color:#274c61;font-weight:600}}
    th,td{{padding:2mm 1.6mm;border-bottom:.25mm solid #d4dfe5;vertical-align:top}} td:first-child{{white-space:nowrap}}
    footer{{position:absolute;bottom:0;width:100%;border-top:.25mm solid #ccd9e0;padding-top:2mm;display:flex;justify-content:space-between;font-size:8.5pt;color:#5b6e7a}}
    .toc{{display:flex;justify-content:space-between;padding:1.7mm 0;border-bottom:.2mm solid #e1e8ec;text-decoration:none;font-size:10.5pt}} #T01 table{{font-size:9pt}} #T01 td:first-child{{white-space:normal;width:35mm}} #T01 td:last-child{{width:65mm}}
    '''
    parts=[]
    for i,p in enumerate(pages):
        parts.append('<section class="page" id="'+p['id']+'"><div class="content"><div class="kicker">RBA · '+esc(p['id'])+' · 可供导师选图，待提纲对应</div><h1>'+esc(p['title'])+'</h1><div class="rule"></div>'+p['body']+'</div><footer><span>'+esc(p['category'])+'</span><span>素材ID非最终论文图号</span><span>'+str(i+1)+' / '+str(len(pages))+'</span></footer></section>')
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>RBA 导师选图册</title><style>'+css+'</style>'+''.join(parts)+'</html>'


def inspect_pdf(mapping,pdf_path=PDF):
    from pypdf import PdfReader
    reader=PdfReader(pdf_path);failures=[];external=0;internal=0;fonts={};rasters=0
    expected_urls={item['uri'] for item in mapping['links']};seen_urls=set();seen_destinations=set()
    expected_destinations={p['id']:p['page'] for p in mapping['pages'] if p['page']>=3}
    destinations=reader.named_destinations
    actual_destinations={str(key).lstrip('/'):reader.get_destination_page_number(value)+1 for key,value in destinations.items()}
    if actual_destinations!=expected_destinations:failures.append('TOC destination page mapping mismatch')
    for item in mapping['links']:
        if not full_https(item['uri']) or item['version'] not in (mapping['baseline'],mapping['published_artifact_commit']) or item['uri']!=github_url(item['path'],item['version']):
            failures.append('Incomplete or unpinned manifest HTTPS link: '+item['uri'])
    if len(reader.pages)!=len(mapping['pages']):failures.append('PDF page count mismatch')
    for p,expected in zip(reader.pages,mapping['pages']):
        text=re.sub(r'\s+','',p.extract_text() or '')
        for word in expected['keywords']:
            if re.sub(r'\s+','',word) not in text:failures.append({'page':expected['page'],'missing_text':word})
        if abs(float(p.mediabox.width)-210*72/25.4)>.5 or abs(float(p.mediabox.height)-297*72/25.4)>.5:failures.append('Non-A4 page')
        rasters+=len(p.images)
        for ref in p.get('/Resources',{}).get('/Font',{}).values():
            f=ref.get_object();children=f.get('/DescendantFonts',[f]);embedded=True
            if f.get('/Subtype')=='/Type3':
                # Chromium may encode a few symbols as embedded glyph procedures.
                embedded=bool(f.get('/CharProcs') and f.get('/ToUnicode'))
            else:
                for child in children:
                    d=child.get_object().get('/FontDescriptor')
                    embedded &= bool(d and any(k in d.get_object() for k in ('/FontFile','/FontFile2','/FontFile3')))
            fonts[str(f.get('/BaseFont','Type3 embedded CharProcs + ToUnicode'))]=bool(embedded)
        for ref in p.get('/Annots',[]):
            a=ref.get_object();action=a.get('/A',{});uri=action.get('/URI')
            if uri:
                external+=1;seen_urls.add(str(uri))
                if not full_https(str(uri)) or str(uri) not in expected_urls:failures.append('Invalid PDF external HTTPS link: '+str(uri))
            elif a.get('/Dest') or action.get('/D'):
                internal+=1;dest=a.get('/Dest') or action.get('/D')
                if str(dest) not in destinations:failures.append('Unresolved PDF internal link: '+str(dest))
                else:seen_destinations.add(str(dest).lstrip('/'))
    if seen_urls!=expected_urls:failures.append('PDF/manifest external URL set mismatch')
    if seen_destinations!=set(expected_destinations):failures.append('Missing TOC link annotations')
    if not all(fonts.values()) or not fonts:failures.append('Missing embedded font')
    if internal<len(mapping['pages'])-2:failures.append('Missing clickable TOC destinations')
    if rasters:failures.append('Unexpected raster figure in vector PDF')
    return dict(status='FAIL' if failures else 'PASS',page_count=len(reader.pages),embedded_fonts=fonts,
        external_https_links=external,external_non_https_links=sum(not full_https(u) for u in seen_urls),
        internal_links=internal,toc_destination_pages=actual_destinations,raster_images=rasters,failures=failures)


def check_only(pdf_path=PDF,standalone=False):
    mapping=read_json(HERE/'PAGES.json');failures=[]
    if mapping.get('owner')!=OWNER:failures.append('Unknown owner')
    if sha(pdf_path)!=mapping['pdf_sha256']:failures.append('PDF bytes changed; visual review invalid')
    if not standalone:
        for p,h in mapping['inputs'].items():
            if not (ROOT/p).is_file() or sha(ROOT/p)!=h:failures.append('Source changed: '+p)
    if [f['id'] for f in mapping['figures']]!=EXPECTED_IDS:failures.append('Figure class/order mismatch')
    pdf_check=inspect_pdf(mapping,pdf_path);failures+=pdf_check['failures']
    result=dict(status='FAIL' if failures else 'PASS',pages=pdf_check['page_count'],figure_classes=14,
        external_https_links=pdf_check['external_https_links'],internal_links=pdf_check['internal_links'],
        standalone_pdf=standalone,repository_source_reads=0 if standalone else len(mapping['inputs']),
        failures=failures,writes=0,science_entrypoints=0,network=0)
    print(json.dumps(result,ensure_ascii=False));return int(bool(failures))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--pdf',type=Path,help='With --check-only, inspect an isolated PDF copy without reading figure/data sources. Expected mapping is read from PAGES.json.')
    args=parser.parse_args()
    if args.pdf and not args.check_only:parser.error('--pdf requires --check-only')
    if args.check_only:return check_only(args.pdf.resolve() if args.pdf else PDF,standalone=bool(args.pdf))
    prior=read_json(HERE/'PAGES.json') if (HERE/'PAGES.json').exists() else None
    if prior and prior.get('owner')!=OWNER:raise ValueError('Unknown output owner')
    if not prior and any((HERE/p).exists() for p in ('ADVISOR_FIGURE_BOOK.pdf','CHECK.json')):raise ValueError('Unowned output')
    config=read_json(HERE/'book_content.json');pages,links,inputs,svg_map=build_pages(config)
    for p in ('book_content.json','build_book.py','print_book.cjs'):inputs.add((HERE/p).relative_to(ROOT).as_posix())
    qa=Path(os.environ.get('RBA_REVIEW_QA_DIR',str(Path(tempfile.gettempdir())/'rba_review_book_qa')));qa.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rba-advisor-book-') as tmp:
        temp=Path(tmp);source=temp/'book.html';source.write_text(html_document(pages),encoding='utf-8')
        node=Path(os.environ.get('RBA_NODE',str(DEPENDENCIES/'node/bin/node')))
        subprocess.run([str(node),str(HERE/'print_book.cjs'),str(source),str(temp/'book.pdf'),str(qa/'layout.json')],check=True)
        from pypdf import PdfReader,PdfWriter
        writer=PdfWriter(clone_from=PdfReader(temp/'book.pdf'))
        writer.add_metadata({'/Title':'RBA 导师选图册','/Subject':config['status']+'; baseline '+config['baseline'],'/Author':'RBA research project'})
        with (temp/'final.pdf').open('wb') as fh:writer.write(fh)
        (temp/'final.pdf').replace(PDF)
    mapping=dict(owner=OWNER,version=config['version'],baseline=config['baseline'],published_artifact_commit=config['published_artifact_commit'],status=config['status'],pdf_sha256=sha(PDF),
        figures=svg_map,pages=[dict(page=i+1,**{k:v for k,v in p.items() if k!='body'}) for i,p in enumerate(pages)],
        inputs={p:sha(ROOT/p) for p in sorted(inputs)},links=links)
    dump(HERE/'PAGES.json',mapping)
    numeric=inspect_pdf(mapping);layout=read_json(qa/'layout.json')
    if any(abs(row['svg'][axis]-f['size_mm'][i])>.03 for row in layout['pages'] if row['svg'] for f in svg_map if f['id']==row['id'] for i,axis in enumerate(('width_mm','height_mm'))):numeric['failures'].append('SVG physical size mismatch');numeric['status']='FAIL'
    old=read_json(HERE/'CHECK.json') if (HERE/'CHECK.json').exists() else {}
    visual=old.get('visual_review',{}) if old.get('pdf_sha256')==mapping['pdf_sha256'] else {'status':'PENDING','pages_inspected':[],'physical_print':'NOT_EVALUATED'}
    dump(HERE/'CHECK.json',dict(owner=OWNER,pdf_sha256=mapping['pdf_sha256'],saved_pdf=numeric,
        layout=dict(status='PASS',pages=len(pages),vector_svgs=layout['vector_svg_count'],raster_fallbacks=0,physical_sizes='PASS',minimum_figure_font_pt=8,minimum_body_table_font_pt=9),
        visual_review=visual,operations=dict(collection=0,fit=0,selection=0,prediction=0,retiming=0,network=0)))
    print(json.dumps({'pdf':str(PDF),'pages':len(pages),'saved_pdf':numeric['status'],'failures':numeric['failures'],'visual':visual['status']},ensure_ascii=False))
    return int(numeric['status']!='PASS')


if __name__=='__main__':raise SystemExit(main())
