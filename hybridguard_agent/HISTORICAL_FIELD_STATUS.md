# 历史云真机的字段状态补标

旧的 `expanded_collected_data.jsonl` 没有采集端上报的 `collection_status`，但当前冻结契约可验证它的完整 payload。每次运行 `build_dataset_snapshot.py` 时，管线会为通过 expanded-v2 校验、又没有采集端状态对象的原始记录生成：

`artifacts/<run_id>/historical_field_status_backfill.jsonl`

每条 sidecar 以 `sample_id`、`session_id_hash` 和原始 payload SHA-256 关联，并明确写入：

- `status_schema_version: field-status-v1-historical-inferred`；
- 177 个**扁平 expanded-v2 契约字段**的状态；
- `collector_emitted: false`，说明这不是当时 App 上报的状态；
- 推断依据和不能推断的内容。

对通过当前固定 field-set 和类型校验的历史记录，每一个 177 字段都存在且非空，所以 sidecar 会标为 `177 observed / 177`。这与旧 App 的“完整三层 payload 才上传”流程一致，但 sidecar 仍不能倒推单个探针的真实失败原因。

不能补造 `collection_manifest`：旧数据没有持久 `collector_install_id`、`android_user_id`、受管 Profile 状态、provider run ID 或 collection round。管线仍会生成启发式稳定画像键供 QC/分组使用，但它不是 `device_manifest_id`，不能伪装成采集时记录的设备画像。

新版本 featureapp 会直接上报 `collection_manifest` 和 `collection_status`（内部版本 `field-status-v1`）。新记录应优先使用采集端状态，而不是这个历史补标 sidecar。
