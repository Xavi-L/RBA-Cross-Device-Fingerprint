# P4 规则执行台账

这是检查项台账，不是独立规律或已验证攻击规则的数量。87 项来自旧目录 57 项与 P3 研究目录 30 项；48 项可执行、2 项停用、37 项尚未实现。相似检查保留来源和细微语义差异，不累加成独立风险票。

48 项 = 旧设备规则 10（CORE-002 已改写）+ 旧官方派生 8 + P3 30。按来源分为经验/历史设备 20、官方派生 22、采集器自洽 6。

| ID | 来源 | 执行状态 | 证据家族 | 处置 |
|---|---|---|---|---|
| CORE-001 | device_mined_rule | NOT_IMPLEMENTED | CORE-001 | legacy_natural_language_not_executable |
| CORE-002 | device_mined_rule | ACTIVE | featureapp_bridge | sensor_count_branch_removed_no_short_circuit |
| CORE-003 | device_mined_rule | NOT_IMPLEMENTED | CORE-003 | legacy_natural_language_not_executable |
| NW-001 | device_mined_rule | NOT_IMPLEMENTED | NW-001 | legacy_natural_language_not_executable |
| NW-002 | device_mined_rule | ACTIVE | app_os | legacy_predicate_retained_without_attack_claim |
| NW-003 | device_mined_rule | NOT_IMPLEMENTED | screen_geometry | legacy_natural_language_not_executable |
| NW-004 | device_mined_rule | NOT_IMPLEMENTED | NW-004 | legacy_natural_language_not_executable |
| NW-005 | device_mined_rule | NOT_IMPLEMENTED | NW-005 | legacy_natural_language_not_executable |
| NW-006 | device_mined_rule | ACTIVE | app_surface | legacy_predicate_retained_without_attack_claim |
| NW-007 | device_mined_rule | ACTIVE | mobile_touch | legacy_predicate_retained_without_attack_claim |
| NW-008 | device_mined_rule | NOT_IMPLEMENTED | NW-008 | legacy_natural_language_not_executable |
| NVW-001 | device_mined_rule | NOT_IMPLEMENTED | NVW-001 | legacy_natural_language_not_executable |
| NVW-002 | device_mined_rule | ACTIVE | host_os | legacy_predicate_retained_without_attack_claim |
| NVW-003 | device_mined_rule | NOT_IMPLEMENTED | NVW-003 | legacy_natural_language_not_executable |
| NVW-004 | device_mined_rule | NOT_IMPLEMENTED | NVW-004 | legacy_natural_language_not_executable |
| NVW-005 | device_mined_rule | ACTIVE | debug_cleartext | legacy_predicate_retained_without_attack_claim |
| WVWEB-001 | device_mined_rule | RETIRED | WVWEB-001 | package_version_namespace_is_not_chromium_version |
| WVWEB-002 | device_mined_rule | NOT_IMPLEMENTED | WVWEB-002 | legacy_natural_language_not_executable |
| WVWEB-003 | device_mined_rule | NOT_IMPLEMENTED | WVWEB-003 | legacy_natural_language_not_executable |
| WVWEB-004 | device_mined_rule | ACTIVE | app_surface | legacy_predicate_retained_without_attack_claim |
| PHYS-001 | device_mined_rule | NOT_IMPLEMENTED | PHYS-001 | legacy_natural_language_not_executable |
| PHYS-002 | device_mined_rule | NOT_IMPLEMENTED | PHYS-002 | legacy_natural_language_not_executable |
| PHYS-003 | device_mined_rule | NOT_IMPLEMENTED | PHYS-003 | legacy_natural_language_not_executable |
| PHYS-004 | device_mined_rule | NOT_IMPLEMENTED | PHYS-004 | legacy_natural_language_not_executable |
| PHYS-005 | device_mined_rule | ACTIVE | PHYS-005 | legacy_predicate_retained_without_attack_claim |
| PHYS-006 | device_mined_rule | ACTIVE | PHYS-006 | legacy_predicate_retained_without_attack_claim |
| SCENE-001 | device_mined_rule | ACTIVE | SCENE-001 | legacy_predicate_retained_without_attack_claim |
| SCENE-002 | device_mined_rule | NOT_IMPLEMENTED | SCENE-002 | legacy_natural_language_not_executable |
| SCENE-003 | device_mined_rule | NOT_IMPLEMENTED | SCENE-003 | legacy_natural_language_not_executable |
| SCENE-004 | device_mined_rule | NOT_IMPLEMENTED | SCENE-004 | legacy_natural_language_not_executable |
| AGG-001 | device_mined_rule | NOT_IMPLEMENTED | AGG-001 | legacy_natural_language_not_executable |
| TOL-001 | device_mined_rule | NOT_IMPLEMENTED | TOL-001 | legacy_natural_language_not_executable |
| TOL-002 | device_mined_rule | NOT_IMPLEMENTED | TOL-002 | legacy_natural_language_not_executable |
| TOL-003 | device_mined_rule | NOT_IMPLEMENTED | TOL-003 | legacy_natural_language_not_executable |
| TOL-004 | device_mined_rule | NOT_IMPLEMENTED | TOL-004 | legacy_natural_language_not_executable |
| OFFDER-OS-001 | official_derived_semantic_rule | ACTIVE | app_os | legacy_relation_retained_without_attack_claim |
| OFFDER-OS-002 | official_derived_semantic_rule | ACTIVE | host_os | legacy_relation_retained_without_attack_claim |
| OFFDER-UA-001 | official_derived_semantic_rule | ACTIVE | app_surface | legacy_relation_retained_without_attack_claim |
| OFFDER-WEBVIEW-001 | official_derived_semantic_rule | RETIRED | OFFDER-WEBVIEW-001 | package_version_namespace_is_not_chromium_version |
| OFFDER-UA-002 | official_derived_semantic_rule | ACTIVE | host_ua | legacy_relation_retained_without_attack_claim |
| OFFDER-TOUCH-001 | official_derived_semantic_rule | ACTIVE | mobile_touch | legacy_relation_retained_without_attack_claim |
| OFFDER-BRIDGE-001 | official_derived_semantic_rule | ACTIVE | featureapp_bridge | legacy_relation_retained_without_attack_claim |
| OFFDER-DEVCONFIG-001 | official_derived_semantic_rule | ACTIVE | debug_cleartext | legacy_relation_retained_without_attack_claim |
| OFFDER-GPU-001 | official_derived_semantic_rule | ACTIVE | OFFDER-GPU-001 | legacy_relation_retained_without_attack_claim |
| OFFDER-DISPLAY-001 | official_derived_semantic_rule | NOT_IMPLEMENTED | screen_geometry | legacy_relation_not_executable |
| OFFDER-MEMORY-001 | official_derived_semantic_rule | NOT_IMPLEMENTED | OFFDER-MEMORY-001 | legacy_relation_not_executable |
| OFFDER-SENSOR-001 | official_derived_semantic_rule | NOT_IMPLEMENTED | OFFDER-SENSOR-001 | legacy_relation_not_executable |
| OFFDER-BATTERY-001 | official_derived_semantic_rule | NOT_IMPLEMENTED | OFFDER-BATTERY-001 | legacy_relation_not_executable |
| OFFDER-PACKAGE-001 | official_derived_semantic_rule | NOT_IMPLEMENTED | OFFDER-PACKAGE-001 | legacy_relation_not_executable |
| OFFDER-NET-001 | official_derived_semantic_rule | NOT_IMPLEMENTED | OFFDER-NET-001 | legacy_relation_not_executable |
| OFFDER-PLAY-001 | official_derived_semantic_rule | NOT_IMPLEMENTED | OFFDER-PLAY-001 | legacy_relation_not_executable |
| OFFDER-PLAY-002 | official_derived_semantic_rule | NOT_IMPLEMENTED | OFFDER-PLAY-002 | legacy_relation_not_executable |
| OFFDER-KEY-001 | official_derived_semantic_rule | NOT_IMPLEMENTED | OFFDER-KEY-001 | legacy_relation_not_executable |
| OFFDER-BOOT-001 | official_derived_semantic_rule | NOT_IMPLEMENTED | OFFDER-BOOT-001 | legacy_relation_not_executable |
| OFFDER-WEBSEC-001 | official_derived_semantic_rule | NOT_IMPLEMENTED | OFFDER-WEBSEC-001 | legacy_relation_not_executable |
| OFFDER-PLUGIN-001 | official_derived_semantic_rule | NOT_IMPLEMENTED | OFFDER-PLUGIN-001 | legacy_relation_not_executable |
| OFFDER-EMULATOR-001 | official_derived_semantic_rule | NOT_IMPLEMENTED | OFFDER-EMULATOR-001 | legacy_relation_not_executable |
| P3-X-TIMEZONE-OFFSET | device_mined_rule | ACTIVE | P3-X-TIMEZONE-OFFSET | EMPIRICAL_RESEARCH_RELATION |
| P3-X-LANGUAGE | device_mined_rule | ACTIVE | P3-X-LANGUAGE | EMPIRICAL_RESEARCH_RELATION |
| P3-X-TOUCH | device_mined_rule | ACTIVE | P3-X-TOUCH | EMPIRICAL_RESEARCH_RELATION |
| P3-X-CORES | device_mined_rule | ACTIVE | P3-X-CORES | EMPIRICAL_RESEARCH_RELATION |
| P3-X-DPR | device_mined_rule | ACTIVE | screen_geometry | EMPIRICAL_RESEARCH_RELATION |
| P3-X-SCREEN-SIZE | device_mined_rule | ACTIVE | screen_geometry | EMPIRICAL_RESEARCH_RELATION |
| P3-SCREEN-APP | device_mined_rule | ACTIVE | screen_geometry | EMPIRICAL_RESEARCH_RELATION |
| P3-COLOR-APP | official_derived_semantic_rule | ACTIVE | P3-COLOR-APP | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-SCREEN-BROWSER | device_mined_rule | ACTIVE | screen_geometry | EMPIRICAL_RESEARCH_RELATION |
| P3-COLOR-BROWSER | official_derived_semantic_rule | ACTIVE | P3-COLOR-BROWSER | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-UA-REDUCED-BROWSER | official_derived_semantic_rule | ACTIVE | P3-UA-REDUCED-BROWSER | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-UA-DEFAULT | device_mined_rule | ACTIVE | host_ua | EMPIRICAL_RESEARCH_RELATION |
| P3-UA-SETTINGS | device_mined_rule | ACTIVE | host_ua | EMPIRICAL_RESEARCH_RELATION |
| P3-PROVIDER-PARSE | collector_derived_consistency | ACTIVE | P3-PROVIDER-PARSE | COLLECTOR_CONSISTENCY_ONLY |
| P3-GPU-COPY | collector_derived_consistency | ACTIVE | P3-GPU-COPY | COLLECTOR_CONSISTENCY_ONLY |
| P3-MEM-AVAILABLE | official_derived_semantic_rule | ACTIVE | P3-MEM-AVAILABLE | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-SENSOR-NAME_COUNT | collector_derived_consistency | ACTIVE | sensor_structure | COLLECTOR_CONSISTENCY_ONLY |
| P3-SENSOR-VENDOR_COUNT | collector_derived_consistency | ACTIVE | sensor_structure | COLLECTOR_CONSISTENCY_ONLY |
| P3-SENSOR-TYPE-COUNT | collector_derived_consistency | ACTIVE | sensor_structure | COLLECTOR_CONSISTENCY_ONLY |
| P3-SENSOR-TYPE-ORDER | collector_derived_consistency | ACTIVE | sensor_structure | COLLECTOR_CONSISTENCY_ONLY |
| P3-SENSOR-ACCELEROMETER | official_derived_semantic_rule | ACTIVE | sensor_structure | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-SENSOR-MAGNETIC_FIELD | official_derived_semantic_rule | ACTIVE | sensor_structure | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-SENSOR-GYROSCOPE | official_derived_semantic_rule | ACTIVE | sensor_structure | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-SENSOR-LIGHT_SENSOR | official_derived_semantic_rule | ACTIVE | sensor_structure | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-SENSOR-PRESSURE_SENSOR | official_derived_semantic_rule | ACTIVE | sensor_structure | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-SENSOR-PROXIMITY_SENSOR | official_derived_semantic_rule | ACTIVE | sensor_structure | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-SENSOR-GRAVITY_SENSOR | official_derived_semantic_rule | ACTIVE | sensor_structure | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-SENSOR-ROTATION_VECTOR | official_derived_semantic_rule | ACTIVE | sensor_structure | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-SENSOR-STEP_DETECTOR | official_derived_semantic_rule | ACTIVE | sensor_structure | SEMANTIC_RESEARCH_CONSTRAINT |
| P3-SENSOR-STEP_COUNTER | official_derived_semantic_rule | ACTIVE | sensor_structure | SEMANTIC_RESEARCH_CONSTRAINT |

其中 `WVWEB-001` 与 `OFFDER-WEBVIEW-001` 是同一个不成立的版本假设在两个旧目录中的条目，所以台账“停用 2 项”不等于又推翻两条独立新假设。`CORE-002` 保留桥接检查，删除低传感器数量否决分支，也取消短路。

旧官方和经验关系即使有相近的条件，其适用性、缺失状态、UA 空白处理和来源仍可能不同；当前保留逐项执行，用 evidence_family 表示共享证据，禁用权重和求和。P3 中重新验证旧 UA、屏幕思路的项也不会被宣称为全新规律。
