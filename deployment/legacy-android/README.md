# Android 5–7 HTTPS 兼容部署

状态：2026-09-18 的修复先覆盖 App 内采集请求。当前没有可配置证书的域名或服务器；
本目录是待接入模板，未上线。继续使用 ngrok + GitHub Pages 的 APK 不能宣称外部
旧版系统浏览器已兼容，也不能计为 paired244 验收通过。

## 已确认问题与本轮边界

- Android 6.0 红米 Note 4、Android 7.0 荣耀 Note8 日志均出现票据申请的
  `CertPathValidatorException: Trust anchor for certification path not found`。
  红米的上传 readiness 同样失败；荣耀的上传任务重试，但日志没有其具体异常。
- 当前 ngrok 和 GitHub Pages 的证书链依赖 ISRG 信任根；ISRG Root X1 的标准
  Android 信任支持起点为 7.1.1。厂商信任库、补丁及浏览器不同，可以解释部分机型
  成功、部分失败，但仍需真机证据。Android 5.1.1 全部失败的原因尚未由日志确认。
- App 1.6.3 在 API 21–25 的两个采集 HTTP client 中补充官方 ISRG Root X1，
  保留系统信任、证书链和域名校验。API 26+ 保持系统默认信任。
- 证书/握手错误不再执行无效自动重试；超时等网络错误保留原有重试。
  日志标记为 `TLS_CERTIFICATE_ERROR`、`TLS_HANDSHAKE_ERROR` 或
  `NETWORK_REQUEST_FAILED`，包括请求阶段和 host。待传 payload 保留在 App 私有存储。
- 本次不修改 177/67 字段、配对协议、浏览器选择策略或采集算法。

## 域名和证书就绪后接入

采用同一域名承载静态页面及 API，例如 `https://collect.example.com/`。
`example.com` 是模板占位符，必须换成真实域名。

1. 为域名配置一张完整证书链，根证书必须被目标 Android 5/6/7 浏览器实际信任。
   优先评估 RSA 证书和 TLS 1.2。证书品牌、付费与否、在桌面电脑上通过校验都不是
   旧手机兼容证明；换域名后仍用同一条不兼容链也不能解决问题。
   不使用跳过校验、全信任 TrustManager 或公共 HTTP 降级。
2. 将本仓库 `browser_probe_site/public/` 的内容复制到
   `/srv/hybridguard/browser-probe/`。页面和脚本已有 ES5/XHR 兼容路径，无需部署
   React/Vite 服务。共享探针有修改时先按该目录 README 同步与验证。
3. 用真实域名、完整证书链及私钥路径替换 `nginx.conf.template` 中的占位值，
   放到 nginx 的 `http {}` 配置中（主配置应加载 `mime.types`）。执行
   `nginx -t` 后再上线。模板只代理采集相关路径，不开放 `/docs` 或数据目录。
4. 后端与 nginx 在同一主机，后端只监听 127.0.0.1:8000，并使用一个 worker：

   ```bash
   cd backend_server
   export HYBRIDGUARD_BROWSER_PROBE_ORIGINS='https://collect.example.com'
   # 沿用正式运行已配置的数据目录等环境变量，不能覆盖或混入旧批次。
   python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1 \
     --proxy-headers --forwarded-allow-ips=127.0.0.1
   ```

   已运行的正式批次需要安排批次切换，不能为了套模板直接重启或覆盖数据。
   如需保留旧入口过渡，可把旧页面 origin 也列入逗号分隔的允许列表。
5. 从 `android_app/HybridGuard/` 构建新 APK；显式覆盖所有地址，避免残留配置：

   ```bash
   ./gradlew :featureapp:assembleDebug \
     -PhybridguardRequirePublicEndpoints=true \
     -PhybridguardCollectEndpoint=https://collect.example.com/api/collect/fingerprint \
     -PhybridguardBrowserTicketEndpoint=https://collect.example.com/api/collect/browser-ticket \
     -PhybridguardBrowserPairPollBaseUrl=https://collect.example.com/api/collect/browser-pairs \
     -PhybridguardBrowserProbeBaseUrl=https://collect.example.com/
   ```

## 定点复测

先测试日志中的两台设备，再选 Android 5.1.1 及一台原本正常的较新设备。
依次核验：App readiness → 已校验 App receipt → `ticket_issued` → 实际选中
浏览器打开页面 → Browser67 上传 → 后端 `pair_status=completed`。
浏览器必须同时能访问页面和 API；App 上传成功或浏览器打开不能替代配对完成。

若仍失败，保留从启动至终态的 logcat，重点查 `HG-BrowserFlow`、`HG-BrowserPair`、
`HG-ExpandedUpload`、`HG-BrowserPoll`，记录 APK 版本、OS/API、WebView 和实际浏览器
版本。证书问题优先记录设备当时看到的证书颁发者、网络代理情况和设备时间；后续
JavaScript、系统 API 或设备特有错误按新日志独立定位，不预先归为同一原因。

参考：
- https://letsencrypt.org/docs/certificate-compatibility/
- https://letsencrypt.org/certificates/
- https://developer.android.com/privacy-and-security/security-ssl
