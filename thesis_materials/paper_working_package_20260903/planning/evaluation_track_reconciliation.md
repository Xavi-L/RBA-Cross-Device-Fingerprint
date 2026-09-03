# HybridGuard 两条受控 Evaluation Track 的统一口径

本文件用于解决主仓与攻击侧仓库在数据批次、规则版本和统计分母上的表面差异。结论不是把两边数字强行统一，而是明确它们回答不同问题。

## Track A：Attack-side stability campaign

- 统计单位：effect-positive active run。
- 数据：固定 API 36 emulator，10 个 intervention configurations，每个配置 10 个 complete effect-positive runs，共 100 runs（102 attempts 中 2 次未形成完整可评估证据）。
- evaluator：攻击侧 frozen evaluator，包含 9 direct mechanism rules 与 12 relations；formal response 只使用其声明可用于 attack attribution 的子集。
- headline：70/100 formal responses；7/10 configurations covered；5/8 intervention families covered。
- shared stable gaps：resource capacity、plugin/MIME、display geometry。

这个 track 主要回答：攻击效果能否稳定复现，以及攻击侧 evaluator 在 effect 已确认存在时是否稳定响应。

## Track B：Main-repository paired re-evaluation

- 统计单位：qualified `baseline -> attack_active` pair。
- 数据：23 accepted manifests，69 qualified pairs，14 exact config IDs，4 tool families。
- evaluator 1：main-repository `official-semantic-relations-v1` 的 9 个 executable relations。
- evaluator 2：main-repository `deterministic-rule-predicates-v1` 的 10 个 predicates。
- headline：51/69 与 33/69 baseline-no-alert -> active-alert transitions。
- 另有 229 条 main-repository normal-input records 作为 calibration screen，不作为 benign FPR denominator。

这个 track 主要回答：matched baseline 变成 attack-active 后，主仓 frozen evaluator 是否发生强报警状态转换。

## 为什么同一攻击会得到不同“覆盖”结论

两条 track 的 evaluator 不是同一版本，因此 coverage 不要求一致。例如：

- WebDriver：attack-side 有 direct mechanism rule；main-repository strong-alert registry 不把 standalone WebDriver 作为同等级强关系。
- language / timezone：attack-side repeated-run campaign 可产生 formal response；main-repository paired policy 更保守，因此对应 pair 可能无强 transition。
- WebGL：main-repository official-derived catalog 有显式 Android graphics vs. Windows/Direct3D relation，因此可出现 main-only 的语义覆盖差异。

这些差异是 evaluator policy/version 差异，不是数据冲突。

## 论文统一写法

推荐：

> We report two complementary controlled App177 evaluation tracks. The attack-side stability campaign measures reproducibility and evaluator response over effect-positive active runs, whereas the main-repository paired re-evaluation measures baseline-to-active alert transitions under two different frozen main-repository catalogs. Because the tracks use different statistical units, inclusion rules, and evaluator versions, their headline counts are reported separately and are not pooled into a single detection rate.

禁止把 `70/100`、`51/69`、`33/69` 合并或互相替换，也不应将其中任何一个直接写成 population recall。
