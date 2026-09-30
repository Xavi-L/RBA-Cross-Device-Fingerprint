# 原始观测、三环境、14 配置对照

本轮已完成，先读 [REPORT.md](REPORT.md)。最终同数据比较为 BASE 108/126、新候选池 108/126，两组对照报警均为 0/252；18 条干预预测互换，不能仅凭总分持平认为覆盖相同。两项新候选都通过支持门槛，但最终均未入选。

最新预算为 [prepared/EXECUTION.json](prepared/EXECUTION.json) 的 189/200，剩余 11 次。`CONTRACT.json` 保留执行前登记值，实际开始和完成状态分别在 `RUN_STARTED.json`、`EXECUTION.json`。不要重新执行已经完成的采集或训练脚本；独立输出和启动标记会拒绝覆盖。

只读核查现有结果：

```sh
python3 -B deliverables/rule_semantics_raw_only_expansion_v1/verify_comparison.py --execution
```

`runtime/` 中的模拟器、镜像和 Node 依赖为忽略的本地运行资源。可审核源码、登记、原始 JSONL、失败日志、成员清单、训练模型、预测及测试结果保存在其外。攻击工具源码快照在 `source_snapshot/`；本地 CDP 撤销修订在 `week10_cdp_emulation_runtime_v2.mjs`，没有修改攻击侧仓库。
