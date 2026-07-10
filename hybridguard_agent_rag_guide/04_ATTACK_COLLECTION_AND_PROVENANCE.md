# 攻击采集、配对真值与来源追踪

> authoritative_for: clean_pre/attack/clean_post、Attack Manifest、事实标签、采集门槛和回滚验证
> read_when: 接入攻击工具、制定采集批次、审核攻击样本或扩充真实真值
> do_not_read_when: 只做现有 V2 数据审计或离线检索实现
> default_read_budget: 先读 ATTACK-PAIRING；再按需读 Manifest、流程或门槛
> allowed_second_books: 03 用于 stable key/QC；07 用于锁定 split

## Agent 锚点索引

| Anchor | 用途 |
|---|---|
| ATTACK-PAIRING | 为什么必须同设备配对 |
| ATTACK-MANIFEST | 攻击 Manifest |
| ATTACK-PROTOCOL | 采集前、clean、attack、clean_post |
| ATTACK-LABELS | 标签与来源正交 |
| ATTACK-GATES | Pilot 和正式采集门槛 |

> 阅读方法：先在本文件中搜索 Anchor，仅读取命中小节及其直接上下文；不要默认通读整册。

---
## 7. 攻击数据采集协议

<a id="ATTACK-PAIRING"></a>

### 7.1 为什么必须同设备配对

如果 clean 和 attack 来自不同设备、不同 provider、不同 App 构建或不同采集批次，模型可能只学到：

- 设备型号；
- provider 特征；
- App 版本；
- WebView 版本；
- 网络或时区；
- 攻击工具的固定模板。

这会让实验看起来很高，但不能证明检测的是攻击。

最小实验单元应为：

~~~text
同一 stable_device_key
同一 collector/app 构建
同一采集路径和主要控制条件

clean_pre
  -> attack
  -> clean_post
~~~

<a id="ATTACK-MANIFEST"></a>

### 7.2 攻击 Manifest 必备字段

~~~json
{
  "attack_run_id": "uuid",
  "attack_family": "cross_layer_spoofing",
  "attack_type": "user_agent_spoofing",
  "tool_name": "tool-name",
  "tool_version": "version",
  "tool_sha256": "sha256",
  "config_id": "config-id",
  "config_sha256": "sha256",
  "target_layers": ["web"],
  "expected_mutations": ["web.user_agent"],
  "execution_status": "verified_success",
  "feature_effect_status": "observed",
  "success_evidence": ["tool-log-ref"],
  "rollback_status": "verified"
}
~~~

必须区分：

- 工具是否执行成功；
- 预期字段影响是否真正出现；
- 最终检测器是否识别；
- 攻击是否被成功回滚。

工具执行成功但特征影响有限，是合法的检测难例；工具执行失败或无法验证，则应标为 invalid/unknown，不能作为正样本。

<a id="ATTACK-PROTOCOL"></a>

### 7.3 推荐采集步骤

#### A. 采集前

1. 固定 expanded-v2、App 版本、Git commit 和 APK hash。
2. 创建 capture_batch_id、pair_id 和 attack_run_id。
3. 记录 provider、设备分配 ID、OS、WebView 版本和控制条件。
4. 固定网络、方向、App 启动方式和预热时间。
5. 在采集前创建 manifest，禁止事后凭记忆补配置。

#### B. clean_pre

1. 重启 App 或按固定流程初始化。
2. 等待固定预热时间。
3. 确认攻击工具、代理、Hook 或修改配置未启用。
4. 采集完整 177 字段。
5. 生成 stable key 和 baseline identity。
6. 通过 Schema 和 QC 门禁后再进入 attack。

#### C. attack

1. 首轮每次只启用一个原子攻击配置。
2. 记录工具、版本、配置、目标层和预期字段。
3. 先用独立日志或外部检查确认执行成功。
4. 再采集 177 字段。
5. 保存工具日志、配置 hash 和观测到的字段变化。
6. 复合攻击单独作为后续组合实验。

#### D. clean_post

1. 移除攻击、Hook、代理或修改配置。
2. 按需要重启 App、WebView 或设备。
3. 验证工具已经断开。
4. 再采集 clean_post。
5. 检查身份和控制条件是否恢复。
6. 回滚失败的样本隔离，不标为 benign。

<a id="ATTACK-LABELS"></a>

### 7.4 标签设计

建议事实标签：

- environment_class；
- manipulation_present；
- violation_types；
- attack_success；
- label_provenance；
- adjudication_status。

建议枚举：

~~~text
source_type:
  physical_local
  cloud_real_device
  cloud_emulator
  local_emulator
  remote_script_client
  unknown

pair_role:
  clean_pre
  attack
  clean_post

label_status:
  verified
  pending
  rejected

execution_status:
  not_applicable
  verified_success
  verified_failure
  unknown
~~~

来源与标签必须正交。例如 cloud_real_device 是来源或环境，不等于 attack；remote_script_client 只描述采集客户端形态，API replay 等攻击语义应单独记录在 attack_type、manipulation_present 和 attack_success 中。

<a id="ATTACK-GATES"></a>

### 7.5 数据规模口径

扩采优先级应为：

1. 增加独立 stable profile；
2. 增加攻击家族；
3. 增加工具、配置和 provider；
4. 增加品牌、Android 版本和 WebView 版本；
5. 最后才是同一画像的重复会话。

建议门槛：

#### Pilot

- 至少 3 个代表性攻击家族；
- 每个家族至少 5 个独立 stable key；
- 完整 clean_pre/attack/clean_post 比例不低于 95%；
- verified attack success rate 不低于 90%；
- stable key 配对一致率 100%；
- 所有失败攻击隔离。

#### 正式分组实验

- 正负类各至少 25 个独立 stable group；
- 若使用 5-fold，每个 fold 至少 5 个正类和 5 个负类 group；
- 核心攻击家族至少 10 个独立 stable key；
- 要单独报告性能的攻击家族应尽量达到 25 个独立 stable key；
- 每个核心家族尽量覆盖多个品牌、Android 版本和来源。

数据不足时应降为 3-fold 或明确标为 pilot，不应为了形式强行使用 5-fold。

---

