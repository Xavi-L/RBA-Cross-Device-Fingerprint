# 百度 MTC 云真机采集需求

希望请 MTC 定制自动化脚本，批量采集同一部 Android 真机的 App 与独立浏览器环境特征，用于科研实验。以下为初步需求，实施细节可在确认可行后对接。

## 1 采购方式与采集目标

按 10 元／部采购云真机服务，不购买套餐。符合要求的可用真机都希望采购，预计 600+ 部，不以 600 部为上限。请提供设备及机型清单，数量以实际核定为准。

每部设备至少采集一组 App177＋Browser67。App177 包含原生层 84 项、WebView 宿主层 26 项、App 内网页 67 项；Browser67 是同一设备独立浏览器中的 67 项。成功以我方后台收到两端数据并确认配对有效为准；不支持的个别字段允许缺失并注明原因，失败设备列明原因并补采。

## 2 设备版本与 API 范围

使用 Android 5.0／API 21 及以上实体真机和正式系统，保留原有系统、WebView 与浏览器版本。设备需能运行我方 APK，具备可用 WebView、独立浏览器，并能访问公网 HTTPS 服务。

| Android 版本 | API Level | 范围 |
| --- | --- | --- |
| 5.0／5.1 | 21／22 | 纳入 |
| 6.0 | 23 | 纳入 |
| 7.0／7.1 | 24／25 | 纳入 |
| 8.0／8.1 | 26／27 | 纳入 |
| 9／10 | 28／29 | 纳入 |
| 11 | 30 | 纳入 |
| 12／12L | 31／32 | 纳入 |
| 13／14 | 33／34 | 纳入 |
| 15／16 | 35／36 | 纳入 |
| 17 及后续版本 | 37 及以上 | 正式版本先试跑，确认后纳入 |
| 4.4 及更早版本 | 20 及以下 | 不纳入 |

当前 APK 为 minSdk 21、targetSdk 36；targetSdk 不是运行版本上限。模拟器、预览／测试版系统不纳入本轮。新系统和旧浏览器的实际兼容性先通过少量试跑确认。

## 3 参考伪代码

我方提供 APK、采集网页和接收服务；MTC 负责设备调度、跨应用操作及浏览器引导页处理。以下函数为流程示意，需按 MTC 平台改写；后台结果查询由双方对接，等待时间和重试次数在试跑时确认。

```pseudo
for device in confirmed_devices:  # 全部符合条件的真机
    prepare_device_and_network(device)
    install_app(device)
    prepare_browser(device)       # 处理首次欢迎页、协议等
    success = False

    for attempt in range(1, 3):   # 示例：最多采集两轮
        round_id = new_round(task_id, device.id)
        restart_app(device, task_id, round_id)
        # App 自动采集，并打开本轮独立浏览器探针
        deadline = now() + WAIT_TIMEOUT

        while now() < deadline:
            handle_agreed_browser_dialogs(device)
            result = query_backend(task_id, device.id, round_id)
            if result.paired and result.data_valid:
                save_success(device, round_id, result)
                success = True
                break
            wait(POLL_INTERVAL)

        if success:
            break
        save_failure_reason_and_logs(device, round_id)
        recover_known_blocker(device)  # 保留原轮次记录

    save_final_device_result(device, success)
    release_device_after_results_saved(device)
```

关键要求：App 跳转浏览器后脚本仍能继续操作；等待两端上传及配对，不提前卸载 App。重试使用新轮次，保留此前失败记录。建议先少量试跑，再执行全部设备。

## 4 请 MTC 先确认

• 能否实现跨应用脚本，并处理不同品牌浏览器的首次使用页面？

• 符合要求的真机有多少部、覆盖多少机型，可以安排哪些设备试跑？

• 10 元／部包含多长使用时间？脚本定制及失败重跑是否另行收费？
