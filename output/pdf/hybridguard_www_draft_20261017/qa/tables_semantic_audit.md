# 表格视觉化语义与计数审查

**最终结论：PASS。** 六表的视觉改造未改变实验计数、统计单位、状态定义或结论边界，已核对最终 PDF 的实际呈现。没有发现需要退回修改的语义、数字或冻结输入问题。

## 审查绑定的版本

- 基线：`hybridguard_latex_v3`。
- 最终候选：`hybridguard_latex_v4/build/matrix/HybridGuard_layout_v1_matrix.pdf`。
- SHA-256：`82fb37b0970666015928762e7c6913621474f28b80dab32ce014eb74274cd72e`。
- 主文 8 页，总计 10 页。
- 本审查只写本 Markdown 和同名 JSON；没有改正文、表格、数据或图，没有编译，没有重跑实验或扩大事实研究。

## 六表的最终检查

| 表 | PDF 页 | 结论 | 核验内容 |
| --- | ---: | --- | --- |
| Table 1 | 3 | PASS | 六行文献及原引用均保留；六个证据类型徽记有完整定义，表达研究焦点而非能力缺失或优越性。Optional Browser、explicit domains、适用性/证据可用性成本、normal alarms 与 unknown outcomes 均明确。主行紧凑且无截断。 |
| Table 2 | 5 | PASS | 八组材料的计数全部不变，Δ/N 的含义明确且单位仍是 record positions，而非独立设备。训练/开发暴露、非新盲测历史保留、专项边界和配对材料的开发使用均保留。 |
| Table 3 | 6 | PASS | 30 个方法格逐格显示；独立解析最终 PDF 后，每格检出数、非零差值、组权重均匹配 CSV。✓/半圆/×只编码本次测试修改的全/部分/零检出。 |
| Table 4 | 6 | PASS | 七项原检查及全部检测/正常报警分数保留；正常报警使用单独三角符号。六次正常系统/布局变化的归属、六次 no-effect memory 排除、U/FAILED 为零及 Host bound standalone 均可见。 |
| Table 5 | 7 | PASS | 确为单栏。四组 Integrated App / No-cap 三状态计数及 N=144/117 不变；01/02 并列而非合并。F=definite no alert，U=unknown，全深灰条明确表示正常记录全报警。 |
| Table 6 | 8 | PASS | 原 N 与 T 计数不变，App 短表头有定义；normal alarms 行单独分隔且没有检出符号。开发使用历史、U/FAILED 为零，以及修改行/正常行的不同 T 含义保留。 |

### 基准与统计单位

原始 14 个 recipe 各有 9 个有效修改位置，完整六方法状态向量相同的分组权重仍为 1、1、2、8、2。六方法总检出分别为 **105、108、96、96、105、72 / 126**，漏检为 **21、18、30、30、21、54**；全部 controlled-normal 报警仍为 **0/252**。U、FAILED、EMPTY_MODEL 为零的范围、rule 的 saved RETENTION、tree 的 saved FITTED、独立 refit 和 no-cap 额外三次 screen 检出对应的正常报警成本均保留。

Table 2 的数值依次为 Controlled App **126/252**，MTC discovery/history-development/history-reserved **630/144/117** 个正常位置，Memory **18/48**，Timezone **6/30**，Geometry **6/66**，Paired App–Browser **14/46**。配对总数仍为 **60 = pilot 18 + matched 42**；三个配置没有被当成三份独立材料累加。历史材料的 01/02 也没有合并分母。

### 比例条和符号语义

共享条形宏使用 T/(T+F+U)、F/(T+F+U)、U/(T+F+U)，没有为小段设置人为最小宽度。进一步读取最终 PDF 的矢量填充矩形，八条三状态条的实际宽度比例均与计数匹配，误差小于 0.00002 的 PDF 浮点容差。T=1 的小段未被放大；T=0、F=0、U=0 的段宽保持为零。深灰不是“成功”色，表注明确了正常记录上的报警含义。

T1 的证据类型键没有把文献“未讨论”改写成“无能力”。结果表的 ✓/半圆/× 均局限于本轮所测试修改；正常材料没有被标成普遍安全。F 不等于确认正常，U 没有并入 F，失败零也未被更名或遗漏。

## 冻结输入和批准段落

- **19 个输入 Markdown 全部与 v3 字节一致**，文件集合相同。
- **9 个 CSV 全部与 v3 字节一致**。
- **9 个冻结图资产全部与 v3 及 FROZEN.json 的 SHA-256 一致**。
- 摘要规范原文、摘要 Markdown、批准改动记录、FROZEN.json、图注目录和 references.bib 均未改变。
- 最终 PDF 的摘要提取文本与 v3 **逐字符相同**。规范摘要 SHA-256 为 `db2a9d1a54fd6ca7000521a302b5d7e0524fb7fcea716e402bf3206f243d074e`；摘要 Markdown SHA-256 为 `45245ded7f77fd520f934d08e9204edffba883c881eccd0cc1594b77bbe0f8bd`。
- **A1、A2** 在第 4 页各完整出现一次；**B1** 在第 3 页完整出现一次；**A3 两段**在第 9 页各完整出现一次。PDF 检查只忽略换行、连字符与数学字体差异；源文件同时通过严格字节锁定。

## 图注、引用与版面

三个 figure caption 的源文字与基线一致，其完整文字分别在 PDF 第 **3、4、7** 页可检索。文献条目保持 **15** 条；references.bib、编译后的 BBL、citation key 出现次数和引用编号映射均与 v3 一致。六表及三图编号均解析正常。最终日志未发现 undefined reference/citation、重复标签、overfull 或缺字警告。

已查看最终渲染第 **3、5、6、7、8** 页。Table 3 位于第 6 页，Figure 3 位于第 7 页，中间保留 Results 正文；Table 5 在第 7 页右侧单栏，其全部数字、限定和图例可见。未见裁切、重叠或方法列归属不清。

## 审查边界

本报告确认新版呈现与既有稿件和保存结果一致，不把呈现一致性当成新的实验复现或独立验证。完整哈希、每格数值、比例条宽度和逐项判定保存在 `tables_semantic_audit.json`。
