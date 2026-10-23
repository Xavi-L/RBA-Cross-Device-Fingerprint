#!/usr/bin/env python3
"""Restyle Fig3, preserving text and scientific bounds while unifying frame radii.

Pure vector artwork. Python standard library only; Inkscape exports previews.
Run from any directory: python3 source/build_fig3_v3.py [--export]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
STEM = "HybridGuard_Fig3_mechanisms_v3"
BASE = ROOT / "HybridGuard_Fig3_mechanisms_v2.svg"
ASSETS = ROOT / "style_v3_assets"
NS = "http://www.w3.org/2000/svg"
XL = "http://www.w3.org/1999/xlink"
INK = "http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("", NS)
ET.register_namespace("xlink", XL)
ET.register_namespace("inkscape", INK)

C = dict(line="#718E9D", dark="#526E7F", fine="#9DB1BA",
         pale="#F4F7F9", panel="#FAFCFD", blue_fill="#EDF4F8",
         blue="#1976D2", green="#16A34A", red="#E53935",
         gold="#F4B52C", green_fill="#EFF6F0", red_fill="#FCF0EF")
# Shared physical frame scale across the current Figures 1, 2 and 3.
# The 1800-unit-wide canvas is 180 mm wide: 10 SVG units per millimetre.
FRAME_RADIUS_MM = {"container": 1.2, "card": 0.8, "label": 0.5}
SVG_UNITS_PER_MM = 10
SCIENTIFIC_FRAME_BOUNDS = (("1280", "171", "265", "185"),
                           ("1280", "212", "425", "104"))
PANEL_IDS = ("device-context", "legitimate-cochange", "container-context")
GEOMETRY_KEYS = ("d", "points", "x", "y", "width", "height", "rx", "ry",
                 "x1", "y1", "x2", "y2", "cx", "cy", "r",
                 "marker-start", "marker-end", "stroke-dasharray", "stroke-width")


def frame_radius(role, inset=0):
    value = round(FRAME_RADIUS_MM[role] * SVG_UNITS_PER_MM - inset, 6)
    assert value >= 0, "A frame inset exceeds its corner radius"
    return int(value) if value.is_integer() else value


def el(parent, tag, **attrs):
    node = ET.SubElement(parent, "{" + NS + "}" + tag)
    for key, value in attrs.items():
        if value is not None:
            node.set(key.replace("_", "-"), str(value))
    return node


def group(parent, name):
    return el(parent, "g", id=name)


def rect(parent, x, y, w, h, fill="white", stroke=None, sw=1.5, rx=None, **attrs):
    if rx is None:
        rx = frame_radius("card")
    return el(parent, "rect", x=x, y=y, width=w, height=h, rx=rx,
              fill=fill, stroke=stroke or C["line"], stroke_width=sw, **attrs)


def path(parent, d, stroke=None, sw=2, fill="none", **attrs):
    return el(parent, "path", d=d, fill=fill, stroke=stroke or C["line"],
              stroke_width=sw, stroke_linecap="round", stroke_linejoin="round", **attrs)


def glyph(parent, name, x, y, w, h=None):
    node = el(parent, "use", x=x, y=y, width=w, height=h or w,
              data_role="semantic-icon")
    node.set("{" + XL + "}href", "#f3-" + name)
    return node


def find_id(svg, name):
    return next(n for n in svg.iter() if n.get("id") == name)


def prepend(parent, node):
    parent.remove(node)
    parent.insert(0, node)
    return node


def card(parent, name, x, y, w, h, band=True, fill="white", levels=2,
         header_h=38, header_rule=True):
    g = group(parent, name)
    for level in range(levels, 0, -1):
        rect(g, x + level * 5, y - level * 4, w, h,
             C["pale"], C["fine"], 1.25)
    rect(g, x, y, w, h, fill, C["line"], 1.6)
    if band:
        rect(g, x + .8, y + .8, w - 1.6, header_h - 1,
             C["blue_fill"], "none", 0, frame_radius("card", inset=.8))
        if header_rule:
            path(g, f"M{x} {y+header_h}H{x+w}", C["fine"], 1.05)
    return g


def symbol(defs, name, body, viewbox="0 0 32 32"):
    node = ET.fromstring(f'<symbol xmlns="{NS}" id="f3-{name}" viewBox="{viewbox}">{body}</symbol>')
    defs.append(node)


def import_symbol(defs, name):
    src = ET.parse(ASSETS / (name + ".svg")).getroot()
    node = el(defs, "symbol", id="f3-" + name, viewBox=src.get("viewBox", "0 0 32 32"))
    for key, value in src.attrib.items():
        if key not in ("id", "viewBox", "x", "y", "width", "height", "version"):
            node.set(key, value)
    for child in src:
        node.append(copy.deepcopy(child))


def clock_state(parent, cx, cy, color, fill="white"):
    g = group(parent, f"clock-state-{cx}-{cy}")
    # The unchanged a/b letters are the abstract offsets, not measured clock times.
    el(g, "circle", cx=cx, cy=cy, r=23, fill=fill, stroke=color, stroke_width=1.7)
    for d in (f"M{cx} {cy-19}v2", f"M{cx+19} {cy}h-2",
              f"M{cx} {cy+19}v-2", f"M{cx-19} {cy}h2"):
        path(g, d, color, 1.45)


def text_snapshot(svg):
    return [(dict(n.attrib), "".join(n.itertext())) for n in svg.iter("{" + NS + "}text")]


def geometry_snapshot(svg):
    return {name: [(n.tag.rsplit("}", 1)[-1], {k: n.get(k) for k in GEOMETRY_KEYS if n.get(k) is not None})
                   for n in find_id(svg, name)
                   if n.tag.rsplit("}", 1)[-1] in ("path", "rect", "circle", "line", "polygon")]
            for name in PANEL_IDS}


def expected_rounded_geometry(before):
    """Allow only rx on the two original Host/viewport foreground rectangles.

    All coordinates, widths, heights, scientific paths and other attributes stay
    in the comparison. The original v2 baseline is never rewritten.
    """
    expected = copy.deepcopy(before)
    matched = []
    for tag, attrs in expected["container-context"]:
        bounds = tuple(attrs.get(k) for k in ("x", "y", "width", "height"))
        if tag == "rect" and bounds in SCIENTIFIC_FRAME_BOUNDS:
            attrs["rx"] = str(frame_radius("card"))
            matched.append(bounds)
    assert sorted(matched) == sorted(SCIENTIFIC_FRAME_BOUNDS)
    return expected


def rounded_chrome_clip(defs, name, bounds, inset=1.6):
    """Clip only inset window artwork; the original window bounds stay exact."""
    x, y, w, h = map(float, bounds)
    clip = el(defs, "clipPath", id=name, clipPathUnits="userSpaceOnUse")
    el(clip, "rect", x=x + inset, y=y + inset,
       width=w - 2 * inset, height=h - 2 * inset,
       rx=frame_radius("card", inset=inset))
    return f"url(#{name})"


def build(export=False):
    baseline = ET.parse(BASE).getroot()
    svg = copy.deepcopy(baseline)
    text_before = text_snapshot(baseline)
    geometry_before = geometry_snapshot(baseline)
    geometry_expected = expected_rounded_geometry(geometry_before)
    defs = next(n for n in svg if n.tag == "{" + NS + "}defs")

    for name in ("brand-android", "color-memory", "color-clock", "color-dimensions",
                 "color-host", "color-phone", "color-browser", "mismatch-symbol"):
        import_symbol(defs, name)

    # JS letters are vector contours, keeping all 41 original text nodes exact.
    symbol(defs, "javascript", '''
      <rect x="1" y="1" width="30" height="30" rx="2" fill="#F7DF1E" stroke="#D6BE12" stroke-width=".7"/>
      <path d="M10.5 10V22.3C10.5 24.6 9.2 25.6 7.3 25.6C5.8 25.6 4.8 24.8 4.2 23.7L6.7 22.2C6.9 22.7 7.1 22.9 7.6 22.9C8.1 22.9 8.3 22.6 8.3 21.8V10Z" fill="#263238"/>
      <path d="M27.4 12.2L25.1 13.8C24.5 12.8 23.7 12.4 22.6 12.4C21.3 12.4 20.6 13 20.6 13.9C20.6 15 21.4 15.4 23.2 16.2L24.3 16.7C27 17.8 28.1 19.1 28.1 21.4C28.1 24.2 26 25.8 22.7 25.8C19.5 25.8 17.5 24.3 16.5 22.2L19 20.8C19.7 22.1 20.8 23 22.6 23C24.1 23 25.1 22.3 25.1 21.2C25.1 20.1 24.3 19.6 22.6 18.9L21.5 18.4C19 17.3 17.6 16 17.6 13.8C17.6 11.3 19.5 9.6 22.6 9.6C24.8 9.6 26.4 10.5 27.4 12.2Z" fill="#263238"/>
    ''')
    symbol(defs, "match", '''
      <circle cx="16" cy="16" r="14" fill="#16A34A"/>
      <path d="M8.5 16L13.5 21L24 10" fill="none" stroke="white" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
    ''')
    symbol(defs, "alert", '''
      <path d="M13.9 2.8Q16 .7 18.1 2.8L29.2 13.9Q31.3 16 29.2 18.1L18.1 29.2Q16 31.3 13.9 29.2L2.8 18.1Q.7 16 2.8 13.9Z" fill="#E53935"/>
      <path d="M16 8.5V18" stroke="white" stroke-width="3.3" stroke-linecap="round"/>
      <circle cx="16" cy="23.1" r="1.8" fill="white"/>
    ''')
    symbol(defs, "quiet-bell", '''
      <circle cx="16" cy="16" r="14.5" fill="#EDF4F8" stroke="#718E9D" stroke-width="1.4"/>
      <path d="M10 18V13A6 6 0 0 1 22 13V18L24 21H8ZM13 24Q16 27 19 24" fill="none" stroke="#526E7F" stroke-width="1.7" stroke-linejoin="round"/>
      <path d="M7 7L25 25" stroke="white" stroke-width="4.8"/>
      <path d="M7 7L25 25" stroke="#526E7F" stroke-width="2.1" stroke-linecap="round"/>
    ''')
    symbol(defs, "study", '''
      <path d="M11 3H21M13 3V13L5 25Q3 29 8 29H24Q29 29 27 25L19 13V3" fill="#FFF8E3" stroke="#D99000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M9 21H23L26 26Q27 27 24 27H8Q6 27 7 26Z" fill="#F4B52C"/>
      <circle cx="14" cy="22.7" r="1.1" fill="white"/><circle cx="20" cy="25" r=".9" fill="white"/>
    ''')

    # Existing labels, lines, markers, ticks and their coordinates remain intact.
    # Saturation is introduced through separate semantic artwork and quiet framing.
    a, b, c = (find_id(svg, name) for name in PANEL_IDS)
    for panel, label in zip((a, b, c), ("A · Device context", "B · Legitimate co-change", "C · Container context")):
        panel.set("{" + INK + "}groupmode", "layer")
        panel.set("{" + INK + "}label", label)

    # A — identical ruler coordinates, with the local bound's exceeded segment shaded.
    under_a = prepend(a, group(a, "device-card-depth"))
    card(under_a, "global-threshold-card", 18, 117, 548, 169, header_h=32, header_rule=False)
    card(under_a, "native-envelope-card", 18, 300, 548, 204, header_h=37, header_rule=False)
    rect(under_a, 23, 243, 276, 37, C["pale"], "none", 0, frame_radius("label"))
    rect(under_a, 23, 452, 276, 39, C["red_fill"], "none", 0, frame_radius("label"))
    rect(under_a, 76, 201, 404, 18, "#C8E2FF", C["blue"], 1, 1)
    rect(under_a, 480, 201, 55, 18, C["pale"], C["fine"], 1, 1)
    rect(under_a, 76, 381, 202, 18, "#C8E2FF", C["blue"], 1, 1)
    rect(under_a, 278, 381, 202, 18, "#FCA5A5", C["red"], 1, 1)
    rect(under_a, 480, 381, 55, 18, C["pale"], C["fine"], 1, 1)
    rect(under_a, 20, 524, 554, 38, C["blue_fill"], "none", 0, frame_radius("label"))
    icons_a = group(a, "device-semantic-icons")
    glyph(icons_a, "color-memory", 511, 25, 58)
    glyph(icons_a, "brand-android", 374, 67, 28)
    glyph(icons_a, "javascript", 419, 65, 28)
    glyph(icons_a, "color-browser", 521, 122, 29)
    glyph(icons_a, "color-memory", 521, 305, 29)
    glyph(icons_a, "color-memory", 34, 192, 31)
    glyph(icons_a, "color-memory", 34, 372, 31)
    glyph(icons_a, "quiet-bell", 251, 245, 32)
    glyph(icons_a, "alert", 251, 455, 32)

    # B — logos identify the observation surfaces; rings label abstract offset states.
    under_b = prepend(b, group(b, "timezone-card-depth"))
    card(under_b, "normal-system-change-card", 616, 117, 560, 164)
    card(under_b, "web-only-edit-card", 616, 300, 560, 154)
    rect(under_b, 1072, 171, 91, 88, C["green_fill"], "none", 0, frame_radius("card"))
    rect(under_b, 1072, 354, 91, 88, C["red_fill"], "none", 0, frame_radius("card"))
    for x in (826, 1003):
        for y in (190, 240):
            clock_state(under_b, x, y, C["green"], "#F7FCF8")
        clock_state(under_b, x, 373, C["fine"], C["pale"])
        clock_state(under_b, x, 423, C["red"], "#FFF9F8")
    rect(under_b, 620, 524, 558, 38, C["blue_fill"], "none", 0, frame_radius("label"))
    icons_b = group(b, "timezone-semantic-icons")
    glyph(icons_b, "color-clock", 1113, 25, 58)
    for y in (175, 358):
        glyph(icons_b, "brand-android", 748, y, 30)
    for y in (225, 408):
        glyph(icons_b, "javascript", 748, y, 30)
    glyph(icons_b, "match", 1100, 174, 32)
    glyph(icons_b, "mismatch-symbol", 1100, 357, 32)

    # C — preserve Host/viewport bounds and shared x=1280; change only frame rx.
    under_c = prepend(c, group(c, "container-card-depth"))
    rect(under_c, 1223, 62, 250, 39, "#FFF8E3", "none", 0, frame_radius("label"))
    for step in (2, 1):
        rect(under_c, 1280 + step * 6, 171 - step * 6, 265, 185,
             C["pale"], C["fine"], 1.35, frame_radius("card"))
    rect(under_c, 1367, 484, 272, 35, C["red_fill"], "none", 0, frame_radius("label"))
    rect(under_c, 1220, 524, 558, 38, C["blue_fill"], "none", 0, frame_radius("label"))
    host_front = next(n for n in c if n.tag == "{" + NS + "}rect" and n.get("width") == "265")
    viewport_front = next(n for n in c if n.tag == "{" + NS + "}rect" and n.get("width") == "425")
    host_front.set("rx", str(frame_radius("card")))
    viewport_front.set("rx", str(frame_radius("card")))

    # Host chrome is behind the viewport; the viewport keeps its original dimensions.
    host_chrome = group(c, "host-container-chrome")
    host_chrome.set("clip-path", rounded_chrome_clip(
        defs, "f3-host-chrome-clip", SCIENTIFIC_FRAME_BOUNDS[0]))
    rect(host_chrome, 1281.6, 172.6, 261.8, 26, C["blue_fill"], "none", 0, 0)
    path(host_chrome, "M1282 199H1543", C["fine"], 1)
    glyph(host_chrome, "color-phone", 1477, 175, 21)
    glyph(host_chrome, "color-host", 1507, 175, 21)
    c.remove(host_chrome)
    c.insert(list(c).index(host_front) + 1, host_chrome)

    viewport_depth = group(c, "viewport-page-depth")
    for step in (2, 1):
        rect(viewport_depth, 1280 + step * 6, 212 - step * 6, 425, 104,
             C["pale"], C["fine"], 1.35, frame_radius("card"))
    c.remove(viewport_depth)
    c.insert(list(c).index(viewport_front), viewport_depth)

    viewport_chrome = group(c, "viewport-page-chrome")
    viewport_chrome.set("clip-path", rounded_chrome_clip(
        defs, "f3-viewport-chrome-clip", SCIENTIFIC_FRAME_BOUNDS[1]))
    rect(viewport_chrome, 1546.5, 213.6, 156.9, 100.8, "#FDE3E1", "none", 0, 0)
    rect(viewport_chrome, 1281.6, 213.6, 421.8, 15.4, "#F3EAD7", "none", 0, 0)
    for x in (1290, 1297, 1304):
        el(viewport_chrome, "circle", cx=x, cy=221, r=1.75, fill=C["fine"])
    path(viewport_chrome, "M1545 213.5V314.5", C["red"], 1.5, stroke_dasharray="4 4")
    glyph(viewport_chrome, "javascript", 1650, 252, 33)
    glyph(viewport_chrome, "mismatch-symbol", 1589, 252, 33)
    c.remove(viewport_chrome)
    c.insert(list(c).index(viewport_front) + 1, viewport_chrome)

    icons_c = group(c, "container-semantic-icons")
    glyph(icons_c, "color-dimensions", 1713, 25, 58)
    glyph(icons_c, "study", 1438, 65, 31)
    glyph(icons_c, "color-host", 1237, 119, 31)
    glyph(icons_c, "alert", 1645, 484, 31)

    # Neutral footer backing: original divider and full explanatory footnote stay.
    footer = group(svg, "footer-backing")
    rect(footer, 20, 586, 1760, 31, C["pale"], "none", 0, frame_radius("label"))
    svg.remove(footer)
    index = next(i for i, n in enumerate(svg) if n.tag == "{" + NS + "}path" and n.get("d") == "M30 578L1770 578")
    svg.insert(index, footer)

    assert text_before == text_snapshot(svg), "An original text node or its presentation changed"
    assert geometry_expected == geometry_snapshot(svg), "Scientific geometry changed beyond the two permitted frame radii"
    assert dict(baseline.attrib) == dict(svg.attrib), "Canvas or accessibility metadata changed"
    assert not list(svg.iter("{" + NS + "}image")), "Raster artwork is not permitted"
    all_ids = [n.get("id") for n in svg.iter() if n.get("id")]
    assert len(all_ids) == len(set(all_ids)), "Duplicate SVG IDs"
    for n in svg.iter():
        for key, value in n.attrib.items():
            if key.endswith("href"):
                assert value.startswith("#"), "External artwork dependency"

    output = ROOT / (STEM + ".svg")
    ET.indent(svg, space="  ")
    ET.ElementTree(svg).write(output, encoding="utf-8", xml_declaration=True)
    # The serialized file is checked again, not only the in-memory DOM.
    reread = ET.parse(output).getroot()
    assert text_before == text_snapshot(reread)
    assert geometry_expected == geometry_snapshot(reread)
    checks = {
        "figure": STEM,
        "source_commit": "8d92b73e85aadf8ce2ce0ff5186d49122da6421f",
        "base_svg_sha256": hashlib.sha256(BASE.read_bytes()).hexdigest(),
        "canvas": dict(svg.attrib),
        "visible_text_nodes": len(text_before),
        "all_original_text_and_presentation_attributes_unchanged": True,
        "original_scientific_shapes": sum(map(len, geometry_before.values())),
        "all_original_scientific_geometry_except_two_frame_radii_unchanged": True,
        "corner_radius_refinement": {
            "date": "2026-10-23",
            "frame_radius_mm": FRAME_RADIUS_MM,
            "svg_units_per_mm": SVG_UNITS_PER_MM,
            "card_radius_svg_units": frame_radius("card"),
            "label_radius_svg_units": frame_radius("label"),
            "header_inset_radius_svg_units": frame_radius("card", inset=.8),
            "chrome_clip_inset_radius_svg_units": frame_radius("card", inset=1.6),
            "scientific_frame_rx_whitelist": [
                dict(zip(("x", "y", "width", "height"), bounds),
                     rx=str(frame_radius("card")))
                for bounds in SCIENTIFIC_FRAME_BOUNDS
            ],
            "scientific_ranges_rulers_icons_and_logos_unchanged": True,
            "chrome_clipped_to_rounded_inset_bounds": True
        },
        "original_text_css_unchanged": True,
        "original_standalone_scope_and_footnote_unchanged": True,
        "pure_vector": True,
        "self_contained_svg": True,
        "semantic_icon_instances": len(list(svg.iter("{" + NS + "}use"))),
        "svg_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "style_references": [
            "paper/figures/overview/style_preserving_v4_20261023/HybridGuard_Fig1_surfaces_v4.svg",
            "paper/figures/system_design/semantic_vector_v1_20261023/HybridGuard_Fig2_semantic_v1.svg"
        ],
        "notes": [
            "No additional visible text; the JS identifier is vector artwork.",
            "No-trigger is a neutral bell, not a claim that the input is trustworthy.",
            "No browser brand logos are used for App Web.",
            "The Native 4 GiB marker, Web 8 GiB marker and all Host/viewport dimensions retain their original coordinates."
        ]
    }
    (ROOT / "STYLE_V3_CHECK.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if export:
        subprocess.run(["inkscape", str(output), "--export-type=png",
                        "--export-width=3600", "--export-filename=" + str(ROOT / (STEM + ".png"))], check=True)
    print(json.dumps({"svg": str(output), "preserved_text_nodes": len(text_before),
                      "preserved_scientific_shapes": checks["original_scientific_shapes"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", action="store_true", help="Also export a 3600-pixel PNG with Inkscape")
    build(parser.parse_args().export)
