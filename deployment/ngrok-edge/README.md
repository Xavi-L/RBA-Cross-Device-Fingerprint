> **2026-09-22：本机采集链已退役。** 用户明确停止使用本机后端与 ngrok。以下启动／运维说明仅作历史记录，不再执行；后续分析使用 `backend_server/collection_backups/mtc_final_20260922/`。停机与冻结证据见 `deliverables/mtc_p0_20260922/`。

# 最小部署：ECS HTTPS → ngrok → 电脑后端

ECS 只运行 Nginx、证书续期和 Browser67 的五个静态文件。后端、JSON/JSONL 数据和 ngrok 仍在电脑上，只运行一个 uvicorn worker。

## 已部署状态（2026-09-21）

- 正式入口：`https://collect.crossdevicefingerprint.site`。
- DNSPod：`collect` A → `47.76.136.243`，TTL 600，已验证解析及实际访问。
- ECS：香港 Ubuntu 22.04.5，Nginx 1.18.0、Certbot 1.21.0；公网只新增 TCP 80/443，未开放 8000/8090/4040。原 SSH 等规则保持原样。
- ZeroSSL RSA 2048 证书已经签发并启用，2026-09-21 至 2026-12-20 23:59:59 UTC 有效。
- 实际服务链：域名证书 → ZeroSSL RSA DV SSL CA 2 → Sectigo Public Server Authentication Root R46（USERTrust RSA 交叉签名）。
- 分别只加载 AOSP Android 5.1.1、6.0、7.0 的 USERTrust RSA 根证书，连接正式入口并强制 TLS 1.2 / ECDHE-RSA-AES128-GCM-SHA256，三个验证均通过；没有关闭域名或证书验证。这是信任链与协议验证，不能替代 OEM 真机浏览器复测。
- HTTP 除 ACME 验证目录外返回 308 到固定 HTTPS 域名。HTTPS 的静态页、health、readiness 正常；`/docs`、`/openapi.json` 返回 404。
- 证书 `certbot.timer` active/enabled，续期配置保留 ZeroSSL、RSA 2048 和 webroot；部署 hook 已执行通过。`certbot renew --non-interactive` 能识别证书并显示未到期而跳过；未发生实际续签，不把该检查表述成续签成功。
- ngrok 已切换到新 Host 改写 policy，正式后端 origins 包含新域名和原 GitHub Pages。
- 隔离目录 `edge_smoke_20260921` 的合成公网配对返回 `pair_status=completed`，票据的 probe/upload/stage URL 全部使用新域名。正式目录没有混入合成测试记录。
- 正式目录 `backend_server/collection_runs/mtc_20260917` 保留 523 条 App 回执和 347 条配对 provenance。重启后新批次为 `hgbatch-v1-20260921T040430015520Z-14ed4645c6`。
- 完整备份：`backend_server/collection_backups/before_https_20260921T040429Z/`，包含停止旧进程后的正式目录和原 ngrok policy；本地已有画像密钥也单独备份，勿上传这些备份。
- APK：`1.6.4-expanded-v2.2-mtc-https` / versionCode 11，四个入口均指向新域名。构建成功、33 项 Android 单元测试通过；持久 Python 环境下采集合同、配对和批次生命周期 20 项测试通过。
- Android 5.1.1 / 6 / 7 的新版真机 `paired244`：**待复测**。

## ECS 文件与维护

```text
/srv/hybridguard/browser-probe/          五个公开静态文件
/var/www/letsencrypt/                   ACME HTTP 验证目录
/etc/nginx/snippets/hybridguard-ngrok.conf
/etc/nginx/sites-available/hybridguard-bootstrap   当前为 ACME + HTTPS 跳转
/etc/nginx/sites-available/hybridguard-https
/etc/letsencrypt/live/collect.crossdevicefingerprint.site/
/etc/letsencrypt/renewal/collect.crossdevicefingerprint.site.conf
/etc/letsencrypt/renewal-hooks/deploy/hybridguard-nginx.sh
```

两个站点均已启用。原默认站点链接保存在 `/etc/nginx/default-site.before-hybridguard`；临时 8090 站点已禁用，链接保存为 `/etc/nginx/hybridguard-staging.disabled`。最终监听检查仅有 80、443。

用户确认协议并提供邮箱后，ZeroSSL 账户已注册；EAB 配置仅保留在 root 可读的 `/root/.config/hybridguard/zerossl-certbot.ini`（600），不需要再次提供邮箱或将凭据放入仓库。

证书维护检查：

```sh
nginx -t
systemctl status certbot.timer --no-pager
certbot certificates
certbot renew --non-interactive
```

续期 hook 执行 `nginx -t` 后重载 Nginx。保持域名 A 记录、80 端口及 ACME webroot 可用。未来 CA 续签链可能改变，续签后仍应核对旧 Android 信任路径，不只看现代浏览器可访问。

## 仓库中的部署文件

- `bootstrap.conf`：首次签发前的 ACME + 503 配置；当前线上已经升级为 HTTPS 跳转，不要直接覆盖回此文件。
- `crossdevicefingerprint.site/hybridguard-http.conf`：当前线上 HTTP 配置。
- `https.conf.template` 与域名目录内的 `hybridguard-https.conf`：HTTPS 静态文件及 API 白名单。
- `proxy.conf`：ECS → ngrok 转发，启用上游 TLS/SNI 验证，不重试 POST。
- `crossdevicefingerprint.site/ngrok-edge-policy.json`：保留采集接口白名单，在请求到达电脑后端前将 Host 改为新域名。
- `crossdevicefingerprint.site/endpoint.properties`：APK 的四个入口。
- `render.py`：为其他已确认域名生成配置，要求输出到新的空目录，不修改运行中的服务。

Nginx 连接 ngrok 时 Host 和 SNI 必须保持 `hemispheric-overmoist-candance.ngrok-free.dev`，用于隧道路由；由 ngrok policy 在转发前改写 Host。Nginx 清除来路 forwarded 头，由 ngrok 提供 HTTPS 协议信息，Uvicorn 只信任 loopback 代理。否则 FastAPI 可能生成 ngrok 域名的 upload/stage URL，外部浏览器仍会遇到原证书问题。

静态目录仅含 `browser-probe.html`、`browser-probe-bootstrap.js`、`browser-probe-adapter.js`、`probe/canonical_web_probe.js`、`probe/manifest.json`。revision 为 `expanded-web-67-v1`，67 项，core 与后端 manifest 一致。ECS 不保存业务采集数据。

## 电脑上的运行与重启

持久环境：`backend_server/.venv-collection`，依赖固定在 `backend_server/requirements-collection.txt`。当前后端与 ngrok 在后台运行，日志、PID 和切换记录位于忽略目录 `backend_server/runtime/`：

```text
collection-backend.log / collection-backend.pid
collection-ngrok.log / collection-ngrok.pid
https-cutover.json
```

这不是登录或开机自启动服务。电脑需持续开机联网、不休眠；重启电脑后需重新启动后端和 ngrok。证书续期在 ECS 上运行，不依赖电脑。

重启前暂停采集，等当前配对结束，核对 PID 文件对应的命令再正常停止进程（SIGTERM，手动前台启动时用 Ctrl+C）。确认旧进程退出、8000 端口释放后再启动，禁止第二个进程同时访问正式数据目录。每次后端启动会产生新批次，尚未完成的票据要重新采集。

终端一：

```sh
cd /Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/backend_server
HYBRIDGUARD_DATA_DIR="$PWD/collection_runs/mtc_20260917" \
HYBRIDGUARD_BROWSER_PROBE_ORIGINS="https://collect.crossdevicefingerprint.site,https://xavi-l.github.io" \
.venv-collection/bin/python -m uvicorn main:app \
  --host 127.0.0.1 --port 8000 --workers 1 \
  --proxy-headers --forwarded-allow-ips 127.0.0.1
```

终端二：

```sh
cd /Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint
ngrok http http://127.0.0.1:8000 \
  --traffic-policy-file deployment/ngrok-edge/crossdevicefingerprint.site/ngrok-edge-policy.json
```

上述手动前台命令不更新本次后台运行的 PID 文件；后续以实际进程和监听端口为准。沿用原 ngrok 账号认证和固定域名；若 ngrok 域名变化，还须更新 ECS `proxy.conf` 中 Host/SNI/上游地址并重载 Nginx。

重启后确认：

```sh
curl --fail https://collect.crossdevicefingerprint.site/api/collect/readiness
```

应为 `status=ready`、`collection_storage_name=mtc_20260917`，origins 含新域名，177/67 契约不变。日志只在电脑本地排障，不把票据、密钥或正式数据上传到公开站点。

## 提测与回退

新版 APK 和操作说明在 `deliverables/mtc_20260921_https/`。先用此前失败的 Android 5.1.1、红米 Note 4 / Android 6.0、荣耀 Note8 / Android 7.0 做小批复测，保留浏览器/WebView 版本与全流程日志，后台 `pair_status=completed` 才算完整成功。

服务器验证只证明新域名的 TLS 与代理配对流程可用；合成信号不是实机特征采集证据。页面打开、App177 单独成功或自动化脚本通过均不足以证明 Browser67 已配对。

回退时暂停采集，正常停止新 ngrok 和后端；以同一正式数据目录和持久 Python 环境启动，ngrok policy 改回 `backend_server/ngrok-mtc-policy.json`，使用原 ngrok/GitHub Pages 入口的旧 APK。旧入口的 Android 浏览器证书问题仍存在，因此该回退仅恢复旧拓扑。不要用旧备份覆盖已经追加的新采集数据；备份是故障恢复材料。

参考：[ngrok Host rewrite](https://ngrok.com/docs/gateway/endpoints/http#rewriting-the-host-header)、[ngrok add-headers](https://ngrok.com/docs/gateway/traffic-policy/actions/add-headers)、[Nginx proxy](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)、[ZeroSSL ACME](https://zerossl.com/documentation/acme)。
