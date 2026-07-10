# 当前数据、Schema、稳定分组与质量门禁

> authoritative_for: 当前 155/154 数据快照、177 字段口径、canonical registry、stable key、QC 和冻结产物
> read_when: 审计数据、实现 Schema/Normalizer、计算 stable key、处理异常值或质量门禁
> do_not_read_when: 只写论文结论、实现 Retriever 或调整 LLM Prompt
> default_read_budget: 数据统计、Schema、stable key、QC 四类锚点按需读取
> allowed_second_books: 02 用于契约变更；04 用于攻击采集

## Agent 锚点索引

| Anchor | 用途 |
|---|---|
| DATA-BASELINE | 当前数据审计与资产缺口 |
| DATA-SCHEMA | expanded-v2 Schema 与字段分类 |
| DATA-STABLE-KEY | stable_device_key 与 split group |
| DATA-QC | 硬错误、警告、风险证据和冻结产物 |

> 阅读方法：先在本文件中搜索 Anchor，仅读取命中小节及其直接上下文；不要默认通读整册。

---
<a id="DATA-BASELINE"></a>

## 2. 当前仓库与数据基线

### 2.1 177 字段数据审计结论

当前 backend_server/expanded_collected_data.jsonl 应被定义为：

> 未标注环境采集样本。

不能把它直接称为 benign、正常设备数据或攻击数据。

| 检查项 | 当前结果 | 行动含义 |
|---|---:|---|
| JSONL 行数 | 155 | 会话数，不是独立设备数 |
| JSON 有效性 | 155/155 | 可以直接建立校验和转换管线 |
| 唯一 session_id | 155 | 当前无 session_id 重复 |
| expanded-v2 | 154 | 全部严格为 Native 84 + WebView 26 + Web 67 = 177 |
| expanded-v1 | 1 | 第 1 行仅 154 字段，必须从 177 字段实验视图中隔离 |
| V2 固定字段缺失 | 0 | 当前 V2 结构完整 |
| V2 字段类型 | 68 number、38 boolean、66 string、5 array | 177 是结构化字段数，不是 177 个数值维度 |
| UI 动态计数 | 194–256 | 数组展开后的显示值，不能作为论文固定维度 |
| 当前全常量字段 | 71/177 | 当前批次无区分度，但不能据此永久删除 |
| 仅有 2–5 种取值 | 37/177 | 需要更多来源和攻击场景重新评估 |
| V2 device_model | 76 种 | 表面覆盖大于独立画像覆盖 |
| V2 build_fingerprint | 79 种 | 明显少于 154 条会话 |
| 保守稳定画像 | 约 80 组 | 当前有效独立规模应按约 80 报告 |
| 处于重复画像组的 V2 样本 | 138/154，89.6% | 随机按行切分会严重泄漏 |
| 重复会话盈余 | 74 | 不能作为独立设备增加统计可信度 |
| 标签与攻击字段 | 不存在 | 不能训练或评估真实攻击识别 |
| 来源平台字段 | 不存在 | client_ip 全为 null，来源不可审计 |

重复画像的进一步事实：

- 64 个重复组中，57 个组的重复采集发生在 5 分钟内。
- 重复组采集跨度中位数约 262 秒。
- 149/177 个字段在所有重复组内从未变化。
- uptime、可用内存、剩余存储、运行耗时等少量运行态字段会制造“每行都不同”的表象，但这不是独立设备多样性。

#### 2.1.1 当前采集环境共因

154 条 V2 样本全部具备以下环境特征：

- ADB 开启；
- 开发者选项开启；
- App 可调试；
- Wi-Fi；
- CN / Asia/Shanghai；
- WebGL2 不支持。

这说明 ADB、debuggable、地区、网络等字段当前主要反映采集协议，而不是风险标签。任何把这些字段直接归纳为“恶意”的规则都会受到环境共因污染。

#### 2.1.2 已发现的数据语义和质量风险

1. 16 条 battery_voltage_mv 等于 4，可能存在 V/mV 单位差异或厂商返回异常。
2. 94/155 条 screen_resolution_physical 与 display mode 不同；当前前者更接近应用可用显示区域，不应被直接解释为物理屏幕被篡改。
3. 21 条存在代理痕迹，其中 4 条有实际代理 host；但当前没有 manifest 说明代理是否为预期环境。
4. 多个 Audio、字体、插件、MIME、权限错误字段当前恒定或为空。
5. 当前 V2 数据集中采于 2026-07-09 和 2026-07-10，存在明显时间与批次效应。

这些现象说明：在 LLM 自动生成风险规则之前，必须先建立字段语义、单位、缺失和异常值规范。

### 2.2 当前数据可以支持的工作

当前 154 条 V2 数据足以支持：

- expanded-v2 权威 Schema；
- 字段字典和 canonical path registry；
- 类型、缺失、常量、低变和异常值审计；
- stable_device_key 与重复画像分析；
- 六组 EvidenceBundle 设计；
- 规则卡、官方卡和检索索引结构；
- LLM 结构化输出、Verifier 和 DecisionTrace 联调；
- Full-KB、Exact、BM25 等检索基线 smoke test；
- 未标注环境数据上的稳定性与误报风险分析。

当前数据不能支持：

- 有监督攻击检测模型训练；
- 把这 154 条样本全部当作 benign；
- “RAG 提升攻击检测准确率”的结论；
- 攻击识别消融；
- 把 session 数量当作独立设备数量；
- 把 ADB、debuggable、代理、云设备或模拟器环境直接等价为恶意。

### 2.3 当前可复用资产

项目不需要从头重建所有组件。

| 资产 | 当前状态 | 后续定位 |
|---|---|---|
| scoring/rule_knowledge_base.json | 35 条规则；34 条带 official_knowledge；3 条 short-circuit | 正式规则的当前权威输入 |
| google_official_kb/official_sources.jsonl | 30 条官方来源元数据 | 官方来源登记表，后续补正文快照和段落锚点 |
| google_official_kb/feature_risk_cards.json | 20 张风险卡；15 张当前可用，5 张 future-only | 官方知识卡输入 |
| llm_grouped_fusion_validation/prepare_validation_assets.py | 已有稳定身份、证据分组、哈希、权重和扰动逻辑 | 复用到新 EvidenceBundle 管线 |
| llm_grouped_fusion_validation/score_group_evidence_with_glm.py | 已有六组结构化 GLM 输出和断点续跑 | 复用评分接口与缓存格式 |
| llm_grouped_fusion_validation/evaluate_cached_group_fusion.py | 已有 grouped CV 与 Positive ElasticNet | 复用为实验融合评估器 |
| scoring/generate_bad_data.py | 旧 65 字段模拟攻击模板 | 只做流水线 smoke test，不作为真实攻击真值 |
| LLM_GROUPED_FUSION_PLAN.md | 六组评分、权重学习和防泄漏设计 | 继续作为专项融合计划 |

### 2.4 当前关键缺口

#### 2.4.1 177 字段尚未完全进入知识与证据体系

当前主规则库只显式引用约 42/177 个原始字段。V2 新增的 23 个字段尚未进入规则库、官方卡片和六组 evidence payload：

- Native GPU/EGL/GLES 相关 5 个字段；
- Web Audio、字体、权限、插件/MIME hash 等 18 个字段。

新增字段的首轮优先级：

| 优先级 | 字段族 | 当前建议 |
|---|---|---|
| P0 | Native GPU 与 WebGL GPU 族 | 优先构建跨层 GPU 一致性证据 |
| P1 | GLES、EGL、WebGL 能力 | 作为 GPU 和渲染能力的辅助证据 |
| P1 | Permissions 状态 | 先作为 WebView 版本和运行上下文变量，不单独判高危 |
| P2 | audio_hash、font hash | 先作为弱画像或漂移证据 |
| P3 | error、plugin/MIME 空值和当前常量字段 | 保留原值，暂不生成高风险规则 |

#### 2.4.2 存在多套字段路径

- 原始 merged session 使用分层路径；
- expanded_collected_data.jsonl 使用拍平路径；
- 官方卡片主要使用分层路径；
- 当前规则库主要使用扁平路径。

必须建立 canonical field registry，明确每个字段的：

- canonical_path；
- nested_path；
- flat_path；
- 类型；
- 所属层和证据组；
- 是否允许缺失；
- 异常值和单位；
- 稳定性类别；
- 是否可进入 stable key；
- 是否可发送给外部模型；
- 当前规则和官方卡覆盖情况。

#### 2.4.3 后端还没有权威 expanded-v2 契约

backend_server/main.py 当前依靠 extra=allow 接收扩展子层，因此新字段可以落盘，但：

- 新增层未全部进入强类型 Pydantic 定义；
- OpenAPI 不能完整表达 177 字段；
- schema_version 本身也没有成为严格契约；
- 采集端字段漂移不会被服务端立即拒绝。

因此第一阶段应先建立 expanded_v2.schema.json 和 field_registry.json，再决定是否同步改造后端模型。

#### 2.4.4 当前还没有真正的 RAG 与 Agent

当前 LLM 评分链路主要是把整份规则库放入 Prompt。仓库尚未实现：

- 知识卡统一格式；
- 索引版本；
- 字段硬过滤；
- Exact/BM25/Dense/Hybrid 对照；
- reranker；
- 引用验证；
- train-fold-only 案例库；
- Agent 编排；
- 完整 DecisionTrace。

这不是缺点，而是清晰的下一阶段工程边界。当前整库 Prompt 应保留为强基线。

### 2.5 已有试验给出的重要提醒

当前 targeted K0/K1 试验中，加入官方知识后：

- direct MAE 从 2.367 变为 2.750；
- 高风险 F1 均为 1.000；
- 低危弱开发配置出现少量误升。

因此官方知识的当前价值更明确地体现在：

- 字段语义；
- 来源引用；
- 容错边界暴露；
- future-only 证据约束；
- 可审计解释。

不能预设“官方知识或 RAG 一定提高总体数值指标”。后续实验必须允许得到以下结论：

> 官方知识没有提高攻击检测率，但降低了语义错误、无依据引用或边界误判。

这仍然是有效、可发表的系统结论。

---

## 6. Schema、规范化与 stable_device_key

<a id="DATA-SCHEMA"></a>

### 6.1 expanded-v2 权威 Schema

第一阶段必须固定：

- 84 个 Native 字段；
- 26 个 WebView 字段；
- 67 个 Web 字段；
- 每个字段类型；
- 数组元素类型；
- 是否允许空值；
- 默认值、错误值和 unsupported 语义；
- 单位与归一化规则；
- 嵌套/扁平路径映射。

任何新增、删除、重命名或语义变化都必须升级 schema_version，而不是继续依赖宽松接收。

### 6.2 字段稳定性分类

每个字段至少分为：

1. **稳定身份字段**：可用于 stable key。
2. **半稳定环境字段**：可用于证据，但不决定设备身份。
3. **运行时字段**：只描述当前会话，可作为扰动或动态证据。
4. **攻击可能篡改字段**：不能在 attack 样本上重新计算 stable key。
5. **标签/审计元数据**：永远不进入模型输入。

<a id="DATA-STABLE-KEY"></a>

### 6.3 stable_device_key 生成原则

stable_device_key 必须优先在 clean_pre 阶段确定，之后传播给 attack 和 clean_post。不能从攻击后的可篡改字段重新计算。

优先级：

1. 云平台或本地设备稳定 ID 的脱敏 hash；
2. provider device ID + clean 基线身份；
3. 无外部 ID 时，由 clean 基线稳定字段生成启发式 key。

建议 clean 基线字段：

- build_fingerprint；
- device_model、device_product、device_board、device_hardware；
- os_api_level、build_id；
- 排序后的 supported_abis；
- 排序后的物理显示宽高；
- 分桶后的 total_memory_gb；
- sensor_total_count 和排序后的 sensor_type_list；
- 标准化 Native GPU vendor/renderer family。

不应进入 stable key：

- uptime 和 elapsed realtime；
- avail memory 和剩余存储；
- 电量、温度、电压和充电状态；
- 网络、代理、VPN；
- 语言、时区；
- 安装时间；
- bridge latency 和 compute time；
- 具体 UA/WebView 版本；
- orientation；
- canvas/audio/font hash。

同时保存：

- stable_device_key_hash：由 clean 基线确定，整个配对实验不变；
- observed_identity_hash：每条观测按实际字段计算；
- identity_drift_fields：attack 相对 clean 基线发生变化的身份字段。

正式拆分时建议：

~~~text
device_group_id =
  acquisition_domain + "::" + stable_device_key_hash

split_group_id =
  pair_root_id（存在配对时）
  或 device_group_id（无配对时）
~~~

攻击类型和标签绝不能成为分组键的一部分。

---

<a id="DATA-QC"></a>

## 8. 数据质量门禁

### 8.1 硬错误

以下任一情况应 quarantine 或 reject：

- JSON 无法解析；
- 非 expanded-v2 进入 177 字段实验；
- Native/WebView/Web 固定字段数不是 84/26/67；
- 固定字段缺失或类型错误；
- sample_id、session_id 或 payload hash 冲突；
- manifest 缺失或不能一一关联；
- capture 时间和 pair 顺序矛盾；
- attack 没有 verified success evidence；
- clean/attack stable key 不一致；
- 同一 stable key 或 pair 被拆到不同 fold；
- 测试样本进入经验规则或案例索引。

### 8.2 质量警告

警告保留原始值，不静默删除或覆盖：

- battery_voltage 原值疑似以 V 返回；
- display metrics 与 display mode 不一致；
- Permissions API unsupported；
- plugin/MIME/audio/font 可选字段为空；
- 当前批次字段恒定；
- WebView、UA 或 hash 因软件升级漂移。

电压建议保留：

~~~text
battery_voltage_raw
battery_voltage_normalized_mv
battery_voltage_normalization_rule
~~~

原始 JSON 永远不修改，归一化只发生在派生数据层。

### 8.3 不能被清洗掉的风险证据

以下可能正是攻击效果，不能按“异常值”删除：

- Native 与 Web 型号不一致；
- GPU vendor/renderer 不一致；
- UA 与 OS 不一致；
- 时区、语言或屏幕关系不一致；
- 代理、VPN、ADB、root 或 Hook 状态变化；
- canvas/audio/font hash 相对 clean 基线变化。

这些应进入 observed_mutations 和 EvidenceBundle。

### 8.4 建议 QC 状态和错误码

~~~text
QC 状态：
  accepted
  accepted_with_warning
  quarantined
  rejected

硬错误：
  E_JSON_PARSE
  E_SCHEMA_VERSION
  E_FEATURE_COUNT
  E_FIELD_TYPE
  E_MANIFEST_MISSING
  E_RAW_HASH_MISMATCH
  E_DUPLICATE_SAMPLE
  E_PAIR_INCOMPLETE
  E_ATTACK_UNVERIFIED
  E_STABLE_KEY_MISMATCH
  E_GROUP_LEAKAGE

警告：
  W_BATTERY_UNIT
  W_SCREEN_METRIC_SEMANTICS
  W_OPTIONAL_API_UNSUPPORTED
  W_SOURCE_UNKNOWN
  W_CONSTANT_FEATURE
  W_ENVIRONMENT_DRIFT
~~~

### 8.5 每次数据冻结必须生成的产物

~~~text
schema_audit.json
feature_profile.csv
sample_manifest.jsonl
quality_failures.jsonl
pair_audit.csv
stable_group_audit.csv
source_label_crosstab.csv
batch_label_crosstab.csv
split_manifest.csv
dataset_build_manifest.json
~~~

dataset_build_manifest.json 至少记录：

- 原始文件 hash；
- 接受、警告、隔离和拒绝数量；
- session 数和 stable profile 数；
- Schema 和 stable key 版本；
- 生成脚本 commit；
- 随机种子；
- split manifest hash。

---

