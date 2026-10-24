# Clean ZIP rebuild check

**PASS.** The review-bundle snapshot rebuilt from a fresh directory with default migration enabled. It produces **8 main-text pages / 10 total pages**, and all 10 pages exactly match the stable v3 PDF by extracted text and by Poppler 120-dpi RGB pixels.

## Tested bundle

- Original bundle path: `/workspace/scratch/fff1267c1d19/output/pdf/HybridGuard_LaTeX_v1.zip`
- Tested snapshot: `/tmp/hybridguard-v3-rebuild-ixbev09o/tested_bundle.zip`
- `tested_bundle_sha256`: `7b06ad13925d39334b67f7a04f1695ec49e15c4692aa47e20652486670455c60`
- Fresh unpacked project: `/tmp/hybridguard-v3-rebuild-ixbev09o/unpacked`
- ZIP members: **110**; manifest entries verified: **109**. The manifest accounts for every member except itself. All member SHA-256 values and byte sizes match.
- No pre-existing `build` directory was present.

This is the hash of the tested review snapshot. It is not presented as the final ZIP hash: QA and review reports will be added before the final repackaging. The JSON records all **59 compiler/migration input hashes** so the final bundle can be compared without another compilation.

## Build command and environment

```sh
TEXMFHOME=/workspace/scratch/fff1267c1d19/tmp/texmf \
TEXMFCONFIG=/workspace/scratch/fff1267c1d19/tmp/texmf-config \
TEXMFVAR=/workspace/scratch/fff1267c1d19/tmp/texmf-var \
python3 source/build_pdf.py --variant matrix
```

The command ran in the fresh unpacked project and exited **0**. The default migration ran; `--no-migrate` was not used. All 59 recorded input hashes remain identical after migration, confirming that the selected table-layout transformations are idempotent. They also match the current stable v3 source.

## Comparison with the stable PDF

| Check | Result |
|---|---|
| Main-text end marker | Page 8 |
| Total pages | 10 |
| References end / Appendix A starts | Page 9 |
| Appendix end | Page 10 |
| Bibliography entries | 15 |
| Extracted page text | 10/10 exact matches |
| Poppler RGB pixels at 120 dpi | 10/10 exact matches |
| Compile errors | 0 |
| Undefined references/citations | 0 |
| Overfull boxes | 0 |
| Rerun warnings | 0 |

- Stable PDF SHA-256: `bd00d76b84fb1da0a9c04c88a82a9113fc74377cf0e83e4380480e6f588f99dc`
- Rebuilt PDF SHA-256: `b7442f34e370a883426574e917eeb38fe27c98cb9f3cf0caba2a928a0588b820`

PDF byte hashes differ; byte identity is not the acceptance criterion because metadata and document IDs may vary between builds. The full-text and all-page pixel comparisons are exact. Per-page pixel hashes are included in the JSON.

The existing acmart reference-format warning remains, along with 9 underfull hbox and 9 underfull vbox diagnostics. They do not change the rendered output. No v3 compilation source or stable build output was changed during this check; the fresh build and its rendered pages remain in the temporary verification workspace.
