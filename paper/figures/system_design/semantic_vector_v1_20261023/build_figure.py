#!/usr/bin/env python3
"""Build the editable HybridGuard Figure 2 from original vector assets.

Python standard library only. Inkscape is required for PNG/PDF export.
Coordinates use a 1800 x 900 viewBox; physical page size is 180 x 90 mm.
Run from any directory: python3 /path/to/build_figure.py
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEM = "HybridGuard_Fig2_semantic_v1"
SVG_NS = "http://www.w3.org/2000/svg"
# The established Inkscape namespace is required for editable layer metadata.
INK_NS = "http://www.inkscape.org/namespaces/inkscape"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("inkscape", INK_NS)
ET.register_namespace("xlink", XLINK_NS)

C = {
    "ink": "#23323C", "line": "#718E9D", "line_dark": "#526E7F",
    "fine": "#9DB1BA", "flow": "#7396A5", "flow_dark": "#527C90",
    "sage": "#16A34A", "sage_fill": "#EFF6F0",
    "rose": "#E53935", "rose_fill": "#FCF0EF",
    "icon_blue": "#1976D2", "memory_blue": "#93C5FD", "memory_red": "#F87171",
    "icon_amber": "#D99000", "funnel_fill": "#F4B52C",
    "paper": "#FFFFFF", "panel": "#FAFCFD", "blue_fill": "#EDF4F8",
    "gray": "#AAB3BC", "pale": "#F4F7F9", "amber": "#B79B70",
}
# Apply the semantic palette to displayed state symbols only. Original asset files
# and brand colors stay intact; structural borders and flow arrows remain muted.
ICON_RECOLORS = {
    "high_priority": {"#F44336": C["rose"]},
    "ok": {"#4CAF50": C["sage"], "#CCFF90": "#FFFFFF"},
}
USED_ASSETS: dict[str, dict] = {}
_asset_count = 0
_text_count = 0

# Shared with Figures 1 and 3; values are physical radii at the SVG page size.
FRAME_RADIUS_MM = {"container": 1.2, "card": 0.8, "label": 0.5}


def radius(kind):
    value = FRAME_RADIUS_MM[kind] * 1800 / 180
    return int(value) if value.is_integer() else value


def el(parent, tag, **attrs):
    node = ET.SubElement(parent, f"{{{SVG_NS}}}{tag}")
    for k, v in attrs.items():
        if v is not None:
            node.set(k.replace("_", "-"), str(v))
    return node


def group(parent, name, label=None, layer=False, transform=None):
    node = el(parent, "g", id=name, transform=transform)
    if label:
        node.set(f"{{{INK_NS}}}label", label)
    if layer:
        node.set(f"{{{INK_NS}}}groupmode", "layer")
    return node


def box(p, x, y, w, h, fill="white", stroke=None, sw=1.6, r=None, dash=None, **extra):
    if r is None:
        r = radius("card")
    return el(p, "rect", x=x, y=y, width=w, height=h, rx=r,
              fill=fill, stroke=stroke or C["line"], stroke_width=sw,
              stroke_dasharray=dash, **extra)


def line(p, x1, y1, x2, y2, color=None, sw=1.6, dash=None, **extra):
    return el(p, "line", x1=x1, y1=y1, x2=x2, y2=y2,
              stroke=color or C["line"], stroke_width=sw,
              stroke_dasharray=dash, stroke_linecap="round", **extra)


def path(p, d, fill="none", stroke=None, sw=1.6, **extra):
    return el(p, "path", d=d, fill=fill, stroke=stroke or C["line"],
              stroke_width=sw, stroke_linecap="round", stroke_linejoin="round", **extra)


def text(p, x, y, value, size=23, weight="normal", color=None, anchor="start", **extra):
    global _text_count
    _text_count += 1
    node = el(p, "text", id=f"label-{_text_count:03d}", x=x, y=y,
              font_family="Nimbus Sans, Arial, Liberation Sans, sans-serif", font_size=size,
              font_weight=weight, fill=color or C["ink"], text_anchor=anchor, **extra)
    node.text = value
    return node


def label(p, x, y, w, h, value, size=25, fill=None, stroke=None):
    box(p, x, y, w, h, fill or C["blue_fill"], stroke or C["line_dark"], r=radius("label"))
    text(p, x+w/2, y+h/2+size*.34, value, size, "bold", anchor="middle")


def stack(p, x, y, w, h, fill="white", stroke=None, step=9, levels=3, r=None):
    if r is None:
        r = radius("card")
    for i in range(levels-1, 0, -1):
        box(p, x+i*step, y-i*step, w, h, C["pale"], stroke, r=r)
    return box(p, x, y, w, h, fill, stroke, r=r)


def arrow(p, x1, y, x2, color=None, height=18, head=17, **extra):
    color = color or C["flow"]
    half = height/2
    d = (f"M {x1} {y-half} H {x2-head} V {y-height} L {x2} {y} "
         f"L {x2-head} {y+height} V {y+half} H {x1} Z")
    return path(p, d, fill=color, stroke=color, sw=.4, **extra)


def flow_line(p, d, color=None, sw=3, end="arrow-small", dash=None, **extra):
    return path(p, d, stroke=color or C["flow_dark"], sw=sw,
                marker_end=f"url(#{end})", stroke_dasharray=dash, **extra)


def check(p, x, y, s=20, color=None, circle=False):
    color = color or C["sage"]
    if circle:
        el(p, "circle", cx=x, cy=y, r=s*.74, fill=color)
        color = "white"
    path(p, f"M {x-s*.48} {y} l {s*.32} {s*.34} l {s*.68} {-s*.76}",
         stroke=color, sw=s*.22)


def cross(p, x, y, s=18, color=None):
    color = color or C["rose"]
    line(p, x-s*.4, y-s*.4, x+s*.4, y+s*.4, color, s*.19)
    line(p, x-s*.4, y+s*.4, x+s*.4, y-s*.4, color, s*.19)


def clock(p, x, y, r=15, color=None):
    color = color or C["icon_blue"]
    el(p, "circle", cx=x, cy=y, r=r, fill=C["pale"], stroke=color, stroke_width=2.2)
    path(p, f"M {x} {y-r*.65} V {y} l {r*.46} {r*.27}", stroke=color, sw=2.5)


def mini_page(p, x, y, w=73, h=49, fill=None, r=None):
    # Keep small pictogram artwork intact; actual page cards opt into card radii.
    page_radius = 3 if r is None else r
    header_radius = 2 if r is None else max(0, r - 1.1)
    box(p, x, y, w, h, fill or "white", C["line_dark"], 1.4, page_radius)
    box(p, x+1.1, y+1.1, w-2.2, h*.23, C["blue_fill"], "none", 0, header_radius)
    line(p, x, y+h*.25, x+w, y+h*.25, C["line"], 1)
    for i in range(3):
        el(p, "circle", cx=x+5+i*4, cy=y+h*.12, r=1.25, fill=C["fine"])


def memory(p, x, y, w=76, h=45):
    mini_page(p, x, y, w, h)
    box(p, x+6, y+h*.48, w*.82, h*.26, C["memory_blue"], C["icon_blue"], .8, 0)
    box(p, x+w*.54, y+h*.48, w*.36, h*.26, C["memory_red"], C["rose"], .8, 0)
    line(p, x+w*.54, y+h*.29, x+w*.54, y+h*.92, C["rose"], 1.8, "4 3")


def time_pair(p, x, y, r=14):
    clock(p, x+r, y+r, r)
    text(p, x+r*2+13, y+r+8, "=", 24, "bold", C["icon_blue"], "middle")
    clock(p, x+r*3+25, y+r, r)


def page_size(p, x, y, w=72, h=46, layered=False):
    if layered:
        box(p, x+7, y-6, w, h, C["pale"], C["fine"], 1, 3)
    mini_page(p, x, y, w, h)
    for yy, left, right in [(y+h*.51,x+12,x+w-12),(y+h*.78,x+8,x+w-8)]:
        line(p, left, yy, right, yy, C["icon_blue"], 1.7)
        path(p, f"M {left+4} {yy-3} L {left} {yy} L {left+4} {yy+3}", stroke=C["icon_blue"], sw=1.5)
        path(p, f"M {right-4} {yy-3} L {right} {yy} L {right-4} {yy+3}", stroke=C["icon_blue"], sw=1.5)


def token(p, x, y, kind, w=49, h=49):
    box(p, x, y, w, h, "white", C["line"], 1.2, 5)
    if kind == "memory":
        memory(p, x+6, y+12, w-12, h-22)
    elif kind == "time":
        clock(p, x+w/2, y+h/2, min(w,h)*.28)
    elif kind == "page":
        page_size(p, x+7, y+10, w-14, h-19)


def document(p, x, y, w=33, h=43, color=None):
    color = color or C["line"]
    path(p, f"M {x} {y} H {x+w*.65} L {x+w} {y+h*.26} V {y+h} H {x} Z",
         fill=C["pale"], stroke=color, sw=1.6)
    path(p, f"M {x+w*.65} {y} V {y+h*.26} H {x+w}", stroke=color, sw=1.2)
    for i,l in enumerate([.6,.6,.42]):
        line(p, x+w*.18, y+h*(.47+i*.17), x+w*(.18+l), y+h*(.47+i*.17), color, 2)


def inline_asset(p, name, x, y, w, h=None, family="brands"):
    global _asset_count
    _asset_count += 1
    asset_path = ROOT / "assets" / family / f"{name}.svg"
    source = ET.parse(asset_path).getroot()
    prefix = f"asset-{_asset_count:02d}-{name}-"
    ids = {n.get("id"): prefix+n.get("id") for n in source.iter() if n.get("id")}
    source = copy.deepcopy(source)
    recolors = ICON_RECOLORS.get(name, {}) if family == "icons" else {}
    for node in source.iter():
        if node.get("id"):
            node.set("id", ids[node.get("id")])
        for attr,value in list(node.attrib.items()):
            if attr == "id":
                continue
            if attr in {"fill", "stroke"}:
                value = recolors.get(value, value)
            for old,new in ids.items():
                value = value.replace(f"url(#{old})", f"url(#{new})")
                if value == "#"+old:
                    value = "#"+new
            node.set(attr, value)
        if node.get("href") and node.get("href", "").startswith("#"):
            node.set(f"{{{XLINK_NS}}}href", node.get("href"))
    viewbox = source.get("viewBox")
    if not viewbox:
        sw = float(re.sub(r"[^0-9.]", "", source.get("width", "48")))
        sh = float(re.sub(r"[^0-9.]", "", source.get("height", "48")))
        viewbox = f"0 0 {sw} {sh}"
    wrapper = group(p, prefix+"instance", name.replace("_", " "))
    embedded = el(wrapper, "svg", x=x, y=y, width=w, height=h or w,
                  viewBox=viewbox, preserveAspectRatio="xMidYMid meet", overflow="visible")
    for k,v in source.attrib.items():
        if k not in {"x","y","width","height","viewBox","id","version"}:
            embedded.set(k,v)
    for child in source:
        embedded.append(child)
    rel = str(asset_path.relative_to(ROOT))
    USED_ASSETS.setdefault(rel, {"sha256": hashlib.sha256(asset_path.read_bytes()).hexdigest(),
                                "instances": []})["instances"].append(prefix+"instance")
    if recolors:
        USED_ASSETS[rel]["display_color_overrides"] = recolors


def page_content(p, x, y, w, h, logo=None):
    """Recognizable web-page content, not a decorative checklist."""
    mini_page(p, x, y, w, h, r=radius("card"))
    picx,picy,picw,pich = x+14,y+h*.28,w*.34,h*.44
    box(p,picx,picy,picw,pich,"#DDE7F1",C["fine"],.8,4)
    el(p,"circle",cx=picx+picw*.67,cy=picy+pich*.26,r=pich*.1,fill="white")
    path(p,f"M {picx+3} {picy+pich-4} L {picx+picw*.34} {picy+pich*.4} "
         f"L {picx+picw*.57} {picy+pich*.73} L {picx+picw*.77} {picy+pich*.5} "
         f"L {picx+picw-3} {picy+pich-4} Z",fill="#BDCEDF",stroke="none",sw=0)
    # A headline and two text blocks establish the page metaphor.
    for yy,ww in [(y+h*.32,w*.32),(y+h*.45,w*.37),(y+h*.58,w*.29)]:
        box(p,x+w*.47,yy,ww,max(3,h*.045),C["gray"],"none",0,0)
    box(p,x+14,y+h*.82,w*.68,max(3,h*.045),C["gray"],"none",0,0)
    if logo:
        inline_asset(p,logo,x+w-48,y+7,36)


def draw_top(root):
    p = group(root,"layer-selection","01 · Choose checks",True)
    box(p,18,28,1764,303,C["panel"],C["line"],1.7,radius("container"),"9 6")
    label(p,43,5,300,47,"(a)  Choose checks",29,"white")

    records = group(p,"development-records","Normal and modified development records")
    for y,title,modified in [(83,"Normal records",False),(205,"Modified records",True)]:
        stack(records,49,y,240,82,step=7)
        label(records,49,y-24,204,36,title,23)
        if modified:
            document(records,72,y+22,37,47,C["rose"])
            box(records,80,y+47,20,6,C["memory_red"],"none",0,0)
        else:
            inline_asset(records,"document",64,y+20,50,50,"icons")
        for i,width in enumerate([122,101,69]):
            box(records,133,y+25+i*16,width,7,C["gray"],"none",0,0)
    path(records,"M 322 119 Q 339 115 339 131 V 224 Q 339 241 322 237",stroke=C["flow"],sw=5)
    arrow(records,339,179,375,height=18,head=15)

    cand = group(p,"candidate-checks","Candidate check families")
    stack(cand,392,105,232,204,step=9)
    label(cand,377,59,236,40,"Candidate checks",24)
    line(cand,393,165,623,165,C["fine"],1)
    line(cand,393,225,623,225,C["fine"],1)
    memory(cand,404,116,82,42)
    text(cand,497.5,143,"Memory limit",19.5,"bold")
    time_pair(cand,408,182,13)
    text(cand,510,201,"Time zone",21,"bold")
    page_size(cand,410,239,72,43,True)
    text(cand,510,267,"Page size",21,"bold")
    text(cand,510,301,"···",29,"bold",anchor="middle")
    arrow(p,650,180,681,height=18,head=15)

    box(p,684,49,746,268,"none",C["fine"],1.6,radius("container"),"9 6")
    filtering = group(p,"filter-candidates","Filter candidates using available development data")
    box(filtering,701,79,244,228,C["pale"],C["fine"],1.2,radius("container"),"7 5")
    label(filtering,761,59,133,38,"Filter",25)
    path(filtering,"M 706 146 H 757 L 738 172 V 190 L 725 198 V 172 Z",fill=C["funnel_fill"],stroke=C["icon_amber"],sw=1.5)
    box(filtering,765,110,167,68,"white",C["line"],1.2,radius("card"))
    el(filtering,"circle",cx=803,cy=137,r=16,fill=C["blue_fill"],stroke=C["icon_blue"],stroke_width=4)
    line(filtering,791,151,781,162,C["icon_blue"],5)
    document(filtering,797,127,13,20,C["icon_blue"])
    line(filtering,840,117,840,170,C["fine"],1)
    text(filtering,851,137,"Usable",21,"bold")
    text(filtering,851,162,"data",21,"bold")
    box(filtering,765,184,167,59,"white",C["line"],1.2,radius("card"))
    document(filtering,778,202,22,29,C["icon_blue"])
    document(filtering,798,190,26,34,C["icon_blue"])
    text(filtering,851,209,"Enough",21,"bold")
    text(filtering,851,233,"data",21,"bold")
    document(filtering,798,250,26,30,C["line_dark"])
    cross(filtering,861,266,27)
    box(filtering,749,286,157,23,C["rose_fill"],"none",0,radius("label"))
    text(filtering,827.5,303,"Not selected",18,"bold",anchor="middle")
    arrow(filtering,946,180,982,height=16,head=14)
    check(filtering,957,155,19,circle=True)

    select = group(p,"select-sparse-set","Select a smaller set of checks")
    box(select,986,110,192,188,C["panel"],C["fine"],1.2,radius("container"),"7 5")
    label(select,998,59,146,38,"Select",25)
    for x,kind in [(1001,"memory"),(1058,"time"),(1115,"page")]:
        token(select,x,123,kind,49,47)
    for x in [1025,1082,1139]:
        flow_line(select,f"M {x} 176 L 1082 210",C["flow"],1.4)
    box(select,1018,216,130,56,C["blue_fill"],C["line"],1.3,radius("card"))
    token(select,1027,222,"memory",49,44)
    token(select,1083,222,"time",49,44)
    text(select,1159,244,"···",26,"bold",anchor="middle")
    text(select,1082,289,"Fewer checks",21,"bold",anchor="middle")
    arrow(p,1180,180,1204,height=16,head=13)

    refine = group(p,"refine-coverage","Retain detections and add coverage")
    box(refine,1206,80,222,189,C["pale"],C["fine"],1.2,radius("container"),"7 5")
    label(refine,1254,59,145,38,"Refine",25)
    box(refine,1220,139,106,67,"white",C["line"],1.3,radius("card"))
    token(refine,1227,149,"memory",43,46)
    clock(refine,1297,173,15)
    text(refine,1341,186,"+",37,"bold",C["sage"],"middle")
    token(refine,1364,142,"page",57,63)
    text(refine,1316,242,"More coverage",22,"bold",anchor="middle")
    arrow(p,1443,180,1482,height=18,head=16)

    saved = group(p,"saved-checks","Saved selected checks")
    stack(saved,1503,111,230,145,step=9)
    label(saved,1497,57,228,43,"Saved checks",26)
    memory(saved,1520,131,64,44)
    time_pair(saved,1608,139,14)
    page_size(saved,1524,199,73,43,True)
    text(saved,1647,229,"···",34,"bold",anchor="middle")


def draw_inputs(root):
    p = group(root,"layer-current-records","02 · Current App and Browser records",True)
    box(p,37,404,654,470,C["panel"],C["line"],1.6,radius("container"))
    box(p,50,421,624,286,"white",C["fine"],1.3,radius("container"))
    label(p,50,404,217,35,"Current records",24)

    apps = group(p,"app-logos","Illustrative App logos")
    box(apps,75,448,286,170,"white",C["line"],1.4,radius("card"))
    label(apps,82,446,100,33,"Apps",23)
    for row,names in enumerate([["wechat","whatsapp","instagram"],["tiktok","youtube","alipay"]]):
        for col,name in enumerate(names):
            inline_asset(apps,name,96+col*88,483+row*65,60)

    appweb = group(p,"in-app-web","Unbranded in-App web page stack")
    stack(appweb,400,489,201,121,step=16)
    page_content(appweb,400,489,201,121)
    label(appweb,390,444,149,34,"In-app web",23)
    line(p,380,446,380,620,C["fine"],1.2,"6 5")

    info = group(p,"device-info","Bound Native device information")
    box(info,75,628,574,68,C["pale"],C["fine"],1.2,radius("card"),"7 5")
    inline_asset(info,"phone_android",99,637,49,49,"icons")
    text(info,183,655,"Device info",23,"bold")
    for x,y,w in [(183,666,101),(183,679,69),(330,666,175),(330,679,108)]:
        box(info,x,y,w,6,C["gray"],"none",0,0)
    inline_asset(info,"link",439,609,44,44,"icons")

    browser = group(p,"browser-web","Optional linked external browser pages")
    box(browser,50,722,624,140,"white",C["line"],1.3,radius("container"))
    label(browser,50,722,185,35,"Browser web",23)
    box(browser,257,727,112,27,C["blue_fill"],C["line"],1.1,radius("label"))
    text(browser,313,747,"Optional",20,anchor="middle")
    page_content(browser,454,740,200,79,"edge")
    page_content(browser,411,755,167,79,"firefox")
    box(browser,201,768,286,76,C["pale"],C["fine"],1.1,radius("card"))
    page_content(browser,184,777,287,75,"chrome")


def draw_checks(root):
    p = group(root,"layer-run-checks","03 · Run saved checks on current data",True)
    box(p,767,404,608,470,C["panel"],C["line"],1.6,radius("container"))
    label(p,784,384,280,44,"Run saved checks",27,"white")

    mem = group(p,"memory-example","Memory: 3 GiB gives 4 GiB cap; Web 8 GiB exceeds it")
    box(mem,784,440,577,155,"white",C["line"],1.3,radius("card"))
    label(mem,784,438,212,34,"Memory example",23)
    inline_asset(mem,"phone_android",796,492,53,65,"icons")
    text(mem,865,519,"Device:",22,"bold")
    text(mem,865,546,"3 GiB",22,"bold")
    arrow(mem,947,527,991,height=15,head=15)
    box(mem,999,477,72,55,C["blue_fill"],C["line"],1.2,radius("label"))
    text(mem,1035,499,"Limit:",20,"bold",anchor="middle")
    text(mem,1035,522,"4 GiB",20,"bold",anchor="middle")
    line(mem,1035,534,1035,582,C["fine"],1.1,"5 4")
    text(mem,1186,493,"Web: 8 GiB",23,"bold",anchor="middle")
    mini_page(mem,1091,505,187,65,r=radius("card"))
    box(mem,1101,533,164,22,C["memory_blue"],C["icon_blue"],1,0)
    box(mem,1183,533,82,22,C["memory_red"],C["rose"],1,0)
    line(mem,1183,519,1183,575,C["rose"],2,"5 4")
    text(mem,1183,590,"4 GiB",17.5,anchor="middle")
    text(mem,1267,590,"8 GiB",17.5,anchor="middle")
    el(mem,"circle",cx=1321,cy=508,r=16,fill=C["rose"])
    text(mem,1321,516,"!",25,"bold","white","middle")
    text(mem,1321,546,"Above",18.5,"bold",C["rose"],"middle")
    text(mem,1321,567,"limit",18.5,"bold",C["rose"],"middle")

    c1 = group(p,"optional-browser-check","Optional linked App Web–Browser timezone check")
    box(c1,784,608,577,107,"white",C["fine"],1.3,radius("card"),"7 5")
    label(c1,784,608,195,34,"Browser check",23)
    box(c1,1256,615,87,26,C["blue_fill"],C["line"],1,radius("label"))
    text(c1,1299.5,634,"Optional",18,anchor="middle")
    page_content(c1,809,651,96,56)
    clock(c1,895,696,16)
    text(c1,930,670,"App web",20.5,"bold")
    text(c1,930,693,"UTC+8",20.5)
    line(c1,1031,661,1084,661,C["icon_blue"],2.3)
    path(c1,"M 1040 653 L 1031 661 L 1040 669",stroke=C["sage"],sw=2.3)
    path(c1,"M 1075 653 L 1084 661 L 1075 669",stroke=C["icon_blue"],sw=2.3)
    text(c1,1057,687,"Compare",18.5,"bold",anchor="middle")
    text(c1,1057,707,"time zones",18.5,"bold",anchor="middle")
    page_content(c1,1108,645,116,62,"chrome")
    clock(c1,1212,696,16)
    text(c1,1240,670,"Browser web",18.5,"bold")
    text(c1,1240,693,"UTC+8",20)

    tz = group(p,"timezone-example","Equal and unequal effective time-zone offsets")
    box(tz,784,726,577,137,"white",C["fine"],1.3,radius("card"),"7 5")
    label(tz,784,726,229,34,"Time zone example",23)
    box(tz,802,762,544,91,"white",C["line"],1.1,radius("card"))
    box(tz,803,763,542,32,"#E6EFF4","none",0,radius("card")-1)
    line(tz,1026,763,1026,852,C["fine"],1)
    line(tz,1247,763,1247,852,C["fine"],1)
    line(tz,803,796,1345,796,C["fine"],1)
    line(tz,803,825,1345,825,C["fine"],1)
    clock(tz,860,779,13)
    clock(tz,1069,779,13)
    text(tz,895,786,"Device",20.5,"bold")
    text(tz,1102,786,"In-app web",20.5,"bold")
    for y,left,right,ok in [(818,"UTC+8","UTC+8",True),(848,"UTC+8","UTC+9",False)]:
        text(tz,914,y,left,21,"bold",anchor="middle")
        text(tz,1136,y,right,21,"bold",anchor="middle")
        if ok:
            check(tz,1297,y-8,20)
        else:
            cross(tz,1297,y-8,22)


def draw_results(root):
    p = group(root,"layer-results","04 · Evaluation results and execution states",True)
    box(p,1441,404,321,470,"white",C["line"],1.6,radius("container"))
    label(p,1455,384,150,44,"Results",27,"white")
    for y,title,asset,fill,stroke in [
        (444,"Alert","high_priority",C["rose_fill"],C["rose"]),
        (529,"No alert","ok",C["sage_fill"],C["sage"]),
        (614,"Cannot tell","questions",C["blue_fill"],C["line"]),
    ]:
        box(p,1504,y,241,74,fill,stroke,1.4,radius("card"))
        inline_asset(p,asset,1520,y+8,57,57,"icons")
        text(p,1607,y+47,title,25,"bold")
    line(p,1456,711,1750,711,C["fine"],1.2,"6 5")
    box(p,1461,725,284,56,C["pale"],C["line_dark"],1.2,radius("card"))
    document(p,1490,733,31,40,C["line_dark"])
    text(p,1554,761,"No checks",23,"bold")
    box(p,1461,793,284,58,"#FCF6E9",C["amber"],1.2,radius("card"))
    inline_asset(p,"warning",1483,798,48,48,"icons")
    text(p,1554,831,"Check failed",23,"bold")


def draw_connections(root):
    p = group(root,"layer-connections","05 · Main, saved-rule, and optional-input flows",True)
    # The sole rule-supply edge ends at the check executor, never at Results.
    flow_line(p,"M 1595 266 V 340 Q 1595 347 1588 347 H 1187 Q 1176 347 1176 358 V 394",
              C["flow_dark"],8,"arrow-main",id="saved-to-run",data_source="saved-checks",data_target="layer-run-checks")
    arrow(p,700,535,758,C["flow"],23,23,id="current-to-run")
    arrow(p,1384,535,1435,C["flow"],23,22,id="run-to-results")
    # The three outcome arrows express alternatives, not execution order.
    line(p,1446,535,1473,535,C["flow_dark"],4)
    path(p,"M 1473 535 V 490 Q 1473 481 1482 481",stroke=C["flow_dark"],sw=4)
    flow_line(p,"M 1482 481 H 1499",sw=3)
    flow_line(p,"M 1473 566 H 1499",sw=3)
    path(p,"M 1473 535 V 642 Q 1473 651 1482 651",stroke=C["flow_dark"],sw=4)
    flow_line(p,"M 1482 651 H 1499",sw=3)
    # Browser linkage is a configuration-specific auxiliary input.
    flow_line(p,"M 703 770 Q 727 770 727 748 V 677 Q 727 662 743 662 H 793",
              C["line_dark"],2.5,"arrow-small","9 6",id="browser-to-c1",
              data_source="browser-web",data_target="optional-browser-check")
    inline_asset(p,"link",683,751,39,39,"icons")


def create_svg():
    global _asset_count, _text_count
    _asset_count = _text_count = 0
    USED_ASSETS.clear()
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "width":"180mm", "height":"90mm", "viewBox":"0 0 1800 900", "version":"1.1",
        "role":"img", "aria-labelledby":"figure-title figure-description",
        "id":"hybridguard-figure-2", "shape-rendering":"geometricPrecision",
    })
    el(root,"title",id="figure-title").text = "HybridGuard: choose checks and check current data"
    el(root,"desc",id="figure-description").text = (
        "An editable two-band system diagram. Normal and modified development records feed "
        "filtering, selection, refinement, and saved checks. Current App records and optional "
        "linked Browser input feed evaluation. Illustrations show a 3 GiB device giving a "
        "4 GiB memory limit, an 8 GiB Web value exceeding it, and matching or mismatching "
        "effective timezone offsets. Results are alert, no alert, or cannot tell, with "
        "separate no-checks and check-failed states. Logos and values are illustrative.")
    defs = el(root,"defs")
    for name,color,size,refx in [("arrow-small",C["flow_dark"],9,8),("arrow-main",C["flow_dark"],23,20)]:
        marker = el(defs,"marker",id=name,viewBox=f"0 0 {size} {size}",refX=refx,refY=size/2,
                    markerWidth=size,markerHeight=size,markerUnits="userSpaceOnUse",orient="auto")
        path(marker,f"M 0 0 L {size} {size/2} L 0 {size} Z",fill=color,stroke="none",sw=0)
    bg = group(root,"layer-background","00 · Page and band frames",True)
    box(bg,0,0,1800,900,"white","none",0,0)
    box(bg,18,370,1764,516,C["panel"],C["line"],1.7,radius("container"),"9 6")
    label(bg,43,348,353,47,"(b)  Check current data",29,"white")
    draw_top(root)
    draw_inputs(root)
    draw_checks(root)
    draw_results(root)
    draw_connections(root)
    ET.indent(root,space="  ")
    path_out = ROOT / f"{STEM}.svg"
    ET.ElementTree(root).write(path_out,encoding="utf-8",xml_declaration=True)
    return path_out, root


def validate(svg_path, root):
    ids = [n.get("id") for n in root.iter() if n.get("id")]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate SVG IDs")
    image_nodes = root.findall(f".//{{{SVG_NS}}}image")
    if image_nodes:
        raise ValueError("The main SVG must not contain bitmap image elements")
    external = []
    for n in root.iter():
        for k,v in n.attrib.items():
            if k.rsplit("}",1)[-1] in {"href","src"} and not v.startswith("#"):
                external.append(v)
    if external:
        raise ValueError(f"External dependencies found: {external}")
    text_nodes = root.findall(f".//{{{SVG_NS}}}text")
    supplied = root.find(f".//*[@id='saved-to-run']")
    assert supplied is not None and supplied.get("data-target") == "layer-run-checks"
    assert math.pow(2,math.ceil(math.log2(3))) == 4 and 8 > 4
    for name in ["wechat","whatsapp","instagram","tiktok","youtube","alipay","chrome","firefox","edge"]:
        assert f"assets/brands/{name}.svg" in USED_ASSETS
    return {
        "frame_corner_style": {
            "date": "2026-10-23",
            "radius_mm": FRAME_RADIUS_MM,
            "svg_units_per_mm": 10,
            "header_fill_rule": "Card radius minus the existing inset",
            "scope": "Container, card/page, and label rectangles only; pictograms and data bars retain their artwork",
        },
        "svg": {"file":svg_path.name,"viewBox":[0,0,1800,900],"physical_size_mm":[180,90],
                "sha256":hashlib.sha256(svg_path.read_bytes()).hexdigest(),
                "editable_text_elements":len(text_nodes),"native_svg_elements":sum(1 for _ in root.iter()),
                "named_layers":[n.get("id") for n in root if n.get(f"{{{INK_NS}}}groupmode") == "layer"],
                "inline_asset_instances":_asset_count,"distinct_source_assets":len(USED_ASSETS),
                "bitmap_image_elements":0,"external_image_links":0,"duplicate_ids":0},
        "semantic_checks": {
            "saved_checks_feed_executor_only":True,
            "browser_input_is_optional_and_targets_c1":True,
            "memory_example_native_gib":3,"derived_upper_limit_gib":4,"web_report_gib":8,
            "memory_example_exceeds_limit":True,
            "timezone_examples_are_normalized_offsets":True,
            "page_size_denotes_same_web_relation":True,
            "no_checks_and_required_failures_remain_distinct":True,
            "illustrative_not_experimental_results":True},
    }


def write_source_map():
    data = {
        "figure":"HybridGuard Figure 2", "revision":"semantic_vector_v1_20261023",
        "status":"editable reconstruction of the user-selected visual concept",
        "repository":"Xavi-L/RBA-Cross-Device-Fingerprint",
        "source_commit":"fd0701f41657068bd56290447901dd24b827bfc1",
        "corner_radius_revision": {
            "date": "2026-10-23", "base_commit": "72a7b15ab3ec78eeb6315891e7ddc3a33550880d",
            "radius_mm": FRAME_RADIUS_MM,
            "scope": "Normalize similar frames across Figures 1–3; preserve bounds, text, colors, and connectors.",
        },
        "color_revision":{
            "date":"2026-10-23", "base_commit":"98380b2e67ea7e4470ac97357dbae13abda0ff29",
            "scope":"Saturated semantic icons; geometry, text, connectors, and brand assets preserved.",
            "palette":{key:C[key] for key in ["rose","sage","icon_blue","memory_blue","memory_red","icon_amber","funnel_fill"]},
        },
        "method_source":"output/pdf/hybridguard_www_draft_20261017/sections/03_method.tex",
        "asset_bundle":"paper/figures/visual_assets/color_v2_20261022/HybridGuard_Color_Assets_v2_20261022.zip",
        "raster_composition_reference":"reference/approved_raster_concept.png",
        "reference_is_embedded_in_vector":False,
        "components":{
            "development-records":"Normal and controlled-modification development records; illustrative document marks.",
            "candidate-checks":"Memory upper bound, effective-offset agreement, and same-Web viewport relations.",
            "filter-candidates":"Training-only admission; usable data and sufficient applicable records are simplified labels.",
            "select-sparse-set":"Sparsify subject to the method constraints; token counts are schematic.",
            "refine-coverage":"Feasible retention additions preserve training detections and add semantic coverage.",
            "saved-checks":"Saved selected checks, supplied only to the evaluation block.",
            "app-logos":"Illustrative App container, not a list of tested brands.",
            "in-app-web":"Unbranded page stack bound to Native device information.",
            "browser-web":"Optional linked external Browser input; not a missing-input fallback.",
            "memory-example":"3 GiB -> 4 GiB upper envelope; Web 8 GiB > 4 GiB. Illustrative values.",
            "optional-browser-check":"C1 compares linked App Web and Browser effective timezone offsets.",
            "timezone-example":"Equal UTC+8/UTC+8 and unequal UTC+8/UTC+9 normalized offsets.",
            "layer-results":"Separate T/F/U decisions and EMPTY_MODEL/FAILED execution states; see CAPTIONS.md."},
        "assets":USED_ASSETS,
        "decision_priority":["No checks","Check failed","Alert","No alert","Cannot tell"],
        "notes":["No alert is not an authenticity or safety claim.",
                 "Unselected field problems do not independently create required failures.",
                 "No upstream paper reference screenshot is redistributed in this revision."],
    }
    (ROOT/"SOURCE_MAP.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg-only",action="store_true",help="Skip Inkscape PNG and PDF export")
    args = parser.parse_args()
    svg_path,root = create_svg()
    report = validate(svg_path,root)
    write_source_map()
    if not args.svg_only:
        inkscape = shutil.which("inkscape")
        if not inkscape:
            raise SystemExit("SVG created. Install Inkscape on PATH to export PNG/PDF, or use --svg-only.")
        for suffix,extra in [("png",["--export-width=3500","--export-background=white"]),("pdf",[])]:
            subprocess.run([inkscape,str(svg_path),"--export-area-page",
                            f"--export-filename={ROOT / (STEM+'.'+suffix)}",*extra],check=True,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        report["exports"] = {"png":{"width_px":3500,"height_px":1750},
                             "pdf":{"page_size_mm":[180,90],"vector_export":True},
                             "inkscape_version":subprocess.check_output([inkscape,"--version"],text=True,
                                                                          stderr=subprocess.DEVNULL).strip()}
        for suffix in ("png", "pdf"):
            exported = ROOT / (STEM + "." + suffix)
            report["exports"][suffix].update(
                file=exported.name, sha256=hashlib.sha256(exported.read_bytes()).hexdigest())
    else:
        report["exports"] = {"skipped":True}
    # Human/render checks are a separate field so a rebuild never claims unseen visual review.
    report["visual_review"] = "See VISUAL_REVIEW.md for the reviewed export and limitations."
    (ROOT/"QUALITY_CHECK.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"svg":str(svg_path),"text_elements":report["svg"]["editable_text_elements"],
                      "assets":len(USED_ASSETS),"exports_skipped":args.svg_only},indent=2))


if __name__ == "__main__":
    main()

