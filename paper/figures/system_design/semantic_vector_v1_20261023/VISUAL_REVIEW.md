# Visual and export review

Reviewed on **2026-10-23** against `reference/approved_raster_concept.png`.

## Delivered structure

- The two-band composition, compact placement, and plain English wording follow the selected concept.
- Candidate checks use memory, clock, and viewport pictograms. Filter, Select, and Refine use different visual operations; repeated decorative tick-and-text rows are absent.
- The six App logos share one container. In-App Web pages have no browser logo. Optional external Browser pages carry Chrome, Firefox, and Edge logos.
- The Saved checks supply arrow terminates at Run saved checks. The Browser auxiliary input uses a thin dashed arrow to the optional Browser check.
- Memory and timezone examples retain the intended relations. The three main outcomes and two execution states remain visually distinct.
- Original asset colors are preserved. Custom arrows, borders, ticks, crosses, and geometry use muted colors.

## Adjustments made after inspecting the first export

The initial font fallback made some labels too wide. Nimbus Sans was made the first font family, with Arial and Liberation Sans retained as fallbacks. The Memory limit label, right Browser web label, and selection ellipsis were repositioned. Above limit uses two short lines, and Compare / time zones was lifted slightly to keep clear of the bottom edge.

The final PNG and rasterized PDF were visually inspected. The corrected labels fit their containers, the optional comparison remains readable, and no further clipping or incorrect connection was identified. The figure is a reconstruction with minor spacing adjustments, not a pixel trace.

## Export inspection

| Check | Recorded result |
| --- | --- |
| SVG page | 1800 × 900 viewBox; 180 × 90 mm physical size |
| SVG text | 64 editable text elements |
| Original assets | 16 distinct SVG sources; 9 brand logos and 7 technical/state icons |
| SVG raster images | 0 `image` elements |
| External image dependencies | 0 |
| PNG | 3500 × 1750 pixels |
| PDF | One page, 180 × 90 mm |
| PDF raster images | 0 image objects, including the TikTok mark |
| PDF fonts | Nimbus Sans Regular and Bold subsets embedded, with text extractable |

The SVG keeps live text for editing. Rebuilding with another font can change text width; use Nimbus Sans for the reviewed metrics. The PDF is the fixed-layout placement version. This review covers this figure revision and its exports, not manuscript integration or experimental verification.
