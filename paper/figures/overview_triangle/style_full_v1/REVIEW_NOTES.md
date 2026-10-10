# HybridGuard 完整视觉候选稿 v1

**一个完成的推荐候选稿，等待用户检查。** 内容沿用当前完整正式图；视觉继承提交 `1b536b611690df44db3bebc4812bfab220887362` 的三角样块。正式目录、`style_pilot_v1` 和正式 LaTeX 预览未覆盖；没有运行研究实验或自动提交推送。

## 交付

- [完整 SVG](HybridGuard_overview_candidate.svg)、[PNG](HybridGuard_overview_candidate.png)、[矢量 PDF](HybridGuard_overview_candidate.pdf)
- [180 mm 预览](previews/actual_180mm_96dpi.png)、[同宽同透明度前后对比](previews/before_after_same_width.png)、[96 dpi 前后对比](previews/before_after_180mm_96dpi.png)
- [三角](previews/triangle_detail.png)、[几何说明](previews/geometry_detail.png)、[Browser](previews/browser_detail.png)、[Offline](previews/offline_detail.png)、[检测区](previews/detection_detail.png)、[时区旁注](previews/timezone_detail.png) 的局部细节
- [灰度预览](previews/grayscale_180mm_96dpi.png)、[实际 PDF 渲染](previews/pdf_180mm_render.png)、[唯一参考同宽对照](previews/reference_same_width.png)
- [候选文案](COPY.md)、[中英文图注](CAPTIONS.md)、[图标来源](assets/SOURCES.md)及 [MIT 许可](assets/tabler/LICENSE)
- [SVG 生成入口](build_candidate.py)、[PNG/比较预览入口](render_candidate.cjs)、[Chrome 检查和 PDF 入口](render_pdf_and_check.cjs)、[检查结果](CHECK.json)

## 继承与完成的统一设计

三份主对象矢量及其缩放直接继承样块：手机与系统设置、外壳包含内页、JS 折角页面。文字仍在图形旁侧，浅色主要衬托对象，保留衬线字体、原类别底色、深色轮廓及三处红字。补充素材只来自同一固定 Tabler 版本。

右侧两个标签整体向内移动，保持原字号。System–web consistency 与 App Web 名称到 App 右边界分别约 **32.2、38.1 单位**（3.22、3.81 mm），原样块相应约 14.2 单位。几何说明移至虚线上方的独立文字带，末行与两侧节点名称的文字边界间隔 **27 单位**；短引线连接底边，不加标签卡片。正文说明和未集成状态完整保留。

为使去掉卡片后的关系端点归属于整个对象，增加轻量、开放的对象括线：Native 下侧、Host 上/右侧、App Web 上/左/下侧、Browser 左/下侧。比较边落在这些括线上；括线不承担状态编码，线宽 1.2，明显轻于关系线与对象轮廓。主对象和文字仍保持开放组合，没有恢复原来的小图标文本卡片。

同设备外框向下包入 Browser，App 虚线框只包住前三个观察位置。Browser 以浅青窗口为主对象，保留全部三行说明；蓝色时区比较跨过 App 边界，两个端点仍在同设备内。时区例子放在设备框外，以轻括号组织两组原有句子；没有添加不能帮助理解的图标、时间箭头或安全标记。

Offline 改为“材料对象 → 选择模块 → 规则产物”：条件清单和记录集合分别输入紧凑浅紫处理模块；四项目标不配完成标记。Selected rules 作为单独规则文档，从独立端口加载到当前检测区。浅紫集中于对象和处理操作，外层保持白底。

检测区继承上下替代模式和 `or`，各自保留对应规则，当前数据与规则分开进入。仅有一条共同结果箭头，研究评价条带不接入流程。全部区域正常显示，没有淡化旧区或把样块作为整张图片拼接。

## 尺度、检查与范围

完整 SVG 为 **180 × 133 mm**，宽度维持通栏基准；高度较正式稿的 125 mm 增加 8 mm，用于完整对象、几何说明和连接通道的整体排布。正文仍为 28–29 单位（约 7.94–8.22 pt），未缩小字号或压缩字形。PNG 为 3600 × 2660 px，508 dpi；96 dpi 整图预览宽 680 px。显示器上的实际毫米大小取决于查看器缩放。

| 检查 | 实际结果与边界 |
|---|---|
| 内容回归 | 55 个正式正文条目逐项保留，两段中英文图注原文保留。仅做冻结内容与结构回归，没有重新审计研究或扩写能力。 |
| 范围与关系 | 三点在 App 内、Browser 在 App 外且同设备内，Offline 与旁注在设备外；四条关系状态保持。灰边无箭头，未集成几何说明保留。 |
| 当前与开发流 | 两类开发输入独立进入选择；当前数据绕过 Offline；两种模式没有互连、回退或预测融合；固定规则单独输入，一个结果路径。 |
| 排版 | 查看完整论文宽度图、同宽比较、局部放大，检查标签归属、端点括线、图标主次、折角、内边距。Chrome 检查无文字交叠、无主连线穿字或越界。 |
| 灰度 | 实际查看 180 mm 灰度图；实线/虚线/点线与状态文字共同保留区别，不只靠颜色表达。Host 小 JS 继续是辅助细节。 |
| 可编辑输出 | SVG 无嵌入栅格、无嵌套完整 SVG、无重复 ID 或缺失 marker；没有阴影、渐变或文字压缩。PDF 为一页矢量输出，实际重渲染查看；正文可提取，未嵌入栅格图像。 |
| 源文件保护 | 五个正式文件与制作前副本一致，已提交样块未变；当前所有新增图稿、资源、脚本和说明仅在本候选目录。 |

矢量 PDF 由 Chrome 按 180 × 133 mm 页面导出，实际页面约 **179.92 × 133.01 mm**，差异来自导出单位取整。实际 PDF 渲染已查看；未修改论文模板。尚未进行纸质打印、外部读者识别测试或导师验收，不能据此声称可直接投稿。

## 再生成

从仓库根目录执行以下三个入口，均只输出到本目录：

```sh
python3 -B paper/figures/overview_triangle/style_full_v1/build_candidate.py
node paper/figures/overview_triangle/style_full_v1/render_candidate.cjs
node paper/figures/overview_triangle/style_full_v1/render_pdf_and_check.cjs
```

依赖为已配置的 Sharp、Playwright 和本机 Chrome。可用 `RBA_NODE_MODULES`、`RBA_CHROME` 指定路径。生成入口不导入旧绘图脚本，不调用研究模块；旧图比较和文案回归读取 `baseline/` 的本轮只读快照。PDF 渲染预览由 Poppler 从实际候选 PDF 生成。
