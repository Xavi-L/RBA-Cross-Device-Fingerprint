"""Build the isolated Figure 2 v6 candidate from the existing color asset ZIP."""
from pathlib import Path
from zipfile import ZipFile
from html import escape
import json
import re
import colorsys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ARCHIVE = ROOT / 'paper/figures/visual_assets/color_v2_20261022/HybridGuard_Color_Assets_v2_20261022.zip'
PREFIX = 'HybridGuard_Color_Assets_v2_20261022/'
W, H = 1760, 900
INK = '#34444B'
OUTLINE = '#7E9198'
LIGHT = '#E4ECEE'
BLUE = '#718995'
GREEN = '#709780'
RED = '#B77673'
parts = []
assets = set()
text_items = []
serial = 0
state_icons = set()

def blue_fill(color):
    """Change only the hue of the original pastel fill; retain HSL S and L."""
    r,g,b = [int(color[i:i+2],16)/255 for i in [1,3,5]]
    _,lightness,saturation = colorsys.rgb_to_hls(r,g,b)
    channels=colorsys.hls_to_rgb(210/360,lightness,saturation)
    return '#'+''.join(f'{round(c*255):02X}' for c in channels)

def add(s):
    parts.append(s)

def rect(x,y,w,h,fill='white',stroke=OUTLINE,sw=2,r=5,dash=None):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')

def line(x1,y1,x2,y2,color=OUTLINE,sw=2,dash=None):
    add(f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')

def txt(x,y,s,size=24,weight=400,anchor='start',fill=INK):
    text_items.append(s)
    add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{fill}">{escape(s)}</text>')

def path(d,fill='none',stroke=OUTLINE,sw=2,dash=None):
    add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')

def arrow(x1,y1,x2,y2,kind='main'):
    color,sw,marker = (BLUE,6,'main') if kind=='main' else ((INK,2.4,'thin') if kind=='thin' else (GREEN,2.4,'optional'))
    dash=' stroke-dasharray="8 6"' if kind=='optional' else ''
    add(f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="{color}" stroke-width="{sw}"{dash} marker-end="url(#{marker})"/>')

def tick(x,y,s=24,color=GREEN):
    state_icon('check_mark_button_color',x,y,s)

def cross(x,y,s=21,color=RED):
    state_icon('noto_cross_mark',x,y,s)

def state_icon(name,x,y,s):
    state_icons.add(name)
    family='noto-emoji' if name.startswith('noto_') else 'fluent-emoji'
    embed_svg((HERE/'assets/state_icons'/f'{name}.svg').read_text(),x,y,s,s,family+'/'+name)

def embed_svg(raw,x,y,w,h,asset_name):
    global serial
    serial += 1
    el = ET.fromstring(raw)
    ids = {node.attrib['id']:f'a{serial}_{node.attrib["id"]}' for node in el.iter() if 'id' in node.attrib}
    for node in el.iter():
        for k,v in list(node.attrib.items()):
            if k=='id': node.set(k,ids[v])
            else:
                for old,new in ids.items():
                    v=v.replace(f'url(#{old})',f'url(#{new})')
                    if v=='#'+old: v='#'+new
                node.set(k,v)
    el.set('x',str(x));el.set('y',str(y));el.set('width',str(w));el.set('height',str(h))
    el.set('data-asset',asset_name)
    el.set('preserveAspectRatio','xMidYMid meet')
    add(ET.tostring(el,encoding='unicode'))

def asset(name,x,y,w,h=None):
    h = w if h is None else h
    assets.add(name)
    with ZipFile(ARCHIVE) as z:
        raw = z.read(PREFIX+'svg/'+name+'.svg').decode()
    embed_svg(raw,x,y,w,h,name)

def stack(x,y,w,h,fill='white',layers=3,stroke=OUTLINE,step=7,r=4):
    for i in range(layers-1,0,-1):
        rect(x+i*step,y-i*step,w,h,'#F2F5F5',stroke,1.8,r)
    rect(x,y,w,h,fill,stroke,2.1,r)

def strokes(x,y,w,n=3,gap=12,color='#B7C5CA'):
    for i in range(n):
        line(x,y+i*gap,x+w*(1 if i<n-1 else .72),y+i*gap,color,2.3)

def page(x,y,w,h,brand=None,fill='#EDF2F3'):
    rect(x,y,w,h,'white',OUTLINE,2,4)
    rect(x,y,w,25,fill,'none',0,4)
    line(x,y+25,x+w,y+25,OUTLINE,1.6)
    for i in range(3):
        add(f'<circle cx="{x+10+i*8}" cy="{y+12}" r="2" fill="#9EADB2"/>')
    rect(x+12,y+39,w*.29,h-52,fill,'none',0,2)
    strokes(x+w*.4,y+44,w*.48,2 if h<78 else 3,11)
    if brand:
        # The emblem sits in its own top-right tab; rear pages expose this tab.
        rect(x+w-34,y+2,31,30,'white','none',0,3)
        asset('02_browsers/'+brand,x+w-31,y+4,25)

def title_tab(x,y,w,number,title):
    rect(x,y,w,45,'#EDF2F3',OUTLINE,2.1,5)
    add(f'<circle cx="{x+25}" cy="{y+23}" r="15" fill="{BLUE}"/>')
    txt(x+25,y+29,str(number),20,700,'middle','white')
    txt(x+50,y+31,title,28,700)

ET.register_namespace('','http://www.w3.org/2000/svg')
add(f'<svg xmlns="http://www.w3.org/2000/svg" width="1760" height="900" viewBox="0 0 {W} {H}">')
add('<title>HybridGuard: choose checks, then check current reports</title>')
add('<desc>Two bands separate offline rule preparation from current checking. Illustrative App logos, plain in-app pages, and optional branded browser pages feed fixed checks. Results preserve no-check and failure states.</desc>')
add('<defs><marker id="main" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L12 6 L0 12 Z" fill="#718995"/></marker><marker id="thin" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#34444B"/></marker><marker id="optional" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L10 5 L0 10" fill="none" stroke="#709780" stroke-width="1.7"/></marker></defs>')
add('<g font-family="Arial, Helvetica, sans-serif">')
rect(0,0,W,H,'white','none',0,0)

# Band 1. Record stacks and object-led selection; rejected candidates stay local.
rect(20,38,1720,248,'#FBFCFC',OUTLINE,2.1,7,'8 6')
title_tab(40,17,293,1,'Choose checks')
txt(1688,68,'Before use',21,400,'end','#75858C')
for y,label in [(104,'Normal records'),(210,'Modified records')]:
    stack(54,y,231,64,layers=3,step=5)
    rect(62,y-26,208,31,'#F0F4F6',OUTLINE,1.7,4)
    txt(166,y-3,label,22,600,'middle')
    asset('05_records_rules/document',69,y+12,38)
    strokes(122,y+16,136,3,14)
# A single brace collects both development-record groups into the candidates.
path('M309 117 C327 117 327 117 327 135 V159 Q327 186 345 186 Q327 186 327 211 V235 C327 253 327 253 309 253',stroke=BLUE,sw=4)
arrow(346,186,397,186,'main')

txt(488,105,'Candidate checks',23,600,'middle')
stack(416,132,147,109,layers=3)
for i in range(3):
    yy=145+i*31
    if i<2: tick(431,yy,26)
    else: rect(433,yy+2,22,22,'white',OUTLINE,1.7,3)
    strokes(475,yy+7,72,2,10)
arrow(588,184,630,184,'thin')

txt(696,105,'Filter',25,700,'middle')
path('M650 129 H743 L709 171 V207 L684 219 V171 Z','#DFE7E9',OUTLINE,2.4)
tick(761,144,28)
cross(648,232,27)
txt(682,254,'Not selected',20,400,fill='#8E6967')
arrow(751,181,797,181,'thin')

txt(870,105,'Select',25,700,'middle')
for i in range(4):
    rect(808+i*11,144-i*8,66,83,'#F0F3F3',OUTLINE,1.9,3)
strokes(853,142,41,4,15)
tick(901,203,28)
arrow(938,181,984,181,'thin')

txt(1064,105,'Refine',25,700,'middle')
stack(1008,139,76,87,layers=2)
strokes(1020,158,51,4,14)
rect(1092,165,55,61,blue_fill('#EFF4EF'),BLUE,1.9,3)
line(1107,193,1131,193,BLUE,3)
line(1119,181,1119,205,BLUE,3)
arrow(1161,181,1203,181,'thin')

txt(1440,105,'Saved checks',25,700,'middle')
stack(1232,135,386,109,blue_fill('#F2F6F4'),3,OUTLINE,7)
for i in range(3):
    tick(1255,145+i*30,29)
    strokes(1304,154+i*30,267-(i==2)*40,2,10)

# Band 2. Large current-check path; the only cross-band connection supplies rules.
rect(20,346,1720,516,'#FFFFFF',OUTLINE,2.1,7,'8 6')
title_tab(40,325,440,2,'Check current information')
txt(1688,377,'For each current record',21,400,'end','#75858C')

# Nested app sources.
txt(158,409,'Current App',26,700)
rect(143,423,445,328,'#F7F9F9',OUTLINE,2.1,6)
txt(254,459,'Native apps',24,600,'middle')
rect(158,471,193,166,'white',OUTLINE,1.8,4)
for i,name in enumerate(['wechat','whatsapp','instagram','tiktok','youtube','alipay']):
    asset('01_apps/'+name,169+(i%3)*57,484+(i//3)*72,52)

txt(456,459,'In-app web',24,600,'middle')
page(380,471,174,146)
page(370,481,174,146)
page(360,491,174,146)
stack(158,661,410,69,layers=2,step=4)
asset('04_device_geometry/phone_android',174,672,44)
txt(231,690,'Device info',22,600)
strokes(231,711,123,1,12)
strokes(381,677,167,3,15)
asset('05_records_rules/link',440,633,31)

# Small collection arrow ends at the document side of the main checking object.
arrow(616,551,751,551)

# Linked external browser pages expose a different logo on every layer.
txt(66,773,'Browser web',24,600)
rect(66,788,105,31,blue_fill('#F0F5F2'),BLUE,1.4,15)
txt(118,810,'Optional',18,500,'middle',BLUE)
page(373,767,219,62,'chrome',blue_fill('#EDF4F1'))
page(345,778,219,62,'firefox',blue_fill('#EDF4F1'))
page(317,789,219,62,'edge',blue_fill('#EDF4F1'))

# Main object is a large working record, with two offset backing sheets.
stack(773,425,532,408,'#FBFCFC',3,OUTLINE,7,6)
txt(795,466,'Run saved checks',28,700)
arrow(1253,259,1253,414)

stack(796,498,126,72,'white',3,OUTLINE,5,3)
asset('05_records_rules/document',807,512,38)
strokes(855,514,52,3,13)
arrow(943,534,988,534,'thin')
stack(1014,491,245,87,blue_fill('#F2F6F4'),3,OUTLINE,5,4)
for i in range(3):
    yy=499+i*25
    tick(1027,yy,24)
    strokes(1067,yy+7,168-(i==2)*25,2,9)

# Example is visually separated from the route; it illustrates one relation only.
line(795,590,1281,590,'#D4DEE1',1.7)
txt(795,618,'Time zone example',22,600)
txt(1278,618,'illustrative',20,400,'end','#879298')
txt(889,653,'Device',20,500,'middle')
txt(1082,653,'In-app web',20,500,'middle')
for y,offset,match in [(688,'UTC+8',True),(731,'UTC+9',False)]:
    asset('03_time/clock',801,y-24,27)
    txt(848,y,'UTC+8',25,500)
    line(954,y-8,985,y-8,'#A8B8BE',2)
    asset('03_time/clock',1018,y-24,27)
    txt(1064,y,offset,25,500)
    if match: tick(1220,y-28,32)
    else: cross(1220,y-28,32)

# Optional C1 is an attached sheet and a separate path, never a required stage.
rect(796,765,486,50,blue_fill('#F4F8F5'),BLUE,1.9,4,'7 5')
asset('05_records_rules/link',808,774,32)
txt(851,798,'Browser check',24,600)
txt(1265,798,'Optional',20,400,'end',BLUE)
arrow(615,790,783,790,'optional')

# Results, with distinct auxiliary states kept legible.
arrow(1325,532,1382,532)
txt(1425,413,'Result',26,700)
def result(y,label,sub,icon,fill):
    rect(1413,y+5,292,78,'#EFF2F2','#B5C1C5',1.4,4)
    rect(1407,y,292,78,fill,OUTLINE,1.8,4)
    if icon=='ok': tick(1420,y+16,47)
    else: asset('06_states/'+icon,1422,y+18,43)
    txt(1477,y+34,label,26,600)
    txt(1477,y+61,sub,20,400,fill='#728087')
result(444,'Alert','A check was triggered','high_priority','#FBF5F3')
result(543,'No alert','All checks were clear','ok','#F2F7F2')
result(642,'Cannot tell','Not enough evidence','questions','#F2F6F9')

rect(1407,750,292,39,'#F6F7F7',OUTLINE,1.5,4)
add('<circle cx="1430" cy="769" r="11" fill="none" stroke="#89969C" stroke-width="2"/>')
line(1422,777,1438,761,'#89969C',2)
txt(1453,777,'No checks',22,500)
rect(1407,800,292,39,'#F8F4F2',OUTLINE,1.5,4)
cross(1418,805,29)
txt(1453,827,'Check failed',22,500)

# Minimal in-figure qualifications keep the picture readable on its own.
txt(36,888,'Logos and values are examples.',20,400,fill='#7A898F')
txt(1724,888,'No alert does not prove authenticity.',20,400,'end','#7A898F')
add('</g></svg>')

HERE.mkdir(parents=True,exist_ok=True)
(HERE/'HybridGuard_Fig2_redesign_v6.svg').write_text('\n'.join(parts))
with ZipFile(ARCHIVE) as z:
    for name in sorted(assets):
        dest=HERE/'assets'/('svg/'+name+'.svg')
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(z.read(PREFIX+'svg/'+name+'.svg'))
    for name in ['SOURCES.csv','licenses/READ_ME_RIGHTS_AND_CREDITS.txt','licenses/SuperTinyIcons-LICENSE.txt','licenses/Icons8-LICENSE.md','licenses/RETAINED_BRANDS_NOTICES.txt']:
        dest=HERE/'assets'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(z.read(PREFIX+name))
(HERE/'SOURCE_NOTES.json').write_text(json.dumps({
    'status':'visual_review_candidate',
    'source_asset_archive':str(ARCHIVE.relative_to(ROOT)),
    'asset_names':sorted(assets),
    'additional_state_icons':sorted(state_icons),
    'additional_state_icon_source':'Microsoft Fluent Emoji shaded check and Google Noto Emoji thick shaded cross; original SVGs and upstream notices retained in assets/state_icons/',
    'method_source':'output/pdf/hybridguard_www_draft_20261017/sections/03_method.tex',
    'method_source_version':'current local working copy; existing uncommitted changes preserved',
    'text_words':len(' '.join(text_items).split()),
    'viewbox':[W,H],
    'new_experimental_evidence':False,
    'manuscript_integration':False,
    'reference_images':'user-supplied Figure 2 annotated refinement reference, plus prior MATE and layered-sentinel screenshots; not redistributed',
    'revision':'v6; five requested visual refinements from v5',
    'green_fill_policy':'Only No alert retains green box fill. Other formerly green fills changed to hue 210 degrees with original HSL saturation and lightness.',
    'asset_treatment':'original SVG colors and geometry retained, only placement and scale changed; custom shapes are muted',
},indent=2)+'\n')
print(json.dumps({'svg':str(HERE/'HybridGuard_Fig2_redesign_v6.svg'),'assets':len(assets),'words':len(' '.join(text_items).split())}))
