# 最终源码包独立重编译检查

日期：2026-10-22。结论：**PASS**。

## 检查方式

把待交付 ZIP 解压到全新临时目录 `/tmp/hybridguard-v2-rebuild-t5lezmua/project`，核验 manifest 后，显式使用已安装的临时 TeX 字体树，执行：

```bash
python3 source/build_pdf.py --variant matrix
```

未使用 `--no-migrate`，因此本检查同时覆盖 Markdown 重新生成、矩阵版浮动体调度、BibTeX 和 PDF 编译。编译退出码为 0。

## 结果

| 项目 | 结果 |
|---|---|
| ZIP 成员 | 97 个 |
| manifest | 96 个文件的字节数和 SHA-256 全部一致 |
| 页数 | 全文 10 页，主文到第 8 页结束 |
| 文本比较 | 10/10 页与版式微调后的稳定 PDF 逐页一致 |
| 栅格比较 | 10/10 页以 1.5 倍渲染后逐像素一致 |
| 参考文献 | 15 条 |
| 未解析引用、缺字、编译错误 | 0 |
| 构建输入 | 已在 JSON 中记录 62 个输入哈希 |

既有 `printacmref=false` 的 ACM 元数据提示和末页 1.499pt overfull vbox 与稳定版一致，没有新增可见问题。PDF 生成时间等元数据可能导致二进制哈希变化；本检查以逐页文本和栅格相同验证交付内容。

## 版本绑定

- `tested_bundle_sha256`：`2227ac97cdd1dbc84c64a9bfb13c2e27fcbbab2a2bcff19c90222fa441a241ee`。
- 稳定版 PDF SHA-256：`4d49d439f85e67b11ef261b346caeadf4b90d7cb42ce45460d8fe16874e6b080`。
- 临时重编译 PDF SHA-256：`d6a2fa5d712ca5ae6d7d5fb5b7924f05405b0d000962aa0cea1e6f92314d0a3a`。

`tested_bundle_sha256` 仅指加入这份检查报告之前的被测 ZIP，不是最终重打包后的 ZIP 哈希。之后可只加入本报告、更新 manifest 并重新打包；编译输入无需改变或再次编译。

所有解压、迁移、编译和栅格比较均在新临时目录中完成。原 v2 工程仅新增本 Markdown 和对应 JSON 检查报告，源码及 build 中的 PDF 均未修改。
