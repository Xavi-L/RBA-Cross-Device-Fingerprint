# Figure 3 v4 design review — 2026-10-24

## Scope

Revise only panel (b) of the latest Figure 3 mechanism schematic. Preserve the complete artwork, scientific content and geometry of panels (a) and (c), the 180 × 57.4 mm canvas, shared radii, typography and embedded vector assets. This is not the earlier F03a results figure.

Baseline: `ebd4535f0ad7a2847d3a2950d7d2a3edc0a686fb`, `HybridGuard_Fig3_mechanisms_v3.svg`.

## Panel (b)

- Replace abstract a/b state letters with illustrative normalized UTC+8 / UTC+9 offsets.
- Add explicit Before / After columns in each scenario.
- Place Native and Web in separate continuous horizontal bands; align labels, values and arrows.
- Keep a right-hand bracket linking only the two After values.
- Show a system timezone change as both sources moving from UTC+8 to UTC+9 (Match).
- Show a Web-only edit as Native remaining at UTC+8 while Web becomes UTC+9 (Mismatch).
- Retain the existing Android, JS, clock and outcome icons, using color to distinguish changes and an unchanged Native reference.
- Use the direct title “Timezone consistency” and the takeaway “Compare Native and Web offsets”.

UTC+8 / UTC+9 are schematic values, not measured traces. The detector compares the two sources within the same applicable observation; Before is only an explanatory device, not a required historical feature. Match/Mismatch refers only to this relation and is not a whole-device safety verdict.

Semantic basis: [timezone relation definition](../../../deliverables/timezone_relation_validation_v1/SEMANTICS.md).

## Panel (c): screenshot assessment

Decision: retain the existing vector schematic in this revision.

Host H is the measured WebView content bound. Reported viewport P is a value converted from JavaScript viewport observations. A reported P above H plus tolerance does not imply that the rendered page visibly extends outside the phone or Host container. Therefore two arbitrary UI screenshots cannot faithfully replace the two comparison rectangles.

The formal geometry report covers 72 observations from three emulators, not physical phones. Its archived run tree and the later engineering closeout tree contain no directly usable PNG/JPEG/WebP screenshots. The later closeout report also explicitly states that physical-device behavior remains unvalidated.

If screenshots are acquired later, use one attributable App screenshot with the Host boundary annotated, paired with a separately labeled reported-dimension ruler. Keep the original capture proportions; do not stretch a screenshot to imply measured overflow. Distinguish an emulator capture from a physical-phone capture and retain same-observation Host/viewport/DPR/scale values.

Sources at the baseline commit:
- [Geometry semantics](../../../deliverables/screen_geometry_observation_v1/SEMANTICS.md)
- [Formal geometry report](../../../deliverables/screen_geometry_observation_v1/REPORT.md)
- [Engineering closeout report](../../../deliverables/screen_geometry_closeout_v1/REPORT.md)

## Validation and delivery

The builder verifies the full XML content of (a) and (c) against v3 and preserves the canvas. All SVG text remains editable; there are no raster images or external artwork dependencies. The new figure has been rendered and visually checked for text collisions, reading order and outcome-bracket placement.

Files: v4 SVG, PNG, builder, bilingual caption and preservation-check JSON. The original v3 artwork, original caption and main draft PDF are retained. This revision delivers figure artwork and does not recompile the full manuscript.
