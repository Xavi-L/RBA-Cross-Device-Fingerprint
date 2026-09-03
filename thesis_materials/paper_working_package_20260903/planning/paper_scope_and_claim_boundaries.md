# HybridGuard 论文范围与主张边界

更新时间：2026-09-03

## 1. 论文当前定位

当前最稳健的论文主线不是“已经完成生产级风险评分系统”，也不是“已经证明 244 维联合特征提升了攻击检测”，而是：

> HybridGuard 是一套面向 Android Hybrid Web 环境的、来源可追溯且缺失语义明确的多层指纹采集与一致性分析框架。它把 Android Native、WebView Host 和 App 内 Web Runtime 的观测组织为 App177，并在受控 `baseline -> attack_active` 协议下验证跨层语义关系能够覆盖哪些环境操纵，同时显式保留不可判定状态、合法反例和当前规则盲区。

推荐工作标题：

> **HybridGuard: Provenance-Aware Cross-Layer Fingerprint Consistency for Android Web Environments**

`Cross-Layer` 比 `Cross-Device` 更准确，因为当前核心问题是同一设备在多个运行层和容器中的环境表征是否一致，而不是多台物理设备之间的身份关联。

## 2. 四个观测面

论文需要严格区分以下观测面：

1. **Android Native**：Android 系统、硬件、Build、内存、显示、传感器、电池和运行状态。
2. **WebView Host**：WebView provider、默认 User-Agent、JSBridge、包与安装上下文、调试和网络安全配置。
3. **App Web Runtime**：在 App 内 WebView 中执行的 JavaScript 探针，包括 UA、platform、screen、DPR、WebGL、Canvas、语言、插件和运行时能力。
4. **External Browser**：由独立系统浏览器执行的 Browser67 探针。

前三层形成当前受控攻击实验使用的 **App177**。独立浏览器形成 **Browser67**。只有两端原始载荷、receipt、关闭批次和 pair provenance 均满足合同，才派生 **paired244**。

## 3. 当前可写为已完成的内容

- 固定字段合同的 App177 采集链。
- 独立 Browser67 探针及其配对协议。
- 后端 receipt、batch、payload hash、raw archive 和 pair provenance。
- `paired244`、`app_only_177`、`quarantine`、sample index、selection audit、QC 和 dataset manifest。
- 字段值与字段状态分离；Browser 缺失不填零。
- SampleManifest、EvidenceBundle、KnowledgeCard 和 DecisionTrace 的数据/证据建模。
- 官方文档知识、官方派生语义关系和 device-mined rule 的来源分离。
- 确定性规则执行、适用性判断、容错、反例和 `not_assessed` 语义。
- 当前 App177 两态受控验证及其覆盖边界。
- 标签和稳定设备分组的实验准入、整组切分和防泄漏框架。

## 4. 当前实验口径

导师要求主实验只考虑：

```text
baseline -> attack_active
```

历史 `clean_post` 不作为主实验状态、准入条件、分母或主要结论依据。若后续个别攻击能够可靠撤销，可以把恢复状态作为附加归因证据，但不能改变主实验的两态定义。

当前冻结受控配置上：

- 229 条正常输入；
- 69 个合格 baseline/attack-active 对；
- 9 条官方派生语义关系产生 51 个“baseline 无报警 -> attack_active 报警”转换；
- 10 条 device-mined predicate 产生 33 个转换；
- 33 对被两轨共同覆盖；
- 18 对只被官方派生语义轨覆盖；
- 18 对两轨均未覆盖。

这些数字只能称为 **controlled relation-transition counts** 或 **controlled relation-violation coverage observations**。不得称为攻击召回率、总体准确率、生产 FPR 或跨工具泛化性能。

## 5. Browser67 与 paired244 的当前边界

由于当前严重缺乏带 Browser67 的完整受控攻击配对数据，现阶段攻击验证直接使用 App177。这不是设计缺陷，也不阻塞草稿写作，但必须在正文中明确阶段边界。

当前可以主张：

- Browser67 探针和采集协议已经实现；
- App 与 Browser 的来源完备配对、App-only 留存和缺失语义已经实现；
- paired244 数据视图能够由 provenance 完整的原始输入确定性派生。

当前不能主张：

- 现有 69 个攻击对属于 paired244 实验；
- 当前决策路径联合消费全部 244 个字段；
- Browser67 已经提高攻击检测效果；
- paired244 已经完成独立设备或 OOD 泛化验证。

完整数据到位后，应在相同两态协议下重新采集，并比较 App177-only、Browser67-only、App177+Browser67、加入 Browser-specific relations 的完整方法，以及移除 Browser67 的消融版本。

## 6. 历史与预验证内容

不限篇幅草稿可以暂时保留：

- 随机 holdout 和 grouped CV；
- teacher risk score；
- RF、MLP 和 Positive ElasticNet；
- LLM 分组评分、RAG、Verifier 和官方知识消融；
- 端侧 riskapp 和轻量部署实验。

这些内容必须放在独立的 `Historical and Preliminary Validation` 章节，并说明数据版本、标签来源和结论限制。正式投稿时再决定保留、压缩、移入附录或删除。

## 7. 禁止使用的越界表述

- “HybridGuard achieves 73.9% attack recall.”
- “The full 244-dimensional detector has been evaluated.”
- “Browser67 significantly improves detection.”
- “Official knowledge improves prediction accuracy.”
- “The system detects fraud or account takeover.”
- “The current results generalize across devices, tools and future attacks.”
- “Google/Android official rules classify these samples as attacks.”

更安全的表达是：

> On the frozen controlled cohort, project-derived relations grounded in official field semantics exhibited baseline-no-alert to active-alert transitions for 51 of 69 qualified pairs. These transitions characterize relation coverage under the tested configurations and are not interpreted as attack recall or production risk estimates.
