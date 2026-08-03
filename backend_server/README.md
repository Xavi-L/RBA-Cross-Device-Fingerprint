# Expanded collection provenance contract

This directory stores the `featureapp` expanded-collection outputs. The contract
below is deliberately about **sessions and platform profiles**, not unproven
physical-device identity.

## Files and authority

| File | Purpose | Hash-verifiable original payload? |
| --- | --- | --- |
| `raw_expanded_payloads.jsonl` | New immutable archive of a newly accepted expanded request, before merge/flattening. | Yes. `canonical_received_payload` is re-hashed with the same canonical JSON rule used by its receipt. |
| `expanded_collected_data.jsonl` | Flattened analysis/training view. | No. It is useful for feature analysis, but not a replacement for an archived request. |
| `expanded_merged_sessions.json` | Mutable latest merged view keyed by `session_id`. | No. It is not an immutable request archive. |
| `collection_receipts.jsonl` | Server receipt per HTTP request: session, receipt ID, canonical payload hash, validation and duplicate status. | It authenticates the canonical payload only when joined to `raw_expanded_payloads.jsonl`. |
| `collection_batches.jsonl` | Append-only backend lifecycle ledger: batch start, clean close, or next-start recovery of an unclean close. | It establishes the server-process batch boundary; it is not a platform run ID. |
| `session_provenance.jsonl` | Derived, per-session handoff sidecar made by `export_session_provenance.py`. | Reports whether its source was a verified raw archive or a legacy flattened record. |
| `raw_browser_payloads.jsonl` | Canonical available-browser request before normalization. | Yes. Its `browser_payload_sha256` hashes `canonical_received_payload`. |
| `browser_provisional_payloads.jsonl` | Browser payload received before the matching App receipt. This is quarantine/staging evidence only. | Yes, but it is not a formal paired sample until delayed binding completes. |
| `browser_collected_data.jsonl` | Validated 67-Web-signal browser analysis row. | The linked raw browser archive remains the hash authority. |
| `browser_pair_events.jsonl` | Ticket issuance, expiry, acceptance, duplicate and replay-conflict audit events. | Tokens are deliberately never persisted. |
| `browser_pair_provenance.jsonl` | One completed App-receipt ↔ browser-receipt linkage per pair. | Joins both canonical hashes within one backend lifecycle batch. |

`raw_expanded_payloads.jsonl` starts only after this backend version is deployed.
It preserves the parsed, canonical `incoming_data` used for hashing; it is not a
byte-for-byte HTTP wire capture. That distinction is intentional: JSON whitespace
and key order are not evidence, while the canonical content and `payload_sha256`
are stable.

## `session_provenance.jsonl` 的作用

`session_provenance.jsonl` 是按 `session_id` 生成的**来源关联 sidecar**，不是
177 维特征数据，也不替代原始 payload。它让接收攻击数据的一方能在不手工拼接
多个 JSONL 的情况下，定位一条 session 的数据来源和解释边界。

每行包含：

- `profile_id`、Profile 规则与 `collection_round`；
- 后端自动生成的 `collection_batch_id`、批次生命周期状态、平台名，以及有真实值时的 `platform_run_id`；
- 品牌/型号、Android API、WebView 与 App 版本、schema；
- `receipt_id`、`payload_sha256`、服务器接收时间与校验结果；
- `raw_payload_available` 与 `payload_sha256_verification`，说明原始 payload
  是否存在、是否可以由 receipt 验证；
- `device_hash` 的作用域与声明，避免把 Profile Hash 误写成平台或物理设备 ID。

关联方式是：以 `session_id` 找到 `raw_expanded_payloads.jsonl` 中的原始嵌套
payload，以 `receipt_id`/`payload_sha256` 核对 `collection_receipts.jsonl`；177
维信号只从原始 payload 或扁平化分析记录读取，不复制到 sidecar。

它不提供攻击标签、平台物理设备证明或跨任务稳定性证明。对于历史扁平化记录，
导出器会保留 Profile/轮次关联，但必须以
`raw_payload_available=false` 和
`payload_sha256_verification=not_verifiable_from_flattened_analysis_record`
明确标记其边界。

## Profile rule used for this platform

The platform owner states that there is no pair of different platform devices
with the same model and OS version, while one model may appear with several OS
versions. Under **that stated platform rule**, the exporter creates:

```text
profile_id = HMAC-SHA256(
  profile-v1 | platform_provider | normalized_brand | normalized_model | normalized_os_version
)[0:24]
```

The result has the form `hgprof-v1-...`. By default, the exporter reads the
ignored root file `.hybridguard_profile_hmac_key`; an explicitly set environment
variable overrides it for CI. The key must not enter source control, JSONL
files, shell history, or a handoff package.

This is a `provider_catalog_brand_model_os` **Profile ID**, not a provider's
physical-device identifier. The app's `collector_install_id` and default
`device_manifest_id` are App-install-lifecycle identifiers, so the exporter
does not use them as the canonical Profile ID. `os_api_level` is retained as an
audit field; inconsistent API values for one brand/model/OS Profile cause the
export to fail rather than silently split or merge a Profile.

If a downstream schema requires `device_hash`, the exporter writes the same
HMAC value but also writes all of the following boundaries:

```text
device_hash_scope = provider_model_os_profile
device_hash_is_platform_device_id = false
platform_device_hash = null
platform_device_hash_status = not_collected_not_required
```

Do not describe this value as a platform device ID or physical-device hash.

## 后端进程生命周期批次 / Backend lifecycle batch

一次正式后端服务启动到正常停止，对应且只对应一个自动生成的
`collection_batch_id`（形式为 `hgbatch-v1-...`）。这不是 App Intent 参数、云测平台
操作员输入、平台 run ID，也不是设备 ID。

- FastAPI startup 先恢复上一进程遗留的未闭合批次，再向
  `collection_batches.jsonl` 写入当前批次的 `started` 事件；
- 本次服务期间每一条 `collection_receipts.jsonl` receipt 都带相同的
  `collection_batch_id`；新 observation 的 `raw_expanded_payloads.jsonl` archive
  envelope 也带相同值。客户端 canonical payload 与其 SHA-256 不会因此改变；
- 正常 SIGINT/SIGTERM 停服会写入 `closed_cleanly`。若断电、SIGKILL 或崩溃，下一次
  启动会写入 `unclean_shutdown_recovered`；其 `ended_at` 仅是最后可观察 receipt 时间，
  **不是**可证明的真实崩溃时间；
- `active_collection_batch.json` 只是运行中的本地恢复标记，正常关闭会删除，不属于
  handoff 文件。

因此云测平台可以同时启动多台设备：它们并发上传到同一个后端 worker，但仍属于同一
批次。当前 JSON/JSONL 持久化会在一个 worker 内依次落盘；不要在同一目录启动第二个
后端实例，也不要使用 `--workers 2+`。正式采集不用 `--reload`，因为重载会开始新的
后端生命周期、也就是新的批次。

App 不需要修改，也不需要为此设置 Intent extra。`GET /api/collect/readiness` 会显示
当前打开的 `collection_batch_id`，可用于采集开始前确认后端已就绪。

## 可用浏览器 67 维配对协议

浏览器行使用独立的 `collector_app=browserprobe` 和
`schema_version=browser-web-v1-status`，不能伪装成 App 的 177 维 expanded 行。它以
`web_probe_revision=expanded-web-67-v1` 和完整的 67 项
`collection_status.fields` 固定字段集证明采集合同与 App 的 Web 子集一致。

1. App 完成 177 项 payload 并持久化后，立即并行执行 App 上传和
   `POST /api/collect/browser-ticket`。同一个高熵 `ticket_request_id` 同时写入 App
   payload 与 provisional ticket 请求；此时不伪造尚不存在的 receipt/hash。
   App 不要求设备已设置默认浏览器：它显式选择一个合格的可用浏览器包，并随 ticket
   请求记录 package、Activity、候选 package、选择状态和策略版本。
2. 后端先以 `provisional_session` 模式签发 `pair_id`、一次性 10 分钟
   `browser_ticket` 和 1 小时 `poll_token`。相同 `ticket_request_id` 与相同请求内容
   返回完全相同的 pair/token；内容变化则以
   `409 TICKET_REQUEST_REPLAY_CONFLICT` 拒绝。旧 App 仍可在 receipt 到达后使用
   `receipt_bound` 模式。
3. `probe_url` 只在 URL fragment 中携带 `pair_id`、`browser_ticket`、
   `browser_upload_url`、`browser_stage_url` 和启动次数，避免它们进入静态站访问日志
   和 HTTP Referrer。
4. App 与静态页以各自 token 调用 `POST /api/collect/browser-stage`，记录
   `launch_attempted`、`page_loaded`、`adapter_started`、`collection_started`、
   `collection_finished`、`upload_started` 和 `upload_failed`。这些是传输诊断，不增加
   或改变 Web67 特征。
5. 静态页以 `Authorization: Bearer <browser_ticket>` 调用
   `POST /api/collect/browser-fingerprint`；跨 ngrok 时同时发送
   `ngrok-skip-browser-warning: 1`。若 App receipt 尚未到达，浏览器 payload 只进入
   `browser_provisional_payloads.jsonl` 隔离区，状态为 `awaiting_app`；只有后端将
   receipt、session、batch、request ID 和 canonical App hash 全部绑定后，才写入正式
   `browser_collected_data.jsonl` 与 `browser_pair_provenance.jsonl`。完全相同的重试
   只返回幂等 receipt；同 ticket 的不同 payload 返回 `409`。
6. App 以 `Authorization: Bearer <poll_token>` 调用
   `GET /api/collect/browser-pairs/{pair_id}`，状态为
   `awaiting_app_and_browser`、`awaiting_app`、`awaiting_browser`、`completed`
   或 `expired`。

后端还会把 ticket 指定的静态页 origin 与 payload 的
`probe_metadata.page_origin` 配对，并验证 `core_revision`、67 字段计数和
canonical bundle SHA-256。默认只允许 `https://xavi-l.github.io` 签发 ticket；
迁移静态站时用逗号分隔的 `HYBRIDGUARD_BROWSER_PROBE_ORIGINS` 显式配置允许
origin，不能接受任意 HTTPS 页。

两个 HMAC token 都绑定 `pair_id`、当前 `collection_batch_id`、App session、
`ticket_request_id` 和 binding mode；receipt-bound token 还绑定 App receipt。
provisional token 的不可变 claims 不会因随后补入 receipt 而失效。签名错误、用途错误、
过期、request ID 不一致或跨 batch token 均 fail closed。默认 HMAC key 在进程启动时
安全随机生成，正好服从“一次后端进程一个 batch”的边界；如需由部署环境显式管理，
可设置 `HYBRIDGUARD_BROWSER_TOKEN_HMAC_KEY`，但不得写入仓库、日志或采集文件。

## Session and collection-round rule

One App launch has one UUID `session_id`. A retry of the same payload creates a
new receipt with `duplicate_payload=true` and `stored_new_jsonl_row=false`; it
does **not** create a new observation or a new round.

For a backend-lifecycle-generated `collection_batch_id`, the exporter assigns:

```text
collection_round = row number within (collection_batch_id, profile_id)
                   ordered by the first receipt where stored_new_jsonl_row=true
                   using server_received_at, then session_id for ties
```

The App manifest's `collection_round` is retained separately as
`declared_collection_round` when present. It is not the authoritative repeated-
launch counter because an automatic cloud launch without an Intent extra uses
the App default of `1` every time.

If a payload input contains the same `session_id` more than once, or its raw
archive and receipt hashes disagree, the exporter fails closed. Resolve or
quarantine that data instead of silently associating incompatible payloads.

## Platform run ID

Use `platform_run_id` only when the provider exposes an actual report/task/run
identifier. When it is unavailable, the exporter records `null` and
`platform_run_id_status=not_available`. The backend-generated
`collection_batch_id` is a local lifecycle boundary only; never rename it as a
platform run ID.

## Export a new batch

Stop the backend after all expected receipts have arrived, then run this from
`backend_server/`. By default the exporter reads `collection_batches.jsonl`,
selects the most recently closed backend batch, and ignores older unbatched
archives. The backend does not write `session_provenance.jsonl` automatically on
shutdown: the exporter intentionally remains a post-run step because
`platform_provider` is a semantic Profile-HMAC input. The
repository-root `.hybridguard_profile_hmac_key` is the default local key file;
it is Git-ignored and must be mode `600` (`chmod 600 ../.hybridguard_profile_hmac_key`).
For CI, set `HYBRIDGUARD_PROFILE_HMAC_KEY`; the environment variable takes
precedence without changing the file.

```bash
python3 export_session_provenance.py \
  --platform-provider '<platform-name>' \
  --platform-run-id '<provider value only when available>' \
  --profile-hmac-key-id wetest-profile-key-2026-01 \
  --input raw_expanded_payloads.jsonl \
  --receipts collection_receipts.jsonl \
  --output session_provenance.jsonl
```

Omit `--platform-run-id` if the platform does not expose one. `--platform-provider`
remains explicit because it is a semantic input to the Profile HMAC and cannot
be inferred honestly from an HTTP request or the batch ID. It is not an
"operator" field. Keep the same
HMAC key and key ID for batches that should retain comparable Profile IDs. Key
rotation requires a new key ID and makes new Profile IDs intentionally
different. Use `--hmac-key-file /safe/path/key` only when moving the local key
outside the repository root.

To re-export an earlier closed backend batch, pass its ledger ID explicitly:
`--collection-batch-id hgbatch-v1-...`. The exporter verifies that it is closed
in `collection_batches.jsonl`; it does not relabel it as a platform run.

The v2 sidecar includes the session, Profile/round semantics, provider/run status,
backend-batch lifecycle status, receipt ID, payload hash, validation result,
brand/model/API, WebView version, App version, schema, and raw-payload
verification state. The 177 signal values
remain in the archived payload or analysis record rather than being duplicated
into the provenance sidecar.

## Legacy or pre-lifecycle-batch records

The automatic rule applies only to requests received after this backend version
starts writing `collection_batch_id`. Older flattened records, and even older
raw archives that lack that envelope field, cannot be retroactively proved to
belong to a server lifecycle. Export them only with an explicit legacy grouping
label:

```bash
python3 export_session_provenance.py \
  --platform-provider '<platform-name>' \
  --collection-batch-id legacy-20260724-01 \
  --input raw_expanded_payloads.jsonl \
  --receipts collection_receipts.jsonl \
  --output session_provenance_legacy_raw.jsonl
```

If the original raw archive does not exist, use the flattened view instead:

```bash
python3 export_session_provenance.py \
  --platform-provider '<platform-name>' \
  --collection-batch-id legacy-20260724-01 \
  --input expanded_collected_data.jsonl \
  --receipts collection_receipts.jsonl \
  --output session_provenance_legacy_flattened.jsonl
```

Every legacy grouping is explicitly marked:

```text
collection_batch_id_source = legacy_cli_supplied
```

The legacy raw-archive command still has
`raw_payload_available=true` and
`payload_sha256_verification=verified_canonical_raw_archive` when its receipt
matches. The flattened-only command is instead marked:

```text
raw_payload_available = false
payload_sha256_verification = not_verifiable_from_flattened_analysis_record
```

Here `--collection-batch-id` is only a human-supplied legacy grouping label. It
must not be described as a backend-lifecycle batch or platform run ID.

Do not upgrade a legacy flattened record into a claimed original payload.
Historical `expanded-v2` rows may also lack `collection_manifest`; their
Profile and round are therefore backend-derived rather than App-declared.
