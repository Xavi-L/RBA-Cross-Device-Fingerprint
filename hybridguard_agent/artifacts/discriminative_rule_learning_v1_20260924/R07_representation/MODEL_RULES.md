# R07 逐折模型与已选条件

| fold | 视图 | model ID | 状态 | 实际条件与极性 | 复杂度 |
|---|---|---|---|---|---|
| LOEO-v1-01 | app_web67 | r03-72ebee654baa2baecddd499a | FITTED | `CAT:NW-006:POSITIVE` OR `CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE` OR `CONTROL:app.web_data.automation_surface_layer.webdriver:EQ:True:POSITIVE` OR `CONTROL:app.web_data.execution_layer.timezone_offset:LE:0.0:NEGATIVE` OR `CONTROL:app.web_data.navigator_layer.device_memory:LE:2.0:NEGATIVE` OR `CONTROL:app.web_data.navigator_layer.languages:LE:1.0:NEGATIVE` | 12 |
| LOEO-v1-01 | host26 | r03-3b72b7237ab996c6e9731f64 | EMPTY_MODEL | EMPTY_MODEL | 0 |
| LOEO-v1-01 | native84 | r03-4e8db0d13d9d30932f529ff1 | EMPTY_MODEL | EMPTY_MODEL | 0 |
| LOEO-v1-02 | app_web67 | r03-4d84d2da75641777abb9ca64 | FITTED | `CAT:NW-006:POSITIVE` OR `CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE` OR `CONTROL:app.web_data.automation_surface_layer.webdriver:EQ:True:POSITIVE` OR `CONTROL:app.web_data.execution_layer.timezone_offset:LE:0.0:NEGATIVE` OR `CONTROL:app.web_data.navigator_layer.device_memory:LE:2.0:NEGATIVE` OR `CONTROL:app.web_data.navigator_layer.languages:LE:1.0:NEGATIVE` | 12 |
| LOEO-v1-02 | host26 | r03-550c0c8d0ce80f356f455c8e | EMPTY_MODEL | EMPTY_MODEL | 0 |
| LOEO-v1-02 | native84 | r03-b787316a502ef7a0a8a0ec3b | EMPTY_MODEL | EMPTY_MODEL | 0 |
| LOEO-v1-03 | app_web67 | r03-de41c87a2bdd0477fc419b12 | FITTED | `CONTROL:app.web_data.navigator_layer.hardware_concurrency:LE:4.0:NEGATIVE` | 2 |
| LOEO-v1-03 | host26 | r03-c1b5e2c7bc159fd4ec8f39d6 | EMPTY_MODEL | EMPTY_MODEL | 0 |
| LOEO-v1-03 | native84 | r03-a2563a27db70ee2e1e6fc5c7 | EMPTY_MODEL | EMPTY_MODEL | 0 |

AppWeb 前两折的六条件依次为：目录 NW-006 的桌面/脚本 UA 或桌面 platform 标记；mime_types_count>0；webdriver=True；timezone_offset>0；device_memory>2；languages 列表长度>1。后五者属于单层控制编码，不强行归入 E/O_u/H/C。第三折仅选择 hardware_concurrency>4。

数值原子定义为 ≤threshold，所选 NEGATIVE 表示在可用且类型有效时 >threshold；U 的否定仍为 U。CAT:NW-006 的 POSITIVE 使用原目录条件方向，不是跨层规范偏差极性的机械复用。阈值由对应 train 的固定 0.25/0.5/0.75 分位点产生并去重；全部 encoder，包括未入选数值输入的阈值，均在 encoders/ 和 encoder_thresholds.jsonl/csv 保存。

R05 参照模型保持三折原 DEVIATION:OFFDER-UA-001:POSITIVE、每模型复杂度2。其模型ID和原冻结时间见 REFERENCE_MODEL_MANIFEST.jsonl；没有复制改写或新建跨层模型。
