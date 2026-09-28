# 远端审核原始文件

主仓库已保存输入核查代码、逐记录清单及其直接引用的研究材料。162条监督记录的原始采集来源位于已有子仓库 `hybridguard-browser-fingerprint-research/`，固定提交为 `9698e8dfeb450094d99c46bdcff15283c995e3b3`。

本次补齐主仓库原先缺失的 `.gitmodules` 地址登记，保留既有子仓库提交指针。远端审核时可递归克隆，或在已有克隆中执行：

```sh
git submodule update --init -- hybridguard-browser-fingerprint-research
```

源码与原始文件可直接在[固定来源提交](https://github.com/computersciencefreshmen/hybridguard-browser-fingerprint-research/tree/9698e8dfeb450094d99c46bdcff15283c995e3b3)查看。

本轮162条接入核查需要的子仓库文件共38项，约4.1 MB：18个 `raw_payloads.jsonl`、18个 `paired_triplet_run.json`、一份 release lock 与一份控制补丁。这38项均已保存在上述固定提交。具体文件和行/session引用分别见 `INPUT_MANIFEST.jsonl` 与 `SOURCE_BINDINGS.json`，无需用最新来源分支替换固定提交。

`REPORT.md`、`SUMMARY.json`、`TEST_RESULTS.json` 中的状态和“尚未提交”等文字仍表示各自生成时的快照；此次发布没有改写这些历史记录，也没有执行新的候选求值、训练或采集。
