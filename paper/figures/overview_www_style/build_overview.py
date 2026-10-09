"""Draw an editable overview style preview; no experiment code is imported."""
from pathlib import Path
from html import escape

HERE = Path(__file__).resolve().parent
OUT = HERE / 'HybridGuard_overview.svg'
W, H = 1800, 892
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
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"'+(' marker-end="url(#arrow)"' if arrow else '')+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')
def text(x,y,s,size=29,weight='normal',anchor='start',color=C['ink'],italic=False):
    add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{color}"'+(' font-style="italic"' if italic else '')+'>'+escape(s)+'</text>')
def circle(x,y,r,fill,stroke='none',sw=1.8):
    add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
def icon(name,x,y,size=48,color=C['ink']):
    add(f'<use href="#{name}" x="{x}" y="{y}" width="{size}" height="{size}" color="{color}"/>')
def frame(x,w,n,title):
    rect(x,94,w,662,'white','#777777',0,1.8,'5 5')
    circle(x+17,94,20,C['blue'])
    text(x+17,103,str(n),28,'normal','middle','white')
    rect(x+42,70,w-54,39,'white','none',0)
    text(x+52,103,title,32,'bold')

add(f'''<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="89.2mm" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
<title id="title">HybridGuard: multi-view observations, constrained rule development, and current-record decisions</title>
<desc id="desc">Style preview inspired by the visual organization of Figure 1 in the supplied Lower Barriers, Greater Threat paper. Native, WebView Host and App Web are App observations; the independent browser is separate. Development fixes App rules, freezes them, and accepts cross-endpoint timezone C1. Two current-record interfaces return T, F or U, with selected execution or binding errors recorded as FAILED. Host geometry and resource checks are separate studies, not integrated additions. No experiments or statistics were changed.</desc>
<style>text {{font-family:'Times New Roman',Times,serif}} use {{fill:none;stroke:currentColor;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round}}</style>
<defs>
<marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L9,4.5 L0,9 L2.5,4.5 Z" fill="#343434"/></marker>
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
text(24,39,'HybridGuard: cross-view fingerprint consistency',34,'bold')
text(1776,39,'METHOD OVERVIEW',27,'normal','end',C['muted'])

# I. Same-device observation locations; the three App locations stay enclosed.
add('<g id="observations">')
frame(24,478,1,'Multi-view observations')
text(263,145,'Same physical device',29,'normal','middle',C['muted'],True)
rect(48,176,252,338,'white',C['ink'],21,2.2)
text(174,211,'App177',31,'bold','middle')
for y,name,count,symbol,fill,col in [(228,'Native','84','chip',C['cream'],C['warm']),(310,'Host','26','host',C['ice'],C['blue']),(392,'App Web','67','web',C['green'],C['sage'])]:
    rect(64,y,220,73,fill,'none',13)
    icon(symbol,78,y+16,43,col)
    text(137,y+30,name,30,'bold')
    text(137,y+61,count+' signals',29)
line(147,490,201,490,'#8a8a8a',3)
text(402,224,'Independent',29,'normal','middle',C['muted'],True)
rect(326,248,151,167,'white',C['ink'],13,2)
line(326,275,477,275,'#666666',1.8)
for x in [341,353,365]: circle(x,261,3,'#898989')
icon('web',371,292,62,C['sage'])
text(401.5,390,'Browser67',29,'bold','middle')
path('M174 514 V552 H270 V584',arrow=True)
path('M402 415 V552 H270')
circle(270,552,3.7,C['ink'])
rect(53,589,420,94,C['gray'],C['ink'],16,1.6)
icon('chain',74,615,44,C['blue'])
text(132,624,'Session / receipt binding',29,'bold')
text(132,661,'paired244',31,'normal')
text(263,732,'Binding IDs are not features',29,'normal','middle',C['muted'],True)
add('</g>')

# The main arrow denotes the development workflow, not an all-fields-required claim.
path('M509 422 H552',sw=2.2,arrow=True)

# II. Fixed App selection, then frozen-base extension; diagnostics remain separate.
add('<g id="development">')
frame(560,662,2,'Constrained rule development')
rect(583,145,616,94,C['cream'],'none',18)
icon('records',604,169,48,C['warm'])
text(669,180,'Controlled changes + normal controls',29,'bold')
text(669,218,'MTC630 normal training records',29)
path('M891 241 V259',arrow=True)
rect(585,269,612,81,C['lavender'],'none',18)
for cx,label,ic in [(687,'Normal alarms','alarm'),(891,'Defined output','coverage'),(1095,'Complexity','tree')]:
    icon(ic,cx-16,277,32,C['blue'])
    text(cx,338,label,29,'normal','middle')
path('M891 351 V374',arrow=True)
rect(594,381,592,93,C['ice'],C['ink'],16,1.6)
icon('rules',618,402,47,C['blue'])
text(686,416,'Fixed App rules',33,'bold')
text(686,451,'Select within-App candidates',29)
path('M891 476 V517',arrow=True)
text(921,504,'Freeze App',29,'normal','start',C['muted'],True)
rect(594,523,592,94,C['green'],C['ink'],16,1.6)
icon('clocks',618,548,47,C['sage'])
text(686,558,'App + C1',33,'bold')
text(686,594,'Accept cross-endpoint timezone',29)
rect(594,649,592,77,'white','#949494',12,1.6,'5 4')
text(890,680,'Host geometry / resource checks',29,'normal','middle')
text(890,713,'Tested separately; not integrated',29,'normal','middle',C['muted'],True)
add('</g>')

# III. The inputs are current observations; models arrive on distinct load arrows.
add('<g id="decision">')
frame(1280,496,3,'Current-record decision')
rect(1302,145,452,94,'white','none',16)
icon('records',1316,169,46,C['blue'])
text(1380,180,'Current observations',31,'bold')
text(1380,217,'App only / bound pair',29)
path('M1528 240 V269',arrow=True)
rect(1330,279,396,53,C['cream'],'none',13)
text(1528,314,'Required-input checks',30,'normal','middle')
path('M1528 335 V372',arrow=True)
rect(1304,381,448,242,'white','#808080',16,1.5)
rect(1317,390,422,76,C['ice'],'none',12)
text(1528,421,'App-only interface',31,'bold','middle')
text(1528,453,'Fixed App rules',29,'normal','middle')
line(1336,499,1487,499,'#b1b1b1',1.3,'4 4')
text(1528,508,'or',29,'normal','middle',C['muted'],True)
line(1569,499,1720,499,'#b1b1b1',1.3,'4 4')
rect(1317,534,422,76,C['green'],'none',12)
text(1528,565,'Paired interface',31,'bold','middle')
text(1528,597,'Fixed App + C1',29,'normal','middle')
path('M1528 625 V657',arrow=True)
for cx,s,label,col in [(1328,'T','Alarm',C['red']),(1467,'F','No alarm',C['sage']),(1627,'U','Unknown',C['warm'])]:
    circle(cx,682,16,col)
    text(cx,692,s,28,'bold','middle','white')
    text(cx+24,692,label,29)
text(1528,737,'Execution / binding error → FAILED',29,'normal','middle',C['muted'])
add('</g>')

for y in (428,571):
    path(f'M1187 {y} H1310',sw=2.2,arrow=True)
    rect(1227,y-34,56,26,'white','none',0)
    text(1255,y-12,'load',29,'normal','middle',C['muted'],True)

# A compact evidence strip, outside selection and current-record processing.
add('<g id="evaluation-evidence">')
rect(24,791,1752,68,C['gray'],'#bebeba',10,1.3)
text(47,834,'Saved evaluation',31,'bold')
for x in [281,642,1014,1361]: line(x,805,x,845,'#c0c0ba',1.3)
icon('chart',306,809,33,C['blue'])
text(354,834,'App + ablations',30)
icon('records',665,809,33,C['blue'])
text(711,834,'MTC: 144 / 117',30)
icon('chain',1038,809,33,C['sage'])
text(1086,834,'Paired studies',30)
icon('cost',1385,809,33,C['warm'])
text(1432,834,'Specialists + cost',30)
add('</g>')
add('</svg>')
OUT.write_text('\n'.join(parts)+'\n')
print(OUT)
