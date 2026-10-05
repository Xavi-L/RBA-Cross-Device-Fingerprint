# 上游契约与当前复制源码复核

审计完成：2026-10-04T23:29:22.738342+08:00。固定上游提交：[`a16ba9d`](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/commit/a16ba9dea3078a66b4e8e4338d00d9dd9df9893b)。截至本次在线核查，main最新提交仍为该版本，提交时间为2026年10月3日15:07:50（上海）；未发现10月4日新增提交。

## 本次结论与审计范围

当前活动采集链路来源核验通过。对当前复制目录中539个现存已追踪文件进行了原始字节比较：491个完全一致，48个仅LF/CRLF换行差异，未发现内容变化。不能把整个复制checkout称为Git原始字节完全一致。逐文件路径、Git blob OID、Git SHA-256、actual_sha256、actual_bytes及matches_git保存在[完整审计](source_current_git_audit.json)。

48个差异按目录分布为{'android_app': 9, 'backend_server': 11, 'browser_probe_site': 25, 'hybridguard_agent': 3}。其中包含已披露的4个构建输入（FeatureApp ProGuard、PEM、gradlew及gradlew.bat）、历史后端JSONL、浏览器站点框架/测试和忽略文件。未修改这些文件；差异原样列入审计。旧source_git_blob_audit.json的478个匹配记录没有逐文件清单，本次采用更广范围独立重查，不将旧计数推广为整仓一致声明。

活动链路的以下文件组全部与Git原始字节一致：

| 文件组 | 检查数 | 原始字节一致数 |
|---|---:|---:|
| manifest_compiler_source_inputs | 41 | 41 |
| backend_python_html_requirements | 15 | 15 |
| browser_public_static_probe | 5 | 5 |
| agent_python_json_source_config_schema | 353 | 353 |
| canonical_web_probe_sources | 3 | 3 |

旧Git对象库位于`C:/Users/Henry/Desktop/Poisoning LLM/output/RBA_Browser67_20261004/upstream`，HEAD与固定提交一致，所需blob完整可读。当前副本`.git`信息不完整，审计使用旧对象库的固定提交tree与`git cat-file --batch`读取原始blob；没有对源码执行换行归一化。

本次只读取源码与已复制APK并写入本报告和审计JSON，没有启动、停止或测试采集服务，没有触碰端口、r8数据或修改运行源码。生成的Android build、.gradle、node_modules、__pycache__、Agent artifacts和后端备份不纳入本源码比较；历史后端文件虽列入广义审计，正式打包应排除。唯一额外源码范围文件local.properties是本机SDK配置，其hash单列，不作为上游源码。

## APK与实际探针

复制APK的SHA-256为`9fbe80595a9ec950370d8005cf08ec8bcfd352eb684dc08d75670618c363453d`，与当前构建manifest一致。当前目录未重新构建；55项单测是原构建记录，未在此处重跑。6个APK内置探针资产均与manifest、当前对应源码及Git blob一致。该结论验证复制后的二进制和资产来源，不等于证明整个APK可由此目录字节级复现。

Canonical Web Probe、Browser public副本、APK内置canonical资产、探针manifest声明hash和Git blob的SHA-256均为`a747c8cfc0ca916c02071e632da476bbbf60983bfbd46dcd25ef6bdfb16f3412`；实际revision为`expanded-web-67-v2`。活动采集源码、后端Python、Browser静态探针与Agent Python/JSON来源通过。48个外围换行差异不得被隐藏或写成零。

`run_backend.py`、runner、verifier及delivery builder属于本地实验框架，不能声称来自上游Git。本次给它们单独记录hash，来源与上游源码分开。

## 当前上游要求

[论文前计划](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/a16ba9dea3078a66b4e8e4338d00d9dd9df9893b/RBA_PRE_PAPER_EXPERIMENT_PLAN.md)将B0双端样例验收列为当前优先项：先完成1–2种固定配置的正常、干预、恢复三阶段，每阶段分别采App177与独立Browser67，证明同一设备/配置与同一阶段。两端不要求原子同步，但干预必须在对应Browser采集时仍然有效；字段实际变化与恢复证据独立于检测器输出。

新顺序为保留App阶段成果、Browser样例对齐、新批次验收、跨端方法开发、再确定最终消融和图表。最终模型、最终消融与最终图表冻结当前暂停。现有105/126干预检出、0/252正常报警属于App侧B_REL_TZ阶段成绩，不能作为本次Browser批次或完整paired244结果。[阶段报告](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/a16ba9dea3078a66b4e8e4338d00d9dd9df9893b/RBA_SUPERVISOR_REPORT.md)

按照[采集交付协议](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/a16ba9dea3078a66b4e8e4338d00d9dd9df9893b/ATTACK_SIDE_COLLECTION_SYNC_NOTE.md)，177/67字段不扩增、不改名；每phase必须尝试Browser，失败保留有效App177并给reason，不能补造或填零。正式配对须回连App/Browser canonical payload hash、两端receipt、已正常关闭batch及一对一pair provenance。scenario_group_id与browser_pair_id分开。Manifest逐文件列行数/hash，并分别列app177_valid_count、browser_attempted_count、paired244_completed_count、browser_incomplete_count。

完整sidecar保留执行、作用域、字段效果、归因、撤销与恢复证据。每条App的[latest-experiment-fact-v1投影](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/a16ba9dea3078a66b4e8e4338d00d9dd9df9893b/hybridguard_agent/schemas/latest_experiment_fact_v1.schema.json)使用app_session_id及app_payload_sha256精确绑定，不替代完整日志。

## 旧默认v8与本批真实v16

根README、同步说明和[latest_paired244_sources.json](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/a16ba9dea3078a66b4e8e4338d00d9dd9df9893b/hybridguard_agent/config/latest_paired244_sources.json)仍含v8/expanded-web-67-v1历史默认值。最新计划明确要求按本批实际APK、backend、probe重新锁定，不照抄历史示例，也不要求采集中途追逐最新版本。

固定提交的[实际构建配置](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/a16ba9dea3078a66b4e8e4338d00d9dd9df9893b/android_app/HybridGuard/featureapp/build.gradle.kts)为versionCode=16、versionName=1.6.9-expanded-v2.2-geometry，探针expanded-web-67-v2。使用上游快照构建器时应传本批独立--config，填入真实版本及本批证据路径；保留默认上游文件，不能改数据来满足陈旧v8锁。

## 工程通过与正式研究准入

完整三阶段先导可证明配对来源、字段干预效果与恢复链路，满足B0接入检查；它不提供跨端泛化或检测准确率。未经上游人工/协议核验的标签保持candidate；单次run身份保持run_profile/run_scoped_unverified，不伪装成跨run设备身份。

[实验准入协议](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/a16ba9dea3078a66b4e8e4338d00d9dd9df9893b/hybridguard_agent/config/latest_experiment_protocol.v1.json)要求正式样本具备verified标签、证据引用、可信physical_device/device_profile/provider_device_profile作用域，以及cross_run_verified或provider_verified稳定性。正式分组条件还要求每个划分至少5个独立组、每类至少2组；本次单模拟器先导不能满足该研究条件。实验组、三阶段与关联重复不能跨训练/评价，标签不能由Browser差异或检测报警自动生成。

## 本地可执行交付清单

1. 保留本批固定源码/构建manifest、APK实际hash、实际Browser包名/版本及本审计。
2. 保存最终批次App raw/analysis/receipts、batch、Browser raw/analysis/provenance/events，并保留每phase绑定。
3. 明确干预安装、Probe放行、原始上传、撤销及恢复时序；按原始字段核对效果。
4. 正常关闭backend后导出session provenance，使用独立真实版本config生成paired244/App-only/QC视图。
5. 完整实验sidecar与candidate准入投影分开，身份声明保持run-scoped。
6. 复核四项独立计数、完整三阶段组数、文件hash和来源证明；失败历史另列，不混入最终成功批次。
7. 可移交ZIP只收显式白名单源码与证据，排除私钥、本机SDK配置、历史后端raw/备份及构建缓存；携带本JSON可以复核被纳入源码的actual hash。
