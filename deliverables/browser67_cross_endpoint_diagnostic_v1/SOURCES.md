# 固定语义依据（2026-10-06 核对）

- [WHATWG NavigatorLanguage](https://html.spec.whatwg.org/multipage/system-state.html#navigatorlanguage)：language/languages 表示用户代理暴露的语言偏好，列表按偏好排序，首项对应 language；标准允许隐私相关的 plausible language。跨容器完全相同并不是硬件不变量。
- [RFC 5646 §2.1、§2.1.1](https://www.rfc-editor.org/rfc/rfc5646)：语言标签大小写不携带意义。这里沿用仓库 limited_full_tag 的保守语法子集，仅做 ASCII 小写；不声称完整 BCP47 注册表验证。不处理扩展、私有标签、旧格式或别名，超出支持范围记 U。C3 只在该解析成功后提取主语言。
- [ECMAScript getTimezoneOffset](https://tc39.es/ecma262/multipage/numbers-and-dates.html#sec-date.prototype.gettimezoneoffset)：偏移为 UTC 时间与本地时间之差，以分钟计。C1 两侧调用同一 Web API，不对任一端额外反号。
- 实际探针 `web_probe/canonical_web_probe.js` 的 getNavigatorFeatures/getExecutionFeatures 直接读取 navigator.language、navigator.languages、new Date().getTimezoneOffset()。源文件摘要收录在运行清单。

候选在 MTC 144/117 值读取前写入 CANDIDATES_FROZEN.json。C2/C3 为新版本；D1 原样调用 P3-X-LANGUAGES@2.0.1，C1 在原 P3 数值相等前增加严格类型门。MATCH → F，COUNTEREXAMPLE → T，UNKNOWN/NOT_APPLICABLE → U。T 仅表示偏离，不是操纵意图证明。
