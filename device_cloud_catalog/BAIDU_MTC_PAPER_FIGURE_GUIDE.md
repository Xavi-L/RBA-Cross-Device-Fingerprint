# 百度 MTC 机型池论文插图说明

本图组基于 `device_cloud_catalog/baidu_mtc_android_custom_models.csv` 生成，面向论文的“实验设备池 / 云测环境覆盖”章节。图内使用英文，以便直接用于英文投稿；中文图题、图注与可复现口径在此说明。

## 统一统计口径

原始 CSV 是百度 MTC 自定义机型目录快照，不是实际设备使用量或市场份额数据。为避免将同一配置的重复目录行写成独立设备，主图统一以**唯一设备配置**作为统计单位：

| 处理步骤 | 条目数 | 说明 |
| --- | ---: | --- |
| 原始目录行 | 1,064 | CSV 全部记录 |
| 排除 Android 4.4.x | 1,060 | 按 `^4\.4(?:\.|$)` 精确匹配排除 4 条 |
| 按 `device_label` 精确去重 | 1,029 | 去除 31 条重复配置；这是图 4-1 至图 4-3 的分母 |
| 唯一 `device_name` | 996 | 用于补充审计，不替代主图分母 |

被排除的四条记录如下：

| 设备名称 | Android | 分辨率 |
| --- | --- | --- |
| 华为荣耀 4X(海外) | 4.4.2 | 1280x720 |
| 三星 Galaxy S5(海外) | 4.4.2 | 1920x1080 |
| 三星 Galaxy Mega2(海外) | 4.4.4 | 1280x720 |
| 酷派 8721 | 4.4.4 | 1280x720 |

## 推荐主图

### 图 4-1：机型池范围与构成

主文件：[fig4-1_baidu_mtc_catalog_scope_and_composition.svg](../thesis_materials/top_journal_figures/fig4-1_baidu_mtc_catalog_scope_and_composition.svg)

建议中文图题：**图 4-1 百度 MTC Android 自定义机型池的筛选范围与组成。**

建议图注：原始目录包含 1,064 条记录；排除 4 条 Android 4.4.x 记录并对 `device_label` 精确去重后，得到 1,029 个唯一设备配置。左图给出 Android 主版本分布，右图给出经中英/大小写别名归一化后的前十品牌类别及长尾类别。Android 17 的三条记录均为目录中的预览/测试标签，不应表述为稳定版覆盖。

适合位置：实验设置、设备池来源或数据集构建小节的开头。

### 图 4-2：品牌与系统版本交叉覆盖

主文件：[fig4-2_baidu_mtc_brand_android_coverage.svg](../thesis_materials/top_journal_figures/fig4-2_baidu_mtc_brand_android_coverage.svg)

建议中文图题：**图 4-2 主要品牌类别与 Android 主版本的交叉覆盖。**

建议图注：热力图以 1,029 个唯一设备配置为统计单位，行展示前 12 个标准化品牌类别及其余长尾类别，列展示 Android 主版本；上方和左侧边际柱表示相应的总量。仅在单元格计数不少于 8 时显示数值，避免稀疏矩阵中的视觉噪声。Android 11 的细分隔线仅用于对齐本文的研究边界，不表示低版本设备质量较差。

适合位置：研究对象的覆盖异质性、按设备族群划分测试集或分组评估设计之前。

### 图 4-3：显示几何覆盖景观

主文件：[fig4-3_baidu_mtc_display_geometry_landscape.svg](../thesis_materials/top_journal_figures/fig4-3_baidu_mtc_display_geometry_landscape.svg)

建议中文图题：**图 4-3 百度 MTC 机型池的显示分辨率与折叠形态覆盖。**

建议图注：每个蓝色圆点对应一个精确的物理像素分辨率，横轴和纵轴分别为短边与长边；圆面积与该分辨率下的唯一设备配置数成比例。浅色虚线为 16:9、18:9、20:9 参考比例，橙色空心菱形表示源目录标注为折叠屏的配置。该图反映的是目录记录的物理像素分辨率，不等同于 CSS 逻辑视口、屏幕尺寸或 PPI。

适合位置：讨论 WebView/UI 适配、屏幕特征、设备异构性或指纹特征泛化时。

## 补充图

### 图 S1：统计单位审计

主文件：[figS1_baidu_mtc_counting_unit_audit.svg](../thesis_materials/top_journal_figures/figS1_baidu_mtc_counting_unit_audit.svg)

建议中文图题：**图 S1 设备池统计单位审计。**

用途：放在附录或方法补充材料，用于回应“目录行、唯一配置与唯一设备名称是否被混用”的问题。正文通常无需重复展示，但所有正文百分比都应复用主图的 1,029 个唯一配置分母。

图形形式：采用“原始目录 → 版本排除 → 精确去重 → 名称级复核”的审计流程图；其中 `device_name` 分支是交叉核验，不应被误读为对主分析分母的第二次过滤。

### 图 S2：Android 大版本覆盖轮廓

主文件：[figS2_baidu_mtc_android_major_distribution.svg](../thesis_materials/top_journal_figures/figS2_baidu_mtc_android_major_distribution.svg)

建议中文图题：**图 S2 百度 MTC Android 自定义机型池的系统版本覆盖轮廓。**

用途：以折线-节点轮廓展示各 Android 主版本的唯一配置数，并用背景分区标出 Android 11+ 的研究边界及 Android 17 的预览标签，避免补充图与主图重复使用柱状图形式。

### 图 S3：规范化品牌类别集中度

主文件：[figS3_baidu_mtc_normalized_brand_categories.svg](../thesis_materials/top_journal_figures/figS3_baidu_mtc_normalized_brand_categories.svg)

建议中文图题：**图 S3 百度 MTC Android 自定义机型池的规范化品牌类别集中度。**

用途：以排序点图呈现前五个具名品牌类别与其余长尾类别的占比，同时直接标出前五类别的合计覆盖。该图表达的是目录构成，不是市场份额或真实用户分布。

## 品牌归一化规则

品牌图只合并同一品牌的中英/大小写/记号别名，例如 `三星(SAMSUNG)` 与 `SAMSUNG(三星)` 归为 `Samsung`，`华为(HUAWEI)` 与 `HUAWEI(华为)` 归为 `Huawei`。HONOR、Redmi、iQOO、Civi 等产品或子品牌保持独立，不被合并到母品牌。因此图中“brand category”应译为“品牌类别”，不能写成厂商市场份额。

## 配色规则

图组使用克制的多色语义，而不是为每个类别随机分配颜色：图 4-1 的 Android 版本按代际从紫、青到金递进，品牌条形图使用青色并把“Other”长尾单独标为紫色；图 4-2 以单调紫色热力图编码计数；图 4-3 用青色表示常规分辨率配置、橙色空心菱形表示折叠屏标记。橙色只用于“排除/折叠屏”这类需要立即辨识的状态，避免颜色本身暗示性能优劣。

## 写作边界

- 可写“目录覆盖”“机型池构成”“配置异质性”；不要写成真实用户分布、厂商销量或市场份额。
- `is_overseas_label` 只能称为“目录标注为海外”，不能据此推断国家/地区覆盖。
- CSV 没有价格、上市时间、SoC、RAM、屏幕尺寸或 CSS viewport 字段，不能从这套数据严谨推出价格层级、设备年代、性能等级或 PPI。
- 图内数据单位是目录中的唯一配置，不等同于 1,029 台相互独立的实体手机。

## 输出与复现

每张图同时输出三种格式至 `thesis_materials/top_journal_figures/`：

- `SVG`：推荐用于 LaTeX、Illustrator/Inkscape 编辑与英文投稿；
- `PDF`：推荐用于版式软件和印刷级排版；
- `PNG`：600 DPI，推荐用于 Word 和答辩 PPT。

重新生成：

```bash
conda run -n cross-device-fingerprint python device_cloud_catalog/make_baidu_mtc_paper_figures.py
```

生成脚本在发现目录总量、Android 4.4.x 排除数量或去重后总量偏离当前已核验口径时会主动失败，避免后续 CSV 更新后悄然沿用过期图表。
