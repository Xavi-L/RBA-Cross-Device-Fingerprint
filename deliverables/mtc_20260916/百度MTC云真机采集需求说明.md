# 百度 MTC 云真机数据采集需求说明

App177 与独立 Browser67 配对采集　｜　2026 年 9 月 16 日

## 1 项目目标与采购方式

我们希望委托百度 MTC 在符合条件的 Android 云端实体真机上运行定制脚本，采集同一设备的 App177 与独立浏览器 Browser67 数据，用于跨设备环境特征和跨运行环境一致性研究。我们提供采集 APK、浏览器探针和接收服务；MTC 负责真机编排、跨应用自动化、浏览器首次启动页面处理以及执行记录。

本次按人民币 10 元每部采购云真机测试服务，不购买套餐。采购范围是 MTC 当前可提供且满足本文条件的全部真机，预计 600 多部；600 部为规模预估，不作为采购上限。实际设备数、使用时长和费用范围以双方核定清单及报价为准。

| 商务项目 | 本次需求 |
| --- | --- |
| 单价 | 云真机服务 10 元／部 |
| 数量 | 全部符合条件的可用真机，预计 600+ 部 |
| 基础费用 | 10 元 × 实际核定计费设备数；600／650／700 部分别为 6,000／6,500／7,000 元 |
| 另需明确 | 是否含税、脚本编写、单部时长、并发额度、日志导出及失败重跑；未明确项目不视为已包含 |

## 2 需要交付的结果

每部纳入执行的真机至少取得一轮可验收的配对采集：App177 为 Native 84 项、WebView 宿主 26 项、App 内 Web 67 项；Browser67 为同一设备独立浏览器中的 67 项。两端通过同一次采集会话对应的配对记录关联，合计形成 paired244 数据单元。

目标是覆盖全部核定设备并尽可能完成全部配对。未成功设备逐部列明原因和补采结果；未经我方确认，不因运行失败缩小原定执行分母。覆盖率与配对完成率单独报告，不能用“安装成功”或“脚本通过”替代数据验收。

| 统计单位 | 计数规则 |
| --- | --- |
| 采购设备数 | 按 MTC 可核对的设备 ID 及其物理设备映射去重；映射无法确认时注明标识作用域 |
| 去重机型数 | 另按规范化品牌与硬件型号统计；同型号的不同实体机保留各自设备记录 |
| 设备配置数 | 另列型号、Android 版本和系统构建；同一实体机的多系统条目不得直接重复计为多部 |
| 有效配对数 | 每个完成质检的采集轮次一组；重传不新增样本，重复采集不新增设备 |

因此，预计购买 600+ 部真机不自动等于获得 600+ 个不同机型。请在报价清单中同时列出设备数、型号数及系统配置数。

<!-- PAGE -->
## 3 设备与版本范围

准入下限为 Android 5.0／API 21。优先使用设备现有的正式系统，不因品牌、分辨率、折叠形态或旧系统年代单独排除。Android 17／API 37 及后续系统可列入候选，但须确认实际系统为正式版本，并通过该版本先导试跑后纳入正式执行。

| Android 版本 | API Level | 处理方式 |
| --- | --- | --- |
| 5.0／5.1 | 21／22 | 纳入；重点验证旧 WebView 和自动化驱动 |
| 6.0 | 23 | 纳入 |
| 7.0／7.1 | 24／25 | 纳入 |
| 8.0／8.1 | 26／27 | 纳入 |
| 9／10 | 28／29 | 纳入 |
| 11 | 30 | 纳入；核实浏览器可见性与启动 |
| 12／12L | 31／32 | 纳入 |
| 13／14 | 33／34 | 纳入 |
| 15／16 | 35／36 | 纳入 |
| 17 及后续版本 | 37 及以上 | 正式系统及对应 API 先导试跑通过后纳入 |
| 4.4 及更早版本 | 20 及以下 | 不纳入；不满足 APK 最低 API 要求 |

当前采集器配置为 minSdk 21、targetSdk 36、compileSdk 36 加 minor API 1，未声明 maxSdk。targetSdk 和 compileSdk 不代表运行系统的上限，也不构成对所有新系统的兼容性保证。版本映射参考 Android 官方文档 [1]。

本轮以 Android 真机手机为主，含折叠屏。平板或其他终端如在可供范围，请单列供双方确认。模拟器、虚拟 Android 实例及不能运行本 APK 的系统不纳入。兼容 Android 的 HarmonyOS／EMUI 设备按实际 Android API 与安装运行能力判断，不按营销版本号换算；不兼容 Android APK 的系统不纳入。

Developer Preview、Beta、Canary、刷机系统、已知 Root 或系统改造设备请单列，不混入本轮常规正式系统数据。MTC 自身所需 ADB、控制代理及自动化工具请披露；存在云测控制环境不自动表示攻击样本。

浏览器和 WebView 不预设统一版本下限，也不要求全部升级。须有可启用的 WebView，以及至少一个可显式启动、可访问 HTTPS 探针并执行采集核心的合格独立浏览器。具体准入以先导试跑为准；个别硬件或 Web API 不支持时允许明确记录缺失状态。无浏览器设备可先列为待准备，补装浏览器须经双方明确，并单独记录环境来源。

<!-- PAGE -->
## 4 采集流程与操作边界

MTC 脚本需持续控制采集 App、系统弹窗和独立浏览器三个界面范围。框架可采用 MTC 已支持的 UIAutomator 或 Appium 等方案，具体驱动版本应覆盖 API 21 及以上；不能因选用新版驱动而静默丢弃旧系统设备。官方脚本编写资料见 [2]，实际云端执行权限以联调为准。

| 阶段 | 需要执行的动作 | 完成依据 |
| --- | --- | --- |
| 设备准备 | 记录设备和系统，保持亮屏、解锁，确认 WebView 和独立浏览器可用 | 环境记录齐全 |
| 浏览器准备 | 处理首次欢迎页、必要协议、跳过登录与可选推荐；保留包名和版本 | 浏览器可正常打开测试页 |
| 网络检查 | 从设备侧检查接收服务与静态探针可达 | readiness 与页面检查通过 |
| 启动 App | 带设备 ID、任务 ID、轮次启动指定入口；App 自动采集 | 后台出现当前轮次 App 回执 |
| 独立浏览器 | 跟随 App 打开的本次配对 URL，处理已约定弹窗 | page_loaded 等阶段出现 |
| 等待配对 | 保持浏览器前台，让 App 后台上传和配对完成 | completed 且两端数据质检通过 |
| 收尾 | 导出逐设备结果；失败时保存截图和日志后有限重试 | 结果留存后再卸载或回收 |

App177 落盘后，现有 APK 会并行上传 App 数据、请求临时配对 ticket，再打开浏览器。脚本必须允许这种并行顺序，不能为了等待 App 上传而把已打开的浏览器强制切回。浏览器不要求回跳 App。

浏览器初始化尽量在正式启动 App 前完成。若首次启动页吞掉了配对链接，先保存本轮结果，再使用新轮次重新启动采集；不要从地址栏复制残缺链接，不要自行拼造 ticket，不要用不带配对信息的首页代替正式探针。浏览器晚到的数据仍按原轮次归档。

| 调度参数 | 建议初值及约束 |
| --- | --- |
| 单轮等待上限 | 180 秒，从本轮 App 启动计时；联调后调整 |
| 单部作业上限 | 600 秒，含准备和最多一次新增采集轮次；不代表 10 元已含此时长 |
| 查询间隔与并发 | 每 5 秒查询一次；先导并发 5，正式并发建议从 20 起按容量调整 |
| 重试 | App 自身处理同 payload 重传；脚本最多新增一轮，使用新轮次和新 session |
| ticket 有效期 | 当前为签发后 10 分钟；poll token 为 1 小时，超时不得复用过期 ticket |

本次只采集运行环境与设备特征。当前 App 仅声明 INTERNET 和 ACCESS_NETWORK_STATE，不需要登录、短信、联系人、相册、位置、相机或麦克风授权。浏览器弹窗只处理预先约定的必要选项；不全量授予权限，不修改 UA、分辨率或 WebView 版本，不安装攻击工具，不主动 Root 或改机。

<!-- PAGE -->
## 5 APK 与后端接口对接

交付基线为包名 com.example.hybridguard.featureapp，入口为 .MainActivity；当前 versionCode 为 8，versionName 为 1.6.1-expanded-v2.2-browser-recovery。正式提测以我方交付清单中冻结的 APK 和版本为准，不能混用历史安装包。

| 数据协议 | 固定口径 |
| --- | --- |
| App | expanded-v2.2-status，177 项 |
| Browser | browser-web-v1-status，67 项 |
| 共同 Web 核心 | expanded-web-67-v1；App 内 Web 与独立 Browser 使用同一字段目录 |
| 浏览器选择 | available-browser-v2-package-scoped；按合格候选选择并限定包启动，不要求预设默认浏览器 |

以下接口已存在，由 App 或浏览器正常调用。后端 origin 和静态探针地址由我方提测时提供；文档中的 BACKEND_ORIGIN 等变量均为占位，不是可执行地址。

| 方法与路径 | 调用方与用途 |
| --- | --- |
| GET /api/collect/readiness | App 与联调端检查协议、配对能力和后端批次 |
| POST /api/collect/fingerprint | App 上传 App177 并取得回执 |
| POST /api/collect/browser-ticket | App 申请本轮浏览器配对票据 |
| POST /api/collect/browser-stage | App／浏览器记录启动与页面阶段 |
| POST /api/collect/browser-fingerprint | 独立浏览器上传 Browser67 |
| GET /api/collect/browser-pairs/{pair_id} | App 使用独立 poll token 查询配对结果 |

MTC 启动 App 时传入以下 Intent extras。DEVICE_MANIFEST_ID 使用 MTC 稳定设备标识的可追溯映射，字符限定为 A–Z、a–z、0–9、点、下划线、冒号、连字符，长度 1–96。每次重新采集递增 COLLECTION_ROUND；同 payload 重传不递增。以下键名均带前缀 com.example.hybridguard.featureapp.。

```text
DEVICE_MANIFEST_ID = "mtc:<stable_device_id>"
RUNTIME_CONTEXT   = "mtc:<platform_run_id>"
COLLECTION_ROUND  = 1
```

现有后端没有按“任务＋设备＋轮次”直接供 MTC 查询的成品接口。参考伪代码中的 RESULT 适配层需由我方在先导测试前完成：从现有回执、原始 App 数据、浏览器阶段和配对记录关联结果，向 MTC 提供经授权的只读查询或等价结果通道。不能把现有 pair 查询视为匿名接口，也不要求脚本读取 App 私有目录中的 token。

正式运行必须使用设备可达的公网 HTTPS 地址。App 上传、ticket、pair 查询使用同一后端 origin；静态探针可使用单独 origin，但须配置允许列表和跨域访问。我方负责固定地址、readiness、并发验证与备份；当前 JSON／JSONL 后端按单进程单 worker 运行，作业期间不热重载，重启须暂停发起新轮次并重新确认批次。

<!-- PAGE -->
## 6 验收与交付

单轮通过须同时满足：当前任务、设备和轮次对应到唯一明确的 App session；App177 与 Browser67 字段目录和逐字段状态符合冻结协议；同一配对记录连接两端真实回执；pair_status 为 completed；数据质检通过。若查询匹配多个无法解释的 session，先标记关联异常，不任选一条算成功。

244 项是字段契约数量，不是 244 项必须非空。unsupported_by_os、not_applicable 等合理缺失可按冻结质检规则接受；permission_denied、runtime_error、timeout 必须保留并评审。核心探针整体未运行或整层超时，不计为有效完整配对。不得填零冒充数据，也不得用 App 内 Web67 复制充当 Browser67。

| 交付结果分类 | 含义 |
| --- | --- |
| PAIRED_VALID | 配对完成且字段质检通过，可计入有效配对 |
| PAIRED_QC_REVIEW | 后台已 completed，但存在待复核的数据问题 |
| APP_ONLY | 已有 App 数据，Browser 缺失或未正式绑定 |
| FAILED | 安装、启动、网络、超时等明确失败，保留阶段原因 |
| NOT_RUN | 未获得执行机会或全局故障暂停；保留在核定清单中 |

这些是本项目结果分类，不替代后端原生状态。awaiting_app_and_browser、awaiting_app、awaiting_browser、expired 均不等于完成；即使界面显示成功或 HTTP 返回 200，也须核对回执及配对事实。

建议先对 20–30 部代表设备试跑，覆盖主要品牌、最低 API、旧 WebView、新系统和不同浏览器首次启动流程。先导通过条件为关联和统计正确、无未解决的共性阻塞、样本缺失原因明确，再扩大至全部清单；先导通过不构成对全量成功率的保证。

MTC 交付设备清单、逐轮执行表、最终逐设备结果、失败截图与日志，以及定制脚本源码和运行说明。逐轮表至少包含设备 ID、品牌型号、系统/API/构建、WebView 与浏览器包名版本、是否后装浏览器、任务与轮次、起止时间、结果和原因。可读取不到的版本字段明确记为 unknown，不据 UA 猜填。

我方交付 App／Browser 原始 JSON 或 JSONL、回执与配对记录、质检结论及汇总。联表需保留 session_id、pair_id、两端 receipt_id、collection_batch_id；后端批次与 MTC 任务 ID 分开记录。必要日志中不保存 ticket、poll token 或含票据的完整 URL；失败截图避开此类凭据。

## 7 请 MTC 在执行前确认的事项

请回复全部合格设备的可供清单和三个数量口径；10 元单价包含的时长、税费、脚本、导出及重跑范围；是否可传 Intent extras 并跨应用控制浏览器；老 API 可用的驱动方案；无浏览器及首次启动页处理方式；平台何时强制停止或回收设备；设备标识作用域和替换规则。对环境不满足、平台失败、采集器失败分别约定补采及费用处理，不预设任何一类失败自动免费。

如后续公开脱敏研究数据，请另确认原始数据、衍生字段与日志可使用和可发布的范围。所有执行设备都保留原始结果，补采成功不抹去先前失败记录。

<!-- PAGE -->
## 8 参考脚本配置与批次调度

以下为 Python 风格伪代码，表达所需行为，不是可直接上传 MTC 执行的脚本。MTC.* 表示平台适配；RESULT.* 表示我方待提供的结果通道；POLICY.* 表示双方在先导测试前冻结的准入与质检规则。真实执行需先完成这三个适配层。

```pseudo
CONFIG = {
  apk: FINAL_APK,
  package: "com.example.hybridguard.featureapp",
  activity: ".MainActivity",
  backend: BACKEND_ORIGIN,
  probe: PROBE_ORIGIN,
  run_id: MTC_PLATFORM_RUN_ID,
  min_api: 21,
  round_timeout_s: 180,
  device_timeout_s: 600,
  max_attempts: 2,       # 首轮加最多一次新增轮次
  poll_interval_s: 5,
  parallelism: CONFIRMED_CONCURRENCY
}

def run_batch():
  require_all_adapters_ready()
  manifest = MTC.confirmed_device_manifest()
  require_unique_platform_device_ids(manifest)
  require_all_eligible_devices_are_listed(manifest)
  RESULT.register_manifest(CONFIG.run_id, manifest)
  # 不在脚本中截取前 600 部，也不执行任何购买动作。
  ready = RESULT.readiness(CONFIG.backend)
  require_expected_contract(ready, app=177, browser=67)
  require_open_single_worker_batch(ready)
  batch_id = ready.collection_batch_id

  pilot = select_representative_devices(manifest, 20, 30)
  pilot_results = run_group(pilot, parallelism=5,
                            expected_batch=batch_id)
  if not POLICY.pilot_accepted(pilot_results):
    RESULT.mark_remaining_not_run("PILOT_NOT_ACCEPTED")
    return RESULT.export_all_results()

  # 已有合格先导数据不强制重复；失败先导项保留待补采。
  remaining = unpaired_devices_with_retry_budget(manifest)
  run_group(remaining, CONFIG.parallelism, batch_id)
  RESULT.reconcile_late_arrivals_without_overwriting()
  RESULT.export_all_results()
```

run_group 必须使用有界并发，并在单部作业异常时保存结果；若 readiness 不可用或后端批次变化，暂停新作业，将尚未执行的设备标记为 NOT_RUN，而非继续大量消耗设备时间。恢复后重新联调并明确新批次，不能把旧 ticket 搬到新批次使用。

<!-- PAGE -->
## 9 参考脚本单设备流程

```pseudo
def collect_device(device, expected_batch):
  deadline = monotonic_now() + CONFIG.device_timeout_s
  try:
    MTC.acquire(device)
    env = MTC.inspect_device(device)
    RESULT.save_environment(device.id, env)
    if not POLICY.environment_eligible(env):
      return RESULT.fail(device.id, "ENVIRONMENT_MISMATCH")
    MTC.unlock_and_keep_screen_on()
    MTC.verify_device_network(CONFIG.backend, CONFIG.probe)
    MTC.install_apk(CONFIG.apk, auto_launch=False)
    MTC.prepare_qualified_browser(POLICY.browser_rules)
    used = RESULT.attempt_count(CONFIG.run_id, device.id)
    for attempt in range(used, CONFIG.max_attempts):
      if monotonic_now() >= deadline:
        break
      require_same_open_batch(expected_batch)
      round_id = RESULT.next_round(CONFIG.run_id, device.id)
      MTC.stop_previous_collector_and_probe_if_any()
      started_at = utc_now()
      MTC.launch_activity(CONFIG.package, CONFIG.activity,
        extras=make_extras(device.id, CONFIG.run_id, round_id))
      round_end = min(deadline,
        monotonic_now() + CONFIG.round_timeout_s)
      while monotonic_now() < round_end:
        require_same_open_batch(expected_batch)
        MTC.handle_only_agreed_dialogs()
        r = RESULT.read_round(CONFIG.run_id, device.id,
                              round_id, started_at)
        if r.identity_conflict:
          RESULT.record_attempt(r, "IDENTITY_CONFLICT")
          break
        if is_valid_pair(r, expected_batch):
          return RESULT.record_attempt(r, "PAIRED_VALID")
        if r.terminal_failure_or_qc_rejection:
          RESULT.record_attempt(r, classify(r))
          break
        sleep(CONFIG.poll_interval_s)
      RESULT.close_attempt_preserving_partial_data(round_id)
      MTC.capture_failure_evidence_without_credentials()
      if not POLICY.recoverable_before(deadline):
        break
      MTC.recover_known_browser_or_network_blocker()
    return RESULT.final_device_result(device.id)
  except Exception as error:
    return RESULT.save_error_and_partial(device.id, error)
  finally:
    RESULT.flush_execution_log()
    MTC.release_if_acquired_after_result_saved()
```

<!-- PAGE -->
## 10 参考脚本验收与适配约定

```pseudo
def is_valid_pair(r, expected_batch):
  if r.identity_conflict or not r.exact_run_device_round_match:
    return False
  if not r.app_receipt_valid or not r.browser_receipt_valid:
    return False
  if r.pair_status != "completed":
    return False
  if r.collection_batch_id != expected_batch:
    return False
  if not r.pair_links_exact_app_and_browser_receipts:
    return False
  if not r.app_catalog_and_statuses_match_177:
    return False
  if not r.browser_catalog_and_statuses_match_67:
    return False
  if not r.web_core_revisions_match_frozen_contract:
    return False
  return POLICY.accept_field_quality(r)

def make_extras(device_id, run_id, round_id):
  prefix = "com.example.hybridguard.featureapp."
  stable_id = approved_device_id_mapping(device_id)
  require_full_match("[A-Za-z0-9._:-]{1,96}", stable_id)
  return {
    prefix + "DEVICE_MANIFEST_ID": stable_id,
    prefix + "RUNTIME_CONTEXT": "mtc:" + run_id,
    prefix + "COLLECTION_ROUND": round_id
  }
```

POLICY.accept_field_quality 使用冻结字段目录和状态规则，不要求所有值非空。RESULT 返回的 app_receipt_valid 等字段是适配层的派生判断，不是现有 HTTP 响应中已存在的字段；需要从真实回执、原始数据和配对记录计算。脚本不能生成指纹值或伪造回执。

RESULT.read_round 应按 App payload 中的 runtime_context、device_manifest_id、collection_round 和本轮时间窗定位，再用 session、ticket request、pair、receipt 关联。出现多个不明 session 时返回 identity_conflict。日志延迟与查询暂时失败应返回可重试状态，不能被误判为已完成。

MTC.prepare_qualified_browser 与 App 的浏览器选择规则须一致，可准备现有合格候选并验证实际前台包名。若正式启动后仍遇到引导页或链接丢失，按第 4 节保存原轮次并重开；不要强行切换到另一浏览器来完成原 ticket。

## 11 交付前参考依据

[1] Android Developers，uses-sdk 与 Android API Level 对照。https://developer.android.com/guide/topics/manifest/uses-sdk-element

[2] 百度智能云，UIautomator2.0 脚本编写。https://cloud.baidu.com/doc/MAT/s/1jwvxlu9f

协议与 APK 配置按 2026 年 9 月 16 日项目源码核对。正式执行以双方冻结的 APK、字段目录、地址、质检规则和 MTC 设备清单为准；我方随提测材料提供采集协议说明。
