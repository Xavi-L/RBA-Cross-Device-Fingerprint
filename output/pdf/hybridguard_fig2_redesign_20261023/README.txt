HybridGuard Figure 2 — v5 visual review candidate — 2026-10-23

Purpose
An editable redesign following the user's two reference screenshots and pasted
design discussion: compact two-band layout, stacked records/pages/rules,
original-color App/browser logos, muted custom strokes, and sparse simple text.
No manuscript references or previously frozen figures are replaced.

Files
HybridGuard_Fig2_redesign_v5.svg: self-contained editable vector source, including
inline editable SVG assets; text stays as text.
HybridGuard_Fig2_redesign_v5.png: 2640 x 1350 preview.
HybridGuard_Fig2_redesign_v5.pdf: one-page vector export, approximately 180 x 92 mm.
build_figure.py and render_figure.cjs: candidate-only rebuild/export entry points.
assets/: exact original SVG assets used, with bundled source and rights notices.
CAPTION.txt: English caption and precise result-state interpretation.
RENDER_CHECK.json: rendering checks; this is not experimental validation.

Reading order
Top: development records and candidate checks -> filter -> select -> refine ->
saved checks. The downward arrow supplies fixed checks to current evaluation.
Bottom: a current App record -> saved checks -> result. In-app web has no browser
logo. The separately linked Browser uses branded stacked pages and a dashed
optional route. The UTC example illustrates one condition, not overall trust.

Scientific scope
The App and Browser logos illustrate source categories; no empirical coverage of
these specific brands is claimed. The UTC values are pedagogical normalized
offsets, not collected observations. Browser C1 is an optional separate App+C1
configuration. Host-Web geometry is not added to Full App. No alert does not
prove authenticity. No collection, fitting, evaluation, or timing was performed.
The user-provided reference images are not redistributed in this folder.

Rebuild from repository root
python3 output/pdf/hybridguard_fig2_redesign_20261023/build_figure.py
node output/pdf/hybridguard_fig2_redesign_20261023/render_figure.cjs

The renderer uses bundled Playwright and local Google Chrome. Its node-module
path and Chrome executable can be adapted for another machine. The Python
generator uses only the standard library and reads the checked-in asset ZIP.
