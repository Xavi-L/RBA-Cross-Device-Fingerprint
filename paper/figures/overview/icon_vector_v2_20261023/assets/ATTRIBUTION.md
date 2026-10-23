# Figure 1 assets and artwork

The three brand SVGs were reused byte-for-byte from `paper/figures/system_design/semantic_vector_v1_20261023/assets/brands/` at repository commit `b49c53ffcb2eaacf1cf9fbaff43b99d18fc469a1`. They originate from the existing color asset catalog dated 2026-10-22. Colors are preserved; only placement, scaling, and internal-ID namespacing are applied when assembling the figure.

| Asset | Source | Retained provenance |
| --- | --- | --- |
| `brands/wechat.svg` | [SuperTinyIcons](https://github.com/edent/SuperTinyIcons/blob/master/images/svg/wechat.svg) | Community vector rendition; MIT notice in `licenses/SuperTinyIcons-LICENSE.txt`. |
| `brands/youtube.svg` | [SuperTinyIcons](https://github.com/edent/SuperTinyIcons/blob/master/images/svg/youtube.svg) | Community vector rendition; MIT notice in `licenses/SuperTinyIcons-LICENSE.txt`. |
| `brands/alipay.svg` | [theSVG](https://github.com/glincker/thesvg/blob/main/public/icons/alipay/default.svg) | Catalog records this rendition as CC0-1.0; original catalog metadata retained in `source_manifest.json`. |

Brand rights are separate from the vector artwork's stated license. Logos illustrate app categories, not a list of tested apps, and do not imply endorsement. `licenses/RETAINED_BRANDS_NOTICES.txt` preserves the catalog's original broader notes; references there to other assets do not imply those assets appear here.

The phone, settings gear, memory chip, clock, memory-limit graphic, viewport dimensions, webpage content, arrows, and layered frames are custom SVG geometry in `../build_figure.py`, adapted to the established Figure 2 drawing conventions. The figure uses no generated bitmap artwork or third-party paper screenshots.
