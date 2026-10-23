#!/usr/bin/env python3
"""Rebuild HybridGuard Figure 3 as editable vector artwork (no raster inputs)."""
from pathlib import Path
from html import escape
import argparse

P = {"ink":"#343434", "muted":"#687078", "blue":"#507cc4",
     "teal":"#3d756c", "amber":"#bd8b47", "light":"#d5d9df"}

def build():
    out = []
    def add(s): out.append(s)
    def txt(x,y,s,size=28,color="ink",weight="400",anchor="start",style=""):
        add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{P.get(color,color)}" font-weight="{weight}" text-anchor="{anchor}"{style}>{escape(s)}</text>')
    def line(x1,y1,x2,y2,color="muted",sw=2,dash=None,markers=None):
        extra = f' stroke-dasharray="{dash}"' if dash else ''
        if markers: extra += f' marker-end="url(#{markers})"'
        add(f'<path d="M{x1} {y1}L{x2} {y2}" fill="none" stroke="{P.get(color,color)}" stroke-width="{sw}" stroke-linecap="round"{extra}/>')
    def circle(x,y,r=7,color="amber",fill=None):
        add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{P.get(fill or color,fill or color)}" stroke="{P.get(color,color)}" stroke-width="2.2"/>')
    def rect(x,y,w,h,color,fill="white",sw=2.5):
        add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{P.get(color,color)}" stroke-width="{sw}"/>')
    def dim(x1,x2,y,label,color):
        line(x1,y-6,x1,y+6,color,1.7)
        line(x2,y-6,x2,y+6,color,1.7)
        line(x1,y,x2,y,color,1.7)
        txt((x1+x2)/2,y+29,label,26,color,anchor="middle")
    add('<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="62mm" viewBox="0 0 1800 620" role="img" aria-labelledby="title desc">')
    add('<title id="title">HybridGuard: three mechanisms of contextual integrity evidence</title>')
    add('<desc id="desc">Three schematic panels explain the value of references, not measured outcomes. A synthetic Native memory of 4 GiB and Web report of 8 GiB do not trigger a global greater-than-8 check, but violate the Native-derived 4 GiB envelope. Normal timezone changes move Native and Web effective offsets together after sign normalization; a Web-only edit changes only the Web offset. The Host geometry specialist compares viewport dimensions after conversion against a container bound; it remains a standalone study outside the integrated detector. All examples assume valid, applicable observations.</desc>')
    add('<style>text{font-family:"Nimbus Roman","Times New Roman",Times,serif}</style>')
    add('<defs>')
    for key in ['blue','amber','muted','teal']:
        add(f'<marker id="arrow-{key}" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="10" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto"><path d="M1 1L9 4L1 7Z" fill="{P[key]}"/></marker>')
    add('</defs><rect width="1800" height="620" fill="white"/>')
    line(600,18,600,563,"light",1.8)
    line(1200,18,1200,563,"light",1.8)

    # Panel A. A pair of identical rulers compares the same report to two limits.
    add('<g id="device-context">')
    txt(30,46,'(a) Device context',33,weight='700')
    txt(30,90,'Native: 4 GiB   ·   Web: 8 GiB',27,'muted')
    txt(30,147,'Global threshold',29,weight='700')
    line(76,210,535,210,'light',2.2)
    line(480,171,480,237,'muted',2.2,'5 5')
    circle(480,210,8.5,'amber')
    txt(480,170,'8 GiB limit',26,'muted',anchor='middle')
    txt(480,266,'Web 8 GiB',26,'amber',anchor='middle')
    txt(30,271,'8 = 8: no trigger',28,'muted')
    txt(30,330,'Native-derived envelope',29,weight='700')
    line(76,390,535,390,'light',2.2)
    line(278,371,278,422,'blue',2.6)
    circle(480,390,8.5,'amber')
    txt(278,356,'4 GiB bound',26,'blue',anchor='middle')
    txt(480,438,'Web 8 GiB',26,'amber',anchor='middle')
    txt(30,481,'8 > 4: trigger',28,'amber',weight='700')
    txt(300,550,'Plausible alone, incompatible together',27,weight='700',anchor='middle')
    add('</g>')

    # Panel B. Offsets are already transformed to one sign convention.
    add('<g id="legitimate-cochange">')
    txt(630,46,'(b) Legitimate co-change',33,weight='700')
    txt(630,90,'Offsets in the same sign convention',27,'muted')
    txt(630,147,'Normal system change',29,'teal',weight='700')
    for y,label in [(199,'Native'),(249,'Web')]:
        txt(647,y,label,28)
        txt(826,y,'a',29,'teal',anchor='middle',style=' font-style="italic"')
        line(855,y-9,966,y-9,'teal',2.2,markers='arrow-teal')
        txt(1003,y,'b',29,'teal',anchor='middle',style=' font-style="italic"')
    line(1040,180,1058,180,'teal',1.8)
    line(1058,180,1058,252,'teal',1.8)
    line(1040,252,1058,252,'teal',1.8)
    txt(1082,226,'match',27,'teal')
    txt(630,330,'Web-only edit',29,'amber',weight='700')
    for y,label,a,b,color in [(382,'Native','a','a','muted'),(432,'Web','a','b','amber')]:
        txt(647,y,label,28)
        txt(826,y,a,29,color,anchor='middle',style=' font-style="italic"')
        line(855,y-9,966,y-9,color,2.2,markers='arrow-'+color)
        txt(1003,y,b,29,color,anchor='middle',style=' font-style="italic"')
    line(1040,363,1058,363,'amber',1.8)
    line(1058,363,1058,435,'amber',1.8)
    line(1040,435,1058,435,'amber',1.8)
    txt(1082,409,'differ',27,'amber')
    txt(900,481,'Distinct offsets a and b illustrate the two cases.',26,'muted',anchor='middle')
    txt(900,550,'Separate co-change from a local edit',27,weight='700',anchor='middle')
    add('</g>')

    # Panel C. Shared left edges encode a dimension violation, never a location test.
    add('<g id="container-context">')
    txt(1230,46,'(c) Container context',33,weight='700')
    txt(1230,90,'Standalone study',28,'amber',weight='700')
    txt(1280,149,'Host View',28,'blue',weight='700')
    rect(1280,171,265,185,'blue','#f5f7fb',3)
    rect(1280,212,425,104,'amber','#fbf5eb',3)
    # Host outlines remain visible on both axes; the viewport exceeds width only.
    txt(1300,253,'Reported viewport',27,'amber',weight='700')
    txt(1300,289,'after unit conversion',26,'muted')
    dim(1280,1545,379,'Host size H','blue')
    dim(1280,1705,441,'Viewport size P','amber')
    txt(1500,512,'P > H + ε: trigger',29,'amber',weight='700',anchor='middle')
    txt(1500,550,'Check dimensions against the container',27,weight='700',anchor='middle')
    add('</g>')

    line(30,578,1770,578,'light',1.4)
    txt(900,609,'Illustrative examples on valid, applicable inputs; quantitative results are reported separately.',25,'muted',anchor='middle')
    add('</svg>')
    return '\n'.join(out)+'\n'

if __name__ == '__main__':
    default = Path(__file__).resolve().parents[1]/'output'/'HybridGuard_Fig3_mechanisms_v2.svg'
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,default=default)
    args=ap.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(build(),encoding='utf-8')
    print(args.output)
