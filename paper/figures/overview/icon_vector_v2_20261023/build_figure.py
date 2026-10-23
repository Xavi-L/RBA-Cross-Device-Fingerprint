#!/usr/bin/env python3
"""Build Figure 1: a compact, editable three-view overview in Figure 2's style.

Python standard library only; Inkscape is required for PNG/PDF export.
Run from any directory. Use --svg-only to skip exports.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
STEM = "HybridGuard_Fig1_overview_v2"
SVG = "http://www.w3.org/2000/svg"
INK = "http://www.inkscape.org/namespaces/inkscape"
XLINK = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG)
ET.register_namespace("inkscape", INK)
ET.register_namespace("xlink", XLINK)

W, H = 1000, 660
C = {
    "ink": "#23323C", "line": "#718E9D", "line_dark": "#526E7F",
    "fine": "#9DB1BA", "panel": "#FAFCFD", "pale": "#F4F7F9",
    "blue_fill": "#EDF4F8", "blue": "#1976D2", "blue_mid": "#93C5FD",
    "red": "#E53935", "red_mid": "#F87171", "green": "#16A34A",
    "green_fill": "#EFF6F0", "amber": "#D99000", "gold": "#F4B52C",
    "amber_fill": "#FFF7E6", "gray": "#AAB3BC", "context": "#8A959F",
}
ASSETS = {}
TEXT_COUNT = 0


def node(parent, tag, **attrs):
    e = ET.SubElement(parent, f"{{{SVG}}}{tag}")
    for key, value in attrs.items():
        if value is not None:
            e.set(key.replace("_", "-"), str(value))
    return e


def group(parent, name, label, layer=False):
    e = node(parent, "g", id=name)
    e.set(f"{{{INK}}}label", label)
    if layer:
        e.set(f"{{{INK}}}groupmode", "layer")
    return e


def box(p, x, y, w, h, fill="white", stroke=None, sw=1.8, r=8, dash=None):
    return node(p, "rect", x=x, y=y, width=w, height=h, rx=r,
                fill=fill, stroke=stroke or C["line"], stroke_width=sw,
                stroke_dasharray=dash)


def path(p, d, fill="none", color=None, sw=2, **attrs):
    return node(p, "path", d=d, fill=fill, stroke=color or C["line"],
                stroke_width=sw, stroke_linecap="round", stroke_linejoin="round", **attrs)


def line(p, x1, y1, x2, y2, color=None, sw=2, dash=None, **attrs):
    return node(p, "line", x1=x1, y1=y1, x2=x2, y2=y2,
                stroke=color or C["line"], stroke_width=sw,
                stroke_dasharray=dash, stroke_linecap="round", **attrs)


def text(p, x, y, value, size=30, bold=False, color=None, anchor="start"):
    global TEXT_COUNT
    TEXT_COUNT += 1
    e = node(p, "text", id=f"label-{TEXT_COUNT:03d}", x=x, y=y,
             font_family="Nimbus Sans, Arial, Liberation Sans, sans-serif",
             font_size=size, font_weight="bold" if bold else "normal",
             fill=color or C["ink"], text_anchor=anchor)
    e.text = value
    return e


def label(p, x, y, w, h, value, size=32, fill=None, stroke=None, color=None):
    box(p, x, y, w, h, fill or C["blue_fill"], stroke or C["line_dark"], r=8)
    text(p, x+w/2, y+h/2+size*.34, value, size, True, color, "middle")


def stack(p, x, y, w, h, levels=3, step=9):
    for i in range(levels-1, 0, -1):
        box(p, x+i*step, y-i*step, w, h, C["pale"], r=8)
    box(p, x, y, w, h, "white", r=8)


def clock(p, x, y, r, color=None):
    color = color or C["blue"]
    node(p, "circle", cx=x, cy=y, r=r, fill="white", stroke=color, stroke_width=2.8)
    path(p, f"M {x} {y-r*.64} V {y} L {x+r*.46} {y+r*.27}", color=color, sw=3.2)


def mini_page(p, x, y, w, h):
    box(p, x, y, w, h, "white", C["line_dark"], 1.8, 4)
    box(p, x+1.2, y+1.2, w-2.4, h*.23, C["blue_fill"], "none", 0, 3)
    line(p, x, y+h*.25, x+w, y+h*.25, C["line"], 1.4)
    for i in range(3):
        node(p, "circle", cx=x+7+i*6, cy=y+h*.12, r=1.8, fill=C["fine"])


def memory_limit(p, x, y, w=94, h=55):
    mini_page(p, x, y, w, h)
    box(p, x+8, y+h*.48, w*.82, h*.28, C["blue_mid"], C["blue"], 1.2, 0)
    box(p, x+w*.54, y+h*.48, w*.36, h*.28, C["red_mid"], C["red"], 1.2, 0)
    line(p, x+w*.54, y+h*.3, x+w*.54, y+h*.93, C["red"], 2.4, "4 3")


def viewport(p, x, y, w=78, h=61):
    box(p, x+7, y-7, w, h, C["pale"], C["fine"], 1.4, 4)
    mini_page(p, x, y, w, h)
    for yy,left,right in [(y+h*.5,x+14,x+w-14),(y+h*.8,x+8,x+w-8)]:
        line(p,left,yy,right,yy,C["blue"],2.2)
        path(p,f"M {left+6} {yy-4} L {left} {yy} L {left+6} {yy+4}",color=C["blue"],sw=2.2)
        path(p,f"M {right-6} {yy-4} L {right} {yy} L {right-6} {yy+4}",color=C["blue"],sw=2.2)


def compare(p, ident, x1, y1, x2, y2, color, sw, head, dash=None, source=None, target=None, scope=None):
    g = group(p, ident, f"{scope} comparison")
    g.set("data-source", source)
    g.set("data-target", target)
    g.set("data-scope", scope)
    line(g,x1,y1,x2,y2,color,sw,dash)
    ux,uy=x2-x1,y2-y1
    length=math.hypot(ux,uy)
    ux,uy=ux/length,uy/length
    # Manually drawn open arrowheads communicate comparison, not a data pipeline.
    for x,y,sgn in [(x1,y1,1),(x2,y2,-1)]:
        bx,by=x+sgn*ux*head,y+sgn*uy*head
        px,py=-uy*head*.55,ux*head*.55
        path(g,f"M {bx+px} {by+py} L {x} {y} L {bx-px} {by-py}",color=color,sw=sw)
    return g


def asset(p, name, x, y, size):
    src=ROOT/"assets"/"brands"/f"{name}.svg"
    original=ET.parse(src).getroot()
    art=copy.deepcopy(original)
    prefix=f"brand-{name}-"
    ids={e.get("id"):prefix+e.get("id") for e in art.iter() if e.get("id")}
    for e in art.iter():
        if e.get("id"):
            e.set("id",ids[e.get("id")])
        for k,v in list(e.attrib.items()):
            if k=="id": continue
            for old,new in ids.items():
                v=v.replace(f"url(#{old})",f"url(#{new})")
                if v=="#"+old: v="#"+new
            e.set(k,v)
        if e.get("href", "").startswith("#"):
            e.set(f"{{{XLINK}}}href",e.get("href"))
    wrapper=group(p,f"{prefix}instance",f"Illustrative {name} logo")
    embedded=node(wrapper,"svg",x=x,y=y,width=size,height=size,
                  viewBox=art.get("viewBox", "0 0 512 512"),preserveAspectRatio="xMidYMid meet")
    for k,v in art.attrib.items():
        if k not in {"x","y","width","height","viewBox","id","version"}:
            embedded.set(k,v)
    for child in art: embedded.append(child)
    ASSETS[f"assets/brands/{name}.svg"]={"sha256":hashlib.sha256(src.read_bytes()).hexdigest(),
                                       "instance":f"{prefix}instance","original_colors":True}


def draw_native(root):
    p=group(root,"native-view","01 - Device and OS observations",True)
    stack(p,56,282,270,203,3,8)
    label(p,48,258,262,42,"Device & OS",32)
    phone=group(p,"device-phone","Device icon with OS settings")
    box(phone,89,310,75,129,C["line_dark"],C["line_dark"],2.3,10)
    box(phone,96,323,61,97,C["blue"],"none",0,4)
    line(phone,116,317,138,317,"white",2)
    node(phone,"circle",cx=126.5,cy=430,r=3,fill="white")
    points=[]
    for i in range(32):
        angle=2*math.pi*i/32
        radius=23 if i%4 in {1,2} else 18
        points.append(f"{126.5+radius*math.cos(angle):.3f},{370+radius*math.sin(angle):.3f}")
    node(phone,"polygon",points=" ".join(points),fill=C["gold"],stroke=C["amber"],stroke_width=1.5)
    node(phone,"circle",cx=126.5,cy=370,r=7.5,fill="white")
    chip=group(p,"native-memory-chip","Physical memory icon")
    box(chip,213,320,61,49,C["blue"],C["blue"],1.8,5)
    box(chip,225,331,37,27,C["blue_mid"],"white",1.6,2)
    for x in [223,235,247,259,271]:
        line(chip,x,313,x,320,C["blue"],2.6)
        line(chip,x,369,x,376,C["blue"],2.6)
    for y in [330,342,354,366]:
        line(chip,206,y,213,y,C["blue"],2.6)
        line(chip,274,y,281,y,C["blue"],2.6)
    clock(p,244,416,26)
    text(p,191,472,"Native APIs",29,False,anchor="middle")


def draw_web(root):
    p=group(root,"app-web-view","02 - Embedded webpage observations",True)
    stack(p,638,105,304,177,3,9)
    label(p,628,78,296,42,"In-app webpage",32)
    mini_page(p,657,135,266,100)
    box(p,672,171,74,50,"#DDE7F1",C["fine"],1.1,4)
    node(p,"circle",cx=729,cy=182,r=5,fill=C["gold"])
    path(p,"M 677 216 L 697 187 L 717 208 L 729 196 L 741 216 Z",fill=C["blue_mid"],color="none",sw=0)
    for y,w in [(176,118),(193,139),(210,95)]:
        box(p,765,y,w,7,C["gray"],"none",0,0)
    text(p,790,268,"App Web (JS)",29,False,anchor="middle")


def draw_host(root):
    p=group(root,"webview-host","03 - App container and host view",True)
    stack(p,638,452,304,167,2,9)
    label(p,628,430,269,42,"App container",32)
    for name,x in [("wechat",666),("youtube",755),("alipay",844)]:
        asset(p,name,x,486,50)
    # A nested viewport makes the containing-view relationship visible.
    mini_page(p,662,544,256,30)
    box(p,678,558,224,10,"white",C["blue"],1.6,2)
    text(p,790,608,"WebView Host",29,False,anchor="middle")


def draw_relations(root):
    p=group(root,"relationship-edges","04 - Three different relationship scopes",True)
    compare(p,"native-web-current",345,322,614,239,C["blue"],5.6,17,
            source="native-view",target="app-web-view",scope="current-detector")
    compare(p,"host-web-separate",794,302,794,416,C["amber"],3.2,12,"11 8",
            source="webview-host",target="app-web-view",scope="separate-study")
    g=group(p,"native-host-context","Shared execution context; not a detection rule")
    g.set("data-source","native-view"); g.set("data-target","webview-host")
    g.set("data-scope","context-only")
    line(g,346,466,613,541,C["context"],2.6,"2 9")
    # Short callout only: the dotted edge stays a visibly slanted triangle side.
    line(g,371,548,432,490,C["context"],1.8)

    current=group(root,"current-checks-label","05 - Current Native-Web check families",True)
    text(current,56,103,"Cross-check reports",34,True,C["blue"])
    label(current,56,120,257,37,"Used by detector",28,C["green_fill"],C["green"],C["green"])
    memory_limit(current,78,165,94,54)
    text(current,125,243,"Memory limit",28,False,anchor="middle")
    clock(current,285,191,24)
    text(current,321,201,"=",30,True,C["blue"],"middle")
    clock(current,357,191,24)
    text(current,321,243,"Time zone",28,False,anchor="middle")

    separate=group(root,"separate-study-label","06 - Host-Web page geometry, separate study",True)
    viewport(separate,377,335,78,61)
    text(separate,481,355,"Page-size check",30,True)
    label(separate,480,369,220,36,"Separate study",28,C["amber_fill"],C["amber"],C["amber"])

    context=group(root,"shared-context-label","07 - Context only annotation",True)
    text(context,57,556,"Shared app context",31,True,C["line_dark"])
    text(context,57,598,"No detection rule",29,False,C["line_dark"])


def build_svg():
    global TEXT_COUNT
    TEXT_COUNT=0
    ASSETS.clear()
    root=ET.Element(f"{{{SVG}}}svg",{
        "width":"86mm","height":"56.76mm","viewBox":f"0 0 {W} {H}","version":"1.1",
        "id":"hybridguard-figure-1","role":"img","aria-labelledby":"figure-title figure-description",
        "shape-rendering":"geometricPrecision"})
    node(root,"title",id="figure-title").text="Three complementary views of one Android app execution"
    node(root,"desc",id="figure-description").text=(
        "Compact triangle with Device and OS at left, an in-app webpage at upper right, "
        "and its app container at lower right. A thick solid blue double-ended comparison "
        "marks memory-bound and timezone relations used by the current detector. A thinner "
        "dashed amber comparison marks a separate host-web page-size study. A gray dotted "
        "line marks shared execution context only, not a detection rule. App logos are illustrative.")
    bg=group(root,"background","00 - Shared app execution boundary",True)
    box(bg,0,0,W,H,"white","none",0,0)
    box(bg,18,28,964,615,C["panel"],C["line"],1.8,10,"9 6")
    label(bg,42,5,487,47,"One app run, three views",34,"white")
    draw_native(root)
    draw_web(root)
    draw_host(root)
    draw_relations(root)
    ET.indent(root,space="  ")
    target=ROOT/(STEM+".svg")
    ET.ElementTree(root).write(target,encoding="utf-8",xml_declaration=True)
    return target,root


def inspect_svg(svg_path, root):
    ids=[e.get("id") for e in root.iter() if e.get("id")]
    if len(ids)!=len(set(ids)): raise ValueError("Duplicate SVG IDs")
    if root.findall(f".//{{{SVG}}}image"): raise ValueError("Raster images are not permitted")
    for e in root.iter():
        for k,v in e.attrib.items():
            if k.rsplit("}",1)[-1] in {"href","src"} and not v.startswith("#"):
                raise ValueError(f"External dependency: {v}")
    text_nodes=root.findall(f".//{{{SVG}}}text")
    return {
        "svg":{"file":svg_path.name,"sha256":hashlib.sha256(svg_path.read_bytes()).hexdigest(),
               "viewBox":[0,0,W,H],"physical_size_mm":[86,56.76],
               "editable_text_elements":len(text_nodes),
               "native_svg_elements":sum(1 for _ in root.iter()),
               "text_size_range_viewbox":[min(float(e.get("font-size")) for e in text_nodes),
                                          max(float(e.get("font-size")) for e in text_nodes)],
               "raster_image_elements":0,"external_image_links":0,"duplicate_ids":0},
        "relationship_scopes":{
            "native-web-current":"Memory upper-bound and effective-timezone checks in the current detector",
            "host-web-separate":"Implemented/evaluated separately; outside current detector and candidate pool",
            "native-host-context":"Shared context only; no independent detection rule"},
        "visual_review":"See VISUAL_REVIEW.md; rebuilding does not claim a new visual review.",
    }


def write_source_map():
    metadata={
        "figure":"HybridGuard Figure 1","revision":"icon_vector_v2_20261023",
        "status":"new redraw for author review; earlier frozen figure preserved",
        "repository":"Xavi-L/RBA-Cross-Device-Fingerprint",
        "base_commit":"b49c53ffcb2eaacf1cf9fbaff43b99d18fc469a1",
        "semantic_source":"paper/figures/overview/frozen_v1/CAPTIONS.md",
        "method_source":"output/pdf/hybridguard_www_draft_20261017/sections/03_method.tex",
        "visual_style_source":"paper/figures/system_design/semantic_vector_v1_20261023",
        "palette":C,"assets":ASSETS,
        "custom_vectors":["phone with settings gear","memory chip","clock","memory upper-bound illustration",
                          "nested viewport","webpage content","open comparison arrows","layered frames"],
        "notes":["Logos illustrate app categories, not tested brands.",
                 "Arrowheads indicate comparison, not communication or mutual authentication.",
                 "No surface is trusted ground truth; one app run does not imply atomic sampling.",
                 "Single-view checks, optional linked Browser, and decisions remain in Figure 2."]}
    (ROOT/"SOURCE_MAP.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg-only",action="store_true")
    args=parser.parse_args()
    svg_path,root=build_svg()
    report=inspect_svg(svg_path,root)
    write_source_map()
    if not args.svg_only:
        inkscape=shutil.which("inkscape")
        if not inkscape: raise SystemExit("Install Inkscape for PNG/PDF export, or use --svg-only.")
        for suffix,extra in [("png",["--export-width=3000","--export-background=white"]),("pdf",[])]:
            dest=ROOT/(STEM+"."+suffix)
            subprocess.run([inkscape,str(svg_path),"--export-area-page",f"--export-filename={dest}",*extra],
                           check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        report["exports"]={"png":{"width_px":3000,"height_px":1980},
                           "pdf":{"page_size_mm":[86,56.76]},
                           "inkscape_version":subprocess.check_output([inkscape,"--version"],text=True,
                                                                         stderr=subprocess.DEVNULL).strip()}
    else:
        report["exports"]={"skipped":True}
    (ROOT/"QUALITY_CHECK.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"svg":str(svg_path),"editable_text_elements":report["svg"]["editable_text_elements"],
                      "original_logo_assets":len(ASSETS),"exports_skipped":args.svg_only},indent=2))


if __name__=="__main__":
    main()
