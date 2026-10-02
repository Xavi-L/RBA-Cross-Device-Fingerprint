# Renderer 语义审计 v1

从 [REPORT.md](REPORT.md) 阅读结论。两个新文本方向不准入告警，NW-005 保持现有 v2 范围。
本目录含官方来源缓存、候选卡、反例分级及十个合成边界；没有新实验样本或模型训练。

```sh
python3 -B deliverables/renderer_semantics_review_v1/verify.py
```

命令核对来源锚点、合成边界和二十条既有 raw payload 的图形投影，不调用采集器或模型。
`--write` 仅更新 `BOUNDARY_RESULTS.json` / `SUMMARY.json`。不得把合成边界并入实验数据。

官方来源使用 Chromium 134.0.6998.135 和它的 DEPS 所指定 ANGLE revision；实际 WebView 二进制
构建一致性未验证。Android 文档为获取日快照，旧图形选项的弃用限制写在报告中。

`fetch_primary.py` 会访问网络并刷新官方缓存，**不属于只读复核**。刷新后应重新审查语义与锚点，
不可仅生成一份新的校验结果就声称原审计仍成立。当前 `SOURCE_REGISTER.json` 和结论是人工审阅产物。
