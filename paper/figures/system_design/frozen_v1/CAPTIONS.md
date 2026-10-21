# System design 图注

## English

System design of HybridGuard. Fixed integrity checks evaluate current Android environment reports. Native, WebView-host and JavaScript observations from one App execution are associated; a validly linked external Browser supports an optional timezone-offset check (C1). The memory example illustrates an upper-bound violation on valid inputs. Only selected checks contribute to the result: execution or association failures take precedence and suppress a detection decision; otherwise any trigger yields an alert, a nonempty set of all definitely false conditions yields no alert, and unresolved cases yield insufficient evidence. No alert does not establish authenticity. Offline selection constrains normal alarms, definite-output coverage and complexity.

## 中文

HybridGuard 的系统设计。固定的完整性检查评估当前 Android 环境报告。来自同一次 App 执行的 Native、WebView Host 和 JavaScript 观测经过关联；有效关联的外部 Browser 支持可选的时区偏移检查（C1）。内存示例展示有效输入上的上界违反。只有选中的检查参与汇总：执行或关联失败优先，并抑制检测判定；否则，任一检查触发即报警，非空检查集合全部明确为假时输出未报警，其余未决情形输出证据不足。未报警不构成真实性证明。离线选择约束正常报警、明确输出覆盖率和复杂度。

## 使用说明

英文沿用批准版本随附说明中的图注；中文为对应译文。最终论文图号和所在章节由正文编排决定。内存数值是合成机制示例，不是新增实验结果。
