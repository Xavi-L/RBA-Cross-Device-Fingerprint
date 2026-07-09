# WeTest 安卓机型统计

## 统计口径

- 来源：WeTest 标准兼容测试设备选择页。
- 计数单位：页面导出的 382 条“机型行”。
- 字段：`hardware_model`, `model_name`, `brand`, `memory_gb`。
- WeTest 当前表格没有系统版本字段，因此不按系统版本展开，也不按 `hardware_model` 去重。
- 品牌归一化：`vivo/VIVO` 归为 `vivo`，`Xiaomi/XIAOMI/Redmi` 归为 `Xiaomi`，`Google/GOOGLE/google` 归为 `Google`，`SAMSUNG/samsung` 归为 `Samsung`。

## 总体统计

- WeTest 安卓机型条目数：382
- 品牌字段未标注：3

## 品牌机型数量与占比

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

## 国产 / 非国产占比

| 归类 | 机型数量 | 占总数比例 |
|---|---:|---:|
| 国产 | 353 | 92.41% |
| 非国产 | 26 | 6.81% |
| 未标注 | 3 | 0.79% |

- 排除未标注后：国产 93.14%，非国产 6.86%。

## 输出文件

- `wetest_android_device_combinations.csv`：WeTest 安卓机型条目表。
