#!/usr/bin/env python3
"""Clarify Figure 3(b) with explicit Before/After columns and UTC offsets.

The source is the frozen v3 SVG. Panels (a) and (c), the three-column canvas,
shared corner radii and embedded assets are preserved. The UTC values are
illustrative, not additional measurements. Python standard library only;
Inkscape is needed only for --export.
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
BASE = ROOT / "HybridGuard_Fig3_mechanisms_v3.svg"
STEM = "HybridGuard_Fig3_mechanisms_v4"
SOURCE_COMMIT = "ebd4535f0ad7a2847d3a2950d7d2a3edc0a686fb"
NS = "http://www.w3.org/2000/svg"
XL = "http://www.w3.org/1999/xlink"
INK = "http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("", NS)
ET.register_namespace("xlink", XL)
ET.register_namespace("inkscape", INK)

C = dict(text="#343434", muted="#687078", line="#718E9D",
         fine="#9DB1BA", pale="#F4F7F9", blue_fill="#EDF4F8",
         green="#16A34A", green_text="#287B53", green_fill="#EFF6F0",
         red="#E53935", red_text="#BA2F2C", red_fill="#FCF0EF",
         amber="#BD8B47")


def el(parent, tag, **attrs):
    n = ET.SubElement(parent, "{" + NS + "}" + tag)
    for k, v in attrs.items():
        if v is not None:
            n.set(k.replace("_", "-"), str(v))
    return n


def txt(parent, value, x, y, size=27, color=None, bold=False,
        anchor="start", name=None):
    n = el(parent, "text", x=x, y=y, font_size=size,
           fill=color or C["text"], font_weight="700" if bold else "400",
           text_anchor=anchor, id=name)
    n.text = value
    return n


def rect(parent, x, y, w, h, fill, stroke="none", sw=0, rx=8):
    return el(parent, "rect", x=x, y=y, width=w, height=h, rx=rx,
              fill=fill, stroke=stroke, stroke_width=sw)


def line(parent, d, color, sw=2, **attrs):
    return el(parent, "path", d=d, fill="none", stroke=color,
              stroke_width=sw, stroke_linecap="round",
              stroke_linejoin="round", **attrs)


def icon(parent, name, x, y, size):
    n = el(parent, "use", x=x, y=y, width=size, height=size,
           data_role="semantic-icon")
    n.set("{" + XL + "}href", "#f3-" + name)
    return n


def by_id(svg, name):
    return next(n for n in svg.iter() if n.get("id") == name)


def snapshot(node):
    """Ignore serialization whitespace; retain every scientific/text attribute."""
    return (node.tag, tuple(sorted(node.attrib.items())),
            (node.text or "").strip(), tuple(snapshot(c) for c in node))


def arrow_defs(defs):
    for name, color in (("green", C["green"]), ("red", C["red"]),
                        ("muted", C["muted"])):
        m = el(defs, "marker", id="f3v4-arrow-" + name,
               markerWidth=8, markerHeight=7, refX=7.5, refY=3.5,
               orient="auto", markerUnits="userSpaceOnUse")
        el(m, "path", d="M0 0L8 3.5L0 7Z", fill=color)


def scenario(parent, y, *, key, heading, normal):
    card = el(parent, "g", id="f3v4-" + key)
    # Retain the shared 0.8 mm content-card radius and quiet stacked-frame style.
    for depth in (2, 1):
        rect(card, 616 + 5 * depth, y - 4 * depth, 560, 173,
             C["pale"], C["fine"], 1.25)
    rect(card, 616, y, 560, 173, "white", C["line"], 1.6)
    rect(card, 616.8, y + .8, 558.4, 34, C["blue_fill"], rx=7.2)
    line(card, f"M616 {y+35}H1176", C["fine"], 1.05)
    txt(card, heading, 630, y + 26, size=28, bold=True,
        color=C["green_text"] if normal else C["amber"],
        name=key + "-heading")

    # Explicit column labels disambiguate the horizontal change arrows.
    txt(card, "Before", 821, y + 57, size=24, color=C["muted"],
        anchor="middle", name=key + "-before-heading")
    txt(card, "After", 989, y + 57, size=24, color=C["muted"],
        anchor="middle", name=key + "-after-heading")

    for i, source in enumerate(("Native", "Web")):
        row_y = y + 66 + 48 * i
        row = el(card, "g", id=key + "-" + source.lower() + "-row")
        rect(row, 628, row_y, 414, 43, C["pale"], rx=5)
        icon(row, "brand-android" if i == 0 else "javascript",
             632, row_y + 8.5, 26)
        txt(row, source, 669, row_y + 29, size=27,
            name=key + "-" + source.lower() + "-label")
        txt(row, "UTC+8", 821, row_y + 29, size=28, anchor="middle",
            name=key + "-" + source.lower() + "-before")
        changed = normal or i == 1
        arrow_color = "green" if normal else ("red" if i == 1 else "muted")
        color = C["green_text"] if normal else (C["red_text"] if i == 1 else C["muted"])
        line(row, f"M881 {row_y+21.5}H933", C[arrow_color], 2.4,
             marker_end="url(#f3v4-arrow-" + arrow_color + ")")
        txt(row, "UTC+9" if changed else "UTC+8", 989,
            row_y + 29, size=28, color=color, bold=changed,
            anchor="middle", name=key + "-" + source.lower() + "-after")

    # The bracket compares only the two After values, within one observation.
    outcome_color = C["green_text"] if normal else C["red_text"]
    line(card, f"M1045 {y+87.5}H1057V{y+135.5}H1045",
         outcome_color, 1.8)
    rect(card, 1067, y + 66, 99, 91,
         C["green_fill"] if normal else C["red_fill"])
    icon(card, "match" if normal else "mismatch-symbol",
         1099.5, y + 77, 34)
    txt(card, "Match" if normal else "Mismatch", 1116.5, y + 141,
        size=24 if normal else 23, color=outcome_color,
        anchor="middle", name=key + "-outcome")


def build(export=False):
    baseline = ET.parse(BASE).getroot()
    svg = copy.deepcopy(baseline)
    before = {k: snapshot(by_id(baseline, k))
              for k in ("device-context", "container-context")}
    b = by_id(svg, "legitimate-cochange")
    for node in list(b):
        b.remove(node)
    b.set("{" + INK + "}label", "B · Timezone consistency")
    title = by_id(svg, "title")
    title.text = "HybridGuard: three mechanisms of contextual integrity evidence"
    by_id(svg, "desc").text = (
        "Three illustrative panels; no additional measured records. "
        "Panel a retains the Native-derived memory-envelope example. "
        "Panel b reads horizontally: each Native or Web row shows a normalized "
        "UTC offset before and after an illustrative change. A system timezone "
        "change moves both from UTC+8 to UTC+9; a Web-only edit leaves Native at "
        "UTC+8 and changes Web to UTC+9. The right bracket compares the two "
        "After values within the same observation; historical Before data are "
        "not required by the detector. Panel c retains the standalone Host "
        "geometry schematic, comparing a reported converted viewport dimension "
        "against a Host bound plus tolerance, not depicting visible overflow."
    )
    defs = next(n for n in svg if n.tag == "{" + NS + "}defs")
    arrow_defs(defs)

    txt(b, "(b) Timezone consistency", 630, 46, size=33, bold=True,
        name="f3v4-panel-title")
    txt(b, "Normalized UTC offsets", 630, 90, size=27,
        color=C["muted"], name="f3v4-subtitle")
    icon(b, "color-clock", 1113, 25, 58)
    scenario(b, 126, key="system-change", heading="System timezone change", normal=True)
    scenario(b, 321, key="web-edit", heading="Web-only timezone edit", normal=False)
    rect(b, 620, 524, 558, 38, C["blue_fill"], rx=5)
    txt(b, "Compare Native and Web offsets", 900, 550,
        size=27, bold=True, anchor="middle", name="f3v4-takeaway")

    # Narrow regression checks protect the scientific content outside this edit.
    assert before == {k: snapshot(by_id(svg, k)) for k in before}
    assert baseline.attrib == svg.attrib, "Canvas changed"
    assert not list(svg.iter("{" + NS + "}image")), "Unexpected raster input"
    ids = [n.get("id") for n in svg.iter() if n.get("id")]
    assert len(ids) == len(set(ids)), "Duplicate SVG IDs"
    for n in svg.iter():
        for k, value in n.attrib.items():
            if k.endswith("href"):
                assert value.startswith("#"), "External asset dependency"

    output = ROOT / (STEM + ".svg")
    ET.indent(svg, space="  ")
    ET.ElementTree(svg).write(output, encoding="utf-8", xml_declaration=True)
    reread = ET.parse(output).getroot()
    assert before == {k: snapshot(by_id(reread, k)) for k in before}
    report = {
        "figure": STEM, "source_commit": SOURCE_COMMIT,
        "base_svg": BASE.name,
        "base_sha256": hashlib.sha256(BASE.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "panels_a_and_c_preserved_exactly_as_xml_content": True,
        "canvas_preserved": dict(svg.attrib),
        "all_text_editable": True, "embedded_raster_images": 0,
        "comparison": "Normalized Native and Web offsets within one observation",
        "arrows": "Illustrate changes; historical Before input is not required",
        "utc_offsets": "Illustrative UTC+8 and UTC+9, not measured traces",
        "geometry_scope": "Standalone study; no screenshot or integration claim added",
        "figure_sources_only": True,
    }
    (ROOT / "DESIGN_V4_CHECK.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if export:
        env = os.environ.copy()
        env.setdefault("XDG_CONFIG_HOME", "/tmp/fig3-v4-inkscape-config")
        env.setdefault("XDG_CACHE_HOME", "/tmp/fig3-v4-inkscape-cache")
        env.setdefault("XDG_DATA_HOME", "/tmp/fig3-v4-inkscape-data")
        subprocess.run([
            "inkscape", str(output), "--export-type=png", "--export-width=3600",
            "--export-filename=" + str(ROOT / (STEM + ".png")),
        ], check=True, env=env)
    print(output)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--export", action="store_true", help="Also export a 3600px PNG")
    build(ap.parse_args().export)
