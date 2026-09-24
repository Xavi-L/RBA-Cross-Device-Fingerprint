# R08 逐配置留出模型与规则
所有14个GREEDY_OR/OP05模型来自各自LOCO训练折，模型ID均为新值；同一规则签名不等于复用R05模型。全部为单原子OR、规范偏差正极性、复杂度2。
`DEVIATION:OFFDER-UA-001:POSITIVE`：来源O_u，原始别名OFFDER-UA-001。原目录T定义为可解释Android宿主且无显式desktop/headless/script UA或desktop platform标记；该原子的规范偏差采用原目录NEGATIVE方向。本模型再对规范偏差取POSITIVE，不能将两层极性混用。不可用仍U，未修改公共测量门控。字段为native os_version及AppWeb user_agent/platform。
| 折 / 留出配置 | 新模型ID | train/outer阶段 | 训练检出 | clean报警/预算 | 所选规则 |
|---|---|---|---|---|---|
| LOCO-v1-01 / w10-cdp-emulation-screen-metrics-only-v1 | r03-7a4f3a6312a66af6c6e7b4d6 | 153/9 | 24/51 | 0/5 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-02 / w10-cdp-emulation-timezone-only-v1 | r03-a70a243fdfe92e552eecc351 | 153/9 | 24/51 | 0/5 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-03 / w6-tool-054-legacy-default-v1 | r03-0011bb436102cd01df7426ff | 153/9 | 21/51 | 0/5 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-04 / w6-tool-055-legacy-default-v1 | r03-5a786695b062001b1c726866 | 153/9 | 21/51 | 0/5 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-05 / w6-tool-056-legacy-default-v1 | r03-b4b5f05452f7c5b5c437d47e | 135/27 | 15/45 | 0/4 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-06 / w6-tool-058-legacy-default-v1 | r03-2cab61e98f21378e7157aa49 | 135/27 | 24/45 | 0/4 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-07 / w9-rule-boundary-cdp-platform-only-v1 | r03-8637acc243877b91b8870ec9 | 153/9 | 21/51 | 0/5 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-08 / w9-rule-boundary-cdp-resource-pair-v1 | r03-d21cff115688f0697e918161 | 153/9 | 24/51 | 0/5 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-09 / w9-rule-boundary-cdp-ua-only-v1 | r03-bff118051e0588c0271f52ee | 153/9 | 21/51 | 0/5 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-10 / w9-rule-boundary-cdp-ua-platform-desktop-v1 | r03-6235a3e83bb45778ff5dba2b | 153/9 | 21/51 | 0/5 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-11 / w9-rule-boundary-cdp-webdriver-only-v1 | r03-21236f60d1da6714c996ef55 | 153/9 | 24/51 | 0/5 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-12 / w9-stealth-boundary-languages-only-v1 | r03-ab2d70b366141bf0b1beaac4 | 153/9 | 24/51 | 0/5 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-13 / w9-stealth-boundary-plugins-mime-v1 | r03-9c63c7c89791177f9be03168 | 153/9 | 24/51 | 0/5 | DEVIATION:OFFDER-UA-001:POSITIVE |
| LOCO-v1-14 / w9-stealth-boundary-webgl-pair-v1 | r03-eccc2d37d80f51d7134f84ea | 153/9 | 24/51 | 0/5 | DEVIATION:OFFDER-UA-001:POSITIVE |

每折登记20个正/反字面量，13个通过训练支持筛选；其全部train成员、可用三态数、true attack三态、包/环境/配置支持保存在support_statistics和training_support_table。固定DIRECT_CORE_OR每折使用10个规范偏差原子的正向OR，14个基线模型单元未作支持筛选。HISTORICAL_SEVEN仅保存结果适配，模型结构计数明确为0，不把历史检测器实际规则数量解释成零。全部模型/来源/别名见MODEL_MANIFEST、rule_sources_aliases及selected_rules。
