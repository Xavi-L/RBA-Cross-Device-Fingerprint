# HybridGuard 方法总览：事实准确性修订

2026-10-09，基于 `197dd608b47db3222dc2ef0f3f1b7b294cc94a38` 的 overview 样稿修订。内容对应仓库已实现的研究方法及保存结果，适用于当前 Method Overview 的导师审阅；本图不提供新的实验或泛化证据。

保留原有横向三阶段、配色、细线图标、衬线字体和虚线分组。视觉参考仍为用户提供的 `_WWW__Lower_Barriers__Greater_Threat_.pdf` 图1（第5页）；本轮不重新设计风格。图标与 SVG 为本项目绘制，未复制参考论文图像。

- [HybridGuard_overview.svg](HybridGuard_overview.svg)：180 × 92 mm，`viewBox="0 0 1800 920"`，文字可编辑。
- [HybridGuard_overview.png](HybridGuard_overview.png)：由同一 SVG 生成的 3600 × 1840 预览。
- [build_overview.py](build_overview.py)：只生成 SVG，不导入研究训练、选择或推理入口。
- [render_preview.cjs](render_preview.cjs)：沿用 Sharp 渲染；从 viewBox 读取尺寸，只在渲染缓冲区改为像素单位，SVG 文件保留物理尺寸。

相比原稿 180 × 89.2 mm，宽度不变，高度增加约 3.1%。正文为 29 viewBox 单位，在 180 mm 宽度下约 8.22 pt；最小的 28 单位仅用于阶段编号和状态字母，约 7.94 pt。建议按双栏通栏宽度使用；继续缩小需要重新检查可读性。

## 中文图注

**HybridGuard 的多视图观测、离线规则开发与当前记录判定。** Native、WebView Host 与 App Web 组成 App177 目录视图，独立 Browser 提供 Browser67；同设备记录经会话与回执关联形成 paired244 目录视图。目录数量不保证逐条完整，也不表示全部字段入模或各观察位置有独立判别贡献。离线开发使用已有开发数据，在正常报警预算、T/F 明确输出覆盖率及模型复杂度约束下，进行 App SPARSE 选择与后续 RETENTION 信号保留/质量替换；固定 App 模型已包含 Native–App Web 内存关系。冻结 App 后，在四个预定跨端集合中按宏平均检出率进行受约束选择，最终选入比较 App Web 与独立 Browser 数值 UTC offset 的 C1。新 Host 几何关系已单独研究但未集成；Browser 资源扩展经过受约束选择，没有新增条件获准加入。当前 App 观测与当前已关联配对分别进入 App-only 和 paired 接口，绕过离线开发，并使用各自加载的固定模型；paired 不自动退回 App-only。T 表示操纵报警，F 表示未报警，U 表示证据不足；选中依赖的执行或绑定失败优先传播为 FAILED。配对不保证原子同步，绑定 ID 不是检测特征，推理不使用攻击/正常、阶段、未来恢复或训练/测试身份标签。底部为已保存评价范围，其中历史 MTC 的 144 + 117 是记录数量，与开发正常数据 MTC630 分开，不构成新的独立盲测。

## English caption

**HybridGuard: multi-view observations, offline rule development, and current-record decisions.** Native, WebView Host, and App Web form the App177 catalog view; an independent Browser67 view is associated through same-device sessions and receipts to form paired244. Catalog counts do not imply complete inputs, use of every field, or independent contributions from every observation location. Offline App development applies SPARSE selection followed by RETENTION signal retention and quality replacement under normal-alarm, defined-output coverage, and complexity constraints. The fixed App models include the Native–App Web memory relation. With the App model frozen, constrained selection over four prespecified cross-endpoint sets maximizes macro detection and selects C1, an App Web–Browser numeric UTC-offset mismatch. New Host geometry was studied but not integrated; constrained Browser-resource selection admitted no additional condition. Current App observations and current bound pairs bypass development and enter separate App-only and paired interfaces using their respective frozen models, without automatic App-only fallback. T denotes a manipulation alert, F no alarm, and U insufficient evidence; execution or binding failures in selected inputs take precedence as FAILED. Association is not atomic synchronization. Binding IDs, experiment labels, phases, future recovery, and train/test identities are not detection features. The bottom strip summarizes saved evaluations; the 144 + 117 historical MTC records are separate from the 630 development normals and are not a new independent blind test.

## 箭头与接口的读法

| 图例 | 实际含义 |
|---|---|
| 赭色虚线 `Dev. data` | 已保存开发记录进入离线 App 选择或跨端选择。中央输入框概括数据类别，不表示把各研究的成员或分母混成一池。 |
| 蓝色 `Current input` | App 在配对前直接分支至上方 App-only 接口；App 与 Browser 关联后的当前配对沿底部到达 paired 接口。两条路径均不穿过离线开发模块。 |
| 黑色 `Frozen model` / `load` | 已选模型加载至各自推理接口；中间的 `Freeze App` 表示跨端选择使用冻结的 App 基线。每个接口的检查范围由其模型实际选中依赖确定。 |

图中接口是现有研究代码的当前输入接口，不表示已经部署的生产采集、在线训练或风险处置系统。

## 修改前后与核查依据

以下依据包含实际代码、协议、保存模型和选择结果；未仅沿用旧 F00 图注。

| 核查项 | `197dd608` 样稿 | 本轮修正 | 已核查依据 |
|---|---|---|---|
| 已集成内存关系 | “resource checks … not integrated” 范围过宽 | 主流程明确 `Includes Native–App Web memory`；三个固定 App 模型的正向选中子句均含 `MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE` | [候选依赖](../../../deliverables/app177_core_ablation_v1/CANDIDATE_DEPENDENCIES.md#L62)、[消融报告](../../../deliverables/app177_core_ablation_v1/REPORT.md#L107)及下方三份实际模型 |
| 新 Host 几何关系 | 与所有资源关系合并描述 | 独立虚线框标为 `studied, not integrated`，不否认旧内存或同 Web 关系已经存在 | [几何语义](../../../deliverables/screen_geometry_observation_v1/SEMANTICS.md#L3)、[当前 App 候选池](../../../deliverables/app177_core_ablation_v1/REPORT.md#L31)、[旧高度条件边界](../../../deliverables/app177_core_ablation_v1/REPORT.md#L130) |
| Browser 资源增量 | 仅笼统称单独测试、未集成 | `Browser-resource extensions: none selected`；已经做选择，三个配置均保留 App+C1 基线，没有新增资源条件 | [报告](../../../deliverables/app_resource_constrained_extension_v1/REPORT.md#L5)、[保存模型](../../../deliverables/app_resource_constrained_extension_v1/results/models.json)、[24个集合检查](../../../deliverables/app_resource_constrained_extension_v1/results/candidate_checks.json) |
| 当前输入与离线开发 | App-only 缺少直接输入，连线易混淆开发与推理 | 两条独立蓝色绕行路径；开发数据与模型加载分用虚线/黑线 | [App 当前输入入口](../../../hybridguard_agent/research/mtc_timezone_selection.py#L143)、[paired 当前输入接口](../../../deliverables/cross_endpoint_constrained_extension_v1/inference.py#L10)、[App 与 Browser 分开校验](../../../deliverables/browser67_cross_endpoint_diagnostic_v1/run.py#L248) |
| C1 操作数 | `Accept cross-endpoint timezone` 未说明对象 | 明确 App Web–Browser **UTC-offset mismatch**，不画 Native 对 Browser 或时区名称一致性 | [C1 依赖与数值检查](../../../deliverables/browser67_cross_endpoint_diagnostic_v1/conditions.py#L5)、[offset 候选语义](../../../hybridguard_agent/research/mtc_p3_candidates.py#L150) |
| C1 准入过程 | “Accept” 容易暗示无条件加入 | 显示受约束跨端选择、四个预定集合、最终选入 C1 | [协议](../../../deliverables/cross_endpoint_constrained_extension_v1/PROTOCOL.md#L3)、[有限枚举与排序](../../../deliverables/cross_endpoint_constrained_extension_v1/selector.py#L55)、[三份 S1 结果](../../../deliverables/cross_endpoint_constrained_extension_v1/results/models.json) |
| 优化与约束 | 只列出 alarms / output / complexity | 改为预算、覆盖、复杂度；分别显示 App SPARSE 目标、RETENTION 与跨端宏平均目标 | [App 评分](../../../hybridguard_agent/research/rule_learning/selector.py#L162)、[SPARSE/RETENTION 调度](../../../hybridguard_agent/research/mtc_timezone_selection.py#L105)、[RETENTION 实现](../../../hybridguard_agent/research/rule_learning_v2/semantic_selection.py#L242)、[跨端目标](../../../deliverables/cross_endpoint_constrained_extension_v1/PROTOCOL.md#L11) |
| 目录和绑定 | `Host` 与数字容易误读为全部入模；同步界限不明显 | `WebView Host`、`Catalog field counts`、`paired244 (catalog)`；注明非原子捕获、ID 不作特征 | [App 字段目录](../../../android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv)、[Browser manifest](../../../browser_probe_site/public/probe/manifest.json)、[目录视图定义](../../../hybridguard_agent/evidence/paired244.py#L20)、[字段投影与时间诊断](../../../deliverables/browser67_cross_endpoint_diagnostic_v1/run.py#L64) |
| 输出状态 | `Alarm` / `Unknown` 和泛化错误说明不够精确 | `Manipulation alert` / `Insufficient evidence`；只对选中依赖声明 FAILED 优先；paired 无自动 App-only fallback | [核心预测器](../../../hybridguard_agent/research/rule_learning/predictor.py#L24)、[合成状态](../../../deliverables/cross_endpoint_constrained_extension_v1/selector.py#L14)、[缺测/绑定错误](../../../deliverables/browser67_cross_endpoint_diagnostic_v1/conditions.py#L27) |
| 历史 MTC | `MTC: 144 / 117` 容易读成比率 | `Historical MTC: 144 + 117 records`；与离线开发的 MTC630 分开 | [数据角色表](../../../deliverables/app177_core_ablation_v1/REPORT.md#L9)、[跨端开发/历史评价成员](../../../deliverables/cross_endpoint_constrained_extension_v1/PROTOCOL.md#L5) |

已逐份读取的固定 App 模型是以下三个 B_REL_TZ RETENTION 文件，图中的 “fixed App” 指该研究基线，而不是所有历史 App 模型：

| 配置 | 模型 ID | 实际文件 |
|---|---|---|
| 01 | `mtc-rel-tz-6e10284c39b1b601ab406240` | [model.json](../../../deliverables/timezone_relation_validation_v1/trials/B_REL_TZ__WEBGL1-LOEO-v1-01__RETENTION/model.json) |
| 02 | `mtc-rel-tz-9c5fa0e310ba10a00e520b1c` | [model.json](../../../deliverables/timezone_relation_validation_v1/trials/B_REL_TZ__WEBGL1-LOEO-v1-02__RETENTION/model.json) |
| 03 | `mtc-rel-tz-4ae67bb9da899cc419dd525f` | [model.json](../../../deliverables/timezone_relation_validation_v1/trials/B_REL_TZ__WEBGL1-LOEO-v1-03__RETENTION/model.json) |

跨端 `results/models.json` 三份均为 `SELECTED_EXTENSION`、`S1`、`extensions=["C1"]`。资源扩展三份均为 `BASELINE_RETAINED`、`selected_set="S0"`、`extensions=[]`；其24条保存集合检查中仅三条 S0 可行。注意两个阶段的 **S0 基线不同**：C1/C2 选择中的 S0 是固定 App；资源增量选择中的 S0 已是固定 App+C1。上述核查仅读取保存文件，没有重新运行选择。

## 必须随图保留的研究边界

1. **目录、候选和模型不是同一集合。** 84 Native + 26 WebView Host + 67 App Web = App177，另加 Browser67 得 paired244；均为目录字段数量。当前 App 池为50个 App Web 基础模板及3个固定关系：同 Web 视口、Native–Web 内存、Native–Web 时区。新的 Host 几何、Browser C1/C2 不在该 App 池中；跨端 C1 是后续增量。目录数不保证可用性，不表示每字段入模，也不能证明四个观察位置都贡献独立检测能力。Native/Host 观测不是真值保证。旧 `inner_height > 710` 和同 Web 视口关系不能改称新 Host 几何关系。

2. **选择方法与最优性有限。** App SPARSE 使用宏平均 TPR 减去复杂度惩罚的贪心选择；权重按既定配置/环境分组构造（[权重实现](../../../hybridguard_agent/research/rule_learning_v2/adapter.py#L145)）。RETENTION 从自己的 SPARSE 初始化，进行可行的新信号保留与同组质量替换，并遵守相应非退化条件；它不继续优化原稀疏目标，保存结果明确为 `optimality=NONE`、`old_sparse_objective_still_optimized=false`。跨端阶段只枚举 S0/S1/S2/S12，先满足每组正常报警、最终 T/F 覆盖、候选可用性及规则/复杂度约束，再最大化四类干预宏平均检出率，继而优先更少新增规则和固定集合顺序。U/FAILED 不从干预分母中删除。该有限空间的精确选择不等于任意规则空间全局最优，也没有新增泛化保证。

3. **数据用途各自固定。** 中央框中的 “App / paired studies + MTC630 normals” 是开发数据类别概括：App 有自己的受控开发折与独立 MTC 正常约束；C1/C2 使用协议固定的 paired 开发成员，不把旧378条并入跨端选择。历史144/117在跨端模型选定后才进入历史评价，仍不是新的盲测、准确率、比值或独立设备数。三个模型重复评价不会增加独立样本量。

4. **绑定与推理分开。** 会话、回执、版本和来源检查用于关联当前观测；它们不是分类特征，也不证明两端测量原子同步。推理载荷只含允许的当前值、状态、质量和绑定错误，不读 attack/normal、pre/change/post、未来恢复或 train/test 身份。App-only 不要求 Browser；paired 的 C1 仅比较 `app.web_data.execution_layer.timezone_offset` 和 `browser.web_data.execution_layer.timezone_offset` 两个有效数值，不比较 Native、时区名称或完整时区规则。

5. **U、FAILED 与没有回退。** 对符合接口契约的当前输入，必要 Browser 操作数缺失/不可用时 C1 为 U，关联失败为 FAILED。模型按已选输入失败优先、再按三值 OR 合成：`T OR U = T`，`F OR U = U`，`T OR FAILED = FAILED`。所以“没有 App-only 回退”不等于“缺 Browser 时最终一律 U”；它表示不能把缺失 C1 当 F 或改走 App-only。未选字段的观测错误不额外使模型 FAILED；额外字段、非法载荷、模型契约错误仍可能被接口直接拒绝，图不承诺任意非法请求都返回四态。F 只是不报警，不能解释为设备安全；T 也不是已证明攻击真值。

6. **未集成分支保留负结果。** 新 Host 几何是有限布局域的独立研究关系，未进入当前固定 App。Browser 资源条件确实参加过受约束选择，但当前冻结基线和预算下没有新增条件可准入。这里的 “none selected” 不否定已集成的 Native–App Web 内存关系，也不把资源探索写成完成了新的保留模型。原正常反例、未检出和 U/FAILED 仍以对应实验报告为准。

## 生成与本轮检查

在仓库根目录，使用有 Python 3 和现有 Sharp 依赖的运行环境执行：

```sh
python3 -B paper/figures/overview_www_style/build_overview.py
node paper/figures/overview_www_style/render_preview.cjs
```

本机使用 Codex 已有 Python/Node runtime，无新增安装。预览脚本默认从 `~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules` 加载 Sharp，也可通过 `RBA_NODE_MODULES` 指定依赖目录。

2026-10-09 对本次重新生成的版本检查，未沿用旧图的视觉验收记录：

- **实际视觉检查通过。** 已打开最终 Sharp PNG 和 Chrome 独立渲染图，核对上方 App-only、下方 paired 绕行、两条模型加载箭头、独立未集成分支及 T/F/U/FAILED；未见遮挡、文字挤压、裁切、缺字或箭头误入离线开发框。
- **基础跨渲染器检查通过。** 现有 Sharp/librsvg 与本机 Chrome 154.0.8037.98 均成功渲染；Chrome 文本边界检查为72个文本元素、0越界、0文本包围框交叠，8个图标引用均有可见尺寸。Chrome 原生 mm 尺寸解析约为680.31 × 347.70 CSS px；高分辨率对照图按相同 viewBox 渲染为3600 × 1840。该检查只覆盖这两种本机渲染环境，不声称所有浏览器或论文排版系统均已验收。
- **编辑性检查通过。** 72个文字元素保持 SVG `<text>`，图内无栅格 `<image>` 或外部资源引用；图标同时提供 `href` 与 `xlink:href`。正文未因新增事实说明而缩小。
- **生成回归通过。** 重复运行生成脚本和现有预览脚本，SVG、PNG 均与已检查版本逐字节一致；Python 语法解析、Node 语法检查、PNG 解码和尺寸、SVG 引用及 `git diff --check` 均通过。结构检查确认两条当前输入折线没有穿过离线开发框内部，37个 README 文件链接均可解析到对应文件。
- **修改范围核对通过。** 与本轮开始前的工作区状态对比，只新增上述5个文件的修改；其余213条已有工作区状态保留。核查与 Chrome 临时预览放在仓库外临时目录，未写入其他论文图或实验目录。

## 本轮修改记录

先读取代码、协议、模型与保存选择结果，再修改生成脚本，重新生成 SVG/PNG，并检查实际渲染。仅修订本目录上述五个文件；未修改算法、输入、标签、实验统计、其他论文图或正式图册。没有新增采集、训练、规则选择、模型/条件预测、评价或计时。

修订意见与已核查实现没有阻碍本图交付的事实冲突。两处需要比简短建议更精确：RETENTION 不是延续同一稀疏优化目标；paired 缺失关系的 U 必须按原 OR 语义合成，不能说成最终状态必然 U。这两点已经落实在图与图注中。保留以上限定后，本版可作为当前研究 Method Overview 的事实准确稿交导师审阅；论文最终措辞、版面和跨环境泛化仍需各自的审阅或实验依据。
