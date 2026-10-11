"""One complete 180 mm candidate. Writes only into this directory.

Native, Host and App Web use the exact adapted vectors from style_pilot_v1.
No research imports, no execution of either previous figure builder.
"""
from collections import Counter
from html import escape
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
W, H = 1800, 730
C = dict(ink='#343434', muted='#666666', blue='#507cc4', warm='#bd8b47',
         context='#9a9a95', red='#D62828', cream='#faf0e2', ice='#e9f0f9',
         green='#edf3e9', cyan='#E9F3F3', purple='#EEE2FA',
         browser_outline='#4d7778', browser_fill='#c7dddd',
         rule_outline='#80649b', rule_fill='#d6c5e6',
         boundary='#B9C0C8', app_boundary='#93938e')
FONT = "'Times New Roman',Times,serif"
TYPE = dict(heading=40, group=32, node=34, role=28, body=29,
            relation=30, geometry=28, action=38, action_body=30)
LINE = dict(selected=3.2, studied=2.6, context=2.6, flow=2.0,
            model=2.2, leader=1.5, boundary=1.5, anchor=1.2)
BOX = dict(device=[18,102,816,608], app=[34,148,746,417],
           example=[1270,104,512,170], offline=[1270,289,512,383],
           process=[1270,488,512,112], detection=[880,110,350,439])
NODES = {
    'native': dict(icon='native', origin=[36,370,4.2], field=[46,374,78,94],
                   text=[140,394], bounds=[40,363,366,110], ys=[394,428,462], fill='cream',
                   copy=['Device & OS','(Native)','Memory and timezone']),
    'webview-host': dict(icon='host', origin=[426,465,4.2], field=[430,463,91,96],
                   text=[535,480], bounds=[425,450,337,109], ys=[480,514,548], fill='ice',
                   copy=['App container','(WebView Host)','Container settings']),
    'app-web': dict(icon='app-web', origin=[430,206,4], field=[440,204,74,102],
                   text=[528,210], bounds=[430,180,340,147], ys=[210,285,319], fill='green',
                   copy=['Embedded webpage','(App Web)','Reported properties']),
    'browser': dict(icon='browser', origin=[391,593,4], field=[404,601,80,90],
                   text=[500,623], bounds=[396,590,396,109], ys=[623,655,687], fill='cyan',
                   copy=['Standalone browser','On the same device','Separate web runtime']),
}
parts, content = [], []
def add(s): parts.append(s)
def at(**kw):
    return ' '.join(f'{k.replace("_","-")}="{escape(str(v),quote=True)}"' for k,v in kw.items() if v is not None)
def path(d, color, width=2, fill='none', **kw):
    return f'<path {at(d=d,stroke=color,stroke_width=width,fill=fill,stroke_linecap="round",stroke_linejoin="round",**kw)}/>'
def rect(x,y,w,h,fill='none',radius=0,stroke='none',width=0,**kw):
    return f'<rect {at(x=x,y=y,width=w,height=h,fill=fill,rx=radius,stroke=stroke,stroke_width=width,**kw)}/>'
def txt(x,y,label,size=29,weight='normal',color=None,anchor='start',emphasis=None,italic=False,lines=None,leading=34):
    content.append(label)
    val=escape(label)
    if lines:
        assert ' '.join(lines)==label
        val=''.join(f'<tspan {at(x=x,y=y+i*leading)}>{escape(line+(" " if i<len(lines)-1 else ""))}</tspan>' for i,line in enumerate(lines))
    elif emphasis:
        left,word,right=label.partition(emphasis)
        assert word
        val=f'{escape(left)}<tspan fill="{C["red"]}">{escape(word)}</tspan>{escape(right)}'
    add(f'<text {at(id=f"copy-{len(content):02d}",x=x,y=y,font_size=size,font_weight=weight,fill=color or C["ink"],text_anchor=anchor,font_style="italic" if italic else None,data_copy="true")}>{val}</text>')
def group(id_, **kw): add(f'<g {at(id=id_,**kw)}>')
def end(): add('</g>')
def source_paths(name):
    return [e.attrib['d'] for e in ET.parse(HERE/'assets/tabler'/f'{name}.svg').getroot().findall(f'{{{NS}}}path')]
def inherited_icon(name):
    r=ET.parse(HERE/'assets'/f'{name}_adapted.svg').getroot()
    return ''.join(ET.tostring(e,encoding='unicode').replace(f' xmlns="{NS}"','') for e in r
                   if e.tag not in [f'{{{NS}}}{n}' for n in ['title','desc','style']])
def browser_icon():
    p=source_paths('browser'); c=C['browser_outline']
    return (path(p[1],c,.60,C['browser_fill'])+rect(4.8,8.65,14.4,10.55,'white',.6)
            +path(p[0],c,.42)+path(p[2],c,.42)
            +path('M10 6h6.5',c,.30)+path('M7.1 11.5h9.5M7.1 14.2h6.7M7.1 16.9h8.1',c,.34))
def material_icon(name):
    p=source_paths(name); c=C['rule_outline']
    if name=='list-details':
        return ''.join(path(d,c,.72,'white' if i>=4 else 'none') for i,d in enumerate(p))
    if name=='files':
        return (path(p[2],c,.66,C['rule_fill'])+path(p[1],c,.68,'white')
                +path('M15 3v4a1 1 0 0 0 1 1h4Z','none',0,C['rule_fill'])
                +path(p[0],c,.58)+path('M12 11h5M12 13.5h3.5',c,.40))
    if name=='file-text':
        return (path(p[1],c,.66,'white')+path('M14 3v4a1 1 0 0 0 1 1h4Z','none',0,C['rule_fill'])
                +path(p[0],c,.58)+''.join(path(d,c,.44) for d in p[2:]))
    raise ValueError(name)
def icon(name,x,y,scale):
    add(f'<g {at(transform=f"translate({x} {y}) scale({scale})",data_icon=name)}>')
    if name in ['native','host','app-web']: add(inherited_icon(name))
    elif name=='browser': add(browser_icon())
    else: add(material_icon(name))
    end()
def relation(id_,src,dst,d,state):
    color={'selected':'blue','studied':'warm','context':'context'}[state]
    marker=None if state=='context' else f'url(#compare-{state})'
    group(id_,data_kind='relation',data_source=src,data_target=dst,data_status=state)
    add(path(d,C[color],LINE[state],stroke_dasharray={'studied':'10 7','context':'1 7'}.get(state),marker_start=marker,marker_end=marker))
    end()
def flow(id_,kind,src,dst,d,model=False,arrow=True):
    group(id_,data_kind=kind,data_source=src,data_target=dst)
    add(path(d,C['rule_outline'] if model else C['ink'],LINE['model'] if model else LINE['flow'],
             marker_end=f'url(#{"model" if model else "input"}-arrow)' if arrow else None))
    end()
def node(id_):
    n=NODES[id_]; x,y=n['text']
    group(id_,data_kind='observation',data_bounds=','.join(map(str,n['bounds'])))
    add(rect(*n['field'],C[n['fill']],17))
    icon(n['icon'],*n['origin'])
    txt(x,n['ys'][0],n['copy'][0],32 if id_=='browser' else TYPE['node'],'bold',
        lines=['Embedded','webpage'] if id_=='app-web' else None,leading=38)
    txt(x,n['ys'][1],n['copy'][1],TYPE['role'])
    txt(x,n['ys'][2],n['copy'][2],TYPE['body'])
    end()

def main():
    original=ET.parse(HERE/'baseline/HybridGuard_overview_triangle.svg').getroot()
    desc=original.find(f'{{{NS}}}desc').text
    add(f'<svg xmlns="{NS}" width="180mm" height="{H/10:g}mm" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">')
    add('<title id="title">HybridGuard: Detecting device-fingerprint manipulation — full visual candidate</title>')
    add(f'<desc id="desc">{escape(desc)}</desc><style>text {{font-family:{FONT}}}</style>')
    add('<!-- Inherited pilot icons and adapted Tabler Icons v3.34.1. MIT notice: assets/tabler/LICENSE. -->')
    add('<defs>')
    for state,color in [('selected','blue'),('studied','warm')]:
        add(f'<marker id="compare-{state}" markerWidth="13" markerHeight="13" refX="10" refY="6.5" orient="auto-start-reverse" markerUnits="userSpaceOnUse">')
        add(path('M2 2L10 6.5L2 11',C[color],2.3)); add('</marker>')
    for name,color in [('input','ink'),('model','rule_outline')]:
        add(f'<marker id="{name}-arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse">')
        add(path('M0 0L10 5L0 10L3 5Z','none',0,C[color])); add('</marker>')
    add('</defs>'); add(rect(0,0,W,H,'white'))
    txt(24,45,'HybridGuard: Detecting device-fingerprint manipulation',40,'bold')
    txt(24,87,'Manipulated reports may conflict across observation points.',29)

    # Counter-clockwise quarter-turn: Native is the left vertex, App Web
    # upper-right and Host lower-right. Glyphs/text remain upright.
    group('device-observations',data_kind='same-device-scope',data_bounds=','.join(map(str,BOX['device'])))
    add(path('M594 102H818Q834 102 834 118V694Q834 710 818 710H34Q18 710 18 694V118Q18 102 34 102H35',C['boundary'],1.5))
    txt(36,126,'One device, multiple observation points',32,'bold')
    group('app-observations',data_kind='inside-app-scope',data_bounds=','.join(map(str,BOX['app'])))
    add(path('M262 148H768Q780 148 780 160V553Q780 565 768 565H46Q34 565 34 553V160Q34 148 46 148H48',C['app_boundary'],1.5,stroke_dasharray='6 6'))
    txt(48,165,'Inside the app',32,'bold')
    group('core-action')
    txt(48,207,'Cross-check',38,'bold',C['red'])
    txt(48,245,'reported properties',30); end()
    group('observation-anchors',data_kind='object-group-anchors')
    add(path('M274 354H306',C['boundary'],LINE['anchor']))
    add(path('M770 242V274',C['boundary'],LINE['anchor'])); end()
    relation('native-host','native','webview-host','M270 480L430 505','context')
    relation('native-app-web','native','app-web','M290 354L440 250','selected')
    relation('host-app-web','webview-host','app-web','M478 463V306','studied')
    group('consistency-label',data_relation='native-app-web')
    txt(48,289,'System–web consistency',30,'bold',C['blue'])
    txt(48,325,'Memory and timezone',29,color=C['blue'])
    add(path('M323 331L332 325',C['blue'],1.5)); end()
    group('context-label',data_relation='native-host')
    txt(42,516,'Shared context',30,'bold',C['muted'])
    txt(42,550,'No detection rule',28,color=C['muted'])
    add(path('M247 503L302 485',C['context'],1.5)); end()
    group('geometry-label',data_relation='host-app-web')
    txt(510,353,'Container–web geometry',28,'bold',C['warm'],lines=['Container–web','geometry'],leading=33)
    txt(510,421,'Not in current detector',28,color=C['warm'])
    add(path('M478 375H499',C['warm'],1.5)); end()
    for id_ in ['native','webview-host','app-web']: node(id_)
    end()
    relation('app-browser','app-web','browser','M770 258H808V584H380V648H404','selected')
    group('browser-label',data_relation='app-browser')
    txt(34,628,'App–browser consistency',30,'bold',C['blue'])
    txt(34,664,'Timezone reports',29,color=C['blue'])
    add(path('M362 646H380',C['blue'],1.5)); end()
    node('browser'); end()

    # Compact middle column: alternative modes, one shared output.
    flow('current-app-exit','current-input','app-observations','app-branch','M780 214H856V285',arrow=False)
    add('<g id="app-branch" data-kind="data-branch" data-point="856,285"/>')
    flow('current-app-only','current-input','app-branch','app-only-interface','M856 285H898')
    flow('current-app-for-pair','current-input','app-branch','linked-pair','M856 285V463',arrow=False)
    flow('current-browser-for-pair','current-input','browser','linked-pair','M792 674H856V463',arrow=False)
    add('<circle id="linked-pair" cx="856" cy="463" r="3" fill="#343434"/>')
    flow('current-linked-pair','current-input','linked-pair','paired-interface','M856 463H898')
    group('current-detection',data_kind='current-rule-application',data_bounds=','.join(map(str,BOX['detection'])))
    add(rect(*BOX['detection'],radius=16,stroke=C['app_boundary'],width=1.7))
    txt(898,146,'Apply selected rules',32,'bold')
    txt(898,183,'Current observations only',28,color=C['muted'])
    group('app-only-interface',data_kind='alternative-mode',data_bounds='898,238,314,94')
    add(rect(898,238,314,94,C['ice'],12))
    txt(914,272,'App observations only',29,'bold')
    txt(914,308,'App rules',28,color=C['muted']); end()
    group('paired-interface',data_kind='alternative-mode',data_bounds='898,395,314,136')
    add(rect(898,395,314,136,C['green'],12))
    txt(914,427,'App + linked browser observations',29,'bold',lines=['App + linked browser','observations'],leading=34)
    txt(914,505,'App + browser rules',28,color=C['muted']); end()
    txt(1055,372,'or',28,color=C['muted'],anchor='middle',italic=True); end()
    flow('selected-mode-result','decision-output','current-detection','decision-vocabulary','M1050 549V568')
    group('decision-vocabulary')
    txt(908,602,'Manipulation alert',29,'bold',C['red'])
    txt(908,638,'No alert',29)
    txt(908,674,'Insufficient evidence',29); end()

    # The right column retains the two-case example and independent materials.
    group('timezone-example',data_kind='illustration',data_bounds=','.join(map(str,BOX['example'])))
    txt(1284,126,'Example: timezone',32,'bold')
    add(path('M1270 141H1782',C['boundary'],1.2))
    txt(1284,164,'Normal system change',30,'bold')
    txt(1284,196,'System and web remain compatible',28)
    txt(1284,231,'Web-only modification',30,'bold')
    txt(1284,263,'Reports may conflict',28,emphasis='conflict'); end()
    group('offline-development',data_kind='offline-scope',data_bounds=','.join(map(str,BOX['offline'])))
    add(path('M1388 289H1770Q1782 289 1782 301V660Q1782 672 1770 672H1282Q1270 672 1270 660V301Q1270 289 1282 289',C['rule_fill'],1.5))
    txt(1284,299,'Offline',28,color=C['muted'],italic=True)
    group('candidate-checks',data_kind='development-material',data_bounds='1286,311,420,62')
    add(rect(1286,311,62,62,C['purple'],12)); icon('list-details',1283,307,2.8)
    txt(1366,333,'Candidate checks',29,'bold')
    txt(1366,367,'Within-view + cross-view',28)
    add(path('M1706 345V373',C['rule_fill'],1.2)); end()
    group('development-data',data_kind='development-material',data_bounds='1286,382,420,96')
    add(rect(1286,382,62,84,C['purple'],12)); icon('files',1280,387,2.8)
    txt(1366,401,'Development data',29,'bold')
    txt(1366,435,'Controlled modifications',28)
    txt(1366,469,'Normal devices and settings',28); end()
    flow('candidate-to-selection','development-input','candidate-checks','rule-selection','M1706 359H1756V474H1700V488')
    flow('data-to-selection','development-input','development-data','rule-selection','M1530 478V488')
    group('rule-selection',data_kind='development-process',data_bounds=','.join(map(str,BOX['process'])))
    add(rect(*BOX['process'],C['purple'],14))
    txt(1282,518,'Select detection rules',32,'bold')
    for x,y,t in [(1282,550,'Improve detection'),(1500,550,'Limit false alarms'),
                  (1500,583,'Limit undecidable cases'),(1282,583,'Keep rules simple')]: txt(x,y,t,28)
    end()
    flow('selection-to-rules','development-output','rule-selection','selected-rules','M1316 600V610',model=True)
    group('selected-rules',data_kind='model-artifact',data_bounds='1286,610,280,56')
    add(rect(1286,610,60,56,C['purple'],12)); icon('file-text',1278,603,2.8)
    txt(1362,647,'Selected rules',29,'bold',C['rule_outline']); end(); end()
    # The fixed model enters the shared frame from the bottom-right. Its port
    # is separate from both data modes and from the shared result arrow.
    flow('load-selected-rules','model-input','selected-rules','current-detection','M1286 641H1248V570H1208V549',model=True)
    group('research-evaluation',data_kind='evaluation-scope')
    txt(858,711,'Research evaluation',29,'bold')
    txt(1126,711,'Detection · False alarms · Undecidable cases · Ablations',28); end()
    add('</svg>')
    result='\n'.join(parts)+'\n'; root=ET.fromstring(result)
    # The reviewed complete candidate is the finishing content authority.
    before=HERE/'compression_baseline_86aa74c/CONTENT_MANIFEST.json'
    expected=json.loads(before.read_text())['candidate']
    assert Counter(expected)==Counter(content),(Counter(expected)-Counter(content),Counter(content)-Counter(expected))
    (HERE/'HybridGuard_overview_candidate.svg').write_text(result)
    (HERE/'CONTENT_MANIFEST.json').write_text(json.dumps({'source':'compression_baseline_86aa74c/CONTENT_MANIFEST.json',
        'expected':expected,'candidate':content,'exact_copy_multiset_equal':True},ensure_ascii=False,indent=2)+'\n')
    (HERE/'layout.json').write_text(json.dumps({'size_mm':[180,H/10],'viewbox':[W,H],'boxes':BOX,'nodes':NODES,
        'palette':C,'type_units':TYPE,'line_units':LINE,
        'compression':{'baseline':'86aa74c','rotation':'90 degrees counter-clockwise; upright icons and text',
                       'app_outlet':[780,214],'app_branch':[856,285],
                       'browser_outlet':[792,674],'paired_join':[856,463],
                       'mode_inputs':[[898,285],[898,463]],'rule_input':[1208,549],
                       'columns':{'observations':[18,834],'current_detection':[880,1230],'auxiliary':[1270,1782]}}
        },ensure_ascii=False,indent=2)+'\n')
    # Export reusable new icon vectors beside the unchanged inherited assets.
    for name in ['browser','list-details','files','file-text']:
        body=browser_icon() if name=='browser' else material_icon(name)
        (HERE/'assets'/f'{name}_adapted.svg').write_text(f'<svg xmlns="{NS}" width="24" height="24" viewBox="0 0 24 24">{body}</svg>\n')
    print(f'Complete candidate: 180 x {H/10:g} mm; {len(content)} formal text entries preserved.')

if __name__=='__main__': main()
