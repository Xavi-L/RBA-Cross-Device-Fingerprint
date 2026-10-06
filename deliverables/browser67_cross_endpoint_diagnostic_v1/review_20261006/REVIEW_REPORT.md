# B2-A 复审（2026-10-06）

**结论：原数值结果和研究范围结论保留；此前输入异常处理和测试存在实质缺口，现已修复。** 本复审重新运行原版本、修复版本，并作了不经过 B2 适配/预测入口的独立核对。没有新样本、训练、采集或规则调参，没有提交推送。

## 发现及修复

1. **App 输入隔离不完整。** 原 `pilot()` 在 Browser 绑定成功后才保留 App 原始记录；缺 Browser 会使 18 条有效 App 记录全部丢失、模型成为 FAILED。此前隔离测试只修改加载后的对象，未覆盖真实加载链。现在先独立绑定当前 App，再处理 Browser。真实删除临时副本中的 Browser 文件也保留全部 App 输入；跨端条件仍明确 FAILED。D2 使用自身 Browser 绑定，App 端缺失不再让这个 Browser 自检跟着失败。
2. **单条坏 MTC 引用会中断整批。** 原代码在逐条错误捕获外直接取 `source_refs.browser_raw_line`，已复现 KeyError。现先检查引用形状，所有 891 个预定位置保留，错配、缺键、错误容器或重复 ID/引用分别标明失败，不替换配对。重复 ID 的两个物理位置均保留。
3. **重汇总只检查总数。** 原逻辑接受“复制一条、遗漏一条但总数不变”的预测结果。现对保存的模型/成员清单检查完整笛卡尔积：18×3 预测及 (18+891)×5 条件，并核对分组、阶段、状态枚举。用来源物理位置区分错误的重复 ID，不在字典里覆盖丢失。
4. **证据绑定与质量处理需要补强。** 先导阶段侧表增加与原 B1 captures 的逐字段关联；历史 MTC 增加 raw↔P1 的实际操作数及状态校验、Browser pair/session/receipt/schema/probe/batch 核验。MTC 缺少 quality 不再从 observed 状态自动补成 observed_value。保留其原版本身份，不转写 v16。

以上修复没有改变 C1—C3、D1—D2 的比较公式、标签解析范围、偏移符号或原 App 模型。D2 的端点错误归属修复遵循原“仅 Browser 输入”定义；实际数据的任何条件状态都未改变。

## 必要结果的复现

| 核验 | 实际结果 |
|---|---|
| 修改前原实现完整回放 | 54 条 App 预测、4,545 条条件记录与原保存文件逐字节一致 |
| 修复后完整回放 | 54 条预测内容、4,545 条条件内容全部不变；仅先导 metadata 新增 capture 引用 |
| 原始配对独立核对 | 909 条配对，5,346 个 MTC 相关原值/状态/quality 核对通过 |
| 独立条件实现 | 从 raw 字段和状态重算 4,545 个条件状态，全部一致 |
| 独立 App 核对 | 只调用原始选中规则内核，另行执行冻结阈值、极性和子句汇总；54 个模型判断、306 个原子状态和 306 个子句状态全部一致 |
| 汇总/轨迹/重叠/失败清单 | JSON/CSV 汇总、TRAJECTORIES、OVERLAP、failures 与复审前逐字节一致 |
| 运行时审计 | 实测 54 次原 App predictor、4,545 次条件调用；无 fit/prepare_fold/train/collect 调用、无子进程或网络；所有写入限于新输出目录 |
| 定向回归 | 36 项诊断测试 + 10 项旧正式协议测试通过 |

独立 App 核对复用原规则内核以保持冻结语义，但不调用 `run.py`、`conditions.py`、B2 编译路径或模型预测器。它检查的是代码接线、输入、阈值和汇总，不是外部算法正确性证明。独立条件实现直接读取原始操作数，不使用保存 T/F/U 作为预期值。多次复现仍是相同 18/891 条记录，不增加样本量，也不构成新盲测。

[运行时审计](RUNTIME_AUDIT.json)、[独立核对](INDEPENDENT_AUDIT.json)、[逐条 App 核对](APP_ORACLE.jsonl)、[逐条条件核对](CONDITION_ORACLE.jsonl)、[结果比较](RESULT_COMPARISON.json)均已保存。

## 原结论的精确边界

三个模型在 18 条先导上均为明确 F，既无干预时新增报警，也无持续环境报警。C1 在三条时区干预为 T，C2/C3 在三条语言干预为 T，12 条先导正常均为 F。D1 在正常先导全部偏离；D2 无新增信号。

MTC 正常研究依据下，D1 为 194/891 偏离；C2/C3 各 1 T、1 U；C1 0 T、25 U（Browser runtime_error）；D2 0 T、6 U。C2/C3 的相同计数仅是这批数据的观察。语言解析仍是明确的保守语法子集，不能声称完整 BCP47 注册表合法性或别名验证；本轮不得按已见结果扩展解析规则。

那条 2,833,629 秒的两端 payload 时间戳差已从真实原始引用复核；它是报告时间戳之差，不能未经核实当成真实采集间隔。它的 C1 仍为 F；没有因异常时间改 U。所有先导 App 的时间区间字段有效且使用原 GMT 固定分支，不涉及补日期或动态 tzdb 替换。

下一轮 C1/C2 仍只能作为有限选择的待检候选；正常偏好、时间非同步、缺测及 C3 粒度损失仍需相应对照，不能由这次工程复审消除。正式 split=0、readiness=false 和旧正式协议保持不变。

## 保留与复现方式

复审前代码、报告、清单和派生结果位于 [before/](before/)。两份较大的逐条文件仅发生 144 行 metadata 更新（54 条预测及 90 条先导条件）；[RAW_OUTPUT_METADATA_DELTA.json](RAW_OUTPUT_METADATA_DELTA.json)保留旧/新 metadata，配合当前记录可以精确还原原 JSONL，避免重复保存相同测量数据。结果比较文件记录还原前后摘要；没有改写原 B1/MTC 原始材料或模型。

从仓库根目录执行，输出路径必须尚不存在：

```sh
python3 -B deliverables/browser67_cross_endpoint_diagnostic_v1/reproduce.py --output /tmp/b2a-review-new
python3 -B deliverables/browser67_cross_endpoint_diagnostic_v1/review.py --results /tmp/b2a-review-new --output /tmp/b2a-review-oracle
```

只读取保存证据重汇总：

```sh
python3 -B deliverables/browser67_cross_endpoint_diagnostic_v1/run.py summarize
```

审查和修复均限定在 B2-A 交付目录。保留原有 Android 构建产物、子模块和其他未提交文件；没有 Git 提交、推送或历史清理。
