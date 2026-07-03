# GLM-5.2 Targeted Pilot Report

## 1. 本轮已完成内容

本轮已经完成独立实验目录搭建，并真实调用智谱 `glm-5.2` 跑通以下 targeted pilot：

| 验证项 | 样本数 | 输出 |
|---|---:|---|
| K0 无官方知识 direct scoring | 60 | `outputs/glm52_direct_k0_targeted_success.jsonl` |
| K1 官方知识 direct scoring | 60 | `outputs/glm52_direct_k1_targeted_success.jsonl` |
| K0 无官方知识六组分数 | 60 | `outputs/glm52_group_scores_k0_targeted.jsonl` |
| K1 官方知识六组分数 | 60 | `outputs/glm52_group_scores_k1_targeted.jsonl` |
| K0/K1 direct paired ablation | 60 | `outputs/knowledge_ablation_direct_targeted_success/` |
| K1 targeted cached fusion | 60 | `outputs/group_fusion_k1_targeted/` |

targeted set 覆盖以下规则族：

- `tri_layer`
- `tolerance`
- `native_webview`
- `attack_scenario`
- `core_integrity`

## 2. 官方知识 direct scoring 消融结果

direct scoring 是判断官方知识是否改善最终风险判断的主要结果。

| 指标 | K0 无官方知识 | K1 官方知识 | K1-K0 |
|---|---:|---:|---:|
| MAE | 2.367 | 2.750 | +0.383 |
| RMSE | 3.291 | 4.649 | +1.358 |
| 五档风险区间匹配 | 96.67% | 96.67% | 0.00% |
| 三档风险区间匹配 | 100.00% | 96.67% | -3.33% |
| 高风险 F1 | 1.000 | 1.000 | 0.000 |
| future-only reason 误引用 | 0 | 0 | 0 |
| paired improved | 7 | - | - |
| paired worsened | 8 | - | - |
| paired unchanged | 45 | - | - |

### 主要观察

1. K1 官方知识没有带来 direct scoring 数值提升；在 targeted set 上 MAE 和 RMSE 略高。
2. 高风险识别没有受损，K0/K1 的高风险 F1 都是 1.000。
3. K1 没有误引用 Play Integrity、Key Attestation、WebView URL/origin 等当前未采集的 future-only 证据。
4. K1 的主要副作用集中在低危弱开发配置样本：两条教师分为 15 的样本被抬到 35。

## 3. 典型样本解释

K1 变差最明显的两条：

| row_index | teacher | K0 | K1 | 现象 |
|---:|---:|---:|---:|---|
| 168 | 15 | 18 | 35 | ADB、debuggable、cleartext 被 K1 解释为测试机架/灰度调试特征 |
| 58 | 15 | 25 | 35 | 系统文件管理器安装 + ADB/debuggable/cleartext 被 K1 抬升到中风险 |

这两条与既有 full holdout 中的 low -> medium 误判方向一致，说明官方知识可能强化了开发配置字段的风险语义，但还需要在规则库或 prompt 中进一步强调：

> ADB、debuggable、cleartext 只有在与 manual 安装、满电/UTC、云测机架或其他跨层异常组合时，才应进入 `medium_cloud_or_test`；如果三端身份链条完整、传感器与 JSBridge 正常、安装来源可解释，应保留在低风险或低中风险。

K1 改善的样本主要体现为更接近低危教师分：

| row_index | teacher | K0 | K1 | 现象 |
|---:|---:|---:|---:|---|
| 239 | 15 | 25 | 18 | K1 reason 明确把 ADB/debuggable 归入容错范围 |
| 44 | 15 | 10 | 15 | K1 更贴近教师分 |
| 31 / 48 / 49 / 63 | 15 | 12 | 15 | K1 对低危容错的表述更完整 |

## 4. 六组分数消融结果

六组分数用简单平均评估时，K1 也没有数值提升：

| 指标 | K0 无官方知识 | K1 官方知识 | K1-K0 |
|---|---:|---:|---:|
| MAE | 16.425 | 17.117 | +0.692 |
| RMSE | 17.704 | 18.528 | +0.825 |
| 五档风险区间匹配 | 51.67% | 51.67% | 0.00% |
| 高风险 F1 | 0.800 | 0.800 | 0.000 |
| future-only reason 误引用 | 0 | 0 | 0 |

注意：六组分数不应直接用简单平均作为最终结论。它只是检查分组输出是否可解析、是否有明显风险方向。正式结论应看 `Positive ElasticNet` 融合。

## 5. 重复画像样本权重的初步结果

在 K1 targeted 六组分数上运行 cached fusion，小样本结果如下：

| 配置 | MAE | RMSE | 高风险 F1 |
|---|---:|---:|---:|
| 原始六组分数，不加权 | 7.983 | 9.954 | 0.333 |
| 原始六组分数 + group sample weight | 6.318 | 7.761 | 0.467 |

初步观察：

1. 组内样本降权在 targeted set 上有正向信号，MAE 从 7.983 降到 6.318。
2. 高风险 F1 从 0.333 提升到 0.467，但 targeted set 样本量较小，不能作为最终结论。
3. 当前还没有调用 GLM 给增强扰动样本打分，因此 P1/WP 与 D0/W1 结果相同；训练扰动方案还需要 full/augmented cache 后才能正式验证。

## 6. 阶段性结论

本轮 targeted pilot 的结论应谨慎表述为：

1. Google 官方知识卡片没有在 targeted direct scoring 上带来整体数值提升。
2. 官方知识没有损害高风险识别，也没有引入 future-only 证据误引用。
3. 官方知识会让 GLM 更敏感地解释 `ADB + debuggable + cleartext` 等开发配置，导致少数低危样本被抬到中风险。
4. 因此下一步不是简单宣称官方知识有效，而是应基于本轮结果加强容错提示和规则表述，再做 K1.1 prompt/rule wording ablation。
5. 重复画像降权在 targeted fusion 上有初步正向信号，但训练扰动增强尚未完成正式验证。

## 7. 建议下一步

建议下一轮按以下顺序推进：

1. 修改 K1 prompt 或规则库 `TOL-*` 表述，明确弱开发配置的容错边界，形成 K1.1。
2. 在同一 60 条 targeted set 上比较 K0 / K1 / K1.1 direct scoring。
3. 若 K1.1 修复低危误升，再扩展到 212 条 boundary set。
4. 最后对 full original group scores 和必要的 augmented evidence 进行 GLM 缓存，运行完整 D0 / W1 / P1 / WP grouped-fusion 矩阵。

## 8. 一句话总结

> 本轮 GLM-5.2 targeted pilot 表明，Google 官方知识卡片并不会削弱高危攻击识别，也没有引入未采集官方强证据的误引用；但它会增强模型对开发配置风险的敏感度，使少量低危弱异常样本被抬升到中风险。因此官方知识的价值更体现在提供可解释依据和暴露容错边界问题，下一步需要针对容错规则做 K1.1 消融，而不是直接宣称已带来整体性能提升。
