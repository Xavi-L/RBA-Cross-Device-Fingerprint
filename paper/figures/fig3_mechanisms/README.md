# Figure 3 — Contextual integrity mechanisms (review v2)

This directory preserves Figure 3 from `HybridGuard_three_figures_v2.zip` (2026-10-22). This schematic is **not** the earlier experimental `F03a` figure.

## Contents

- [HybridGuard_Fig3_mechanisms_v2.svg](HybridGuard_Fig3_mechanisms_v2.svg): original editable SVG, 180 × 62 mm
- [HybridGuard_Fig3_mechanisms_v2_source.zip](HybridGuard_Fig3_mechanisms_v2_source.zip): ready-to-use source package (SVG, Python builder, captions, manifests)
- [source/build_fig3.py](source/build_fig3.py): original Python vector builder
- [CAPTIONS.md](CAPTIONS.md): English and Chinese figure captions
- [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json): original SHA-256 checksums for the SVG, PNG, PDF and builder

The panels show: (a) device context and a Native-derived memory envelope; (b) legitimate Native/Web timezone co-change versus a Web-only edit; (c) Host/container geometry. Examples are illustrative and add no measured records. The Host geometry study is standalone, not integrated with the main App detector.

## Rebuild and export

From this folder, with Python 3, Inkscape and Poppler:

```bash
python3 source/build_fig3.py --output HybridGuard_Fig3_mechanisms_v2.svg
inkscape HybridGuard_Fig3_mechanisms_v2.svg --export-type=pdf --export-filename=HybridGuard_Fig3_mechanisms_v2.pdf
pdftoppm -png -singlefile -scale-to-x 3600 -scale-to-y -1 HybridGuard_Fig3_mechanisms_v2.pdf HybridGuard_Fig3_mechanisms_v2
```

For the original Nimbus Roman typography, install the font locally (font files are not redistributed here). The ZIP also contains legacy review-v2 versions of Fig1 and Fig2, which are deliberately not duplicated: their newer variants are already archived in sibling directories `../overview/` and `../system_design/`.

**Archival scope:** The editable Figure 3 SVG and its code/metadata are committed here. Original PDF and PNG exports are not part of this directory; use the export commands to regenerate them.
