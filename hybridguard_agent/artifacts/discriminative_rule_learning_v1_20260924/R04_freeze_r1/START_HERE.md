# R04-R1 启动与审查入口

本目录是针对提交 `51726c0af36f9bcb1fda7647788be2f945c4f44d` 的独立工程修订。先读 `STEP_REPORT.md`、`CHANGE_RECORD.json` 和 `VALIDATION.json`。原 `R04_freeze` 及其验收、日志、模型和错误 OOF 例保持原样。

运行资源以本目录的 `FREEZE_MANIFEST.json` 和 `RESOURCE_MANIFEST.json` 为准；R01 研究协议 digest 没有变化。`AUTHORIZATION.json` 没有真实 fit 授权。未来正式作业必须在外部验收和另行明确授权后，绑定本修订的摘要；不能复用旧 R04 的批准摘要或修改模型 JSON/时间戳。

从工作区复核已冻结修订包，只运行内置合成套件并写入新临时目录：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 hybridguard_agent/scripts/validate_rule_learning_r04.py --freeze hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R04_freeze_r1
```

入口会复制快照，使用包内 Python 3.12.14、HiGHS 1.12.0 和 NumPy 2.3.5，从空 cwd 的新进程执行。它不回写本目录或旧 R04，也不授予 R05/R07 真实拟合权限。平台仍限匹配的 macOS 15.7 arm64；没有求解器或主工作区回退。

仅为复现本次打包过程，可使用 `prepare_rule_learning_r04_r1.py --out <不存在的新目录>`。该构建器复用旧 R04 的冻结文件与依赖，不重建 R01/R02，不接受覆盖已有目录。正式交付已存在，不能在其上再次构建。

重点记录：

- `isolated_validation/FOCUSED_TESTS.txt`：全部 56 项合成验证。
- `isolated_validation/budget_count/OOF.json`：有回执但没有模型时的修正结果。
- `isolated_validation/R1_RECEIPT_WITHOUT_MODEL.json`：预算、失败、超时及无复用来源的数量未知算例。
- `isolated_validation/R1_KNOWN_MODEL_MISSING_PREDICTION.json`：已知模型缺预测仍保留完整单元分母。
- `isolated_validation/R1_SINGLE_SURFACE_VALIDATION.json`：三种表面的精确允许 ID、编码 ID 及排除项。
- `STAGE_METRIC_PRESERVATION.json`：阶段级指标的总体/分层对账。
- `BINDING_REVIEW.json`、`ALGORITHM_INVARIANCE.json`：正式作业和算法不变量。

下一步是外部验收 R04-R1；本目录不自动启动 R05，不自动提交或推送。
