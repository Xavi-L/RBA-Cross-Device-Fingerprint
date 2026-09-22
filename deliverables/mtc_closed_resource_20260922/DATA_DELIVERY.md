# MTC paired244 数据交付

2026-09-23，用户明确要求把已采集的 paired244 数据随本轮代码一并提交推送。交付来源仅限已经冻结的本次百度 MTC 数据，不含 Testin 或后端根目录的历史采集。历史报告中的“仅本地／被 Git 忽略”描述保留当时状态，以本页交付范围为准。

## 数据入口

| 目录 | 内容 | 文件数 |
|---|---|---:|
| [MTC 最终原始冻结](../../backend_server/collection_backups/mtc_final_20260922/) | 10 个源文件，包含 App／Browser raw、配对 provenance、回执、批次、事件、失败与 provisional 留存；以及冻结清单、统计和采集契约副本 | 22 |
| [P1 QC 快照](../../hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final/) | paired244、App-only、partial、重复记录、QC 和关联审计、字段契约、实现副本 | 19 |
| [P2 冻结分组](../../hybridguard_agent/artifacts/mtc_p2_frozen_20260922/) | 原有分组／切分／代表记录清单、任务准入和保留验证集锁；不新增保留集执行输入 | 15 |

这 56 个文件合计 251,934,296 字节，保留既有内容与目录位置。它们是同一批数据的原始、派生及索引层，不能把各层记录数相加当作独立样本量。根目录的本机 HMAC 密钥、环境凭据、其他采集批次、Android 构建产物和逐样本规则运行输出不在本次数据提交范围内。

另外提交 `artifacts/mtc_closed_resource_study_20260922/` 中目录重建必需的 4 份研究准入记录：`summary.json`、候选表达式快照、`discovery_selection_FREEZE.json` 和 `admitted_candidates.json`。它们是既有研究记录，不是新增采集或重新运行结果；使目录重建测试不再依赖未提交的本地文件。该目录的逐样本研究输出仍留在本地。

直接读取整理后的主视图：[paired_244.jsonl](../../hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final/paired_244.jsonl)。原始两端及关联依据位于最终冻结目录的 `sources/`。

## 数量与边界

- 后台完成配对 **1,029 条**，覆盖 **891 个厂商／型号／Android release 组合**。
- P1 `paired_244.jsonl` 为 **1,028 条**，仍覆盖 891 个组合；另 **1 条已配对记录**因 App 整层超时保留在 `partial.jsonl`。
- `partial.jsonl` 共 11 条，包含上述 1 条已配对和 10 条未配对；App-only 主视图另有 654 条，同 session 额外观测 6 条。失败、重复和 App-only 不冒充完整 paired244。
- 原始 App 归档 1,699 条、Browser 归档 1,029 条；全部留存用于复核分母与配对关系，没有为了提交删除不利记录。
- P2 发现／开发／保留验证代表分别为 630／144／117 条。数据交付不等于解除研究隔离：`reserved_validation_LOCK.json` 继续为 `LOCKED`，没有执行保留集规则评价。
- 数据仍为无独立攻击／正常事实标签的参考观测，推送不改变质控与评价边界。

冻结 manifest 中的绝对路径属于采集和构建时的来源记录，不改写为当前机器路径。其他机器需要重建时，应使用仓库脚本的显式目录参数和新的输出目录，保留这些原始 manifest、分组及锁定记录；不得覆盖既有快照或先查看保留集结果再调整规则。
