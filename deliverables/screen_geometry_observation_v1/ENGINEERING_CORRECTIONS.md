# 工程修正与实际版本

本轮正式矩阵只运行一次，3 个原定环境各 24 个位置，共 72 条。工程冒烟另有 API29 的 6 条。关系只有一个版本，公式、适用域和误差预算没有按正式结果改变；模型拟合为 0 次。

1. 首次构建在配置阶段被仓库原有“必须使用公网端点”设置拒绝，尚未编译。第二次显式传入本地实验端点及 `hybridguardRequirePublicEndpoints=false` 后成功。失败日志保留为 `runtime/build_attempt_1.log`，正式 v15 构建为 `runtime/build.log` 和 `BUILD.json`。
2. 工程冒烟评价最初把 `dumpsys input` 的 SurfaceOrientation 列表误当成单元素。实际输出含多个输入设备。改为检查目标方向存在，并在 Host 有观测时核对实际 configuration orientation。只修正常流程证据，不改任何条件；冒烟初始错误及修正说明保留在 `smoke/NORMAL_PROOF_CORRECTION.json`，没有重采。
3. 正式采集使用预先构建并安装核对过的 **v15 / 1.6.8-expanded-v2.2-geometry**、`featureapp-geometry-v1`。采集期间代码复核发现后快照读取位于异步回调的异常边界之外；派发处的外层 try 无法捕获稍后的 getter 异常。现有 v15 APK、构建记录及正式原始数据均保留。
4. 当前源码另升 **v16 / 1.6.9-expanded-v2.2-geometry**、`featureapp-geometry-v1.1`：保护前/后 Host getter，保存具体错误阶段，限制迟到回调与重试，并继续一次完成旧 payload。成功路径的字段、单位、时序和关系语义不变。独立构建 `runtime/featureapp-v16-geometry-local-only.apk`，55 项 Android 单元测试通过（含新增 4 项异常边界测试）；见 `BUILD_v16.json`。**v16 没有重新安装或追加采集，不把 v15 的 72 条记成 v16 实测。** 两版差异保存在 `runtime/v15_to_v16_error_boundary.patch`，可在独立副本反向应用以查看 v15 源码；不在当前工作区回退。
5. 正式评价前独立复核发现两类评价边界：恢复缺失/撤销失败不应抹去已确认的前→变化目标改变；报告解包遇到 null/错误结构不应使整批退出。分开当前执行、实际效果和恢复证明，补充类型保护及测试。预测关系不变，不按条件是否报警决定正常或攻击身份。正式预测在修正完成后生成。
6. 正式首评仍把“方向请求达到”混入了“已知正常操作执行”的必要条件。API36 的 `dumpsys input` 没有旧版 SurfaceOrientation 字符串；API29/30 部分采样前读数尚未稳定；API36 两次横屏请求实际又回到竖屏。这使首评错误地只认定 36 条正常、4 次有效 A 和 14 组恢复。修正后用本次成功的系统设置命令、App 启动及 CDP/原始接收记录证明已知流程，另存实际方向和目标达到状态。合法操作无效不等于攻击或未知流程，API36 的两次 L1 如实保留为无可观测效应。对同一原始批次重新生成一次评价：66 条正常、6 次有效 A、24 组恢复。首评逐条结果保留为 `runtime/evaluation_before_orientation_fix.jsonl.gz`；直接逐条比较确认 **72 条三个条件的全部输出与诊断完全未变**，改变的只是流程证据归类。最终 43 项相关 Python 测试通过，见 `runtime/python-tests.log`。

7. 收尾核对补上“已接收旧 payload、尚未派发几何模块就销毁 Activity”的适配边界：该 unavailable 回执没有独立模块版本字段，版本已在同一原始 payload 的 manifest 中登记。仅在这个明确失败路径读取 manifest 的实际版本，并保留 unavailable/U 与原因；不回填原始对象、不使窗口变为可用，版本不符仍 FAILED。正式72条不走该分支，逐条输出未变。

这些是构建、采集异常边界和评价程序修正，没有额外训练，没有选择最好批次，没有覆盖旧实验结果。
