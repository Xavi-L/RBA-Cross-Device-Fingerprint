# 第三轮：方法示意、Host专项与成本表

**初稿已生成／供导师选用。** F00、F09是独立素材编号；F10本轮以T05表格交付，**图形化未制作／暂不需要**。正文／附录、最终图号与版面由导师决定。[全图集入口](../README.md)汇总三轮实际素材，F11保持可选／未制作。

本轮只读已有代码、模型说明和保存结果，筛选、计数、换算单位并制图。0采集、0拟合、0选择、0模型或条件预测、0重新计时；无网络、无新实验。参考HEAD为`6bcb5f50e085c3873c3b7abaf8262adbedc3bb4f`。第一／二轮文件不覆盖，前两轮README的后续停止点属于各自当轮记录。

| 素材 | 输出 | 可复查内容 |
|---|---|---|
| F00 方法与分阶段流程 | [SVG](figures/F00.svg) · [300 dpi PNG](figures/F00.png) | [可编辑节点布局源](F00_source.json) · [节点／来源CSV](data/F00_nodes.csv) · [连线／来源CSV](data/F00_edges.csv) |
| F09 宿主几何专项 | [SVG](figures/F09.svg) · [300 dpi PNG](figures/F09.png) | [绘图CSV](data/F09.csv) · [场景／阶段](data/F09_scenarios.csv) · [正常变化](data/F09_normal_changes.csv) · [环境](data/F09_environments.csv) |
| F10／T05 分阶段成本 | [可读表格](T05.md) | [49行固定主表](data/T05_cost_main.csv) · [148阶段组](data/T05_cost_all.csv) · [1480原批次](data/T05_cost_batches.csv) |

[CAPTIONS.md](CAPTIONS.md)提供中英文图注、结论与限制。[FIGURES.json](FIGURES.json)记录来源、摘要、筛选、角色、分母、尺寸及生成文件；[CHECK.json](CHECK.json)只保存检查项目、计数、失败详情、源摘要和实际视觉范围，不复制完整成功数据。PNG与SVG的验收范围分别记录，未查看的格式不声称视觉通过。

## F00 阅读与编辑

观察位置、离线开发／选择、当前记录判断分区。Native84＋Host26＋App Web67为App177，独立Browser67经保存的会话／回执关联形成paired244；这些是目录规模，非模型全部输入、可用字段或相等要求。Native／Host不是真值认证层。同阶段关联不等于原子同步，关联标识不作为检测特征。

App规则选取、冻结App后的C1增量、资源未通过接入分别表达。MTC630训练与历史144／117评价分开。当前App-only和配对接口不同；pre/post、标签和目标不进入判断。缺Browser关系保留原U语义，不能自动回退为App的F；存在其他T时仍按原组合逻辑处理，选中依赖FAILED优先。F只是未报警，不证明安全。虚线仅表示已测试而未整合的Host几何／资源固定关系。

直接编辑SVG中的文本和矢量图元，或修改`F00_source.json`的`label`、`box`（毫米）和连线`points`后重新生成；声明变化须同时更新节点证据。脚本保持SVG文本可编辑，不嵌入字体。布局源、CSV映射和实际SVG共同交付，不构建额外网站或工具平台。

## F09 范围与明细

只用v15正式72条：正常66、有效屏幕修改6；正常布局扩大中间6是66的子集。三个对象是固定条件，**未纳入当前App完整模型**。旧高度报警6/66、同Web与Host各0/66；修改检出分别6/6、0/6、6/6。收益为正常布局少6次报警并保留6次局部检出，不能替换当前完整App模型的屏幕结果。

[72行脱敏来源定位](data/F09_records.csv)、[24组三阶段效果依据](data/F09_effects.csv)、[三个条件映射](data/F09_conditions.csv)保留独立正常与实际变化依据。旋转只有4/6可观测生效，另2次仍为正常尝试。v16工程12、早期smoke、App378、MTC及资源54均排除。

几何语义为网页视觉尺寸×当前DPR×当前缩放，与同期实测WebView内容区域加既定容差作上界比较，详见[原SEMANTICS](../../../deliverables/screen_geometry_observation_v1/SEMANTICS.md)。不补缺失缩放、不跨快照拼值。固定容差并非所有WebView的保证；真机、非零padding、折叠屏、分屏等正常覆盖不足，上界以内或协调改变可能不触发。

## T05 配套表

主表事先固定为R_FULL三个配置和P0四视图，非按耗时择优。R_FULL实际为App+C1；R_NO_CROSS是旧双端消融的App基线。完整P1/P2和慢批次均保留，后续资源组合和新App消融没有套用旧耗时。

- 判断计算：[主表](data/T05_cost_main.csv)、[全部阶段](data/T05_cost_all.csv)、[共享适配](data/T05_cost_shared.csv)、[原批次](data/T05_cost_batches.csv)、[阶段定义](data/T05_stage_definitions.csv)、[原计时设置](data/T05_timing_settings.csv)。原微秒和展示毫秒并列；加载以每模型为分母，其余通常为60位置批均。P95来自10批均值，不是单请求尾延迟；重叠路径和中位数／P95不能相加。
- 模型与依赖：[7模型主表](data/T05_model_resources_main.csv)、[21模型完整表](data/T05_model_resources_all.csv)。来源元数据、预处理与额外基础模型范围明确；不是精简部署包。
- 既有日志：[60条去标识采集区间](data/T05_collection_intervals.csv)、[先导／匹配分组汇总](data/T05_collection_summary.csv)、[历史训练计时](data/T05_historical_training_timing.csv)。只使用同host保存区间，保留正常偏好持久化等待。纯探针与未记录的训练阶段保持“未记录”。

成本测量不包括设备采集、页面启动、上传与配对等待；热文件系统重复读不等于OS冷启动。树与规则公开接口起点不同，不据此作算法倍速排行榜。完整说明见[T05](T05.md)。

## 生成与只读检查

仓库根目录使用已有绘图环境，不安装软件、不运行前两轮主程序：

```bash
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python -B paper/figures/round3_overview/plot_round3.py
```

只检查保存产物、结构和本地链接（标准库即可；不制图、不读取实验结果、不开网络）：

```bash
python3 -B paper/figures/round3_overview/plot_round3.py --check-only
```

可设置`RBA_ROUND3_QA_DIR=/tmp/rba_round3_qa`生成96 dpi工作尺寸校样。F00宽180 mm、F09宽180 mm，最小字号8 pt。数值检查和画布文字边界检查不能替代实际视觉验收；重生成改变PNG摘要时，旧视觉记录失效。

重复生成只覆盖清单归属为本轮的产物，未知文件不覆盖。源码映射仅静态读取代码，不加载模型对象，不导入或调用训练、选择、推理、条件评价或计时入口。本轮结束于方法示意、Host专项、成本表和导航，不自动提交推送、不启动F11、不写整篇论文。
