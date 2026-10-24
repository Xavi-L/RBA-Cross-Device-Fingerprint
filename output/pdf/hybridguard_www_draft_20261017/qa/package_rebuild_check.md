# 源码包独立重编核验

**结果：PASS。** 在全新的临时目录解包，执行默认 Markdown 迁移与 matrix 编译，所得论文为主文 8 页、总计 10 页。10 页的提取文本逐字节相同，120 dpi RGB 渲染像素逐页相同。

## 受测快照

- 测试 ZIP SHA-256：`b3ec96471b2ecd7aa80ae43ada40449a86dd9d5f47ca827091afdd5d2470610d`
- 参考 PDF SHA-256：`82fb37b0970666015928762e7c6913621474f28b80dab32ce014eb74274cd72e`
- 重编 PDF SHA-256：`f1a53def40b0488c42b085f2eaaebbb8c703305429d9f66b7ab9c0ae4d60ef2b`
- 新解包目录：`/tmp/hybridguard_v4_package_rebuild_2yrifbc4/unpacked`
- ZIP 共 126 个文件；manifest 覆盖其余 125 个文件，全部大小与哈希通过核对。
- 解包目录原先没有 build 缓存；执行 `python3 source/build_pdf.py --variant matrix`，未指定 `--no-migrate`。
- 本次重编使用正常默认迁移；没有修改或替换源码、表格、正文或编译脚本。

本报告绑定上面的测试快照。后续将报告补入 ZIP 会改变 ZIP 整体哈希；最终包应保留本报告列出的全部实际编译与迁移输入哈希。报告生成脚本、打包脚本以及 QA/reviews 不属于这份输入清单。

## 版面和内容一致性

| 核验项 | 结果 |
| --- | --- |
| 编译退出码 | 0 |
| 主文结束 / 参考文献结束 / 附录结束 | 第 8 / 9 / 10 页 |
| 总页数 | 10 |
| 参考文献条目 | 15 |
| 10 页 `pdftotext -layout -enc UTF-8` 输出 | 每页全部字节相同，含空白 |
| 10 页 `pdftoppm -r 120 -png` 输出 | 解码后 RGB 像素及尺寸每页相同 |
| 页面像素尺寸 | 每页 1020 × 1320 |
| Overfull / 未定义引用 / 编译错误 / 待重跑警告 | 均为 0 |
| 实际包内编译与迁移输入 | 48 个，全部迁移前后不变且与 v4 相同 |

PDF 文件字节哈希可随重编元数据和标识变化；本次验收比较了每页的完整提取文本和实际渲染像素，不以二进制 PDF 字节相同作为要求。

保留的模板警告为 `printacmref=false` 引起的 ACM reference-format 提示；最终日志另有 8 个 underfull hbox、10 个 underfull vbox 提示。未引入 overfull 或未定义引用。

### 逐页结果

| 页 | 文本一致 | RGB 像素一致 | 尺寸 |
| ---: | --- | --- | --- |
| 1 | 是 | 是 | 1020 × 1320 |
| 2 | 是 | 是 | 1020 × 1320 |
| 3 | 是 | 是 | 1020 × 1320 |
| 4 | 是 | 是 | 1020 × 1320 |
| 5 | 是 | 是 | 1020 × 1320 |
| 6 | 是 | 是 | 1020 × 1320 |
| 7 | 是 | 是 | 1020 × 1320 |
| 8 | 是 | 是 | 1020 × 1320 |
| 9 | 是 | 是 | 1020 × 1320 |
| 10 | 是 | 是 | 1020 × 1320 |

逐页文本 SHA-256 和 RGB 像素 SHA-256 均保存在同名 JSON。

## 实际输入清单与 SHA-256

清单来自新构建的 `.fls` 记录、BibTeX 输入，以及默认迁移脚本实际读取的路径和九份冻结资产哈希检查。`table_visuals.tex` 已明确纳入。未使用的备用 Table 3、补充聚合 Markdown、CSV、报告及打包脚本不误列为本次构建输入。外部 TeX 安装文件以工具版本及环境记录，不混入包内输入清单。

| 相对路径 | SHA-256 |
| --- | --- |
| `ACM-Reference-Format.bst` | `dd98deea9118229dcd97904e34ebe77d6a3df1427dbd32f132200ccf785039b7` |
| `acmart.cls` | `625c4a4e0ae91fa5cf701170531cd8a31ecb0b2ffb2247d26ebd04de16ce7966` |
| `baseline_source/abstract_verbatim.txt` | `db2a9d1a54fd6ca7000521a302b5d7e0524fb7fcea716e402bf3206f243d074e` |
| `baseline_source/main.tex` | `ca61514177c2fe8264161df0e5a01b7a50092a5d79c437a76fa53f47339511b8` |
| `figures/FROZEN.json` | `e3c5765a0a1d2c3e2ec7e164aac0890bf67fa023278d0fdd79ceefac57c46d96` |
| `figures/HybridGuard_Fig1_surfaces_v2.pdf` | `3805d0b554613b5ec1848332d0f9d24e5c57862d99a38468fcf7cff50cf9aba7` |
| `figures/HybridGuard_Fig1_surfaces_v2.png` | `1668b3c28c1b9a072ce6c2b6754529e546892c55024084b93b4663b477eb4f18` |
| `figures/HybridGuard_Fig1_surfaces_v2.svg` | `1902dbfd175a8c43a9ede95cf8be3b5f2336fca80007f0e7e022963bb9c7c43d` |
| `figures/HybridGuard_Fig2_pipeline_v2.pdf` | `c336ac1d49ee31dfb32d0804eb41276259fb0651364a6e6c6bd21fe6dea11292` |
| `figures/HybridGuard_Fig2_pipeline_v2.png` | `abce5b952d3c4d8bcb694c870f984c26a458ca67c1b40e2605ff9fa6aca65464` |
| `figures/HybridGuard_Fig2_pipeline_v2.svg` | `0d8649f97ddb8b708bc5578d0fb1ba54f2fa1f05297ccba7d77e5be0b2ff26c6` |
| `figures/HybridGuard_Fig3_mechanisms_v2.pdf` | `da1f63419b7cfe9c32b2df7e2eb458086324872ecb60ce1a7d9b583a2bf4bafc` |
| `figures/HybridGuard_Fig3_mechanisms_v2.png` | `7a0a399ecd8d7dafab6e4526549832ccca983144f567a17671523676b84e6182` |
| `figures/HybridGuard_Fig3_mechanisms_v2.svg` | `531e2ef097495bd2dd9e4943f3eb30ed89fbafff163dee18447a1d6a13ceecf7` |
| `floats/figure_01.tex` | `91cedddfea3227feefd9e7336ea0bf77b667ba89c1a502efc380451fb83ca2f3` |
| `floats/figure_02.tex` | `ab899f5046393e22065d3183a90107609eff189b772fb300eefdc1f3ad5b3efe` |
| `floats/figure_03.tex` | `e63df10845d2f7cc15a6e7e9ea30c125a45c0650614136ee3c9f1a6aad5194fd` |
| `frontmatter.tex` | `666f3d06eeafc53d1595741e93d899d35a2286296bd2b38425c9f2798f7ca977` |
| `input_markdown/sections/00_abstract.md` | `45245ded7f77fd520f934d08e9204edffba883c881eccd0cc1594b77bbe0f8bd` |
| `input_markdown/sections/01_introduction.md` | `e773d45195456c574e68be277cb8887ff8012468a848c3d708b63635f6e9a439` |
| `input_markdown/sections/02_background_and_scope.md` | `636fe4f2f6a7ed86862730520883b6916d71793ac2895f7fd765e145eb8bd5fc` |
| `input_markdown/sections/03_method.md` | `78de8eb7cbf018ab04fa09b280f98208b8244f335d961320b6f10873e1f00f30` |
| `input_markdown/sections/04_evaluation_protocol.md` | `4c61c56fd0fb03fa9f226c551f4802fbb43ee6c1c27c4d1e57d74ff8d4cbf05b` |
| `input_markdown/sections/05_results.md` | `2afb28636646bcbc5f36a5f781ea982727989292204c948b3493df703f3a5994` |
| `input_markdown/sections/06_discussion.md` | `c6953ba1da2ede045999383d472b993d676d53633a307aa0de1528030620baa9` |
| `input_markdown/sections/07_conclusion.md` | `4b61012971783d53510c3ab2f763b7ab950695ea4cf8e02f6766d3352d3eb6eb` |
| `input_markdown/supplement/00_Appendix_English.md` | `4d1e45594c5c7f505b2bcc32538f720c6b91f1d9e19584ae3bbaff4c695257c1` |
| `main.tex` | `bb5a40652d104c8996888ddc1080dbe9249905baa771e855183a1802fbe879f7` |
| `main_matrix.tex` | `51338dd9f6239061fc944219f1e401f983932901986c659a8fab1ce121df9521` |
| `notes/abstract_lock.json` | `fb0b3ab175fd60f2568230481876fb43289e00877c7c76945c33c96073d7034e` |
| `references.bib` | `bd48ede643f451413e3e24808819bea10a399c7943e2c6637649cbf470692b8d` |
| `sections/01_introduction.tex` | `151c4a01270d5195a50d45118277de818f69514d5489ae1196dd01fa775bbc9d` |
| `sections/02_background_and_scope.tex` | `52b36b1b4b0d3009c9dfbc850dfba493b8e184365a5d3a7e556ea8d42b39f269` |
| `sections/03_method.tex` | `9727f4e6e4038a5f12121df339bdfc8a5f504ec9e742a8e7d924749eaab24d70` |
| `sections/04_evaluation_protocol.tex` | `3c3aa24498b6a181399988c391880afa269e28c2a7043811d3abba2077c386c3` |
| `sections/05_results.tex` | `5e0682fec3a117f6f7a4e2f98d99d6db9cb0373d9bfb4510cbed518683484134` |
| `sections/06_discussion.tex` | `521a7d21f4b59964e3dc0a54b17b63034768a77728c928b730d68d1b33cb0a15` |
| `sections/07_conclusion.tex` | `8f88ffb7e2de42062df3aca5a614d92a3a8d2e8db31d0f895674a6d59723eef0` |
| `sections/08_appendix.tex` | `b03dbe2fd1263a9b77a2d67dc1c7fe165cd7401364fd6dee36144c93491c7ce1` |
| `source/build_pdf.py` | `a233a17d4e12c153ca807118d5eceab4ec9d8d7f52ec189c4ba43aadd18cb165` |
| `source/migrate_manuscript.py` | `50e00d4b81784f6a867d59cd931a2f6956c8678ae554a982220a5a4f9a7d9df3` |
| `table_visuals.tex` | `bde0e9ce2c48b1aee7154f431330274bf342a7ddb791c73f185b1f676044ccd0` |
| `tables/table_01.tex` | `32f94b588fdf08413fad0fb647e76d31830ad2ff84fd58921eecd53daff9de46` |
| `tables/table_02.tex` | `dff328fa306a4c8fde18ad1fbe9f9a41b8e291db170588a29cdb4153f32f0ce2` |
| `tables/table_03_matrix.tex` | `785e4828194872e897161d45ab032a7d8ea6f8264adf0d99abd225a5bbb47e95` |
| `tables/table_04.tex` | `22c5a5e3c8d6465911cbcd9ff6c9ea8def795f9ce102f9cc5641bd2e5774c30a` |
| `tables/table_05.tex` | `43bcd65d8dba4e866517ddd4680cf7dc34a2290f3b2d8f459f7db3baa22a5346` |
| `tables/table_06.tex` | `9d39de3c50353f1cc73cc2ef6039c86440601b6b57e9572590e2a7b2eb911edf` |

以上每个哈希均已核对：测试 ZIP 解包后 = 默认迁移与编译后 = 当前 v4 源目录。

## 重编环境

- `TEXMFHOME=/workspace/scratch/fff1267c1d19/tmp/texmf`
- `TEXMFCONFIG=/workspace/scratch/fff1267c1d19/tmp/texmf-config`
- `TEXMFVAR=/workspace/scratch/fff1267c1d19/tmp/texmf-var`
- python: `Python 3.12.14`
- pandoc: `pandoc 3.1.3`
- pdfLaTeX: `pdfTeX 3.141592653-2.6-1.40.25 (TeX Live 2023/Debian)`
- BibTeX: `BibTeX 0.99d (TeX Live 2023/Debian)`
- latexmk: `Latexmk, John Collins, 31 Jan. 2024. Version 4.83`
- pdftoppm: `pdftoppm version 26.05.0`
- pdftotext: `pdftotext version 24.02.0`

本任务仅回写 `qa/package_rebuild_check.md` 和 `qa/package_rebuild_check.json`。所有独立重编缓存、提取文本、逐页图像及测试 ZIP 快照位于临时核验目录。
