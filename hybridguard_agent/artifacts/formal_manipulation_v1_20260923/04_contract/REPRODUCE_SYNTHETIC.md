# S04 仅合成复现

必须选择新的空输出目录，原验收目录不能原地覆盖。以下入口仅生成合成材料并运行本步聚焦测试；不加载 02_inputs 的真实 inference_inputs，不运行 S01/S02/S03-R。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 hybridguard_agent/scripts/validate_formal_manipulation_s04.py \
  --config-dir hybridguard_agent/config/formal_manipulation_role_gate_v2 \
  --policy-dir hybridguard_agent/config/formal_manipulation_policy_v2 \
  --output /tmp/hybridguard-s04-new-synthetic-run
```

已有合成输入也可分开调用 `run_formal_manipulation_eval.py predict`（明确提供 --inputs、--protocol、--contract-version、--config-dir、--policy、--out），文件关闭后再调用 `evaluate`（--predictions、--evaluation-index、--triplets、--out）。各 out 相互独立且不得覆盖输入。绘图数据由 `plot_formal_manipulation_eval.py --evaluation … --figure-spec … --out …` 读取保存结果导出。

job 的版本、精确 variants 和 expected_units 只属于调度器；payload 单独传入 worker。任何真实 job 必须由将来单独授权的 S05 冻结和后续执行步骤提供，本步没有正式 job。配置及 metric/figure spec 的 schema 版本见同目录副本；接口定义见计划中的 S04_CONTRACT_IMPLEMENTATION_v2.md。
