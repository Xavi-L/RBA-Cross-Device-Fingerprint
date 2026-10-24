#!/usr/bin/env python3
"""Build the current table-redesign report from PDF-bound verification records."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def read_json(name):
    return json.loads((ROOT / name).read_text())


def main():
    pdf = ROOT / 'build/matrix/HybridGuard_layout_v1_matrix.pdf'
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    records = {name: read_json('qa/' + name + '.json') for name in (
        'table_layout_check', 'tables_semantic_audit',
        'table_visual_review', 'package_rebuild_check')}
    for name, record in records.items():
        assert 'PASS' in record['status'].upper(), name
        assert sha in json.dumps(record, ensure_ascii=False), name
    layout = records['table_layout_check']
    assert layout['pdf']['main_pages'] == 8
    assert layout['pdf']['total_pages'] == 10
    changes = [
        ('Table 1', '证据类别徽记、单行主体、三行双列图例',
         '六条文献记录全部单行。D/C/I/G/S/R 只标识证据类型，完整释义保留；不把未讨论的能力标成缺失。'),
        ('Table 2', '材料分组与 Δ/N 列',
         'MTC 和 Specialist 合并重复组名，八条材料记录全部单行；每项计数、开发使用与排除条件保持。'),
        ('Table 3', '六方法逐格符号矩阵',
         '全检出、部分检出和零检出与精确计数并排；不合并方法格。每原始 recipe 的分母9、组权重及非零差值保持。'),
        ('Table 4', '三个机制组与独立报警提示',
         'Memory、Timezone、Geometry 分组；检测列与正常报警列采用不同含义的标记，保留 standalone 和 no-effect 等边界。'),
        ('Table 5', '单栏、cohort 组标题与状态比例条',
         '与 Table 6 同宽。T/F/U 三元数保留，条段按原始整数比例绘制，01/02 等值并列显示而非汇总。'),
        ('Table 6', '简洁表头、检测符号与独立 normal 行',
         'App 在 caption 中定义为 Integrated App；主体与表头均为单行，normal alarms 用横线单独分隔。'),
    ]
    record = {
        'date': '2026-10-22', 'status': 'TABLE_REDESIGN_APPLIED_AND_VERIFIED',
        'pdf': layout['pdf'], 'baseline_pdf_sha256': layout['baseline_pdf_sha256'],
        'changes': [{'table': t, 'presentation': a, 'scope': b} for t, a, b in changes],
        'float_pages': layout['float_pages'],
        'table_1_measurement': layout['table_1_measurement'],
        'single_column_widths_pt': layout['single_column_widths_pt'],
        'body_prose_changed': False, 'abstract_changed': False,
        'frozen_figure_assets_changed': False,
        'previous_approved_edits_retained': ['A1', 'A2', 'A3', 'B1'],
        'not_applied': ['B2'],
        'verification_reports': ['qa/' + n + '.json' for n in records],
        'historical_reports': 'reviews/history_v3/',
    }
    reviews = ROOT / 'reviews'
    (reviews / 'final_read_assessment.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    rows = ['| 表格 | 新的表达 | 关键处理 |', '|---|---|---|']
    rows += [f'| {t} | {a} | {b} |' for t, a, b in changes]
    positions = ['| 图表 | 上一轮 | 本轮 |', '|---|---:|---:|']
    names = {'tab:related': 'Table 1', 'tab:materials': 'Table 2',
             'tab:app': 'Table 3', 'tab:specialists': 'Table 4',
             'tab:normals': 'Table 5', 'tab:paired': 'Table 6',
             'fig:mechanisms': 'Figure 3'}
    positions += [f'| {name} | 第 {layout["float_pages"][key]["before"]} 页 | '
                  f'第 {layout["float_pages"][key]["after"]} 页 |'
                  for key, name in names.items()]
    measure = layout['table_1_measurement']
    width = layout['single_column_widths_pt']['Table 5']
    parts = [
        '<div class="eyebrow">HYBRIDGUARD · TABLE DESIGN · 2026-10-22</div>',
        '# 六张表的视觉化与紧凑版式已完成',
        '<div class="status">六表已更新 · Table 5 单栏 · Table 3 / Figure 3 分页 · 主文 8 页 / 全文 10 页</div>',
        '本轮根据用户给出的研究表格示例，采用分组、定义明确的符号和紧凑标签改善阅读。变更集中在表格表达及浮动体位置；正文、已批准的 A1/A2/A3/B1、摘要、实验数据与三张冻结图保持。',
        '## 1. 六张表的实际变化', '\n'.join(rows),
        '## 2. 符号的精确定义',
        '| 标记 | 表达的含义 | 使用边界 |\n|---|---|---|\n'
        '| ✓ | 该格所对应的测试修改全部检出 | 不表示模型全面优于另一模型 |\n'
        '| ◐ | 检出一部分修改，0 < d < N | 类别符号，不表示50%；具体比例由旁边的计数确定 |\n'
        '| × | 该格的测试修改零检出 | 不用于断言文献没有某项能力 |\n'
        '| △ | 正常记录出现非零报警 | 仅用于正常报警列，与检测成功分开 |\n'
        '| 深灰 / 浅灰 / 白 | T / F / U | 分别是报警、明确无报警、未知，不把 F 当作真实性或安全性保证 |',
        'Table 5 的每段长度直接取 T、F、U 除以该行状态总数。没有为视觉显眼而扩大 1/144 或 1/117 等微小报警段；旁边保留完整三元数。No-cap 的全深灰条表示这组正常记录全部报警。',
        '## 3. 紧凑性与版面结果',
        f'Table 1 的六条主体记录全部为单行。首末横线之间的表体高度由 {measure["before_height_pt"]:.2f} pt 降至 {measure["after_height_pt"]:.2f} pt，减少 {measure["reduction_percent"]:.1f}%。这个比例只比较表体，不把新增的证据图例或 caption 混入；完整的证据定义仍在表下可见。Table 2 的八条主体记录也全部为单行。',
        f'Table 5 已从双栏浮动体改为单栏。最终 PDF 中它与 Table 6 的横线实测宽度同为 {width:.2f} pt。Cohort 组名与 N 移至组标题，减少重复列；数值下方的短条保留 T/F/U 组成关系。',
        'Table 3 保留在第6页，Figure 3 移至第7页。第6页表格下方有 RQ1/RQ2 正文，第7页图下方有 RQ2/RQ3/RQ4 正文，解决了原先表与图连续堆叠的问题。',
        '\n'.join(positions),
        '通过精简表头和重复表注，最终仍为8页主文、10页全文。正文和表体继续使用既有 ACM 字体、字号、行距与页边距；新表注统一为表注字号，没有通过缩小正文或冻结图补空间。',
        '## 4. 数据和冻结内容核验',
        '独立核验逐项对照了六表旧版与聚合 CSV。Table 3 的30个方法格、recipe 权重、各方法差值与加权总量保持；Table 4 的七项检查和所有分母保持；Table 5 的八组三状态整数及配置边界保持；Table 6 的检测和正常报警计数保持。',
        '19份 Markdown 输入、9份聚合 CSV、9份冻结图资产及相关锁定/批准记录与上一轮逐字节一致。摘要仍为已提交的257词、三段文本；A1/A2/A3/B1 保留，B2 未应用。图注与十五条参考文献保持。',
        '## 5. 版式检查与源码重编',
        '最终10页经过逐页渲染检查：未见裁切、文字或符号重叠、数字错列及图例缺失。编译没有 overfull、缺字、未解析引用或待重跑交叉引用。既有匿名审稿配置的 ACM reference-format 提醒保留。',
        '源码包另行解压到全新的临时目录，执行默认 Markdown 迁移与 matrix 编译；结果仍为8页主文、10页全文，全部10页提取文本与120 dpi RGB渲染像素逐页一致，48个实际编译和迁移输入在重编前后及当前版本的哈希一致。具体结果见 `qa/package_rebuild_check.md/json`。最后仅补齐报告和核验记录，已测试的论文编译输入保持一致。',
        '## 6. 使用新版',
        '阅读新版 `HybridGuard_layout_v1_matrix.pdf`。将 `HybridGuard_LaTeX_v1.zip` 导入 Overleaf 时，选择 `main_matrix.tex` 为 Main document，编译器选择 pdfLaTeX。表格可直接在 `tables/` 修改；符号和精确比例条由 `table_visuals.tex` 统一定义。',
        '当前报告记录表格改版。上一轮关于 A1/A2/A3/B1 的落实与审读记录保存在 `reviews/history_v3/`，其中页码和哈希仅对应当时版本。本轮没有进行新的实验、采集或模型拟合，也没有更新投稿平台。',
        f'本报告绑定的 PDF SHA-256：`{sha}`。',
    ]
    md = reviews / 'final_read_assessment.md'
    md.write_text('\n\n'.join(parts) + '\n')
    html = reviews / 'HybridGuard_final_read_assessment.html'
    subprocess.run(['pandoc', '--from=gfm', '--to=html5', '--standalone', '--embed-resources',
                    '--metadata=pagetitle:HybridGuard · 表格改版与核验', '--metadata=lang:zh-CN',
                    '--css=' + str(ROOT / 'source/assessment.css'), str(md), '-o', str(html)], check=True)
    target = ROOT.parent / 'output/review/HybridGuard_final_read_assessment.html'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(html.read_bytes())
    print(json.dumps({'report': str(target), 'pdf_sha256': sha}, ensure_ascii=False))


if __name__ == '__main__':
    main()
