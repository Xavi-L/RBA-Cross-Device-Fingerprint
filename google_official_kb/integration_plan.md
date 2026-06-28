# 外挂知识库合入计划

> 当前状态：阶段一和阶段二已经完成。`scoring/rule_knowledge_base.json` 已新增 `external_knowledge_base` 顶层元数据，并为 34 条当前规则补充 `official_knowledge`。详细结果见 `integration_report.md`。

## 阶段一：保持独立审阅

当前目录先作为外挂资料包存在，不修改主规则库。该阶段已完成。

交付物：

- `official_sources.jsonl`
- `feature_risk_cards.json`
- `collection_report.md`

审阅重点：

- 来源是否全部来自 Google 官方域名。
- 每个 feature 是否能映射到当前采集字段。
- 风险结论是否区分官方事实和项目推导。
- 容错说明是否足够保守。

## 阶段二：给主规则库增加出处字段

该阶段已完成。实际落库字段为 `official_knowledge`，其中包含卡片引用、官方来源引用、推理层级、证据强度和一句话依据。

对 `scoring/rule_knowledge_base.json` 中每条相关规则增加：

```json
{
  "source_refs": ["android-build-api", "chrome-ua-client-hints"],
  "official_basis": "Android Build 定义 Native 设备身份字段，Chrome UA 文档说明 UA 暴露系统和浏览器运行时线索。",
  "inference_level": "derived",
  "evidence_strength": "medium"
}
```

建议不要在这一阶段大改 `trigger` 和 `score_range`，只先补出处和容错依据。

## 阶段三：更新 LLM prompt 输入

当前 LLM 评分脚本会压缩读取规则库：

- `scoring/sorting_rule_kb.py`
- `zhipu_glm_eval/score_with_glm.py`

合入后建议保留 `source_refs` 和 `official_basis`，但在 prompt 中压缩显示：

```json
{
  "id": "NW-002",
  "name": "Android 版本一致性",
  "fields": ["android_native_data.os_version", "web_data.user_agent"],
  "trigger": "Native Android 主版本与 Web UA 声明版本不一致。",
  "official_basis": "Android Build.VERSION 定义系统版本字段；Chrome UA 可暴露系统版本线索。",
  "tolerance": "无法解析版本时记为未知，不单独高危。"
}
```

这样 LLM 能看到“为什么这个字段可以用”，但不会被长文档占满上下文。

## 阶段四：分组融合对齐

把 `feature_risk_cards.json` 中的 `groups` 映射到 `LLM_GROUPED_FUSION_PLAN.md` 的六组：

| 卡片 group | 融合计划 group |
|---|---|
| `native_web` | Native-Web |
| `native_webview` | Native-WebView |
| `webview_web` | WebView-Web |
| `tri_layer_semantic` | Tri-layer semantic |
| `physical_runtime` | Physical runtime |
| `attack_scenario` | Attack scenario |

后续生成分组证据摘要时，可以把官方依据作为每组解释的一部分。

## 阶段五：验证

建议新增轻量检查脚本，目标是防止知识库漂移：

1. `official_sources.jsonl` 每行必须是合法 JSON。
2. `feature_risk_cards.json` 中每个 `source_refs` 必须存在于 sources。
3. 每个 `target_rule_ids` 如果不是 `FUTURE-*`，应能在 `scoring/rule_knowledge_base.json` 中找到。
4. 每张卡片必须包含 `tolerance`，避免只强化高危判断。

建议验证命令：

```bash
python3 -m json.tool google_official_kb/feature_risk_cards.json
python3 - <<'PY'
import json
from pathlib import Path

base = Path("google_official_kb")
sources = {}
for line_no, line in enumerate((base / "official_sources.jsonl").read_text().splitlines(), 1):
    item = json.loads(line)
    sources[item["source_id"]] = item

cards = json.loads((base / "feature_risk_cards.json").read_text())
missing = []
for card in cards["cards"]:
    for ref in card["source_refs"]:
        if ref not in sources:
            missing.append((card["id"], ref))

if missing:
    raise SystemExit(f"missing source refs: {missing}")
print(f"ok: {len(sources)} sources, {len(cards['cards'])} cards")
PY
```
