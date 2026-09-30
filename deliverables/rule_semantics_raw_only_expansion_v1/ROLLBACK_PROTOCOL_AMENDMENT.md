# 撤销观测修订：保留原失败，独立登记修正后的尝试

在第一次扩展的 API 30 与 API 29 环境中，原时区 runner 报告 ROLLBACK_FAILED。原日志显示 Emulation.setTimezoneOverride 的撤销命令成功，时区已从 America/Los_Angeles 恢复到 Asia/Shanghai，偏移恢复到 -480；与此同时 WebView inner/outer/visual viewport 高度发生变化（API30 约639→573）。原判据比较整个运行时对象，因非时区部分不同而拒绝。

FeatureApp 的 activity_main.xml 使用 wrap_content 的状态文字面板和 layout_weight=1 的 WebView。MainActivity 在上传及浏览器伴随流程更新状态文字，因此上传前后的宿主可用视口不保证等高。日志证明“时区已恢复但整个运行时对象不相等”；上述布局机制提供了非时区差异的解释，不能将原全量不相等直接写成全字段恢复成功。

本修订不覆盖或改名原失败，不更改 App、攻击参数、配置 ID、模型候选、预算或语义中的 U。攻击侧仓库不修改；本仓库保留原 runner 源码快照，并派生 week10_cdp_emulation_runtime_v2.mjs，只修订撤销观测的合同。

修订后的两级核查：

1. 原进程中：撤销命令必须成功。时区配置必须恢复时区 ID 与偏移；屏幕配置必须恢复 screen.width/height、availWidth/availHeight、devicePixelRatio 五个 CDP 状态锚点。任何缺失或不一致均失败。原完整对象比对结果继续保存，绝不声明它已相等。
2. 独立重新启动后的 clean_post：必须与 clean_pre 在该配置声明的**所有**字段上恢复一致，包括屏幕配置的 inner/outer/visual viewport 字段。只允许原配置预先规定的数值容差；不根据本轮偏差拟合新容差。缺少 clean_post、字段不可观测或恢复失败，整组三联样本不能准入。

运行时回执中 paired_payload_restoration_required=true，measurementRevision=cdp-runtime-rollback-plus-paired-restoration-v2。这个回执单独不等于最终三联样本准入；独立 audit_effects.mjs 必须完成第二级核查。

原计划的失败与未尝试位置继续保留并进入过程统计。等原三个环境的执行退出后，逐一登记尚无完整三轮的配置，创建独立修订 campaign，每配置仅一次三轮采集机会、不自动重试。已完成的配置复用原完整三联样本，不重复挑选。最终主比较成员必须明确列出来源及排除原因；技术失败不能被报告成模型漏检，也不能从采集过程分母中消失。

本修订发生在任何本轮 fit/predict 之前，依据是工具撤销观测与宿主布局的冲突，不依据候选或检测器分数。仍只允许同数据、同分割的原规则与新规则比较；不能把它写成对旧14配置历史成绩的直接提升。
