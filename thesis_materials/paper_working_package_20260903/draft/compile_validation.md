# ACM 草稿编译与版式验证记录

## 主草稿来源

本工作包以此前完成的“Full Prose”版本为主：所有提纲式章节已经改写为连续英文正文，图片和最终结果表暂不处理。为便于在 GitHub 中保存和重新导入 Overleaf，归档版本将所有 section 和 appendix 内联到单一 `hybridguard_draft.tex`，并保留独立 `references.bib`。

## 原完整工程验证

完整模板依赖版本曾使用 `latexmk` 和 Biber 成功编译，得到 16 页 review PDF。验证结果包括：

- 未解析 citation：0；
- 未定义 cross-reference：0；
- LaTeX/package error：0；
- overfull horizontal box：0；
- overfull vertical box：0；
- 正文 TODO：0；
- 全部页面均完成渲染检查；
- PDF 可打开，未加密，不是扫描件；
- 标题、摘要、双栏正文、表格、参考文献和附录未观察到裁切、重叠或乱码。

## 仓库中的精简 ZIP

`HybridGuard_ACM_Draft_Flattened_Overleaf_20260903.zip` 仅包含：

- `hybridguard_draft.tex`；
- `references.bib`；
- `README.md`。

它不包含：

- 编译 PDF；
- `.aux`、`.bbl`、`.bcf`、`.blg`、`.fdb_latexmk`、`.fls`、`.log`、`.out`、`.run.xml` 等构建产物；
- `acmart.cls`；
- `ACM-Reference-Format.bst`。

Overleaf/TeX Live 已提供 ACM 类文件和 bibliography style，因此这些文件无需在项目 ZIP 中重复保存。将 ZIP 导入 Overleaf 后，把 `hybridguard_draft.tex` 设置为 Main document。

## 完整性信息

- 文件：`HybridGuard_ACM_Draft_Flattened_Overleaf_20260903.zip`
- 大小：37,482 bytes
- SHA-256：`9940c0b0f2d1dd786e294a82513f5977dd086212c5ab01d2602ac533b6404744`
- ZIP 内未保留外部 `\\input{...}` 依赖；章节和附录均已内联。

## 当前研究边界

编译通过只证明 LaTeX 工程和版式可用，不提升实验结论等级。草稿仍遵循：当前受控攻击验证对象为 App177；协议为 `baseline -> attack_active`；51/69 和 33/69 是关系转换计数而非 recall；Browser67/paired244 检测增量属于未来实验；历史 ML/LLM 内容为暂时保留的预验证材料。
