# Figure captions and alternative text

## English caption

**HybridGuard rule construction and current-record evaluation.** (a) Normal and controlled-modification development records support candidate admission, sparse selection, and retention under normal-alarm and definite-output coverage constraints. Candidate relations are illustrated by a Native-based memory upper bound, effective timezone agreement, and within-Web viewport relations. (b) Saved checks evaluate bound current App records. The optional C1 configuration adds a comparison of linked App Web and external Browser offsets. Memory and timezone panels show illustrative values, not experimental results. Outputs retain alert, no alert, and unknown; an empty rule set and required execution or association failures remain separate. Logos and displayed rule sets are schematic. No alert does not establish authenticity or safety.

## 中文图注

**HybridGuard 的规则构建与当前记录评估。**（a）利用正常与受控修改的开发记录，在正常报警和确定输出覆盖约束下，完成候选准入、稀疏选择及保留补足。图中以 Native 参照的内存上限、有效时区偏移一致性及同一网页内部的视口关系示意候选检查。（b）保存的检查作用于关联好的当前 App 记录；可选 C1 配置额外比较有效关联的 App Web 与独立 Browser 的时区偏移。内存与时区面板中的数值仅用于说明机制，不代表实验结果。系统保留报警、未报警与无法判断三类结果，空规则集以及必要的执行或关联失败分别处理。品牌标识与规则组合均为示意；未报警不构成真实性或安全性证明。

## Concise alternative text — English

Two-band HybridGuard diagram. Development records feed candidate filtering, selection, refinement, and saved checks. Current App records and optional linked Browser records feed memory and timezone checks. A 3 GiB device gives a 4 GiB memory limit; Web memory of 8 GiB exceeds it. Matching and mismatching timezone examples lead to results: alert, no alert, or cannot tell, with separate no-checks and check-failed states.

## 简短替代文本 — 中文

上下两层的 HybridGuard 流程图。上层从开发记录中筛选、精简、补足并保存检查；下层对当前 App 记录及可选的关联浏览器记录运行内存和时区检查。设备内存 3 GiB 对应 4 GiB 上限，网页报告 8 GiB 表示超限。时区示例展示匹配与不匹配。结果包括报警、未报警、无法判断，并单列无检查与检查失败。

## Terminology for editors

| Figure wording | Meaning to preserve |
| --- | --- |
| Memory limit | A Native-derived upper envelope for Web-reported memory. |
| Time zone | Agreement of effective offsets under each check's applicability rules. |
| Page size | Relations within the same Web observation; not Host–Web geometry. |
| Browser check / Optional | Optional C1 comparison of validly linked App Web and external Browser offsets. |
| No alert | All selected checks are evaluable and return `F`; not a claim of authenticity or safety. |
| Cannot tell | Unresolved evaluation (`U`), distinct from a required execution or association failure. |

Status precedence is **No checks → Check failed → Alert → No alert → Cannot tell**. This denotes decision priority, not a sequence through which every record passes.
