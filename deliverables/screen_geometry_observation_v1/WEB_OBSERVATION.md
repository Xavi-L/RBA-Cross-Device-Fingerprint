# Web 同步几何快照

`web_probe/webview_geometry_observer.js` 的版本为 `webview-web-geometry-v1`。FeatureApp 的资产页正常加载此模块，Android 在宿主前后快照之间调用 `HybridGuardProbe.captureWebViewGeometry(request)`；CDP 无需安装观察器。函数没有 Promise、计时器、DOM 写操作或跨帧读取，全部 Web 值来自当前文档的一次同步调用。

`fields` 的每项保存 `{value,status,reason,unit}`。`inner_width/height`、`screen_width/height`、`avail_*`、DPR、`visual_viewport_*` 和方向使用 canonical 探针的相同平台 getter。新模块增加 `document.documentElement.clientWidth/clientHeight`、visual viewport 的 offset/page 位置、viewport meta、URL、readyState 和 compatMode。由于旧投影会补 0、1 或 -1，新原始快照不直接调用该有损投影；旧 canonical 源码、67 项目录及原始投影行为保持不变。

CSSOM View 的长度口径是 CSS 像素；innerWidth/Height 涉及布局视口，visualViewport 描述可见视口，screen 描述 Web 暴露的屏幕而非 WebView View 大小。文档根元素的 client 尺寸依赖标准/怪异模式，故一并记录 compatMode。DPR 与 visualViewport.scale 分别记录，不把任一数值转换成宿主 density 或 Android 缩放。语义依据：[CSSOM View 的像素与缩放定义](https://drafts.csswg.org/cssom-view/#css-pixels)、[Window 属性](https://drafts.csswg.org/cssom-view/#extensions-to-the-window-interface)、[VisualViewport](https://drafts.csswg.org/cssom-view/#visualviewport)。这些是 API 口径依据，不构成跨层等式或特定 WebView 实现一致性的保证。

不存在或为 null 的 API 记为 `unsupported`，getter 抛错记为 `runtime_error`，错误类型记为 `wrong_type`，非有限数记为 `non_finite`；后两者均不转换成正常默认值。实际读到的 0 保留为 observed，由关系判断有效域。缺少 scale 不补 1。几何是否矛盾不影响读取状态；稳定性由 Android 独立确定。

`binding` 回传 session、WebView 实例、文档代次、观测和尝试 ID；每个文档独立创建 `document_id`，旧桥上传中的 `collection_observations.geometry_document_id` 与其一致。document_id 是关联标识，不是防篡改凭据。Android 必须校验回调仍属于当前实例及文档。JS Date 的 Unix 毫秒与当前文档 performance 毫秒分别保存，不能与 Android 单调时钟直接相减。

新快照在旧67字段采集完成、桥提交之后读取，明确保存 `same_snapshot_as_legacy_screen_layer=false`；不可把旧 screen_layer 的值塞进新同步关系。页面在桥提交前完成状态文字与日志更新，随后冻结 DOM 状态更新，直到 Android 结束几何观察后调用 updateResult。开始常规探针前最多80次、间隔50ms查询只读 readiness 标志；超时仍上传旧字段，附上超时原因。

后端现有允许附加键的请求模型、原始存档和合并存储已经保留完整 collection_observations，不修改生产存储逻辑。新增定向测试覆盖 null、错误原因、失败尝试、旧 webdriver/WebGL 观测及177字段状态目录，重复请求仍只新增回执而不新增数据行。

验证命令：

```bash
node --test browser_probe_site/tests/webview-geometry-observation.test.mjs browser_probe_site/tests/featureapp-webgl-integration.test.mjs browser_probe_site/tests/probe-contract.test.mjs
(cd backend_server && .venv-collection/bin/python -B -m unittest test_geometry_observation_storage test_collection_contract)
```
