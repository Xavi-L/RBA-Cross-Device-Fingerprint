# 方法总图：参考论文风格样稿

这一版以用户提供论文第5页的图1为视觉参考：横向结构、浅色圆角分组、细线图标、虚线阶段框、蓝色编号和衬线字体。图标与SVG均为本项目重新绘制，未复制参考论文图像。图中文字使用英文，便于继续用于论文；SVG保留可编辑文字与独立图形分组。

- `HybridGuard_overview.svg`：180 × 89.2 mm的可编辑矢量稿。
- `HybridGuard_overview.png`：同一SVG的预览。
- `build_overview.py`：仅生成SVG，不导入实验入口。
- `render_preview.cjs`：用现有Sharp渲染同一SVG为3600 × 1784 PNG。

本稿对应现有F00的方法总览，作为视觉方向样稿单独保存，未替换原图、选图册或制图清单。未新增采集、训练、模型选择、预测或计时，未改统计结果。

## 图注

**中文。** HybridGuard的方法与现有评价范围。App包含Native、WebView Host和App Web三个观察位置，独立Browser提供另一端网页观察；同设备观测通过已保存会话与回执关联。开发阶段在正常报警、明确输出覆盖和复杂度约束下固定App规则，再冻结App并接受跨端时区C1。当前记录按所选App-only或paired接口，结合已加载固定模型输出T、F或U；选中依赖的执行或绑定错误优先输出FAILED。Host几何与资源条件仍属单独研究分支。底部列出既有评价范围，历史MTC144/117不进入图中的MTC630训练部分，也不代表独立盲测。

**English.** Overview of HybridGuard. Three App observation locations and an independent browser provide same-device fingerprint views. Development fixes App rules under alarm, defined-output, and complexity constraints, then freezes the App model and accepts the cross-endpoint timezone relation C1. A current App record or bound pair is processed through its chosen fixed-model interface. T, F, and U denote alarm, no alarm, and insufficient evidence; execution or binding errors in selected dependencies take precedence as FAILED. Host-geometry and resource checks remain separate studies. The lower strip summarizes saved evaluation scopes; historical MTC evaluation is separate from selection and is not a blind test.

**阅读边界。** App177/Browser67/paired244是目录视图数量，非每条输入完整性的保证。Native/Host并非可信真值。绑定ID不作检测特征，当前判定不使用pre/change/post标签。需要的Browser观测缺失不自动回退为App-only或F。

## 内容依据

仅压缩既有说明，不重新推断实验结果：`../round3_overview/F00_source.json`、`../round3_overview/F00_main_source.json`、`../round3_overview/CAPTIONS.md`，以及`../../../deliverables/cross_endpoint_constrained_extension_v1/PROTOCOL.md`和`inference.py`。视觉参考文件为仓库根目录的`_WWW__Lower_Barriers__Greater_Threat_.pdf`，图1（第5页）。

## 预览检查

2026-10-09：打开最终渲染检查文字、分组、图标与连线；未发现文字重叠或裁切。SVG文字保持文本，未包含栅格图像或外部资源。此记录仅表示样稿的视觉检查，不表示导师或论文定稿验收。
