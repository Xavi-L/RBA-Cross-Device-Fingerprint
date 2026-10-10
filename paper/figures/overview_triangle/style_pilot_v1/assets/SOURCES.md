# 图标来源与修改

本轮统一使用 [Tabler Icons 官方仓库](https://github.com/tabler/tabler-icons/tree/v3.34.1)，固定版本 **v3.34.1**。原始文件存于 `tabler/`，完整 MIT 许可及 Copyright (c) 2020-2024 Paweł Kuna 保留于 [tabler/LICENSE](tabler/LICENSE)。没有使用论文里的图标图元，也不推测其来源。

| 原始图标 | 官方固定版本文件 | 实际采用与修改 |
|---|---|---|
| device-mobile | [SVG](https://raw.githubusercontent.com/tabler/tabler-icons/v3.34.1/icons/outline/device-mobile.svg) | 沿用手机外轮廓和听筒路径；新增屏幕内框与局部填充，把底部点改为短横，调整轮廓线宽。 |
| adjustments-horizontal | [SVG](https://raw.githubusercontent.com/tabler/tabler-icons/v3.34.1/icons/outline/adjustments-horizontal.svg) | 完整三行滑杆路径作为手机屏幕内的系统设置辅助符号；统一等比缩放、调整颜色和线宽。 |
| app-window | [SVG](https://raw.githubusercontent.com/tabler/tabler-icons/v3.34.1/icons/outline/app-window.svg) | 沿用外壳轮廓；两点替换为简短应用栏，增加白色内容区。与下面的页面组成原创包容构图，无浏览器导航、尺寸标尺或测量箭头。 |
| file-type-js | [SVG](https://raw.githubusercontent.com/tabler/tabler-icons/v3.34.1/icons/outline/file-type-js.svg) | 沿用折角路径和页面几何语言，补闭合下缘；不采用原文件外侧的路径字母，改成页面内可编辑 `JS` 文本；增加两条无字段名称/数值的属性记录短线。 |

三个定制资源由 `build_sample.py` 生成：`native_adapted.svg`、`host_adapted.svg`、`app-web_adapted.svg`。Host 与 App Web 复用同一个 `page_icon()`，Host 内页采用同族蓝色并弱化线宽，突出外壳；App Web 以较大的绿色页面为主体。定制形状与原始资源分开保存。最终样块内联矢量，不依赖在线资源；与该目录一起再分发时须保留 Tabler 的完整许可声明。

下载时间：2026-10-10。没有宣称此固定版本是最新版本。
