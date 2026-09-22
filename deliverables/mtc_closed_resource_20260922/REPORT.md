# 现有资源下的最终规则研究与结案

2026-09-22。用户明确：现有数据就是全部资源，没有补采机会；无法验证的条目不继续纠结。按此约束，已完成剩余 **17 项规则研究及 8 项数据缺口的最终处置**。没有启动采集、训练模型、拼接旧 Testin 数据或请求新设备。

## 最终数量与含义

| 本轮处理的 25 项 | 数量 | 处置 |
|---|---:|---|
| 接入限定范围的一致性观察 | 3 | 明确型号与 App UA、型号与 system HTTP agent、Native/App Web GPU 家族 |
| 保留描述性研究结果 | 11 | 结果有价值，但不足以启用通用异常判断；本轮结案 |
| 现有证据无法验证并关闭 | 11 | 原 8 项数据缺口及 3 项缺少独立重放/攻击事实的场景判断 |

**当前 v3 总目录为 87 项：57 项可执行、11 项仅描述、11 项证据不足关闭、4 项合并、4 项停用。待研究与待补采项均为 0。**

57 是程序可执行检查数，含部署策略、上下文、共享证据与采集器自检；不是 57 条独立攻击规律。“关闭”也不表示验证成功或证明规则错误，而是明确终止当前资源无法支持的主张。详见 [25 项最终处置](RESOLUTIONS.md)。

## 固定研究方法

在本轮读取新的候选结果前，保存了 `mtc_closed_resource_protocol.v1.json` 与恰好 4 个候选表达式。只使用 P2 已准入的发现 630 条/610 组、开发 144 条/142 组主代表。没有为增加支持读取保留验证集，也未把同组多次观测当成独立支持。

沿用原 P2/P3 预先声明的研究门槛：发现至少 30 个可评估组/3 个厂商、开发至少 10 个可评估组/2 个厂商，组级一致比例至少 95%。这只是工程研究筛选，不是显著性检验、检测准确率或旧效果目标。任何反例优先计入该组；未知和不适用不作为一致票。

先落盘发现集选择清单，再读取开发集；开发集不能挽救发现集落选的候选。开发集在前几阶段已经接触过，本轮仍属于开发验证，不称独立盲测。没有新建型号别名表、调节容差、优化风险分数或为了达到某个规则数量重跑。

## 四项候选的实测结果

表中按防泄漏分组计数，依次为“一致 / 反例 / 未知 / 不适用”。

| 候选 | 发现集 610 组 | 开发集 142 组 | 最终处置 |
|---|---|---|---|
| NW-001：Native 型号与 App UA 显式型号 | 606 / 0 / 0 / 4 | 142 / 0 / 0 / 0 | 接入 |
| NVW-001：Native 型号与 Dalvik system agent 显式型号 | 571 / 0 / 0 / 39 | 136 / 0 / 0 / 6 | 接入 |
| NW-005：Native GLES 与 App WebGL 的可识别 GPU 家族 | 603 / 0 / 7 / 0 | 142 / 0 / 0 / 0 | 接入 |
| NW-003：显示尺寸双边残差 ≤1 CSS px | 185 / 425 / 0 / 0 | 45 / 97 / 0 / 0 | 仅描述，停止启用研究 |

每个候选的可评估数据均覆盖发现 41 个厂商、开发 21 个厂商。全部候选结果与全部屏幕反例均保留，没有逐机型豁免或删去反例。

接入的含义有明确限制：

- **NW-001** 仅比较 Android UA 中紧邻显式 `Build/` 的、可无歧义解析的型号；只做大小写/空白归一。没有型号、简化型号、歧义格式不能获得一致票；不按营销名、子串或未经验证的别名模糊匹配。Chrome 的型号简化说明支持这一限制：[官方 UA reduction 说明](https://privacysandbox.google.com/blog/user-agent-reduction-android-model-and-version)。
- **NVW-001** 仅适用于显式 Dalvik 格式。AOSP 默认 system HTTP agent 与 Native 字段共享 `Build.MODEL` 来源，因此该检查不是独立的设备身份证明；系统属性也不是当前 WebView 网页的 UA。依据：[AOSP RuntimeInit](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/master/core/java/com/android/internal/os/RuntimeInit.java)。
- **NW-005** 改为限定的 Native/Web renderer 家族比较，**没有恢复旧的硬件型号/主板 → GPU 对照推断**。只识别预先列出的 Adreno/Mali/PowerVR/Tegra/Vivante 字面家族；未知或歧义保持未知，软件回退不适用；同家族不证明同型号 GPU 或同设备。renderer 的驱动语义及隐私限制见 [Khronos 扩展](https://registry.khronos.org/webgl/extensions/WEBGL_debug_renderer_info/)。

**屏幕双边候选只在约三成可评估组满足固定条件，因此不启用。** 单记录最大双边残差的中位数为发现 63、开发约 64.33 CSS px，最大约 97.14/100 CSS px。Native 字段实际来自 App `DisplayMetrics`，不能叫物理面板尺寸；当前记录不能充分区分系统栏、窗口或缩放影响。没有把容差调大到覆盖这些记录。这里否定的是本轮声明的双边 1 CSS px 候选，不宣称已证明所有可能的屏幕规则无效，也不将其当作重新验证旧 10% 阈值。原 P3 短边检查保持原样。

## 其余研究为何结案

| 研究方向 | 现有数据实际观察 | 结案依据 |
|---|---|---|
| ABI/platform | 发现集存在 14 条 arm64-v8a 对应 Linux armv7l，另有 4 条 armeabi-v7a 对应 Linux armv8l；开发也有后者 2 条 | 记录的是兼容性暴露，不能将字符串或位数差异直接作为硬件冲突；保留对照分布 |
| Native/Web 内存 | 715 条可描述、59 条不可用；发现绝对差中位约 0.81 GiB、最大约 7.28 GiB，开发中位约 1.31 GiB | Native 为内核可见内存，Web 为受实现边界限制的近似暴露；不建立固定 3–4GB 或严格相等规则 |
| 传感器能力 | 发现总数 3–125，开发 1–126；共保留各能力标志组合的完整分布 | 未知真实设备能力和攻击标签，不能把数量少定为异常；P3 字段自洽检查继续保留 |
| 模拟器/软件渲染线索 | 774 条中预先列出的硬件/软件渲染关键词观察均为 0 | 没有阳性环境真值，不能用零命中证明识别能力，也不生成模拟器攻击标签 |
| 插件/MIME | 774 条均为零或 API 回退不可区分 | 探针同时用 0 表示无枚举与 API 缺失；不把全零作为真机规则或空枚举的证明 |
| 重放/无头场景组合 | 没有独立的干预执行和攻击标签；主视图本身经过完整配对/QC 选择 | 多项弱线索组合仍无法验证场景结论；CORE-001、SCENE-002、SCENE-003 关闭 |

内存口径的依据为 [Android MemoryInfo](https://developer.android.com/reference/android/app/ActivityManager.MemoryInfo) 与 [W3C Device Memory 草案](https://www.w3.org/TR/device-memory/)。platform/plugin 的兼容性语义见 [HTML Navigator 定义](https://html.spec.whatwg.org/multipage/system-state.html)。这些来源用于限制项目推断，不能代替本批样本的环境/攻击真值。

全部描述性记录和汇总已保存。原 8 项待补数据（耗时重复观测、两项电池时间关系、两项 Play Integrity、Key Attestation、Verified Boot、导航 Origin）均标为 **CLOSED_UNVERIFIABLE**，不再提出采集或继续验证要求。

## 运行时与验收

默认入口已升级为 `paired244-runtime-catalog-v3`。新增 3 项进入规则、检索卡、Verifier 和 trace。描述性与关闭项只保留处置记录，不进入活跃证据卡，不当成检查成功。决策明确 `research_backlog_open=false`、`collection_requested=false`，同时保留 `catalog_fully_assessed=false`，避免把结案误读为全部主张已验证。

- **79 项重点/兼容测试通过**，其中本轮 17 项覆盖型号解析、GPU 未知与回退、固定屏幕边界、分组未知、发现集冻结、闭环状态与遮蔽。修复测试发现的一处文件句柄未关闭后，这 17 项在 ResourceWarning 视为错误的条件下再次通过。
- **1,548 次 Full244/App177 离线运行全部完成，无运行失败。**
- **83,592 次原 54 项检查的完整结果对照无变化**；再与此前冻结 v2 实际输出的 216 个分组/视图/规则汇总单元核对，无差异。
- **2,322 次新研究结果与运行时对照一致**；Browser 被移除后的 **6,966 次相关检查均未评估**。
- 新增 GPU 检查保留 7 个未知观察；其中 6 条使发现集 Full244 的总体状态从上下文改为部分可评估，没有将它们改成通过以维持旧效果。

保留验证集继续锁定。没有模型调用、风险融合、训练或攻击检测指标；没有改写原始数据，也没有启动已退役的本机后端或 ngrok。测试合成记录只验证程序边界，不作为真实设备攻击证据。

复现时必须使用新输出目录：

```bash
python3 hybridguard_agent/scripts/run_mtc_closed_resource_study.py \
  --out-dir hybridguard_agent/artifacts/mtc_closed_resource_study_NEW
python3 hybridguard_agent/scripts/run_mtc_closed_resource_runtime.py \
  --study-dir hybridguard_agent/artifacts/mtc_closed_resource_study_20260922 \
  --out-dir hybridguard_agent/artifacts/mtc_closed_resource_runtime_NEW
```

本批权威产物为 `artifacts/mtc_closed_resource_study_20260922/` 与 `artifacts/mtc_closed_resource_runtime_20260922/`。摘要见 [研究结果](STUDY_SUMMARY.json)、[运行结果](RUNTIME_SUMMARY.json)、[验收记录](VALIDATION.json)、[最终产物核对](FINAL_AUDIT.json)。源码、参数、来源与完整反例均有对应副本。

## 后续实验范围调整

P5 补采取消，不再作为阻塞项。P6 可在现有数据上执行冻结检查的输入/规则/知识来源比较，报告覆盖、关系偏差、未知/不适用、遮蔽行为和运行成本；保留集只在另行冻结的一次性评价协议下执行。没有独立真值的数据不能产出可信的攻击准确率、TPR/FPR、F1 或检测收益，此类结论从本项目当前实验范围排除，而不是继续等待补采。合成扰动如开展，只能作为程序敏感性检查单列。

本次已完成现有条件下的规则研究与收尾，尚未执行 P6 矩阵。P4 以来的源码、版本化目录、测试与汇总报告纳入本次提交。2026-09-23 用户进一步明确要求推送已采集的 paired244 数据，因此 MTC 最终原始冻结、P1 QC 快照和 P2 分组清单也纳入提交，见 [数据交付说明](DATA_DELIVERY.md)。完整逐样本规则运行产物仍保留本地；没有解锁保留验证集或进行新的规则评价。
