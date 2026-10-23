# Figure 1 v4 artwork sources

## Existing Figure 1 identity assets

The Android robot is reproduced from work created and shared by Google and used according to terms described in the Creative Commons 3.0 Attribution License.

- Android source: https://developer.android.com/distribute/marketing-tools/brand-guidelines
- License: https://creativecommons.org/licenses/by/3.0/
- Chrome source: https://www.google.com/chrome/static/images/chrome-logo-m100.svg
- Google brand guidance: https://about.google/brand-resource-center/guidance/

Android and Chrome remain inline vector assets inherited unchanged from the Figure 1 v3 baseline. Detailed original provenance and attribution are preserved in `../reference/V3_ASSET_MANIFEST.json` and `../reference/V3_ASSET_CREDITS.txt`.

The reference SVG contains v3's original WebView image and Tabler definitions so the exact baseline can be compared. The delivered v4 SVG removes the image and uses newly authored technical pictograms. The preserved Tabler MIT notice is `../reference/LICENSE-tabler.txt`.

## Six app marks reused from Figure 2

Source repository directory at commit `9ac8037a953280689062f906f5762536c40e1851`:

`paper/figures/system_design/semantic_vector_v1_20261023/assets/brands/`

| Assets | Source and recorded rights |
| --- | --- |
| WeChat, WhatsApp, Instagram, TikTok, YouTube | Community vector renditions from [SuperTinyIcons](https://github.com/edent/SuperTinyIcons). MIT notice in `licenses/SuperTinyIcons-LICENSE.txt`; brand rights are separate. |
| Alipay | [theSVG collection asset](https://github.com/glincker/thesvg/blob/main/public/icons/alipay/default.svg). The original project catalog records CC0-1.0; brand rights are separate. |

The six source files preserve the bytes read from the existing repository. Internal identifiers and references are namespaced on embedding; geometry and source presentation colors are retained. `FIG2_SOURCE_MANIFEST.json` and `FIG2_ATTRIBUTION.md` are preserved provenance records for the complete Figure 2 set; only the six app assets listed above are added to Figure 1. Broader notices from that asset package do not imply use of its other artwork.

The app marks are illustrative identities. They do not identify an expanded set of tested applications or imply endorsement.

## New vector artwork

The memory, clock, dimensions, files, association link, browser-window, WebView-container, interval, phone, and mismatch pictograms are original SVG geometry authored in `../build_figure.py` for this revision. The WebView pictogram is not represented as Google's official product mark. The blue clocks are schematic offset cues, and the red mismatch cross applies only to the illustrated C1 condition.
