# Suggested captions

## Figure 1. Observation surfaces and comparison boundaries

**English.** Complementary observation surfaces in HybridGuard. Native APIs, App Web JavaScript, and WebView Host observations are associated with one App execution. Solid blue denotes integrated Native-Web memory and timezone relations; dashed ochre denotes Host-Web geometry evaluated as a standalone study, outside Integrated App and its candidate pool. The dotted Native-Host edge denotes shared context only, not an independent detection rule. A validly linked external Browser supports the optional C1 timezone comparison with App Web. Counts describe catalogued schema fields, not the inputs used by every selected detector. Association does not imply atomic sampling, and no surface is trusted ground truth.

**中文。** HybridGuard 的互补观测面。Native APIs、App Web JavaScript 与 WebView Host 的观测关联于同一次 App 执行。蓝色实线表示已集成的 Native-Web 内存和时区关系；赭色虚线表示独立评估的 Host-Web 几何专项，该专项不属于 Integrated App 及其候选池。Native-Host 灰色点线仅表示共享上下文，不代表独立检测规则。有效关联的外部 Browser 支持与 App Web 进行可选的 C1 时区比较。字段数表示观测 schema 的规模，并非每个检测器实际使用的输入数。关联不意味着原子同步采样，任何观测面都不是可信真值。

## Figure 2. Offline construction and state-aware evaluation

**English.** Offline rule construction and current-record evaluation in HybridGuard. Candidate checks and development data supply constrained selection and retention; frozen rules and parameters determine the selected checks. Current App observations, optionally associated with a linked Browser, retain their values, collection states, and provenance. The ordered decision list returns the first matching case: EMPTY_MODEL for an empty selection; FAILED for a relevant execution or binding failure; otherwise ALERT for any T, NO ALERT for all F, or UNKNOWN for the remaining cases. T denotes a triggered predicate, F a definite non-trigger, and U unavailable or inapplicable evidence. App-only and App-plus-Browser are two evaluated configurations. Host geometry is not integrated into these checks. The returned evidence does not certify authenticity.

**中文。** HybridGuard 的离线规则构建与当前记录判定。候选检查和开发数据用于约束选择及保留，冻结规则与参数决定实际参与判定的检查。当前 App 观测及可选的关联 Browser 保留数值、采集状态和来源上下文。有序判定列表采用首个匹配条件：空选择输出 EMPTY_MODEL；相关执行或关联失败输出 FAILED；否则，存在任一 T 时输出 ALERT，全部为 F 时输出 NO ALERT，其余输出 UNKNOWN。T 表示谓词触发，F 表示明确未触发，U 表示证据缺失或不适用。App-only 和 App-plus-Browser 是两种评估配置，Host 几何未集成于这些检查，未报警不构成真实性证明。

## Figure 3. How contextual references contribute

**English.** Illustrative mechanisms on valid, applicable observations. (a) With Native memory of 4 GiB and a Web report of 8 GiB, the report does not exceed the fixed 8 GiB comparator but violates the Native-derived 4 GiB upper envelope. These values are a schematic example, not additional experimental records. (b) After converting offsets to the same sign convention, a legitimate system change can move both Native and Web offsets from a to b; a Web-only edit leaves the Native reference unchanged and creates a mismatch. Distinct a and b illustrate the contrast rather than measured traces. (c) A reported viewport dimension P, converted to the comparison unit, violates the Host bound when P exceeds H plus tolerance epsilon. The aligned left edges emphasize dimension rather than position. Geometry remains a standalone study; quantitative results are reported separately.

**中文。** 有效且适用观测上的机制示意。(a) 当 Native 内存为 4 GiB、Web 报告为 8 GiB 时，Web 报告未超过固定的 8 GiB 比较器，却超过由 Native 推导的 4 GiB 上界；这些数值是说明性示例，并非新增实验记录。(b) 统一时区偏移符号后，正常系统变化可使 Native 与 Web 从 a 共同变化到 b，而仅修改 Web 时 Native 参照保持不变，从而产生不一致。不同的 a、b 用于概念说明，不是测量轨迹。(c) Web 视口经单位转换后的尺寸 P 超过 Host 尺寸 H 与容差之和时触发检查；两个框左侧对齐，以强调尺寸比较而非位置偏移。几何仍是独立专项，定量结果另行报告。
