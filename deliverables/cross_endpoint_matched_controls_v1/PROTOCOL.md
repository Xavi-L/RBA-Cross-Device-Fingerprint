# B2-B 本地同环境对照协议

本轮在 `ad121b53015f34ce22644f27bceec5d9d24bcf4e` 上新增独立批次。`PLAN.json` 固定七种过程、各两轮、pre/change/post，共 42 个位置。`FROZEN.json` 在正式采集前登记采集代码、原条件、三个 RETENTION 模型及直接依赖。训练调用为 0，候选公式、阈值、解析器、模型、旧 18 条、MTC891 及正式协议资格均不改变。

唯一环境为本机新启动的 `Medium_Phone_API_36.1`、arm64、Chrome/WebView 134。原 B1 为 x86_64 / Chrome133，不能合并为同一环境。本轮初始系统为 en-US / Asia/Shanghai，Chrome 网页首选列表为 en-US、en；保留此真实基线，不为了扩大差异改成 UTC。固定目标为 fr-FR、单元素列表 `[fr-FR]`、Asia/Tokyo。全部有效且恢复成立时应有 8 个有效干预位置和 34 个正常位置；该数字不是强制验收目标。

正常设置与运行时干预分开：

- `L_SYS_LANG`：Android Languages UI 添加 Français (France)、移到首位并确认；post 删除法语并确认恢复英语。该系统操作会同时改变地区，保存 UI 和 Native 原值。
- `L_SYS_TZ`：Android AlarmManager shell 设置真实系统时区，暂关自动时区；post 恢复 Asia/Shanghai 和原自动时区值 1。
- `L_BROWSER_LANG`：Chrome Settings → Languages → **Preferred languages** 中添加 French (France)、Move to top；post 删除该项。保留 en-US、en，未改 Chrome 界面语言或翻译目标。
- `A_APP_*`：仅当前 App PID 的 WebView DevTools socket / 当前空白页。语言通过新文档前脚本安装 B1 相同 getter，时区使用 Emulation.setTimezoneOverride；导航到原 APK 的原探针页面。
- `A_BROWSER_*`：仅独立 Chrome 的 exact-ticket 页面，复用 B1 的语言 getter / timezone override，原 adapter JS 被阻塞时安装，随后放行原字节。

Chrome 的官方说明将网页首选语言、应用界面语言与翻译设置分列；本机 134 版本 UI 有独立 Preferred languages 列表，并已工程验证排序、删除、恢复。依据：[Chrome Android 语言设置](https://support.google.com/chrome/answer/173424?co=GENIE.Platform%3DAndroid&hl=en)。当前设备是否改变 navigator 值由 raw 与观察值判断，不能由文档推定。

所有阶段采用相同的 App 空白页等待、CDP 连接、导航、Chrome 预热、adapter gate、exact-ticket 配对与收据等待流程。正常位置不安装运行时目标修改。两个控制端点分别记录 channel、PID/target、操作前/持有中/结束/恢复值；只有两个记录已完成或有界等待失败后才撤销。失败保留单端 raw、独立身份错误与全体预定输出，不按时间最近猜配。

App 和 Browser 的 payload 时钟属于设备报告域；CDP 的 Date.now 同样属于对应运行时。控制主机 UTC、主机 monotonic ns 与本机服务端 UTC 分别标记。控制范围主要由程序先后顺序（App 新文档脚本、Browser gate）、收据及持有结束观察证明；不把会受设置影响的设备时钟跨域相减作为因果证明。

工程冒烟为单独的 12 个位置（四类运行时干预各一组三阶段）。正常 UI 的工程操作不采入正式数据。首次 Chrome 通知弹窗及菜单描述出现更新提示导致的脚本失败全部保留。仅修复这些已观察到的工程路径，不查看模型分数挑参数。配置冻结后正式矩阵一次；若出现工程错误，须另留首次失败和受影响补跑清单，不覆盖记录。

本轮确有一次正式采集后的工程修复：首轮 `L_BROWSER_LANG` 的 UI 中法语置顶成功，但立即 force-stop 后，冷启动 UI 显示法语已经丢失。不能据此判定 Chrome 对持久化偏好不响应。一次固定 15 秒等待后的冷启动检查确认偏好可持久化。修复只在实际浏览器偏好操作/恢复后增加 15 秒等待及冷启动列表核对；原脚本快照、问题登记、修复摘要和事前六位置替换表分别保留。首轮 42 个配对加两组修复三阶段，共 48 次正式/修复采集尝试；规范评价仍为 42 个预定位置，不将额外记录增加到分母。

Chromium 的 `ImportantFileWriter` 实现存在延迟提交机制，默认间隔为 10 秒，这为上述工程假设提供背景；本机的实际冷启动 UI 对照才是本轮修复依据，不能将当前源码直接当作已安装 134 版本的逐行证明。参见 [Chromium 原始实现](https://chromium.googlesource.com/chromium/src/+/lkgr/base/files/important_file_writer.cc)。

`evaluate.py` 是明确命名的新批次适配器，复用 B2-A 纯字段和预测代码，不调用旧 pilot 的 18 条限定入口。每个模型仅收到当前 App raw；条件仅收到当前阶段投影，pre/post 仅供独立操作资格与恢复审计。资格判断不能访问模型或条件输出。已执行但无可观测变化、缺端、未执行、恢复失败、算法 U、预测 FAILED 都保留不同状态。

新完整指纹、票据、CDP 通信和 APK 放在忽略的 `private_runs/`。本轮未获新 raw 公开授权；报告只公开必要的语言/时区操作数和汇总。没有复制 B1 488 文件，没有自动提交、推送或训练。

结束时恢复系统语言、时区、网页语言列表，关闭本轮测试 App、Chrome 和服务；只停止本轮 emulator-5580，不停止共享 ADB server。模拟器以只读临时 overlay 启动且不保存快照，退出后原 AVD 的旧 App、数据和设置保持原样。
