#!/usr/bin/env python3
"""Build the approval-to-application report from the stable manuscript and QA."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import fitz

ROOT = Path(__file__).resolve().parent.parent


def read_json(relative):
    return json.loads((ROOT / relative).read_text())


def main():
    base = read_json('reviews/history_v2/final_read_assessment.json')
    approval = read_json('notes/APPROVED_EDITS.json')
    reader = read_json('reviews/approved_content_review.json')
    integrity = read_json('qa/approved_integrity_check.json')
    layout = read_json('qa/approved_layout_check.json')
    rebuild = read_json('qa/package_rebuild_check.json')
    for check in [reader, integrity, layout, rebuild]:
        assert 'PENDING' not in check['status'].upper(), check['status']
        assert 'PASS' in check['status'].upper(), check['status']
    pdf = ROOT / 'build/matrix/HybridGuard_layout_v1_matrix.pdf'
    pdf_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    for check in [reader, integrity, layout, rebuild]:
        assert pdf_sha in json.dumps(check, ensure_ascii=False), 'QA must bind the final PDF hash.'
    aux = pdf.with_suffix('.aux').read_text()
    labels = {m[0]: {'number': m[1], 'page': int(m[2])}
              for m in re.findall(r'\\newlabel\{([^}]+)\}\{\{([^}]*)\}\{([0-9]+)\}', aux)}
    doc = fitz.open(pdf)
    main_pages = labels['marker:main-text-end']['page']
    assert main_pages == 8 and len(doc) <= 12
    compact = [re.sub(r'\s+', '', re.sub(r'(?<=\w)[-\u00ad]\n(?=\w)', '',
                                       p.get_text())).replace('\u00ad', '') for p in doc]
    anchors = {
        'A1': ['Semantic coverage counts distinct'],
        'A2': ['The same-Web comparator flags'],
        'A3': ['S0 is the frozen', 'The four-view diagnostic uses'],
        'B1': ['ActivityManager.MemoryInfo.totalMem'],
    }
    sections = {'A1': '§3.4：semantic coverage / quality',
                'A2': '§3.4：same-Web viewport 对照',
                'A3': '附录 A.3：资源条件、四视图与批次划分',
                'B1': '§3.3：Native memory 观测口径'}
    applied = []
    for item in base['candidates']:
        if item['id'] not in approval['approved_ids']:
            continue
        pages = sorted({i + 1 for needle in anchors[item['id']]
                        for i, text in enumerate(compact)
                        if re.sub(r'\s+', '', needle) in text})
        assert pages, item['id']
        applied.append(dict(item, applied=True, status='APPLIED_AND_VERIFIED',
                            pages=pages, location_text=sections[item['id']]))
    floats = [('Table 2', 'tab:materials'), ('Table 3', 'tab:app'),
              ('Figure 3', 'fig:mechanisms'), ('Table 4', 'tab:specialists'),
              ('Table 5', 'tab:normals'), ('Table 6', 'tab:paired')]
    before = read_json('qa/history_v2/layout_polish.json')['after_matrix_float_pages']
    record = {
        'date': '2026-10-22', 'status': 'APPROVED_EDITS_APPLIED_AND_VERIFIED',
        'approved_ids': approval['approved_ids'], 'paper_text_edits_applied': True,
        'applied': applied, 'not_applied': ['B2'],
        'word_counts': {'main': 91, 'appendix': 86, 'total': 177},
        'pdf': {'name': pdf.name, 'sha256': pdf_sha, 'main_pages': main_pages,
                'total_pages': len(doc), 'labels': labels},
        'previous_assessment': 'reviews/history_v2/final_read_assessment.json',
        'previous_pdf_sha256': base['pdf']['sha256'],
        'verification_reports': ['reviews/approved_content_review.json',
                                 'qa/approved_integrity_check.json',
                                 'qa/approved_layout_check.json',
                                 'qa/package_rebuild_check.json'],
        'source_package_verification': {
            'status': rebuild['status'],
            'tested_bundle_sha256': rebuild['tested_bundle_sha256'],
            'compile_input_count': rebuild['compile_input_count'],
            'all_page_texts_equal': rebuild['all_10_page_texts_equal'],
            'all_page_pixels_equal': rebuild['all_10_page_pixels_equal'],
        },
        'author_facts': {
            'MTC_use_and_public_dataset_permission': 'Explicitly confirmed by the author in the conversation.',
            'institution': 'Beihang University',
            'ethics': 'Author understands there is no applicable review requirement; no formal approval, exemption, or institutional determination is asserted.',
            'scope': 'Updated notes only; no additional data-collection, ethics, or artifact-availability text added to the manuscript.',
        },
    }
    rev = ROOT / 'reviews'
    (rev / 'final_read_assessment.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    table = ['| 编号 | 已落实内容 | 新版位置 | 新增英文词数 |', '|---|---|---|---:|']
    for item in applied:
        pages = '、'.join(map(str, item['pages']))
        table.append(f'| {item["id"]} | {item["location_text"]} | 第 {pages} 页 | {item["net_added_words"]} |')
    float_rows = ['| 图表 | 上轮版式版 | 本轮修改版 |', '|---|---:|---:|']
    for name, key in floats:
        float_rows.append(f'| {name} | 第 {before[key]} 页 | 第 {labels[key]["page"]} 页 |')
    parts = [
        '<div class="eyebrow">HYBRIDGUARD · APPROVED EDITS · 2026-10-22</div>',
        '# A1、A2、A3、B1 已落实并核验',
        f'<div class="status">已通过的 4 项修改全部落稿 · 主文 {main_pages} 页 / 全文 {len(doc)} 页 · 摘要与三张图继续冻结</div>',
        '本报告记录本轮经用户明确批准的修改。此前的“建议尚未应用”评估保存在 `reviews/history_v2/`，其页码与 PDF 哈希仅对应上一轮版本。本轮没有把未批准的 B2 或其他文字建议一并加入。',
        '## 1. 实际修改', '\n'.join(table),
        '主文新增 91 个英文词，附录新增 86 个英文词，共 177 词。只有方法节和附录的输入稿发生文字变化；去掉四项新增句子后，两份输入稿均可逐字恢复上一轮原文。数学变量沿用原稿形式，API 名采用等宽字体。',
        '## 2. 已加入论文的句子',
    ]
    for item in applied:
        parts += [f'### {item["id"]} · {item["title"]}',
                  '**位置：** ' + item['location_text'] + '，第 ' + '、'.join(map(str, item['pages'])) + ' 页。',
                  '\n\n'.join('> ' + paragraph for paragraph in item['proposal'].split('\n\n')),
                  '**修改前的问题：** ' + item['assessment']]
        if item['id'] == 'B1':
            parts.append('论文中 `m_native` 和 `m_web` 已排成现有公式的数学变量；`ActivityManager.MemoryInfo.totalMem` 与 `deviceMemory` 保持 API 拼写。')
    parts += [
        '## 3. 版式与编译结果',
        f'最终 PDF 的主文在第 {main_pages} 页结束，全文 {len(doc)} 页。四项新增文字完整保留，所有图片尺寸、字体、字号、页边距和行距沿用上一轮。矩阵版沿用上一轮的浮动体登记位置；本轮调整 Table 1、Table 2 的局部列宽，并让 Table 3 和 Table 6 的表头以单行显示，其中 Table 6 同步重分配列宽。所有表头用词、图注与数值保持原样。B1 定义与其后原有内存说明排在同一段。具体测量与检查见 `qa/approved_layout_check.md`。',
        '\n'.join(float_rows),
        '## 4. 核验范围',
        '- **修改范围：** A1、A2、B1 各出现一次，A3 的两个定义段各出现一次；没有额外改写原有句子。\n- **冻结摘要：** 保持旧 draft 的 257 词、三段原文；源码与 PDF 提取结果均已核对。\n- **图表与数据：** 三张图的 9 份冻结资产、图注、CSV 数据和参考文献保持原字节；表格可见文字与数值不变，局部列宽等版式差异单列核验。\n- **结果：** 没有新增实验、采集、拟合或预测；没有改变已有检测/报警数字。\n- **页面：** 最终 PDF 经渲染检查；交叉引用和参考文献解析状态见版式核验记录。',
        '## 5. 作者事实与本轮边界',
        'MTC 的研究使用、论文分析/发表与公开数据集等权限已按用户明确确认记录为允许。所属机构记录为北京航空航天大学；“据作者了解没有相关伦理审查要求”保留为作者当前了解，没有扩展为正式批准、豁免或机构认定。',
        '这些更新保存在 `notes/AUTHOR_FACTS_TO_CONFIRM.md`。本轮正文修改仍限定在 A1、A2、A3、B1，没有额外增加采集日期、授权/伦理声明或匿名制品入口表述。B2 继续保持未应用。',
        '## 6. 可编辑来源',
        '源码包以 `main_matrix.tex` 为本轮已核验的编译入口。`input_markdown/` 保存批准后的输入文字，`sections/` 保存已生成且可直接编辑的 LaTeX。默认迁移流程与包内表格文件共同重现本轮文字、表格版式与浮动体安排。上一轮审读及版式记录已明确归档，避免把历史结论误当作当前状态。',
        '源码 ZIP 已解压到全新临时目录，按默认流程执行迁移与编译。重编结果仍为 8 页主文、10 页全文，全部 10 页提取文本与 120 dpi 渲染像素均与交付 PDF 一致。59 个编译及迁移输入文件的哈希在迁移前后保持一致。测试完成后补齐审读与修改落实记录；最终打包保留这 59 个已测试输入。详见 `qa/package_rebuild_check.md`。',
        f'本报告绑定的 PDF SHA-256：`{pdf_sha}`。',
    ]
    md = rev / 'final_read_assessment.md'
    md.write_text('\n\n'.join(parts) + '\n')
    html = rev / 'HybridGuard_final_read_assessment.html'
    subprocess.run(['pandoc', '--from=gfm', '--to=html5', '--standalone', '--embed-resources',
                    '--metadata=pagetitle:HybridGuard · 已批准修改落实记录', '--metadata=lang:zh-CN',
                    '--css=' + str(ROOT/'source/assessment.css'), str(md), '-o', str(html)], check=True)
    target = ROOT.parent / 'output/review/HybridGuard_final_read_assessment.html'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(html.read_bytes())
    print(json.dumps({'html': str(target), 'pdf_sha256': pdf_sha, 'main_pages': main_pages,
                      'total_pages': len(doc), 'applied_ids': approval['approved_ids']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
