# B1 证据公开与远端审查

2026-10-06，用户在首次代码提交后明确授权将有用证据一并提交，排除API key等敏感凭据；两个ZIP不提交。本次扩展证据交付范围，不执行新采集、训练、检测器评分、E1、B2或E2。

## 提交内容

| 目录/文件 | 内容与身份 |
|---|---|
| `evidence_archive/` | 证据ZIP内全部488个文件的逐字节副本：原始App/Browser数据、receipt、pair、batch、18阶段控制日志与provenance、计划、冻结核验器、安装APK与源APK、冻结主仓源码/目录/manifest、原交付快照、facts/readiness、历史工程失败说明 |
| `source_reference/` | 源码ZIP中本批B1工具目录的13个文件，包含source_manifest、公开runner、核验器、测试、模板与说明；不混入其他实验或论文资料 |
| `local_acceptance/` | 已完成的本地主仓重建快照、完整sample_index、QC、逐成员比对、阶段去向、字段质量侧表、readiness、核验报告与测试日志；这是历史B1验收留档 |
| `PUBLICATION.json` | 488项原路径→提交路径映射、大小/摘要、凭据检查范围、派生路径转换说明与排除项 |
| `PUBLIC_REVIEW.json` | 对公开证据实际执行、不依赖ZIP的重建核验结果 |
| `PUBLICATION_VALIDATION.json` | 20/20相关测试及从Git暂存区独立检出、无ZIP/无私有目录复核通过的记录 |

测量证据文件内容**没有改写**。两个原`.git`身份文件仅改存于`evidence_archive/upstream_git_metadata/`，复核时恢复到临时输入树，仓库内不创建嵌套Git仓库；不对这两个元数据文件执行pull/reset，也不补造Git对象。目录中的历史Windows绝对路径属于冻结测量记录，由原核验器的路径兼容入口解释。

本地主仓派生留档只有3个文件含当前机器路径，发布副本已替换为`${EVIDENCE_ROOT}`、`${REVIEW_RUN}`或`${REPO_ROOT}`；具体文件列在`derived_path_transformations`。这些配置/元数据仅供阅读，引用的SHA字段仍表示当时原文件的身份，不能拿路径转换后的配置去冒充原配置字节。远端命令会重新生成本机配置并重建新输出。原始本机验收文件和首次解压原件保持不变。

原始归档中的“仅本地保存”“尚未外传”等文字描述归档形成时的状态；本文件记录用户后续授权公开的状态，二者不要混用。源码参考中的pilot_plan仍是中性模板，README的旧交付状态不覆盖已经存在的真实测量证据。

## 凭据处理

提交前对证据、B1源码参考和派生留档进行定向检查；已检查APK内部成员。未发现所查API/access-token格式或完整PEM私钥。源码中的私钥BEGIN标记是检测器/测试字符串，不是私钥材料；JSON中的HMAC key ID/source是标识与来源元数据，不是HMAC密钥。

HMAC私钥、keystore、Chrome用户配置、设备备份本来就不在输入包中，不提交。18个实验配对票据均为已过期的本地loopback记录，最后过期时间为2026-10-04T15:39:22Z；保留用于关联和事件顺序审查，不是账户API凭据。此检查有明确范围，不声称穷尽所有秘密格式，也没有重新执行HMAC签名验证。

两个ZIP、工作区其他实验/构建改动和本地Git状态噪声不在此次提交中。`.gitattributes`保留证据字节，避免Git换行转换破坏摘要链。

## 不依赖ZIP的复核

从主仓根目录运行：

```sh
python3 -B deliverables/browser67_pilot_intake_v1/review_evidence.py verify
```

默认在临时目录恢复输入并完成核验，打印汇总后清理临时工作副本。要保留输出，提供一个不存在的目录：

```sh
python3 -B deliverables/browser67_pilot_intake_v1/review_evidence.py verify --output /tmp/browser67-review
```

命令检查488个公开文件的身份和原487项清单，执行未改条件的归档核验与8项自测试，调用当前主仓snapshot/experiment-plan脚本，逐sample_id比较244项值、状态和完整来源索引。全程不读取两份ZIP、不依赖本机私有验收目录、不启动backend/Node采集runner/ADB或模型。

验收结果：18/18阶段通过、自测试8/8通过；18 paired244、0 App-only、0 quarantine；4,392项值、4,392项状态及完整索引一致。候选事实和原协议保持，train/development/test为0/0/0，structural_ready=false。整包ZIP的大小/SHA/CRC是首次本地接入的历史验收结论，远端没有ZIP时不冒称再次完成整包验证。

另已从Git暂存区把公开文件及主仓依赖检出到仓库外的临时目录，在不存在两个ZIP和本机私有验收目录的条件下再次运行复核，结果与`PUBLIC_REVIEW.json`完全一致。相关测试20/20通过、无跳过；这是本地模拟远端检出的验证，不声称已在另一台机器或GitHub CI上运行。

只读取已保存本地B1验收结果、更新摘要的旧`summarize`命令仍需原本机私有run；远端复核使用上面的`verify`命令。效果与恢复通过不代表检测率或跨设备泛化；最终消融仍暂停。
