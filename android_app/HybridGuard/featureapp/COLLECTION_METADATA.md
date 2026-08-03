# featureapp 采集契约与付费批次验收

`:featureapp` 当前版本为 `1.6.1-expanded-v2.2-browser-recovery`
（`versionCode=8`），面向 Android API 21+，上报 `expanded-v2.2-status`。177 个原始
信号仍按 Native 84、WebView 26、Web 67 的固定口径组织；新增对象都是采集元数据，
不能作为模型特征。

## 三类元数据

- `collection_manifest`（`device-profile-manifest-v1`）：记录安装/Profile、Android API、WebView/App 版本、运行批次与轮次，用于稳定分组和追溯；
- `collection_status`（`field-status-v1`）：对 177 个固定信号逐项记录 `observed`、`unsupported_by_os`、`permission_denied`、`runtime_error`、`timeout` 或 `not_applicable`；
- `collection_diagnostics`：记录 Web 子探针状态和 Native 侧保底原因，用于解释默认值或空值来自“不支持”还是“采集失败”。

这里的 `collection_status.fields` 是采集可用性；攻击登记表中的 `field_effect_status` 是“干预是否改变了目标字段”。二者语义不同，不能互相替代。

## API 21+ 降级原则

`minSdk` 已降到 21，但新 API 不会被强行调用：Display Mode、Security Patch、NetworkCapabilities、cleartext policy、WebView provider、managed-profile 等能力按系统版本守卫。旧系统不支持的字段保留在 177 字段契约中，值为 `null`，状态为 `unsupported_by_os`；它们不是采集失败，也不要求伪造非空值。

运行 `python3 device_cloud_catalog/verify_featureapp_api21_coverage.py` 可复核当前百度 MTC CSV：1064 行中 Android 5.0+ 共 1060 行，只有 4 行 Android 4.4 被明确排除。

本地 Web 探针已移除 `async/await`、箭头函数、`Array.from` 等旧 WebView 可能无法解析的语法。若 WebView 页面、JSBridge 或子探针仍在 15 秒内没有返回，Native 层会生成带 `timeout` 状态的部分 payload 并继续上传，不会整条丢弃。

## 稳定画像和编排参数

首次启动会在 App 私有存储生成 `collector_install_id`。未提供外部设备标识时，它也作为 `device_manifest_id`，因此代表“该次安装所在的 Android Profile”，不等于跨重装、跨云机生命周期的物理设备 ID。

编排端可传入：

```text
com.example.hybridguard.featureapp.DEVICE_MANIFEST_ID  # provider/device 稳定标识
com.example.hybridguard.featureapp.RUNTIME_CONTEXT     # provider:run-id 等批次上下文
com.example.hybridguard.featureapp.COLLECTION_ROUND    # 同一 run 的轮次，从 1 开始
com.example.hybridguard.featureapp.COLLECT_ENDPOINT    # 仅 debug APK 接受的临时 endpoint
```

`DEVICE_MANIFEST_ID` 只接受 1–96 位字母、数字、`.`、`_`、`:`、`-`。攻击工具、攻击结果、clean/active/post 角色和人工标签必须留在独立登记表中。

## Endpoint、readiness 与回执

默认 endpoint 为模拟器使用的 `http://10.0.2.2:8000/api/collect/fingerprint`。为真机云构建 APK 时用 Gradle 属性固化地址：

```bash
./gradlew :featureapp:assembleDebug \
  -PhybridguardCollectEndpoint=https://example.test/api/collect/fingerprint \
  -PhybridguardRequirePublicEndpoints=true
```

`hybridguardRequirePublicEndpoints=true` 是云测构建门禁：collect、browser-ticket 和
browser-pairs 必须使用同一公网 HTTPS origin 及规定路径，任何 `10.0.2.2`、localhost、
凭据、query 或 fragment 都会让构建直接失败。未启用该门禁时仍保留模拟器默认地址。

App 每个进程首次上传前会验证 `GET /api/collect/readiness`，确认后端支持当前 schema、部分 payload 和 collection receipt。POST 成功后还会检查响应中的 `receipt_id`、`session_id` 与 `payload_sha256`；仅 HTTP 200 或 ngrok HTML 页面不会被误判为采集成功。

上传回执按 `collection-receipt-v1` 验证 receipt ID/hash 格式、内外层
`session_id`、collector/schema、存储目标、验证状态和 `collection_batch_id`。
每次 Activity 还生成稳定的 `browser_ticket_request_id`，并把它写入已持久化的 App
payload。payload 落盘后，App 上传与 provisional browser-ticket 请求立即并行：
ticket 不伪造尚不存在的 receipt/hash；后端等 App receipt 到达后，用同一
request ID、session、batch 和 canonical payload hash 完成最终绑定。

## 可用浏览器配对采集

默认静态 HTTPS 探针为
`https://xavi-l.github.io/RBA-Cross-Device-Fingerprint/`；ticket 和 poll
地址默认从 `hybridguardCollectEndpoint` 的 origin 推导，也可分别覆盖：

```bash
./gradlew :featureapp:assembleDebug \
  -PhybridguardCollectEndpoint=https://backend.example/api/collect/fingerprint \
  -PhybridguardRequirePublicEndpoints=true \
  -PhybridguardBrowserProbeBaseUrl=https://probe.example/ \
  -PhybridguardBrowserTicketEndpoint=https://backend.example/api/collect/browser-ticket \
  -PhybridguardBrowserPairPollBaseUrl=https://backend.example/api/collect/browser-pairs \
  -PhybridguardWebProbeRevision=expanded-web-67-v1
```

静态页只托管 HTML/JS，不保存 ngrok 域名或 token。每次采集的后端地址、pair ID
和短期 browser token 都由 App 写入 URL fragment；页面读取后立即清空 fragment。
其余默认值不会另存一份 ngrok 域名，避免 collect/ticket/poll 指向不同隧道。

App 会枚举全部可见的 HTTPS `VIEW+BROWSABLE` handler，并与
`MAIN+APP_BROWSER` 声明及受审查的浏览器包/标签规则交叉判断。若系统已明确解析到
合格浏览器，记录 `available_browser_resolved`；若未设置默认浏览器但存在合格候选，
按固定顺序选择并记录 `available_browser_ranked`。只有网页处理能力、但不能证明是
独立浏览器的社交/搜索 App 不会被选中；没有合格候选时记录
`no_trusted_browser_candidate`，完全没有 HTTPS handler 时记录 `no_handler`。
整个策略版本记为 `available-browser-v2-package-scoped`，同时持久化选中 package、解析到的 Activity
和候选 package 列表。177 项 payload 完成并落盘后，App 一边上传 payload，一边申请
provisional ticket；ticket 返回后立即对 `probe_url` 限定选中 package，并让浏览器
自行路由正确的内部 Activity，不会弹出跨 App 的系统 chooser。App 和静态页会上报
`launch_attempted`、`page_loaded`、采集与上传等阶段；若8秒内没有页面阶段且 App 已
回到前台，只进行一次 package-scoped 重启。WorkManager 携带独立 Bearer poll token 轮询 pair，
浏览器无需回跳 App。poll token 和 browser ticket 只保存在 App 私有存储或 URL
fragment 中，日志不打印 token。

仓库根 `web_probe/canonical_web_probe.js` 是 Web 67 维的唯一采集核心；
`:featureapp` 构建会校验该目录并作为额外 assets 打包，WebView 和静态浏览器页
应只保留各自的薄适配层。

后端输出：

- `expanded_merged_sessions.json`：按 session 保存的原始嵌套结构；
- `expanded_collected_data.jsonl`：完整或部分 expanded payload；
- `collection_receipts.jsonl`：每次请求的服务器接收时间、payload hash、重复抑制和验证警告；
- `browser_provisional_payloads.jsonl`：browser 先到时的隔离暂存，不能计作完成样本；
- `browser_collected_data.jsonl` 与 `browser_pair_provenance.jsonl`：receipt/hash
  绑定完成后才写入的正式 browser 行与配对证据。

## 付费批次前最低验收

1. 用最终部署地址构建 APK，并访问 `/api/collect/readiness`；
   当前后端必须保持单 uvicorn worker，不能让多个进程竞争 JSON/JSONL 文件；
2. 运行 `./gradlew :featureapp:lintDebug` 和 `./gradlew :featureapp:assembleDebug`；
3. 用本地 API 21、23、26、30 和最新 API 模拟器走至少一遍安装、启动、上传；免费随机真机只补充厂商差异，不承担完整边界覆盖；
4. 检查 `collection_receipts.jsonl` 有相同 session/request ID 的有效回执；
5. browser 先到时允许短暂出现 `awaiting_app`，但正式验收必须以
   `browser_pair_provenance.jsonl` 的 `pair_status=completed` 为准；
6. 运行 `hybridguard_agent/scripts/run_pipeline.py`，确认新批次没有 schema/status
   错误后再扩大云测范围。

无脚本的标准兼容/Monkey 测试不会替设备跳过浏览器欢迎页；本策略不要求设备预先设置
默认浏览器，但至少要有一个可见、已启用且可显式启动的合格浏览器。首次启动页、无浏览器、
安装失败、网络中断和平台过早卸载仍需单独统计。若 App 即时上传失败而 WorkManager 后续成功，
receipt 会按同一 `browser_ticket_request_id` 自动激活已存在的 provisional pair，不需要
Activity 再回到前台签发第二张 ticket。

Android Lint 能确认代码不存在未守卫的新 API 调用，但不能证明 1060 台设备的厂商 WebView、网络和云平台编排都相同，因此保底上传、逐字段状态和服务器回执仍然必须保留。
