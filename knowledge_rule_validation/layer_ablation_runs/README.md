# 单端与跨端输入消融

本实验固定现有规则，不训练随机森林或其他模型，不调用 LLM，不修改阈值。当前交付是 App177 攻击材料上的探索性 pilot，完整 App177＋独立 Browser67 实验留待配对攻击数据与正式判别器就绪。

当前结果：[2026-09-16 报告](app177_pilot_20260916/单端与跨端消融报告.md)。报告列出单端、双端与 App177 的报警计数、可执行覆盖和无法评估项，并保留两类规则及设计暴露 cohort 的边界。

复现命令（在仓库根目录，输出目录必须尚不存在）：

```bash
python3 hybridguard_agent/scripts/build_latest_paired244_snapshot.py \
  --run-id layer_ablation_qc_new \
  --output-dir /private/tmp/hg_layer_ablation_qc_new
python3 hybridguard_agent/scripts/run_layer_ablation_pilot.py \
  --latest-snapshot /private/tmp/hg_layer_ablation_qc_new \
  --output-dir knowledge_rule_validation/layer_ablation_runs/app177_pilot_new
python3 -m unittest hybridguard_agent.tests.test_layer_ablation_pilot -v
```

`--latest-snapshot` 可省略，此时只重放攻击对照。它提供的当前采集记录始终作为独立无标签 QC，不能作为正常负例。默认攻击选择为 `knowledge_rule_validation/config/layer_ablation_attack_input_set.v1.json`；2026-09-16 只更新了源仓库提交引用，选中的23份攻击清单、原始 payload 与接受证据均无变化。

输入组：Native84、WebView host26、App Web67、三种双端、App177。先删除不可见层，再重新提取派生事实与执行规则；不会借用全量输入提前生成的一致性特征。Browser67 和 Full244 明确为 NOT_EVALUATED，既不伪造缺失字段，也不把 App Web 当作独立浏览器。

本实验继承当前两态协议：仅比较 baseline→attack_active，历史 clean_post 只计数。NOT_EVALUATED 表示当前输入下没有可评估的报警规则，不是阴性/漏检；即使有可评估规则，NO_ALERT_OBSERVED 也只表示没有观察到报警，不能据此断言正常。软语义偏差单列，不升级为强报警。

后续正式实验需补齐同设备、同配置、同阶段的完整 paired244、可信独立组和核验标签，并实现/冻结实际使用 Browser67 的判别路径。本次结果不能用于调规则后在同一批数据上自证，也不能作为跨设备泛化结果。
