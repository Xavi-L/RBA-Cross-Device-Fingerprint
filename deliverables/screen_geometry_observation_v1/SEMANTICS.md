# 同期屏幕观测与一个固定上界检查

本轮只有一个新模板 `SCREEN_GEOMETRY:WEB_PHYSICAL_VIEWPORT_EXCEEDS_HOST:v1`，不拟合参数，不修改或训练保存模型。旧 `inner_height > 710` 与 `REL:SCREEN_VISUAL_EXCEEDS_LAYOUT:v1` 分别保留定义和身份。旧条件使用本次原 `screen_layer` 的同一次同步读取；新条件只使用新增观察窗口内的 Web 快照与宿主前后快照。两个快照明确标为 `same_snapshot_as_legacy_screen_layer=false`，不拼操作数。

## 原值与时序

FeatureApp 正常路径主动执行主线程宿主前读取 → 异步 evaluateJavascript 中一次 Web 同步读取 → 主线程宿主后读取。独立模块为 `collection_observations.webview_geometry`，版本 `webview-geometry-v1`；Web 子模块 `webview-web-geometry-v1`。固定最多两次尝试，单次 1800 ms、总计 5000 ms；所有尝试保留，选中 observation ID 唯一。当前 session、WebView 实例、document generation、document ID 和 observation/attempt ID 必须一致。Host 布局、方向、density、窗口与布局参数、缩放事件序号在前后未变化才可评价；不以 Web/Host 是否一致判断稳定。

Android `elapsedRealtime`、Unix epoch、Web `performance` 分属不同时间域；只在各自域内核验先后关系，不直接相减。前后未见变化不是绝对原子快照。事件可能在窗口外发生，异步渲染仍是限制。

| 观测 | 实际来源与单位 | 本轮用途 |
|---|---|---|
| width/height、padding | 当前 Android WebView View；物理布局像素整数 | 内容区域 = View 尺寸减该轴 padding 两边，仅减一次 |
| 窗口位置、可见矩形、root/parent、insets | View 与 WindowInsets；物理像素 | 保留布局/裁剪上下文，不再从内容尺寸扣系统栏 |
| density/densityDpi、方向 | 当前 resources configuration | 上下文及宿主稳定性，不把 density 当 Web DPR |
| onScaleChanged | WebViewClient 实际回调、代次、事件序号、单调时刻和 age | 原始诊断；缺失不填 1，不从 Web 宽度反推 |
| getScale | UI 线程实际调用 | 明确为 deprecated/race-prone 诊断，不作必要真值或回调替代 |
| inner、document client、screen/avail、DPR、visualViewport | 当前文档同一段同步 DOM API 读取 | 每字段 value/status/reason/unit；读取失败保留 null |
| viewport meta、document URL/ready/compat、方向与 visual offsets | 同一个 Web 快照 | 保存页面口径，不当作攻击/正常标签 |

## 固定关系

对每个轴定义 `P = visualViewport尺寸 × devicePixelRatio × visualViewport.scale`，单位为声明的物理像素；`H = Host View轴尺寸 − 两边padding`。检查 `P > H + ε`，其中：

`ε = 2 + 4 × 2^-23 × max(|P|, |H|, 1)` 物理像素。

固定 2 px 是两端布局边缘各最多 1 px 的量化预算，后项保守容纳四步 float32 相对舍入传播；它是本研究显式数值误差预算，不是所有实现的官方误差保证。全环境同式，在正式批次前确定，不由攻击或正常结果反推。保留每轴原值、换算值、ε 和差值，后续可以检验此误差假设。

CSSOM 的 DPR 是当前 page zoom 下 CSS 像素与设备像素之比，定义时 visual scale 为 1；VisualViewport 的尺寸为 CSS 像素且随 page zoom/visual scale 缩小。因此乘上另读的 visual scale 恢复第二种缩放。这里**没有**假定 DPR 等于 Android density、visual scale=1 代表全部缩放为1，也没有通过 `Host宽/Web宽` 估计比例。[CSSOM DPR](https://drafts.csswg.org/cssom-view/#dom-window-devicepixelratio)、[VisualViewport](https://drafts.csswg.org/cssom-view/#the-visualviewport-interface)。

适用域是当前可见且 attached、View 的 scaleX/scaleY=1、rotation=0、四边 padding 均有观测且为0、同文档且 Host 前后稳定的 App WebView。当前 App 自身 WebView 没有 padding，父容器 padding 已反映在实际 View 尺寸中。`AwContents.onSizeChanged` 转交 View w/h；公共 WebView 口径尚不足以保证非零自身 padding 一定缩减网页渲染视口，所以本轮固定排除该未建立口径，而不是任意扣边距后报冲突。尺寸/DPR/visual scale 要有有效有限正数观测。窗口大小和真实方向变化本身不报警。Host 内容语义不明、缺值、0/-1不可用值、错误类型、非有限数分别保留 U；绑定混错或执行异常为 FAILED。域内真实有效但偏离的值始终参与计算。

只取上界：IME、裁剪、经典滚动条等可能缩小视觉区域，因此 `P < H` 不当作矛盾。T 为任一轴超过上界；两轴有效且均未超过才 F。`T OR U = T`，`F OR U = U`。此单向条件不能识别所有缩小型伪造，也不证明 F 就没有干预。

Android View 的 width/height 是当前 View 布局尺寸，padding 属于其内部，区别于整个显示器、窗口与可见裁剪区域。[View 尺寸](https://developer.android.com/reference/android/view/View#getWidth())、[View padding](https://developer.android.com/reference/android/view/View#getPaddingLeft())。当前 App XML 父布局没有额外旋转/缩放；其他 App/复杂祖先变换尚未验证。

## 为什么不登记第二条“scale 相等”

Android 官方说明 getScale 存在渲染/UI 线程竞态，推荐 onScaleChanged；回调只说明 applied scale 改变，不是同期独立硬件真值。[getScale](https://developer.android.com/reference/android/webkit/WebView#getScale())、[onScaleChanged](https://developer.android.com/reference/android/webkit/WebViewClient#onScaleChanged(android.webkit.WebView,%20float,%20float))。

核对实验版本的 Chromium `AwContents.setPageScaleFactorAndLimits`，回调值为 `pageScaleFactor × getDeviceScaleFactor()`，且仅 pageScaleFactor 改变才发事件；初始状态可能没有本代次回调。它不等于纯 `visualViewport.scale`。本轮保存回调及新鲜度，不默认值、不另登记容易混淆的等式。[WebView91源码](https://chromium.googlesource.com/chromium/src/+/refs/tags/91.0.4472.114/android_webview/java/src/org/chromium/android_webview/AwContents.java)、[WebView134源码](https://chromium.googlesource.com/chromium/src/+/refs/tags/134.0.6998.135/android_webview/java/src/org/chromium/android_webview/AwContents.java)。

L3 使用真正 `WebView.zoomBy(1.25)`，该 API 是缩放操作且可能被浏览器缩放限制夹紧；API 返回 void 只证明调用，实际效果仍由前后原值确认。不把 CSS transform 或 DPR 改写当正常缩放。[zoomBy](https://developer.android.com/reference/android/webkit/WebView#zoomBy(float))。

## 结论边界

Host 内容矩形独立读取，但 Web 换算操作数来自同一渲染器。CDP 会影响渲染/暴露状态，可能让多项值一致改变；若换算与 Host 仍相容，必须保留为有效干预未检出，不能改标或转 U。该候选是有限 App 布局域内的研究上界，不是任意浏览器/正常设备的官方不变量。旧 MTC 和旧378条缺同期几何观察，不补填、不拼接，不重训或更新旧分数。
