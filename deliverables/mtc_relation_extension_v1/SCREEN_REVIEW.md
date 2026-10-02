# 屏幕关系核实

本轮只新增一个同 Web 表面的检查 `REL:SCREEN_VISUAL_EXCEEDS_LAYOUT:v1`。不把尺寸大、DPR 高、平板或横屏作为偏离，不建立未经观测支持的 Native/Web 等式。

| 项目 | 固定定义 |
|---|---|
| 字段 | `app.web_data.screen_layer.{inner_width,inner_height,visual_viewport_width,visual_viewport_height,visual_viewport_scale}` |
| 来源 | 同一次 App WebView 主页面 `getScreenFeatures()`；全部为 `app_web67`，不含 Native/Host 独立证据 |
| 单位 | 前四项为 CSS 像素；scale 为无量纲视觉缩放比例 |
| 适用域 | 同 App 原始记录、同同步 Web 探针、质量为 observed_value、所需值为有限正数，视觉 scale≥1 |
| T（偏离） | 任一已知轴满足 `visual > inner + 1 CSS px` |
| F（满足） | 两轴均有效且均未越界 |
| U | 来源绑定不足；缺失、默认 0、不可用 -1、错误类型、质量不足；或 scale<1 的明确不适用域。分别保留原因 |
| 合成逻辑 | 一轴已知 T、另一轴 U 时仍 T；一轴 F、另一轴 U 时 U |
| 参数 | 固定 1 CSS px，仅容纳整数 inner 与浮点 visual 的舍入；不从数据拟合，无候选权重加成 |

公共实验适配入口首先核验当前 App 来源；跨记录、跨 session 或来源绑定失败记为 **FAILED**，不进入上述字段关系计算。上表的绑定不足 U 是底层屏幕函数独立调用的保守结果，不用于掩盖实验入口的执行失败。

CSSOM 将这些尺寸定义在 CSS 像素中；inner 对应 layout viewport，visual viewport 可因捏合缩放、输入法而缩小。scale<1 下视觉区域可能超出该边界，因此此版本不判。键盘、滚动条、缩放和方向变化不要求两者相等；只检查保守上界。它是有明确适用域的研究检查，不是任意浏览器实现的攻击真值。[CSSOM View](https://drafts.csswg.org/cssom-view/#dom-window-innerwidth)、[VisualViewport](https://drafts.csswg.org/cssom-view/#the-visualviewport-interface)。

采集源码 `web_probe/canonical_web_probe.js:368–386` 逐项调用 Window 与 VisualViewport API，未把 inner 值复制为 visual 值。历史采集依据提交 `134201114a8a15a682bb41ee94c796d14e550c9e` 中同函数保持该读取方法。旧探针无 visualViewport 时直接写 -1，不能将它当有效尺寸。源码为同步顺序读取，但没有逐字段时间戳；极端布局切换仍是需保留的实现限制。

## 不采用的关系

- **innerHeight 等于 Native/屏幕高度**：Native `screen_resolution_physical` 的名称误导；实际来自 Activity `resources.displayMetrics.widthPixels/heightPixels`，不是面板分辨率。API 描述的是 available display size；页面 WebView 只占 Activity 中一块区域。见 `ExpandedFingerprintCollector.kt:40,113–122`、[DisplayMetrics](https://developer.android.com/reference/android/util/DisplayMetrics#widthPixels)。
- **innerWidth×DPR 等于 Native 宽度，或旧 P3 短边等式**：`MainActivity.kt:138–154` 先读取 Native 再配置 WebView；Host26 没有 WebView 实测矩形，旧记录没有同刻窗口/方向/页面缩放的充分参照。已有 `P3-SCREEN-APP`（`mtc_p3_candidates.py:57–59,210–217`）已明确是短边 Native/DPR 与 Web screen 的经验关系，无法用改名消除分屏、窗口、缩放与时机限制，本轮不重复登记。
- **DPR 等于 densityDpi/160**：Web page zoom 与 visual scale 不是同一量，visual scale=1 不能证明 page zoom=1；不能用这一门槛冒充充分条件。
- **available screen 等于 full screen / viewport**：系统栏、窗口与浏览器暴露策略不同，不把大小不等本身定义成攻击。`expanded_probe.html:5` 有 width=device-width/initial-scale=1，但 `MainActivity.kt:176–187` 没有记录全部缩放和窗口实测状态；[WebSettings viewport](https://developer.android.com/reference/android/webkit/WebSettings#setUseWideViewPort(boolean)) 还区分 useWideViewPort 对 meta 的处理。

## 训练侧原值核对

这里只在正式模型拟合前读取第 01 折允许的 252 条受控训练记录和固定 630 条 MTC discovery；没有读取新模型的 144/117 评价结果。

- 初始字段/适用域诊断：受控 clean_pre 84、attack 84、clean_post 84 条全部满足；MTC discovery 593 条满足、37 条未知、0 条偏离。最终含完整来源/质量校验的统计由正式训练产物给出。
- 保留真实正常反例 `webgl1fresh-c6370eab-9f06-4543-b532-1f486f84db34`：Native `1080×2400`，inner `411×710`，visual `411.4285583496094×710.4761962890625`，scale=1。这说明 WebView 视口高度不能替代 Native 显示高度，也说明整数/浮点舍入容差的用途。
- 同训练配置攻击 `webgl1fresh-eaed3e03-9353-4ad1-baaa-942250fa3ee2`：inner `393×851`，visual `393.1428527832031×851.047607421875`，scale=1，仍满足关系。原始引用为 `deliverables/webgl1_fresh_comparison_v1/runs/api36_swiftshader/backend/raw_expanded_payloads.jsonl` 对应 session_id。CDP 同时改变多个 Web 字段时，真实关系也可能完全没有区分信息；不因此编造跨层等式。
- 正常未知实例 `mtc-pair-hgpair-v1-bc5c0c80ffbf0ea3e040ba72`：inner `360×452`，visual 三字段均 -1。它仍是原正常成员，不因无法评价而删除。

若要检验真正的 WebView/Native 几何关系，最小补采是同一稳定布局时刻的 WebView 内容矩形（设备像素）、窗口 insets、显示/方向、page zoom 与 visual scale，并保留采样时刻；本轮不启动补采。
