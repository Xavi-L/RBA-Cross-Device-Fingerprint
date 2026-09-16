# HybridGuard 可用浏览器 Web67 探针

这是 App 显式选择设备上一个合格可用浏览器后访问的纯静态页面，不要求用户预先
设置默认浏览器。它与 App WebView 共用仓库根
`web_probe/canonical_web_probe.js`，因此 Web 层固定为同一套 67 字段、同一版本
`expanded-web-67-v1`，页面本身不复制采集算法。

公网入口：

```text
https://xavi-l.github.io/RBA-Cross-Device-Fingerprint/
```

## 安全与配对边界

- 静态文件不包含 ngrok 地址、长期凭据或设备标识；
- App 先把 177 字段 payload 持久化，再并行申请 provisional browser ticket 和上传
  App payload；
- 后端把一次性的 `pair_id`、短期 browser token 和上传地址放进 `probe_url`；
- 这些参数位于 URL fragment，不会随静态页 HTTP 请求发给 GitHub Pages；
- 页面读取后立即清空 fragment，采集 Web67 并直接 POST 到本次 ngrok 后端；
- Browser 先到时只进入 `browser_provisional_payloads.jsonl` 隔离暂存；后端拿到
  同一 request/session/batch 的 App 回执与 payload SHA-256 后才写正式配对数据。

页面请求包含 `ngrok-skip-browser-warning: 1`，所以 Web67 POST 不依赖人工点击
ngrok 免费域名的警告页。这个 header 只用于浏览器到 API 的跨域请求，不会改变
Web67 字段值。

ES5 bootstrap 会先报告 `page_loaded`，薄适配层也保持 ES5 语法、不依赖
`URLSearchParams`，且在旧系统浏览器没有 `fetch` 时使用带超时的
`XMLHttpRequest`；因此旧 Chromium 系统浏览器仍能读取 fragment、报告执行阶段并
上传同一份序列化 payload。Web67 采集核心本身保持逐字节一致。

## 同步、测试和发布

### 网页完成状态

浏览器上传回执为 `completed` 时，页面显示固定文字 **本机采集完成**。
如果浏览器先上传、后台仍为 `awaiting_app`，页面保留本轮缓存，并使用原有
`browser_ticket` 每 2 秒查询一次
`GET /api/collect/browser-fingerprint/{pair_id}/status`。该接口仅返回本轮配对状态和
浏览器回执编号，不需要 App 传入新的参数，也不需要 MTC 另外查询后台。

只有返回的 `pair_id`、浏览器回执和当前轮次一致且 `pair_status=completed`，
页面才显示完成并清理缓存。最长等待配对 120 秒；连续 3 次查询异常、不可恢复的
接口错误或异常配对结果显示 `采集失败：原因`，凭证过期或配对等待超时显示
`配对超时：原因`。所有终态均停止继续查询，迟到回包不能覆盖超时结果。
刷新等待中的页面会重发原缓存 payload，再继续确认配对，不重新采集一份数据。
MTC 可读取 `#status`（`role=status`）的完整文字判断终态。

本功能发布时先部署更新后的后端，再发布静态网页；现有 APK 的启动链接格式保持兼容。
本地浏览器验证不代表已完成 MTC Android 真机验收。

### 常用命令

先从唯一采集核心生成站点副本，再验证字段清单与文件哈希：

```bash
npm run sync-probe
npm test
npm run build
```

`npm test` 会检查：

1. canonical probe 恰好包含 67 个字段；
2. 站点副本与仓库根文件逐字节一致；
3. HTML 只加载 ES5 bootstrap、共享核心和薄适配层；
4. 刷新页面或超时重试时重发同一缓存 payload，不产生第二份不同指纹；
5. `fetch` 缺失时，手工 fragment 解析和 XHR 兼容路径仍可完成上传。
6. bootstrap、薄适配层和共享核心都能被 ES5 语法解析器接受。
7. 两种上传顺序、自动查询、超时、查询异常与本轮结果校验均遵守统一完成标准。

GitHub Pages 发布内容是 `public/` 目录的扁平副本，来源分支为 `gh-pages`、目录为
`/ (root)`。每次修改共享核心后，必须先运行上述同步与测试，再更新 Pages 分支；
不能只更新 App assets 或只更新静态站。
