# 国际真机云 Android 测试类型与机型数量补充统计

统计日期：2026-07-06

## 统计口径

- 对齐本目录已有 WeTest / Sauce Labs / 百度 MTC 口径：优先统计唯一 Android 机型 / 硬件型号，而不是 Android 版本组合数。
- 如果平台只公开“iOS + Android 总设备量”或只在登录后展示设备目录，不把营销总量反推为 Android 唯一机型数。
- “类似脚本兼容测试”指上传 APK 后由平台自动执行基础遍历、随机事件、AI/无脚本流程或批量兼容性检查的能力；不同平台叫法不一致。
- 本轮只使用公开官方资料和本机可用工具。Firebase 官方目录 API 本机请求超时，且当前机器没有 `gcloud`；AWS CLI 也未安装，因此 AWS / Firebase 没有生成精确设备明细表。

## 结论表

| 平台 | 类似脚本兼容测试可用 Android 型号数 | Appium 测试可用 Android 型号数 | Robo test 可用 Android 型号数 | 当前可统计性 |
| --- | ---: | ---: | ---: | --- |
| AWS Device Farm | 未公开；需登录 Console 或 API 拉取 Public Devices 后过滤 Android | 未公开；同一 Android 设备目录过滤后可得 | 不支持 Firebase-style Robo；有 Built-in Fuzz | 可精确，但需要 AWS Console / API |
| Firebase Test Lab | 可由 Robo / Robo script 的 Android catalog 精确得到；本机未拉取成功 | 不支持官方 Appium 测试类型 | 可由 Android catalog 精确得到；本机未拉取成功 | 可精确，但需要 `gcloud` / API Explorer / console |
| TestMu AI | 未公开 Android-only 数；官网只给 `10000+` real iOS + Android 总池 | 未公开 Android-only 数；同上 | 未发现 Firebase-style Robo | 公开资料不足，需登录或销售导出 |
| HeadSpin | 未公开 Android-only 数；官网只描述 real-device infrastructure | 未公开 Android-only 数；支持 Appium，但无公开机型表 | 未发现 Firebase-style Robo | 公开资料不足，需账号或销售导出 |

## 平台说明

### AWS Device Farm

- 官方设备列表页说明 Device Farm 使用真实 iOS / Android 设备，并提示要查看带详细信息的支持设备列表，需要登录 AWS 账号查看 Public Devices list。
- Android 自动化框架里官方列出 Automatic Appium tests 和 Instrumentation。
- Built-in test type 只有 Built-in Fuzz，行为是向设备随机发送 UI 事件并报告结果；它最接近“无脚本兼容性 / Monkey 类测试”，但不是 Firebase 的 Robo。
- 因此 AWS 的三个口径应写成：Built-in Fuzz = 可用但数量需登录/API；Appium = 可用但数量需登录/API；Robo = 不支持。

精确化建议：

```bash
aws devicefarm list-devices \
  --region us-west-2 \
  --filters attribute=PLATFORM,operator=EQUALS,values=ANDROID \
  --output json > device_cloud_catalog/aws_device_farm_android_devices_raw.json

jq '[.devices[] | {manufacturer, model, modelId, os, formFactor, availability, fleetType}]
    | unique_by(.modelId // (.manufacturer + " " + .model))
    | length' device_cloud_catalog/aws_device_farm_android_devices_raw.json
```

### Firebase Test Lab

- 官方文档说明可通过 Firebase console、`gcloud firebase test android models list` 或 Google APIs Explorer 查看可用设备。
- Android Test Lab 文档列出 instrumentation test、Robo test、Robo script、Game Loop test 等工作流。
- Firebase Test Lab 的强项是 Robo / Robo script，而不是 Appium；我没有在本轮检查到官方 Android Test Lab Appium 测试类型。
- 当前机器没有 `gcloud`，直接请求 `https://testing.googleapis.com/v1/testEnvironmentCatalog/android` 超时，所以没有写入精确型号数。

精确化建议：

```bash
gcloud firebase test android models list --format=json \
  > device_cloud_catalog/firebase_test_lab_android_models_raw.json

jq 'length' device_cloud_catalog/firebase_test_lab_android_models_raw.json
```

如果需要区分真机 / 虚拟设备、手机 / 平板，先查看 JSON 字段后再加筛选条件：

```bash
jq '.[0]' device_cloud_catalog/firebase_test_lab_android_models_raw.json
```

### TestMu AI

- 官方 Real Device Cloud 页面写明可以在 `10000+` real iOS and Android devices 上测试，并支持 manual、automated、AI-native tests。
- 同页写明兼容 Appium、XCUITest、Espresso、Detox、Maestro，并提供 KaneAI 这种无脚本 / AI-native app automation。
- 但公开页面没有给出 Android-only 机型表，也没有把 `10000+` 拆成 Android / iOS / OS-version / device-instance 口径。
- 因此只能记为：Appium 和 AI/无脚本自动化可用，但 Android 唯一机型数公开不可统计；Robo test 未发现。

### HeadSpin

- HeadSpin 官方页面描述 real-device mobile app testing、global device infrastructure，以及 50+ global locations。
- Appium & Selenium 页面说明可把 Appium 脚本接入 HeadSpin real devices，并提到 thousands of real devices and browser/OS combinations、Samsung / Google Pixel / Motorola 等移动设备。
- 公开页面没有可下载或可解析的 Android 机型表，价格页也只描述套餐和功能，不给 Android-only 型号数量。
- 因此只能记为：Appium 可用，但 Android 唯一机型数需账号或销售导出；Robo test 未发现。

## 机器可读结果

- `INTERNATIONAL_ANDROID_DEVICE_AVAILABILITY_BY_TEST_TYPE.csv`：按平台和测试类型列出的可用性 / 数量状态表。

## 官方来源

- AWS Device Farm device list: https://aws.amazon.com/device-farm/device-list/
- AWS Device Farm test types: https://docs.aws.amazon.com/devicefarm/latest/developerguide/test-types.html
- AWS Device Farm Built-in Fuzz: https://docs.aws.amazon.com/devicefarm/latest/developerguide/test-types-built-in-fuzz.html
- AWS Device Farm ListDevices API: https://docs.aws.amazon.com/devicefarm/latest/APIReference/API_ListDevices.html
- Firebase Test Lab available devices: https://firebase.google.com/docs/test-lab/android/available-testing-devices
- Firebase Test Lab Robo test: https://firebase.google.com/docs/test-lab/android/robo-ux-test
- TestMu AI Real Device Cloud: https://www.testmuai.com/real-device-cloud/
- HeadSpin mobile app testing: https://www.headspin.io/solutions/mobile-app-testing
- HeadSpin Appium & Selenium automation: https://www.headspin.io/solutions/appium-selenium-test-automation
