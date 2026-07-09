# Sauce Labs 安卓唯一机型统计

## 统计口径

- 范围：仅统计 Sauce Labs Real Device Cloud 中的 Android 设备。
- 当前采用你确认的 106 种口径：按唯一 `model_number` / `canonical_model` 统计，不按 Android 系统版本展开。
- `os_versions_seen` 字段保留该机型在原始 API 中出现过的 Android 版本，便于后续需要时再展开。

## 总体统计

- Sauce Labs Android 原始设备/系统版本组合数：219
- Sauce Labs Android 唯一机型数：106

## 品牌机型数量与占比

| 品牌 | 机型数量 | 占比 | 归类 |
|---|---:|---:|---|
| Samsung | 81 | 76.42% | 非国产 |
| Google | 23 | 21.70% | 非国产 |
| Xiaomi | 2 | 1.89% | 国产 |

## 国产 / 非国产占比

| 归类 | 机型数量 | 占总数比例 |
|---|---:|---:|
| 国产 | 2 | 1.89% |
| 非国产 | 104 | 98.11% |

- 排除未标注后：国产 1.89%，非国产 98.11%。

## 输出文件

- `sauce_labs_android_unique_models.csv`：按 106 种口径生成的 Sauce Labs 安卓唯一机型表。
