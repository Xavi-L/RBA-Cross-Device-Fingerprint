# 导师选图册

**可供导师选图，待提纲对应。** [ADVISOR_FIGURE_BOOK.pdf](ADVISOR_FIGURE_BOOK.pdf)共22页：导读、可点击目录、14类图稿（含F00正文候选），以及T01范围、T02主结果、T05四页成本选读。F00两个版式共用一个素材ID；F10仅表格，F11未制作。正文/附录标注是候选建议，不是定稿。

事实基线为`7ae5bc1d71233d141d29b3ca48172a31108a1f11`。证据与未改图稿链接固定该提交；F00_main、修正后的F09及第三轮当前图注是本地修订，PDF中的相对链接需随仓库目录一起打开，并未冒充已推送文件。页内矢量图、中文说明和表格独立嵌入；[PAGES.json](PAGES.json)记录稿件版本、源摘要、原图尺寸、页码与链接，[CHECK.json](CHECK.json)记录结构和实际视觉范围。

F09只将未整合对象限定为新Host几何，旧高度仍用于APP_FULL 01/02；CSV、SUMMARY和状态不变。F00正文候选用8个主框和1个旁注，将测量输入、固定模型加载和选择约束分开，历史MTC评价依赖放在图注；[详细说明版](../round3_overview/figures/F00.svg)保持原样。所有数值来自保存表，无采集、拟合、选择、条件评价、预测或重新计时。

## 生成与仅检查

在仓库根目录执行，使用现有Codex文档运行时，不升级研究环境：

```bash
/Users/xavier/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B paper/figures/review_pack/build_book.py
```

仅检查现有PDF、源摘要、顺序、字体、文字和本地链接目标；不绘图、不联网、不导入实验入口、不写文件：

```bash
/Users/xavier/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B paper/figures/review_pack/build_book.py --check-only
```

生成器读取[轻量内容源](book_content.json)、已有SVG和CSV；[Python组版与检查](build_book.py)与[本地打印辅助](print_book.cjs)采用一种HTML/CSS → 无界面Chrome矢量PDF路径。现有Python环境没有SVG转换库，因此直接使用已有Chrome的SVG打印能力；无SVG转换失败、无PNG回退、不生成截图拼图。pypdf只处理版本明确的相对链接、文档元数据及检查。Chrome使用临时独立配置，不访问用户浏览器会话，页面网络请求被禁用。

依赖为现有Node/playwright-core、Chrome、pypdf；`RBA_NODE`、`RBA_NODE_MODULES`、`RBA_CHROME`可指定已有安装。中文使用本机Arial Unicode TrueType，原SVG使用现有绘图环境的DejaVu Sans；字体嵌入PDF，少数符号由Type3嵌入字形及ToUnicode处理，不依赖阅读者字体。可用`RBA_CJK_FONT`指定其他可嵌入中文TrueType；不复制字体文件到仓库。

生成只覆盖自身PDF/PAGES/CHECK，未知归属拒绝覆盖；不会调用前三轮制图器或改写数据。PNG/SVG若有修改须独立重导出并检查，再生成册子；PDF字节改变会清空其视觉通过状态。中间HTML与PDF使用临时目录，页面校样不入仓库。

## 检查范围

全部图采用原始毫米尺寸；F03b和F05a维持85 mm宽，其余180 mm宽，图中文字不缩小。正文/表格至少9 pt；原图至少8 pt。目录包含全部14类图和6个表格页面的20个内部跳转，证据/图稿链接另外检查目标存在和版本，未做联网可达性验证。

视觉校样用Poppler逐页渲染为96 dpi（100%屏幕尺寸近似），逐页检查标题、图面、中文、表格分页、页脚和链接位置；另打开F00_main/F09最终PNG及96 dpi图稿。SVG在PDF中的矢量渲染和尺寸单独登记，不能以PNG通过替代。物理打印未检查。最终实际检查状态与所绑定摘要以[CHECK.json](CHECK.json)及[F00_main记录](../round3_overview/F00_main_MANIFEST.json)为准。

停止于选图材料；未提交、未推送。下一步等待导师提纲/选图意见。
