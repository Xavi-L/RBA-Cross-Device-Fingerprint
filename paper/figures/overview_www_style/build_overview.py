"""Draw an editable overview style preview; no experiment code is imported."""
from pathlib import Path
from html import escape

HERE = Path(__file__).resolve().parent
OUT = HERE / 'HybridGuard_overview.svg'
W, H = 1800, 920
C = dict(ink='#343434', muted='#606060', blue='#507cc4', cream='#faf0e2',
         ice='#e9f0f9', green='#edf3e9', lavender='#e3e9f7', sage='#65855a',
         warm='#bd8b47', red='#bd5049', gray='#f6f6f3')
parts = []

def add(s): parts.append(s)
def rect(x,y,w,h,fill='white',stroke=C['ink'],r=15,sw=1.8,dash=None):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')
def line(x1,y1,x2,y2,color=C['ink'],sw=2,dash=None):
    add(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" stroke-width="{sw}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')
def path(d,color=C['ink'],sw=2,arrow=False,dash=None):
    marker = 'arrow-current' if color==C['blue'] else ('arrow-development' if color==C['warm'] else 'arrow')
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"'+(f' marker-end="url(#{marker})"' if arrow else '')+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')
def flow(id,kind,d,source,target):
    colors={'current':C['blue'],'development':C['warm'],'model':C['ink']}
    add(f'<g id="{id}" data-flow-kind="{kind}" data-source="{source}" data-target="{target}">')
    path(d,colors[kind],2.3,True,'7 5' if kind=='development' else None)
    add('</g>')
def text(x,y,s,size=29,weight='normal',anchor='start',color=C['ink'],italic=False):
    add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{color}"'+(' font-style="italic"' if italic else '')+'>'+escape(s)+'</text>')
def circle(x,y,r,fill,stroke='none',sw=1.8):
    add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
def icon(name,x,y,size=48,color=C['ink']):
    add(f'<use href="#{name}" xlink:href="#{name}" x="{x}" y="{y}" width="{size}" height="{size}" color="{color}"/>')
def frame(x,w,n,title):
    rect(x,94,w,698,'white','#777777',0,1.8,'5 5')
    circle(x+17,94,20,C['blue'])
    text(x+17,103,str(n),28,'normal','middle','white')
    rect(x+42,70,w-54,39,'white','none',0)
    text(x+52,103,title,32,'bold')

add(f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="180mm" height="92mm" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
<title id="title">HybridGuard: observations, offline constrained rule development, and independent current-record interfaces</title>
<desc id="desc">Catalog views: Native84, WebView Host26 and App Web67 form App177; Browser67 is separate. Blue current-input paths bypass offline development: App directly enters App-only, while session/receipt-associated App and Browser enter paired inference. Dashed ochre arrows carry saved development data; black arrows load frozen models. The fixed App includes the Native–App Web memory relation. App SPARSE selection and signal/quality retention differ from finite constrained cross-endpoint selection. Four prespecified extension sets select C1, an App Web–Browser UTC-offset mismatch. New Host geometry was studied separately; Browser-resource extensions were selected against and none admitted. T means manipulation alert; F no alarm; U insufficient evidence. Selected-input execution or binding failures take priority as FAILED. No automatic App-only fallback exists in paired mode. Catalog counts are not completeness or trust guarantees; association is not atomic synchronization.</desc>
<style>text {{font-family:'Times New Roman',Times,serif}} use {{fill:none;stroke:currentColor;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round}}</style>
<defs>
<marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L9,4.5 L0,9 L2.5,4.5 Z" fill="#343434"/></marker>
<marker id="arrow-current" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L10,5 L0,10 L3,5 Z" fill="#507cc4"/></marker>
<marker id="arrow-development" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L9,4.5 L0,9 L2.5,4.5 Z" fill="#bd8b47"/></marker>
<symbol id="chip" viewBox="0 0 48 48"><rect x="11" y="11" width="26" height="26" rx="4"/><rect x="17" y="17" width="14" height="14" rx="2"/><path d="M17 5v6m7-6v6m7-6v6M17 37v6m7-6v6m7-6v6M5 17h6m-6 7h6m-6 7h6M37 17h6m-6 7h6m-6 7h6"/></symbol>
<symbol id="host" viewBox="0 0 48 48"><rect x="5" y="7" width="38" height="33" rx="4"/><path d="M5 15h38M11 11h1m5 0h1"/><rect x="13" y="22" width="22" height="12" rx="1"/><path d="M9 27h4m22 0h4M24 18v4m0 12v3"/></symbol>
<symbol id="web" viewBox="0 0 48 48"><rect x="4" y="7" width="40" height="34" rx="4"/><path d="M4 16h40M11 12h1m5 0h1M17 23l-6 6 6 6m14-12l6 6-6 6m-5-14l-4 16"/></symbol>
<symbol id="chain" viewBox="0 0 48 48"><path d="M20 30l-3 3a9 9 0 0 1-13-13l9-9a9 9 0 0 1 13 0m2 7l3-3a9 9 0 0 1 13 13l-9 9a9 9 0 0 1-13 0M17 31l14-14" transform="translate(1 -1) scale(.94)"/></symbol>
<symbol id="records" viewBox="0 0 48 48"><path d="M13 5h24v32H13zM7 12H4v32h25v-3M19 13h12m-12 8h12m-12 8h8"/></symbol>
<symbol id="alarm" viewBox="0 0 48 48"><path d="M11 31c5-6 4-11 4-16a9 9 0 0 1 18 0c0 5-1 10 4 16zM20 38a4 4 0 0 0 8 0M24 3v3"/></symbol>
<symbol id="coverage" viewBox="0 0 48 48"><circle cx="24" cy="24" r="17"/><path d="M15 24l6 7 13-15"/></symbol>
<symbol id="tree" viewBox="0 0 48 48"><rect x="19" y="4" width="10" height="10" rx="2"/><rect x="5" y="33" width="10" height="10" rx="2"/><rect x="33" y="33" width="10" height="10" rx="2"/><path d="M24 14v9M10 33V23h28v10"/></symbol>
<symbol id="rules" viewBox="0 0 48 48"><rect x="7" y="5" width="33" height="38" rx="4"/><path d="M13 15l3 3 4-6m5 3h9M13 26l3 3 4-6m5 3h9M13 36h21"/></symbol>
<symbol id="clocks" viewBox="0 0 48 48"><circle cx="16" cy="18" r="12"/><circle cx="33" cy="32" r="12"/><path d="M16 11v8l5 3m12 3v8l5 2M29 7h11v11m-1-10l-8 8M7 29v11h11m-10-1l8-8"/></symbol>
<symbol id="lock" viewBox="0 0 48 48"><rect x="10" y="21" width="28" height="22" rx="4"/><path d="M16 21v-9a8 8 0 0 1 16 0v9M24 29v7"/></symbol>
<symbol id="chart" viewBox="0 0 48 48"><path d="M7 6v36h35M15 34V22m10 12V12m10 22V17"/></symbol>
<symbol id="cost" viewBox="0 0 48 48"><circle cx="25" cy="25" r="17"/><path d="M25 14v12l8 5M19 3h12M25 3v5"/></symbol>
</defs>''')
rect(0,0,W,H,'white','none',0)
text(24,34,'HybridGuard: cross-view fingerprint consistency',32,'bold')
# Three arrow semantics are explicit. Color alone is not the only cue:
# current paths are named bypasses, development is dashed, model arrows say load.
for x,label,col,dash in [(998,'Dev. data',C['warm'],'7 5'),(1211,'Current input',C['blue'],None),(1480,'Frozen model',C['ink'],None)]:
    path(f'M{x} 25 h45',col,2.3,True,dash)
    text(x+55,34,label,29)

# I. Catalog views, with an App-only branch before any Browser association.
add('<g id="observations">')
frame(24,478,1,'Multi-view observations')
text(263,145,'Catalog field counts',29,'normal','middle',C['muted'],True)
add('<g id="current-app">')
rect(48,176,282,338,'white',C['ink'],21,2.2)
text(189,211,'App177',31,'bold','middle')
for y,name,count,symbol,fill,col in [(228,'Native','84','chip',C['cream'],C['warm']),(310,'WebView Host','26','host',C['ice'],C['blue']),(392,'App Web','67','web',C['green'],C['sage'])]:
    rect(64,y,250,73,fill,'none',13)
    icon(symbol,77,y+16,41,col)
    text(124,y+30,name,29,'bold')
    text(124,y+63,count+' fields',29)
line(162,490,216,490,'#8a8a8a',3)
add('</g>')
add('<g id="current-browser">')
text(418,224,'Independent',29,'normal','middle',C['muted'],True)
rect(343,248,150,185,'white',C['ink'],13,2)
line(343,275,493,275,'#666666',1.8)
for x in [365,377,389]: circle(x,261,3,'#898989')
icon('web',387,290,60,C['sage'])
text(418,382,'Browser67',29,'bold','middle')
text(418,415,'67 fields',29,'normal','middle')
add('</g>')
flow('app-to-binding','current','M189 514 V552 H270 V584','current-app','current-bound-pair')
flow('browser-to-binding','current','M418 434 V552 H270','current-browser','current-bound-pair')
circle(270,552,3.7,C['blue'])
add('<g id="current-bound-pair">')
rect(53,589,420,94,C['gray'],C['ink'],16,1.6)
icon('chain',74,615,44,C['blue'])
text(132,624,'Session / receipt binding',29,'bold')
text(132,661,'paired244 (catalog)',30)
add('</g>')
text(263,722,'Same device; not atomic captures',29,'normal','middle',C['muted'],True)
text(263,758,'IDs are not detection features',29,'normal','middle',C['muted'],True)
add('</g>')

# II. Offline inputs originate here, never from the blue current-observation paths.
add('<g id="development">')
frame(560,662,2,'Offline constrained rule development')
add('<g id="saved-development-data">')
rect(588,145,607,79,C['cream'],'none',18)
text(891,177,'Saved development records',32,'bold','middle')
text(891,213,'App / paired studies + MTC630 normals',29,'normal','middle')
add('</g>')
flow('saved-to-constraints','development','M891 226 V240','saved-development-data','selection-constraints')
add('<g id="selection-constraints">')
rect(588,246,607,102,C['lavender'],'none',18)
for cx,l1,l2,ic in [(689,'Normal-alarm','budget','alarm'),(891,'Defined-output','coverage','coverage'),(1093,'Model','complexity','tree')]:
    icon(ic,cx-15,253,30,C['blue'])
    text(cx,307,l1,29,'normal','middle')
    text(cx,341,l2,29,'normal','middle')
add('</g>')
flow('constraints-to-app','development','M891 350 V367','selection-constraints','fixed-app')
add('<g id="fixed-app">')
rect(588,374,607,140,C['ice'],C['ink'],16,1.6)
text(891,405,'App selection → fixed App',32,'bold','middle')
text(891,439,'SPARSE: macro-TPR − λ·complexity',29,'normal','middle')
text(891,472,'RETENTION: signal / quality retention',29,'normal','middle')
text(891,505,'Includes Native–App Web memory',29,'normal','middle')
add('</g>')
flow('freeze-app','model','M891 516 V542','fixed-app','fixed-paired')
text(922,541,'Freeze App',29,'normal','start',C['muted'],True)
add('<g id="fixed-paired">')
rect(588,550,607,148,C['green'],C['ink'],16,1.6)
text(891,582,'Constrained cross-endpoint selection',31,'bold','middle')
text(891,616,'4 prespecified sets · max macro detection',29,'normal','middle')
text(891,652,'Selected extension: C1',32,'bold','middle')
text(891,686,'App Web–Browser UTC-offset mismatch',29,'normal','middle')
add('</g>')
# The paired development members independently enter extension selection.
flow('saved-to-cross-selection','development','M588 201 H572 V591 H584','saved-development-data','fixed-paired')
rect(588,709,607,72,'white','#949494',12,1.6,'5 4')
text(891,738,'New Host geometry: studied, not integrated',29,'normal','middle')
text(891,772,'Browser-resource extensions: none selected',29,'normal','middle',C['muted'],True)
add('</g>')

# III. Two separate interfaces, each with its own current-input and model port.
add('<g id="decision">')
frame(1280,496,3,'Current-record decision')
add('<g id="app-interface">')
rect(1304,179,448,211,'white','#808080',16,1.5)
text(1528,212,'App-only interface',32,'bold','middle')
text(1528,248,'Current App observations',29,'normal','middle')
text(1528,282,'Selected-input checks',29,'normal','middle')
path('M1528 292 V308',C['blue'],2.3,True)
rect(1317,315,422,69,C['ice'],'none',12)
text(1528,343,'Fixed App rules',30,'bold','middle')
text(1528,377,'→ T / F / U / FAILED',29,'normal','middle')
add('</g>')
add('<g id="paired-interface">')
rect(1304,405,448,211,'white','#808080',16,1.5)
text(1528,438,'Paired interface',32,'bold','middle')
text(1528,473,'Current bound pair',29,'normal','middle')
text(1528,507,'Selected-input checks',29,'normal','middle')
path('M1528 517 V533',C['blue'],2.3,True)
rect(1317,540,422,69,C['green'],'none',12)
text(1528,568,'Fixed App + C1',30,'bold','middle')
text(1528,602,'→ T / F / U / FAILED',29,'normal','middle')
add('</g>')
text(1528,645,'No automatic App-only fallback',29,'normal','middle',C['muted'],True)
for cx,cy,s,label,col in [(1315,668,'T','Manipulation alert',C['red']),(1619,668,'F','No alarm',C['sage']),(1315,702,'U','Insufficient evidence',C['warm'])]:
    circle(cx,cy,15,col)
    text(cx,cy+10,s,28,'bold','middle','white')
    text(cx+23,cy+10,label,29)
text(1528,746,'Selected-input execution / binding',29,'normal','middle',C['muted'])
text(1528,780,'failure → FAILED',29,'normal','middle',C['muted'])
add('</g>')

# Actual current-input bypasses: neither path traverses a development block.
flow('current-app-direct','current','M330 192 H528 V60 H1245 V240 H1298','current-app','app-interface')
rect(760,40,258,26,'white','none',0)
text(889,59,'Current App only',29,'normal','middle',C['blue'],True)
flow('current-pair-direct','current','M473 642 H528 V803 H1790 V466 H1758','current-bound-pair','paired-interface')
text(1019,832,'Current bound pair',29,'normal','middle',C['blue'],True)
# The App port comes from its source before binding, never from the paired box.
circle(330,192,3.7,C['blue'])
flow('load-app-model','model','M1196 440 H1264 V349 H1311','fixed-app','app-interface')
rect(1210,446,56,31,'white','none',0)
text(1238,469,'load',29,'normal','middle',C['muted'],True)
flow('load-paired-model','model','M1196 640 H1264 V574 H1311','fixed-paired','paired-interface')
rect(1210,645,56,31,'white','none',0)
text(1238,669,'load',29,'normal','middle',C['muted'],True)

# Historical evaluation is outside both selection and current inference.
add('<g id="evaluation-evidence">')
rect(24,848,1752,63,C['gray'],'#bebeba',10,1.3)
text(47,888,'Saved evaluation',30,'bold')
for x in [276,584,1136,1446]: line(x,860,x,898,'#c0c0ba',1.3)
text(301,888,'App + ablations',29)
text(609,888,'Historical MTC: 144 + 117 records',29)
text(1160,888,'Paired studies',29)
text(1470,888,'Specialists + cost',29)
add('</g>')
add('</svg>')
OUT.write_text('\n'.join(parts)+'\n')
print(OUT)
