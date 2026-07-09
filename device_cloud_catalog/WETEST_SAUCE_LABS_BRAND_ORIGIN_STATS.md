# WeTest / Sauce Labs 安卓机型品牌与国产占比统计

## 统计口径

- WeTest：按页面导出的 382 条“机型行”统计；平台未暴露系统版本，因此不再按 `hardware_model` 去重。
- Sauce Labs：按你确认的 106 种口径统计，即唯一 `model_number` / `canonical_model`，不按 Android 系统版本展开。
- 品牌归一化：`vivo/VIVO` 归为 `vivo`，`Xiaomi/XIAOMI/Redmi` 归为 `Xiaomi`，`Google/GOOGLE/google` 归为 `Google`，`SAMSUNG/samsung` 归为 `Samsung`。
- 国产机归类：按大陆手机品牌归类，包含 HUAWEI、HONOR、vivo、OPPO、Xiaomi、realme、OnePlus、MEIZU、ZTE、SMARTISAN、BlackShark、nubia。Samsung、Google、ASUS 等归为非国产；未标注品牌单列。

## WeTest

总机型条目：382

### 品牌机型数量与占比

| 品牌 | 机型数量 | 占比 | 归类 |
|---|---:|---:|---|
| HUAWEI | 109 | 28.53% | 国产 |
| vivo | 88 | 23.04% | 国产 |
| Xiaomi | 46 | 12.04% | 国产 |
| OPPO | 44 | 11.52% | 国产 |
| HONOR | 33 | 8.64% | 国产 |
| Samsung | 17 | 4.45% | 非国产 |
| realme | 13 | 3.40% | 国产 |
| OnePlus | 11 | 2.88% | 国产 |
| Google | 5 | 1.31% | 非国产 |
| ASUS | 4 | 1.05% | 非国产 |
| BlackShark | 4 | 1.05% | 国产 |
| (未标注) | 3 | 0.79% | 未标注 |
| ZTE | 3 | 0.79% | 国产 |
| MEIZU | 2 | 0.52% | 国产 |

### 国产 / 非国产占比

| 归类 | 机型数量 | 占总数比例 |
|---|---:|---:|
| 国产 | 353 | 92.41% |
| 非国产 | 26 | 6.81% |
| 未标注 | 3 | 0.79% |

- 排除未标注后：国产 93.14%，非国产 6.86%。

## Sauce Labs

总唯一机型：106

### 品牌机型数量与占比

| 品牌 | 机型数量 | 占比 | 归类 |
|---|---:|---:|---|
| Samsung | 81 | 76.42% | 非国产 |
| Google | 23 | 21.70% | 非国产 |
| Xiaomi | 2 | 1.89% | 国产 |

### 国产 / 非国产占比

| 归类 | 机型数量 | 占总数比例 |
|---|---:|---:|
| 国产 | 2 | 1.89% |
| 非国产 | 104 | 98.11% |

- 排除未标注后：国产 1.89%，非国产 98.11%。

## 输出文件

- `wetest_sauce_labs_brand_origin_stats.csv`：两平台品牌数量、占比、国产/非国产归类明细。
