HybridGuard WWW 英文草稿 — 第一轮全文统稿，2026-10-18

当前标题：HybridGuard: Cross-Layer Consistency as Integrity Evidence for Android Web Environments
阅读：HybridGuard_WWW_Draft.pdf
Overleaf 上传包：HybridGuard_WWW_Overleaf.zip
主文件：main.tex；编译器：pdfLaTeX。
本地编译：latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
Overleaf 包解压后也可直接运行：latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

本轮隔离构建的实际篇幅为 11 页：正文第 1–9 页，参考文献第 10 页，附录第 11 页。
采用现有 ACM sigconf/anonymous/review 排版；本轮未核验投稿页数要求，不据此声明满足投稿限制。
未修改模板、字体、页边距、行距或分页设置。保留 review 行号；新标题由 LaTeX 自然排版。
编译正常完成，引用已解析。日志仍有基线中已有的 Abstract 1.47083pt overfull hbox，以及隐藏出版用 ACM reference block 导致的非致命 class warning；未新增这两类问题。分页日志另有 underfull vbox 提示；逐页检查未见遮挡或孤立标题。第 9 页右栏留白，参考文献仍按原有设置另起一页。

正文围绕跨层语义一致性何时能为 Web 可见环境报告提供完整性证据展开，包含摘要、引言、问题定义、方法、四项研究问题、讨论、相关工作、结论及复现附录。
本轮仅统一标题、术语、衔接和研究表述，并删减重复内容；方法、判据、参数、模型与结果保持不变。

图表沿用已接受的材料：
1. overview_triangle/style_full_v1 的 overview 矢量 PDF；
2. 01 合并消融矩阵；
3. 02 跨层参照机制表；
4. 03 正常约束表；
5. 04 双端扩展表。
四张表格的源文件、保存数据、分组、颜色及数字未修改；overview 与附录未修改。

实验与主张边界：
- 三个核心观察面是 Android Native、WebView Host 和 App Web；external Browser 是另一执行上下文的扩展。
- Full App 同时包含视图内与跨视图检查；105/126、0/252 仅限所述受控主实验。
- 三组固定检查保持各自的专项身份；Host geometry 未集成进 Full App。
- 891 是历史代表记录，不是 891 台独立物理设备；历史材料有开发使用历史，历史评价记录不提供阈值。
- 保留正常报警、未知、执行失败、漏检与未通过准入的结果；无报警不证明真实。
- Full App+C1 是保留的跨端扩展；C1 不含 timestamp gate。
- Native 与 Host 不构成可信根；现有证据不建立独立设备攻击泛化或生产部署成效。
- 现有研究文档未建立伦理审查、豁免或参与者同意状态；最终声明仍需作者提供记录。

保存计数核对：python3 tables/verify_tables.py
在原研究仓库交叉核对：python3 output/pdf/hybridguard_www_draft_20261017/tables/verify_tables.py --repo .
该脚本只核对保存计数与分组，不执行检测器。本轮未启动采集、拟合、规则选择、预测或性能计时；核对通过不等于重新验证实验效力。

交付检查包括全部 11 页的渲染检查、ZIP 内文件与当前源文逐字节比较，以及独立解压后的重新编译。README 中页数以本轮构建为准。
qa/ 与 notes/ 保留历史检查和研究记录，未在本轮更新，不代表本轮验证结论，也不打包到 Overleaf。
Overleaf 包仅包含编译所需文件及汇总级表格数据，不包含原始设备载荷、配对票据、稳定设备标识或参考论文 PDF；该包的范围不等于整个仓库的内容范围。
