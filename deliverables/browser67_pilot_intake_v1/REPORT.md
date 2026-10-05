# Browser67 B1 本地接入验收

接入日期：2026-10-06。状态：**B1 先导接入完成；正式分组未具备条件。**
Browser语言/时区两配置先导已完成主仓接入；跨端关系开发与正式评价尚未完成，最终消融仍暂停。

## 1. 本地双包与原始证据

两个根目录 ZIP 的大小、整包 SHA-256、CRC、安全路径及首次解压字节通过核验；证据包共488个文件，487项清单的大小、摘要及已登记JSONL行数全部一致。`package_contents.json` 由整包摘要锁定，不要求循环自哈希。

- 源码ZIP身份：`59a0cff18386150eca90fcf09b2f6169ff186a1e`（ZIP comment）；用于实现及 source_manifest 核对。
- 测量主仓身份：`a16ba9dea3078a66b4e8e4338d00d9dd9df9893b`；与本次重建HEAD一致。
- 使用证据包的测量计划、原始runner与冻结核验器。源码包runner包含便携ADB路径改动，source_manifest可回连；中性计划模板未覆盖归档计划。
- `pilot_r8` 原始证据 **18/18通过**，**6/6三阶段组的目标效果与恢复通过**；归档自测试 **8/8通过**（真实基线＋7种篡改拒绝）。两份新报告与原报告解析内容完全一致，包括输入摘要。
- 原ZIP及全部首次解压文件的前后摘要一致；旧工程失败/跳过尝试的归档说明保留，未混入本批分母。

## 2. 跨平台兼容

macOS直接调用原核验函数复现 `FileNotFoundError`，原因是本机 `Path` 解释Windows路径。`path_compat.py`（`browser67-windows-path-compat-v1`）仅替换归档模块的 `Inputs.locked_path`；原核验函数、8项自测试、断言和证据字节均保留。

只接受构建清单中 `source_checkout` 的父目录和 `resume_archive_origin.directory` 两个根；以 `PureWindowsPath.relative_to` 映射完整相对路径，拒绝未知盘符/根、`..`、不支持路径和符号链接逃逸。完整旧根与本机路径只记在私有 `path_mapping.json`。归档核验器SHA-256：`9185c07796b69f5219432af80f32cd71b2947b235622798bdd05185161f5fad8`。

## 3. 主仓重建与逐成员一致性

调用实际主仓 `build_latest_paired244_snapshot.py`，生成独立的批次配置：App versionCode=16、versionName=`1.6.9-expanded-v2.2-geometry`、App schema=`expanded-v2.2-status`、Browser schema=`browser-web-v1-status`、probe=`expanded-web-67-v2`。8个数据源按登记原根映射到归档 `data/`；构建文件、177/67目录和探针manifest引用包内冻结材料。历史v8/v1默认配置与发布校验保留。

核对 35 个相关文件，均与冻结副本字节一致。 明细见 `INTAKE_SUMMARY.json` 的 `source_comparison`。

| 验收项 | 结果 |
|---|---:|
| paired244 / App-only / quarantine | 18 / 0 / 0 |
| 逐sample_id的244项原值 | 18/18，4,392项一致 |
| 逐sample_id的244项原状态 | 18/18，4,392项一致 |
| 完整sample_index（两端session、摘要、receipt、pair、batch等） | 18/18一致 |
| 捕获位置与重建索引的来源绑定 | 18/18一致 |
| 字段目录、QC、选择审计和其他分流视图 | 一致 |

交付与重建的 paired JSONL 仅CRLF/LF不同，未为匹配文件摘要修改输入。18个预定位置完整保留。`observed`共App 3,186项、Browser 1,206项，只说明原始采集状态，不代表每种任务都可比较。原值与状态不改；私有 `field_quality_sidecar.jsonl` 记录0/-1/false等需逐字段解释的字面值和附加观测引用，不统一判有效或无效，不生成检测规则或将未知补F。几何、WebGL1、webdriver附加观测保留在原始引用/侧表，不扩充244目录。

## 4. 控制、保持与恢复

范围为 **1个API36模拟器、独立 `com.android.chrome`、实录Chrome/133.0.6943.137**，App v16、Browser probe v2。

| 配置 | 核验内容 | 完整三阶段组 |
|---|---|---:|
| language_fr | active阶段Browser language/languages变为fr-FR；Browser时区目标保持；App Native/App Web语言与时区目标保持；post恢复pre | 3/3 |
| timezone_tokyo | active阶段Browser时区为Asia/Tokyo、offset=-540；Browser语言目标保持；App Native/App Web语言与时区目标保持；post恢复pre | 3/3 |

归档事件顺序确认控制先于Browser采集生效、上传之后再撤销；安装APK与源APK、探针字节、版本锁及干净停批次一致。摘要、回执与关联复核不等于重新执行HMAC密码学签名验证。

18阶段＝6个干预位置＋12个前后对照位置，不是18种攻击或18台设备；6/6为目标效果/恢复，不是检测率。未主张全载荷恒定。

## 5. 正式分组为何为空

本批facts原样保留 `candidate`、`identity_scope=run_profile`、`identity_stability=run_scoped_unverified`。实际主仓 `build_latest_experiment_plan.py` 使用原协议产生 train/development/test **0/0/0**；`structural_ready=false`、`grouped_data_prerequisites_met=false`，与交付readiness完全一致。

阻塞原因是无verified标签、无可信跨运行独立分组，继而不满足各split组数和类别覆盖；6组重复不能当成6台设备。该状态是正式研究准入限制，B1接入本身已完成。

## 6. 后续与停止边界

可以在**下一轮明确范围后**开展App冻结基线回放及少量、标明先导性质的App↔Browser关系诊断；本批不自动并入旧E1分母，不获得正式train/dev/test或泛化评价资格。本轮 **0训练、0新增采集、0检测器评分**，未执行E1、B2、E2；无自动提交或推送。

## 本地复现

从实际主仓根目录运行（Python 3.10+，标准库；无需网络、ADB、Node采集runner或HMAC密钥）：

```sh
python3 -B deliverables/browser67_pilot_intake_v1/intake.py run
python3 -B deliverables/browser67_pilot_intake_v1/intake.py summarize
```

第一条确认本地排除、核验双包、复用/首次解压原件、运行冻结核验和自测试、生成v16/v2配置、调用两个主仓builder、逐成员比较并运行必要测试；每次生成新的私有run。第二条只读取最近一次验收保存结果并重写脱敏摘要/本报告，**不代表重新核验当前输入**。也可指定 `--run-id` 选择私有run；已有run不覆盖。

本次私有run引用：`.private/browser67_pilot_20261004/runs/b1_20261006_final`。`.private/browser67_pilot_20261004/originals/`保留两个首次解压树；`latest_run.json`记录最近验收；run内含verification、自测试、路径映射、本机配置、paired/app-only/quarantine、sample_index、QC、目录/来源清单、阶段去向、逐成员比对、字段质量侧表、readiness和测试日志。本机原件保留在被本地忽略的私有目录；后续获授权的证据公开副本见下方说明。

验证：本次接入测试 **14/14**、现有快照/准入回归 **18/18**，均无跳过。接入测试包含真实材料的8项归档自测试。无私有证据的其他检出环境会显式跳过真实材料测试，不视为真实验收通过。旧模型、历史结果及子模块指针未修改。

## 后续授权的证据公开

用户于2026-10-06明确授权提交有用证据，排除凭据和两个ZIP。现提供488个测量归档文件的原字节副本、13个B1源码参考文件和主仓验收留档。详见[EVIDENCE_PUBLICATION.md](EVIDENCE_PUBLICATION.md)与[公开证据复核结果](PUBLIC_REVIEW.json)。

远端无需ZIP或本机私有目录，运行：

```sh
python3 -B deliverables/browser67_pilot_intake_v1/review_evidence.py verify
```

原B1结果和正式准入边界保持不变；本节更新的是公开范围。
