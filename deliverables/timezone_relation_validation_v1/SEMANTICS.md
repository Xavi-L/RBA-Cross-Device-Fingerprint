# 本轮时区关系语义

唯一新增模板为 `MTCREL:NATIVE_ZONE_AT_ACQUISITION_VS_WEB_OFFSET_DIFFERS`。它扩展既有 `V2REL:FIXED_NATIVE_VS_WEB_OFFSET_DIFFERS` 的适用域，复用其固定偏移解析和比较；新增部分是根据同次设备采集日期处理 IANA 地区时区。旧模板仅支持语法上固定的 UTC/GMT 偏移，所以两者并不等价。本轮没有重复注册旧固定模板，也没有给新模板选择加分。

| 输入 | 来源与含义 | 使用方式 |
|---|---|---|
| `app.android_native_data.locale_timezone_layer.native_timezone_id` | Native `TimeZone.getDefault().id` | 决定适用时区；不按型号或来源推断 |
| `...native_timezone_offset_min` | Native `rawOffset / 60000`，向东为正的标准时分钟偏移 | 固定时区分支复用旧一致性要求；动态地区分支仅保留诊断，不当作含夏令时的当前偏移 |
| `app.web_data.execution_layer.timezone_offset` | Web `new Date().getTimezoneOffset()`，向西为正的当前分钟偏移 | 与日期换算后预期 Web 偏移比较 |
| `...timezone_id` | Web `Intl.DateTimeFormat().resolvedOptions().timeZone` | 仅供解释，不以文本不同触发 |
| `collection_manifest.collection_started_at_ms` / `collection_diagnostics.collection_finished_at_ms` | 设备墙钟 Unix 毫秒 | 仅作为日期换算的封闭采集区间 |
| payload `timestamp` | 设备构造上传内容时的 Unix 秒 | 可用时检查与设备区间相容，绝不作为缺失起止日期的替代 |

Android 官方说明 [getRawOffset](https://developer.android.com/reference/java/util/TimeZone#getRawOffset()) 不包含夏令时；[ECMAScript getTimezoneOffset](https://tc39.es/ecma262/multipage/numbers-and-dates.html#sec-date.prototype.gettimezoneoffset) 使用 UTC 与当地时间之差，方向与 Native 相反。`0`、`-1` 都可能是有效偏移，本入口不应用旧数值候选的通用负一哨兵策略。有效值须为有限整数分钟，绝对值小于1440；字符串、布尔、非有限数、缺失和质量不足保留 U。

采集代码依据是 `android_app/HybridGuard/featureapp/src/main/java/com/example/hybridguard/featureapp/` 下的 `ExpandedFingerprintCollector.kt`（Native时区）、`CollectionManifestBuilder.kt`（开始毫秒）、`MainActivity.kt`（先建manifest，再collectNativeLayered，最后接收Web探针并保存结束毫秒），以及 `web_probe/canonical_web_probe.js#getExecutionFeatures`。历史 MTC v9/v11 对应源码提交 `134201114a8a15a682bb41ee94c796d14e550c9e`，v14对应既有绑定的 `bdd0b11a915b3bf5028bb3600c21e8b7b10a1f54`。这证明区间包围两次读取，**不证明精确同时读取**。服务端收到时间没有被当作测量时刻。

日期换算使用 [Python标准库 ZoneInfo](https://docs.python.org/3/library/zoneinfo.html) 和本机 `/usr/share/zoneinfo/+VERSION` 标识的 **IANA 2026c** 数据。读取时核对版本，其他版本作为依赖失败处理；复现可用 `HYBRIDGUARD_TZDB_DIR` 指向带 `+VERSION` 的同版本数据库。没有隐式回退到操作系统新版本或执行当天日期。为避免只看区间两端漏掉两次季节变化，用 CPython 自带的 `_common.load_data` 和 `_zoneinfo._parse_tz_str` 读取TZif转换及未来规则尾部，由 ZoneInfo 判断转换前后实际偏移；没有手写任何地区的夏令时规则。该内部接口依赖已在本机Python上测试，换Python实现时应先运行本轮边界测试。

判定固定如下：

- **F**：Native ID可解释，采集区间内有效偏移唯一，实际Web分钟偏移等于该值取反；不同ID但同一当前偏移仍为F。
- **T**：相同适用域内实际Web偏移不同。正常流程下出现的可比较偏离仍为T，不因标签或低于误报预算改成U。
- **U**：真实字段缺失或质量不足；未知ID；动态地区无可靠日期；时间无效或秒/毫秒不相容；区间经过实际偏移变化；历史亚分钟偏移。无日期时，仅保留既有语法固定时区分支，要求Native rawOffset与该固定ID一致。
- **FAILED**：来源会话/原始记录绑定失败，或固定时区数据库不可用/版本不符。与证据不足分开。

来源适配在旧规则完整App字段外新增 `acquisition_time` 侧信息；旧50候选、内存/屏幕关系输入和编码器不变。MTC读取冻结清单给出的原始行，核对App session、原始payload引用和时区原值；受控记录沿原prepared引用回到同次App。新本地批次采用独立 `timezoneonly-` 身份；不放宽旧入口的ID、版本或路径限制。日期、phase、标签、目标地区、型号和未来恢复信息不加入预测特征。

候选冻结前只查看训练侧：discovery630条均有起止时间（最长13.156秒），新关系为630F；fold01受控训练252条为246F、6T，没有U/FAILED。144/117评价成员不参与这些决定；本关系无拟合参数或容差。

该关系检查的是**当前偏移相容性**。只改ID但仍采用相同当前偏移、Native和Web一起改变、地区不同但当前偏移相同，均可不触发。正常系统设置变化若两侧已稳定继承同一设置应为F；Native先读、Web后读之间恰有系统设置改变、进程缓存未更新、墙钟跳变或设备与2026c规则库有差异仍可能造成偏离。旧材料未保存设备tzdb版本及每字段读取时刻，无法完全排除这些原因；因此T是研究条件偏离，不是普遍攻击证明。已知可比较反例保留为T，不按地区白名单或额外60分钟容差隐藏。
