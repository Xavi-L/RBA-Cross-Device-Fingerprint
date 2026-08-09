# HybridGuard 攻击侧最新采集同步说明

> 状态：供下一批攻击实验前对齐使用。本文只约定采集与交付，不要求攻击侧实现主仓的 Agent、RAG、数据切分或模型。

## 结论

- 当前 **不增加或改名** App 177 项、Browser 67 项信号字段。
- 正式新采集默认目标为 `paired244`：同一实验阶段分别取得 App177 和独立 Browser67，并由 backend provenance 配成一个样本单位。主侧在通过 QC 后生成 244 维派生视图，供给侧不改变两份原始 payload 的独立 Schema。
- 每个 `clean_pre | attack_active | clean_post` 阶段都必须尝试 Browser67；Browser 失败时保留有效 App177，并记录失败状态与原因，不能补造或填零。
- 新实验必须使用双方确认并冻结的最新版 FeatureApp、主仓 FastAPI backend 和 Web Probe，不能继续使用旧轻量 receiver 或旧 APK lock。
- 攻击侧负责交付可追溯的 App/Browser 原始采集、身份与实验事实；主侧第一批只负责 QC 和244维派生视图，Evidence、切分/标签实验、Agent/RAG 与模型属于后续阶段。
- 历史 `expanded-v2.1-status`、旧 APK lock 和旧实验结果保持原样，不重标为新版本。

## 为什么需要同步

攻击侧当前 release lock 仍是 upstream `3a16d89`、FeatureApp `1.2` / versionCode 2；主仓当前 FeatureApp 已是 `1.6.1-expanded-v2.2-browser-recovery` / versionCode 8，并包含独立 Browser67 配对。

此外，现有攻击脚本主要等待 `expanded_collected_data.jsonl` 中的 App 分析行，没有完整绑定 App canonical raw、receipt、backend batch 和 Browser pair。旧攻击 `pair_id` 表示 clean/active/post 实验组，而主仓 `pair_id` 表示一条 App session 与一条 Browser session 的配对，二者不能混用。

## 攻击侧需要做的最小调整

### 1. 每批先冻结 release manifest

至少记录：

- upstream commit；
- FeatureApp versionName/versionCode、APK SHA-256；
- `feature_schema_version=expanded-v2.2-status`；
- 177 字段目录版本及 hash，并注明 hash 是 source bytes、规范化内容还是 APK 内置 asset；
- collection protocol/readiness 版本；
- backend commit；
- `browser_schema_version=browser-web-v1-status`；
- `web_probe_revision=expanded-web-67-v1` 及 Web Probe core hash；
- Browser pair provenance schema 版本。

不要覆盖历史 lock；为新批次生成新的 lock。

### 2. 活动 runner 使用主仓 backend

- 停止使用只有 `/health` 和裸上传接口的轻量 receiver；它没有标准 receipt、batch、raw archive 和 Browser pair 接口。
- 正式采集前调用 `/api/collect/readiness`，至少确认：batch 为 `open`、batch ID 非空、App 固定 177、Browser 固定 67、raw archive 与 receipt 已启用。
- runner 按 `collection_batch_id + runtime_context + collection_round + device_manifest_id` 找到本次新 session，不再依赖全量 JSONL 的行数差。
- 保存后端返回的 `receipt_id`、canonical `payload_sha256` 和 `collection_batch_id`。若保留分析行 hash，请命名为 `receiver_projection_sha256`，不能冒充 canonical payload hash。
- 正式批次应正常关闭 backend；不要把强制结束进程产生的批次写成 `closed_cleanly`。

### 3. WebView 攻击只补 debug-only 控制

CDP/stealth 等正式 WebView 实验需要最新版上游 debug APK 支持：

- `ENABLE_WEBVIEW_DEBUG`；
- `PROBE_DELAY_MS`。

这两个 Intent 必须受 `BuildConfig.DEBUG` 保护，release APK 必须忽略。攻击侧直接使用更新后的上游 debug APK，不再把历史 API29 patch 覆盖到最新版源码上。

Browser companion 在 App payload 已持久化后启动。runner 每个 scenario phase 都必须触发 Browser 尝试，并在进入下一 phase 前等待 `completed`、明确终态或有界超时。`completed` 计为 paired244；失败或超时计为 App-only，但不删除 App177，也不阻断后续 phase。首轮不增加 browser disable/defer 开关；只有实测确认外部浏览器抢前台影响 runner 时，才讨论 debug-only 延迟开关。

### 4. 分开实验组与浏览器配对标识

新 sidecar 使用：

- `scenario_group_id`：同一组 clean/active/post 共用；
- `scenario_repetition`：第几轮重复；
- `scenario_phase`：`clean_pre | attack_active | clean_post`；
- `browser_pair_id`：某一条 App session 与某一条 Browser session 的一对一配对，由 backend provenance 提供；
- `collection_round`：原始采集轮次，不替代 scenario repetition。

一个 scenario group 有三条 App session，正式目标是三个 paired244 单位。每个 phase 必须记录一次 Browser 尝试：成功时恰有一个 `browser_pair_id`；失败或不支持时 `browser_pair_id=null`，但必须提供 `browser_capture_status` 和 reason code。`not_requested` 仅允许用于历史数据或明确批准的协议豁免，不能作为新版正式采集的正常状态。历史攻击 `pair_id` 读取时可映射为 `scenario_group_id`，但新数据不再复用这个名称。

### 5. 补齐身份与干预作用域

- 提供隐私安全、非空的 stable device/Profile key，并写明作用范围和稳定性。
- 如果只能证明同一次 run 内一致，标记 `run_scoped_unverified`，不得伪装成可跨 run 的设备身份。
- 明确 `intervention_scope`：`app_native | app_webview_host | app_web_runtime | external_browser_web | network_path | system_runtime`。
- 明确 `expected_external_browser_effect=true | false | unknown`。App WebView 与外部 Browser67 不一致不能自动成为攻击标签。

## 每个 run 的最小交付

### App 侧

- `raw_expanded_payloads.jsonl` 中本批次的 canonical raw；
- App177 分析行；
- `collection_receipts.jsonl` 中对应 receipt；
- 对应 batch 记录或本批 session provenance。

### Browser 侧

每个 scenario phase 都需交付 Browser 尝试结果：

- `browser_capture_status=completed | attempted_incomplete | unsupported`；
- 非 `completed` 时必须提供 reason code；
- `not_requested` 仅用于 legacy 或 `protocol_exception`，且不能进入正式 paired244 主视图。

`completed` 时交付：

- `raw_browser_payloads.jsonl`；
- `browser_collected_data.jsonl`；
- `browser_pair_provenance.jsonl`。

`attempted_incomplete` 或 `unsupported` 时，交付相关 pair events、runner/browser launch diagnostics 或终态说明；已经签发的 pair 不得静默丢失。

同时记录 resolved browser package；版本可取得时一并记录，无法取得时保留 `unknown`，不得推测。

Browser 失败只阻断该 phase 的 paired244/Browser-pair 实验资格，不会抹掉有效的 App177 实验记录。App-only 样本不能补造 Browser67，也不能把缺失值填零后伪装成244维样本。

### 攻击事实 sidecar

- scenario group/phase/repetition；
- attack run、工具和固定配置的 ID/版本/hash；
- execution、observable effect、field effect、attribution、rollback、label status；
- expected/observed mutation；
- 可定位的工具日志、截图或配置证据。

工具名、攻击标签和实验角色不得写入 App177 或 Browser67 原始信号。

### Delivery manifest

列出版本锁、run/batch、文件名、行数、文件 hash、App/Browser session 和隔离原因，并分别报告 `app177_valid_count`、`browser_attempted_count`、`paired244_completed_count` 和 `browser_incomplete_count`。

## 供给侧不需要做的事情

- 不实现主仓 latest-only snapshot builder；
- 不生成 EvidenceBundle、Browser pair evidence 或 DecisionTrace；
- 不把 App177 与 Browser67 拼成供给侧自定义的扁平244维 payload；主侧统一生成派生视图；
- 不划分 train/dev/test；
- 不做特征选择、风险分、阈值、分类器、RAG 或 Agent 评估；
- 不把候选攻击标签直接升级成正式评估标签。

这些工作由主侧在收到全部数据后统一完成。

## 验收标准

- 新 APK、backend、Web Probe 与 release manifest 一致；
- 每个 scenario phase 均有一条可验证 App177，canonical raw、receipt、batch 可回连，177 项状态合同通过；
- 每个 phase 均有 Browser 尝试证据，不允许新版正式数据静默 `not_requested`；
- paired244 主视图只接收 `pair_status=completed` 且 App canonical hash、Browser canonical hash、两端 receipt 与 provenance 可回连的记录；
- Browser67 固定字段及状态合同通过；部分字段为 `unsupported_by_os` 或 `not_applicable` 不等于字段数不足；
- Browser 失败的 phase 保留在 App177 留存视图，并具有明确 status/reason；
- scenario group 与 browser pair 使用不同 ID；
- stable device/Profile identity 非空并注明稳定范围；run-scoped identity 不进入正式 grouped split；
- raw 中没有攻击标签、工具名或实验角色；
- candidate 标签在正式 label gate 前保持隔离；
- 四项交付计数可以相互核对，不把 App 数、Browser 尝试数和 completed pair 数混为一个样本数。

## 将来真的增加信号字段时

本轮不改变 177/67 信号目录。以后如确需新增、删除、改名或改变字段类型，必须：

1. 主侧先给出字段定义、类型、采集层、状态语义和必要性；
2. 显式升级 feature schema 或 Browser schema/catalog revision，不能继续沿用旧版本名；
3. 同步修改 collector/probe、backend validator、字段状态、供给侧 validator 和 release lock；
4. 先用少量 clean/active/post 做合同验收，再开始批量采集；
5. 旧数据保留旧 schema，不补默认值伪装成新版本。

仅新增 envelope/provenance metadata 时，不改变 177/67 维数；消费者应保留未知 metadata，并按 required subset 做兼容校验。
