# Figure 1 v4 review — 2026-10-23

Reviewed the original Figure 1 v3 and the regenerated v4 PNG at 1500 px width, with Figure 2's current saturated-icon SVG as the visual reference.

- No visible text clipping or collisions were found. The added app-logo tray occupies existing blank space above the Native card. The Native, App Web, external Browser, and C1 excerpts keep their original foreground boundaries and gain shallow offset outlines.
- All six app marks render in their original source colors. The SVG embedding preserves source-root presentation attributes, and both modern `href` and compatible `xlink:href` references resolve, including Instagram's gradient fills.
- New technical pictograms fit the original icon slots. The collection-interval, device, C1 clock, association-link, and mismatch additions stay clear of existing labels.
- Both C1 clocks use the same saturated blue with differing illustrative hands. Red is reserved for the condition-level mismatch cross; neither operand is visually assigned as ground truth or as the incorrect source.
- The two-head solid arrow, standalone geometry dashes, context dots, and record-excerpt leaders keep their original positions, direction, weight, and dash patterns.
- The 65 visible text nodes match the baseline in both text and complete SVG attributes. This includes the original serif headings; font and text metrics were retained to honor the layout constraint.
- Independent review confirmed unchanged text and relation coordinates, with no duplicate SVG identifiers and no embedded raster artwork.

The review covers the SVG and PNG deliverables. No manuscript insertion or new experimental evidence is claimed.

## Shared-corner refinement

Reviewed the regenerated 1500 px PNG after applying the shared 1.2 / 0.8 / 0.5 mm container/card/label radii. Foreground cards and their rear page outlines now agree; inset header fills follow the rounded card edge without visible overflow. No text clipping, connector displacement, or artwork changes were found.

An element-by-element comparison with the preceding v4 SVG confirms that the only changes are `rx` on 33 rectangles, with all 337 elements and their order retained. The original 178 mm canvas, 65 visible text objects, and all other SVG attributes are unchanged. The 3200 px and 1500 px PNGs were regenerated from this SVG with Inkscape.
