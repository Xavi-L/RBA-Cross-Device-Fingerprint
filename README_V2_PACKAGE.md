# HybridGuard V2 路线图资料包

制定日期：2026-09-25。仓库事实基线：`5aabe2d609ab6ab737a7a057d4b9260479385fad`。

**这是可放入仓库的文档ZIP，不是已经推送到远端的提交。没有执行V2训练或预测，也没有制作R10图表。**

## 包内文件

| 路径 | 用途 |
|---|---|
| `V2_DEVELOPMENT_ROADMAP.md` | 主开发路线图：证据、假设、候选表示、诊断、实验设计、三个检查点、论文边界与文献 |
| `deliverables/v2_development/EXECUTION_PLAN.md` | A/B/C阶段与轻量调度迁移 |
| `deliverables/v2_development/DEFAULT_DEV_CONTRACT.json` | 第一批拟议参数、数据角色、6次fit/600秒计算预算和范围 |
| `deliverables/v2_development/EXECUTION_STATUS.json` | 文档交付时的真实初始状态，尚未授权/执行实验 |
| `deliverables/v2_development/AGENT_START_PROMPT.md` | 发给agent的完整A阶段启动指令；发送后才授权第一批 |
| `deliverables/v2_development/SOURCE_REGISTER.json` | 固定提交的证据路径、一手文献入口与核查范围 |
| `deliverables/v2_development/research_references.bib` | 两篇核心方法/验证参考文献 |
| `V2_PACKAGE_MANIFEST.json` | 包内文件SHA-256与字节数，不是实验冻结清单 |

## 安装

将ZIP解压到临时位置，让agent按包内相对路径复制到仓库根目录。包内只含新增路径，不含V1主线、旧执行计划或旧状态的覆盖副本。同名文件已存在时先比较，不能直接覆盖后续V2工作。

然后发送`AGENT_START_PROMPT.md`中的指令。Agent会在V2-A开始时追加旧入口的路由提示、按原字节归档可变旧状态，再将当前调度指向V2。冻结目录始终只读。

本包中的代码/结果目录是计划路径，不代表那些程序或产物已经存在。`DEFAULT_DEV_CONTRACT.json`是开发批次规格，不是可直接交给V1 dispatcher的runnable job。

## 当前调度

R10后置；V1保持基线。第一批先做漏检/参照诊断、保存结果的事后组合分析，再开发S_FLAT/J0最小适配并在获授权后进行最多6次真实拟合。A结束停一次；B/C不自动授权。

独立确认、采集、攻击工具、付费服务、公开数据及Git提交/推送都不是文档创建自动授予的权限。

## 校验

可用任意SHA-256工具核对`V2_PACKAGE_MANIFEST.json`。源证据文件保留在原仓库，没有复制原始指纹、执行日志、论文全文、依赖包或字体文件。

本包只对JSON格式、内部文件引用、配套参数、文件清单和ZIP字节一致性进行静态检查；没有独立复跑V1实验或实现V2学习器。
