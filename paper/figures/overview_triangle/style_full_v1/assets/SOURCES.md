# 同一家族的本地矢量资源

固定采用 [Tabler Icons v3.34.1 官方版本](https://github.com/tabler/tabler-icons/tree/v3.34.1)，完整 [MIT 许可](tabler/LICENSE) 保留 Copyright (c) 2020-2024 Paweł Kuna。下载和定制资源均在本目录；最终 SVG 内联矢量，不依赖网络，不嵌入图像或整张样块。

## 直接继承的三个对象

`native_adapted.svg`、`host_adapted.svg`、`app-web_adapted.svg` 从 `style_pilot_v1/assets/` 原样复制，轮廓、屏幕、设置滑杆、外壳内页、折角、JS 及线宽不再重画。完整图中的等比缩放也分别保持 6、6.1、5.5。

原始图标继续保存在 `tabler/`：

- [device-mobile](https://raw.githubusercontent.com/tabler/tabler-icons/v3.34.1/icons/outline/device-mobile.svg)：手机外轮廓和听筒；样块增加屏幕、局部填充并调整底部短横。
- [adjustments-horizontal](https://raw.githubusercontent.com/tabler/tabler-icons/v3.34.1/icons/outline/adjustments-horizontal.svg)：手机屏幕内的辅助设置符号。
- [app-window](https://raw.githubusercontent.com/tabler/tabler-icons/v3.34.1/icons/outline/app-window.svg)：Host 外壳；样块增加内容区并组合页面。
- [file-type-js](https://raw.githubusercontent.com/tabler/tabler-icons/v3.34.1/icons/outline/file-type-js.svg)：样块沿用折角/页面语言、闭合页面下缘，JS 移入页面并保留为 SVG 文本；Host 和 App Web 复用同一内页图形。

## 本轮补充的四个对象

| 官方固定版本图标 | 用途与定制 |
|---|---|
| [browser](https://raw.githubusercontent.com/tabler/tabler-icons/v3.34.1/icons/outline/browser.svg) | Browser 主体保留窗口、页签及栏线，增加白色内容区和无值短线；使用浅青衬托及深青轮廓，与 App Web 文档区分。 |
| [list-details](https://raw.githubusercontent.com/tabler/tabler-icons/v3.34.1/icons/outline/list-details.svg) | Candidate checks：空条件条目及无值短线；没有认证勾或指标达成标记。 |
| [files](https://raw.githubusercontent.com/tabler/tabler-icons/v3.34.1/icons/outline/files.svg) | Development data：叠放记录页，添加少量无值记录线和局部填充。 |
| [file-text](https://raw.githubusercontent.com/tabler/tabler-icons/v3.34.1/icons/outline/file-text.svg) | Selected rules：独立的规则列表产物，保留折角与无值列表，不写虚构规则或阈值。 |

这四份官方源 SVG 保存于 `tabler/`；定制版由 `build_candidate.py` 导出为同名 `_adapted.svg`。只调整填充、笔画重量、抽象内容短线和同族色彩。没有采用其他图标家族或提取论文截图里的图元。再分发时请同时保留完整 MIT 许可。
