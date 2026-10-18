HybridGuard WWW 英文完整草稿 — 2026-10-17；首创性措辞修订 2026-10-18

阅读：HybridGuard_WWW_Draft.pdf
Overleaf 上传包：HybridGuard_WWW_Overleaf.zip
主文件：main.tex；编译器：pdfLaTeX；建议 TeX Live 2025 或更新。
本地编译：latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex

当前为匿名审稿排版草稿：主文 7 页、参考文献 1 页、附录 1 页，共 9 页。
采用 WWW 2027 Research Track 已公布的 ACM sigconf/anonymous/review 格式：主文上限 8 页，总 PDF 上限 12 页。
官方依据：https://www2027.thewebconf.org/research-track-papers/
未修改 acmart.cls 的版心、字号或行距。保留 review 行号；隐藏出版用 ACM reference block 会产生一条预期 class warning，不影响编译或文献引用。

正文已完整撰写摘要、引言、背景/威胁模型、方法、四项实验、讨论/局限/伦理、相关工作、结论及复现附录，非旧稿插图预览。
依据 paper/EXPERIMENT_OUTLINE.md 与当前保存实验结果。未修改 Abstract.md 或原提纲。

图表仅用：
1. overview_triangle/style_full_v1 的现有 overview 矢量 PDF；
2. 10/16 已接受的 01 合并消融矩阵；
3. 10/16 已接受的 03 正常约束表；
4. 10/16 已接受的 02 设备参照机制表；
5. 10/16 已接受的 04 双端扩展表。
四项结果素材转为原生可编辑英文 LaTeX 表，保留原分组、相邻同值合并、配色语义、分母和负面结果；未替换原 SVG/PNG。

实验与主张边界：
- 105/126、0/252 仅限所述受控主实验。
- 891 是历史代表记录，不是 891 台独立物理设备。
- 保留 MTC 未知、无报警上限时全部报警、WebGL/webdriver 漏检及语言漏检。
- Host 几何仍是专项条件，未接入完整 App；C1 不含时间同步门槛。
- 现有材料有开发使用历史；未称新盲测、普遍泛化或生产风控效果。
- 保留“据我们所知，首次明确建模 Native—WebView 宿主—App Web 三观测面互证”的限定性框架主张；不称首次指纹一致性检测，不暗示三端所有关系已联合进入完整模型。
- 没有补造伦理审批、豁免或参与者同意记录；正式提交前需作者确认适用要求。

没有运行采集、训练、模型选择、预测或计时。表格校验仅核对已保存的计数。
本地数字检查：python3 tables/verify_tables.py
可选：具备原研究工作区及其素材数据时，在仓库根目录交叉检查：python3 output/pdf/hybridguard_www_draft_20261017/tables/verify_tables.py --repo .

QA：全部 9 页已渲染并查看；无文字溢出、未解析引用或缺字。详见 qa/CHECK.json。
notes/ 保存证据索引、方法实现审查、文献核验与格式依据，不打包到 Overleaf。
Overleaf 包包含编译所需文件及汇总级表格数据，不包含原始设备载荷、配对票据或私密标识；包已在独立临时目录解压重编译。

原 2026-09-03 Overleaf ZIP 当前无法正常读取，未尝试覆盖修复。模板从项目中可用的 HybridGuard_triangle_template_preview 副本取得。
本次交付只涉及此新目录，提交范围不含原论文、实验、图表源文件和其他本地改动。
