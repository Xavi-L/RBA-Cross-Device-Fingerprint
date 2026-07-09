# WeTest / Sauce Labs 安卓机型合并去重汇总

## 统计口径

- 来源表格：`wetest_android_device_combinations.csv` 与 `sauce_labs_android_unique_models.csv`。
- WeTest：页面导出 382 条机型行；合并去重时按 `hardware_model` 折叠为唯一硬件型号。
- Sauce Labs：采用你确认的 106 种口径，即唯一 `model_number` / `canonical_model`。
- 合并去重主键：WeTest `hardware_model` 与 Sauce Labs `model_number` 归一化后精确匹配。

## 合并结果

| 项目 | 数量 |
|---|---:|
| WeTest 原始机型行 | 382 |
| WeTest 按 `hardware_model` 去重 | 329 |
| Sauce Labs 唯一机型 | 106 |
| 两平台硬件型号精确重叠 | 5 |
| 合并后严格去重机型数 | 430 |

严格去重结果文件：`wetest_sauce_labs_android_unique_models_strict.csv`

## 重叠机型

| WeTest 硬件型号 | WeTest 机型名 | Sauce model_number | Sauce 机型名 |
|---|---|---|---|
| M2004J19C | 红米 9 | M2004J19C | Xiaomi Redmi Note 9 |
| Pixel 4 | Pixel 4 | Pixel 4 | Google Pixel 4 |
| Pixel 6 | Pixel 6 | Pixel 6 | Google Pixel 6 |
| Pixel 9 | Google Pixel 9 | Pixel 9 | Google Pixel 9 |
| Pixel 9 Pro | Pixel 9 Pro | Pixel 9 Pro | Google Pixel 9 Pro |

## 说明

这个合并口径回答的是“两个平台合起来覆盖多少唯一硬件型号 / model_number”。如果后续要按 Sauce Labs 的 Android 系统版本展开，应另建展开表；当前清理后的保留口径以 Sauce Labs 106 种唯一机型为准。
