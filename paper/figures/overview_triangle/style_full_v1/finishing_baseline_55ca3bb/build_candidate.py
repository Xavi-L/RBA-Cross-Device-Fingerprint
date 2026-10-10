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
W, H = 1800, 1330
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
BOX = dict(device=[24,124,1160,814], app=[44,178,1120,556],
           example=[1214,124,562,251], offline=[1214,397,562,541],
           process=[1228,694,534,128], detection=[24,994,1140,270])
NODES = {
    'native': dict(icon='native', origin=[422,202,6], field=[437,208,112,134],
                   text=[572,249], bounds=[431,203,411,148], fill='cream',
                   copy=['Device & OS','(Native)','Memory and timezone']),
    'webview-host': dict(icon='host', origin=[48,567,6.1], field=[54,564,132,140],
                   text=[204,602], bounds=[54,550,382,157], fill='ice',
                   copy=['App container','(WebView Host)','Container settings']),
    'app-web': dict(icon='app-web', origin=[713,567,5.5], field=[727,564,102,140],
                   text=[834,602], bounds=[718,550,416,157], fill='green',
                   copy=['Embedded webpage','(App Web)','Reported properties']),
    'browser': dict(icon='browser', origin=[725,768,6], field=[744,780,118,134],
                   text=[886,817], bounds=[733,776,431,148], fill='cyan',
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
def txt(x,y,label,size=29,weight='normal',color=None,anchor='start',emphasis=None,italic=False):
    content.append(label)
    val=escape(label)
    if emphasis:
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
    txt(x,y,n['copy'][0],32 if id_=='browser' else TYPE['node'],'bold')
    gap=39 if id_=='native' else 37
    txt(x,y+gap,n['copy'][1],TYPE['role'])
    txt(x,y+gap*2+2*(id_!='native'),n['copy'][2],TYPE['body'])
    end()

def main():
    original=ET.parse(HERE/'baseline/HybridGuard_overview_triangle.svg').getroot()
    desc=original.find(f'{{{NS}}}desc').text
    add(f'<svg xmlns="{NS}" width="180mm" height="133mm" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">')
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

    group('device-observations',data_kind='same-device-scope',data_bounds=','.join(map(str,BOX['device'])))
    add(path('M615 124H1168Q1184 124 1184 140V922Q1184 938 1168 938H40Q24 938 24 922V140Q24 124 40 124H45',C['boundary'],1.5))
    txt(54,144,'One device, multiple observation points',32,'bold')
    group('app-observations',data_kind='inside-app-scope',data_bounds=','.join(map(str,BOX['app'])))
    add(path('M276 178H1152Q1164 178 1164 190V722Q1164 734 1152 734H56Q44 734 44 722V190Q44 178 56 178H58',C['app_boundary'],1.5,stroke_dasharray='6 6'))
    txt(64,191,'Inside the app',32,'bold')
    # Light open brackets associate terminals with the complete icon/text object.
    group('observation-anchors',data_kind='object-group-anchors')
    add(path('M431 343V351H842V343',C['boundary'],LINE['anchor']))
    add(path('M54 558V550H436V707H428',C['boundary'],LINE['anchor']))
    add(path('M1134 558V550H718V707H1134V699',C['boundary'],LINE['anchor']))
    end()
    relation('native-host','native','webview-host','M454 351L280 550','context')
    relation('native-app-web','native','app-web','M748 351L880 550','selected')
    relation('host-app-web','webview-host','app-web','M436 590H718','studied')
    group('context-label',data_relation='native-host')
    txt(346,404,'Shared context',30,'bold',C['muted'],'end')
    txt(346,439,'No detection rule',28,color=C['muted'],anchor='end')
    add(path('M363 418H395.4',C['context'],1.5)); end()
    group('consistency-label',data_relation='native-app-web')
    txt(821,404,'System–web consistency',30,'bold',C['blue'])
    txt(821,439,'Memory and timezone',29,color=C['blue'])
    add(path('M792.44 418H805',C['blue'],1.5)); end()
    group('core-action')
    txt(598,423,'Cross-check',38,'bold',C['red'],'middle')
    txt(598,461,'reported properties',30,anchor='middle'); end()
    group('geometry-label',data_relation='host-app-web')
    txt(577,504,'Container–web geometry',28,'bold',C['warm'],'middle')
    txt(577,539,'Not in current detector',28,color=C['warm'],anchor='middle')
    add(path('M577 551V590',C['warm'],1.5)); end()
    for id_ in ['native','webview-host','app-web']: node(id_)
    end() # App scope

    relation('app-browser','app-web','browser','M963 707V752H658V846H733','selected')
    group('browser-label',data_relation='app-browser')
    txt(235,817,'App–browser consistency',30,'bold',C['blue'])
    txt(235,854,'Timezone reports',29,color=C['blue'])
    add(path('M582 833H658',C['blue'],1.5)); end()
    group('browser-anchor',data_kind='object-group-anchors')
    add(path('M741 776H733V924H1164V916',C['boundary'],LINE['anchor'])); end()
    node('browser'); end() # Device scope

    # An explanatory two-case note. No flow, success badge, or invented values.
    group('timezone-example',data_kind='illustration',data_bounds=','.join(map(str,BOX['example'])))
    txt(1240,162,'Example: timezone',32,'bold')
    add(path('M1214 184H1776',C['boundary'],1.2))
    add(path('M1226 201H1218V252H1226',C['boundary'],1.5))
    txt(1240,214,'Normal system change',30,'bold')
    txt(1240,251,'System and web remain compatible',28)
    add(path('M1226 292H1218V343H1226',C['boundary'],1.5))
    txt(1240,305,'Web-only modification',30,'bold')
    txt(1240,342,'Reports may conflict',28,emphasis='conflict'); end()

    # Offline: two materials, a processing module, and a rule artifact.
    group('offline-development',data_kind='offline-scope',data_bounds=','.join(map(str,BOX['offline'])))
    add(path('M1343 408H1760Q1776 408 1776 424V922Q1776 938 1760 938H1230Q1214 938 1214 922V424Q1214 408 1230 408',C['rule_fill'],1.5))
    txt(1240,418,'Offline',28,color=C['muted'],italic=True)
    group('candidate-checks',data_kind='development-material',data_bounds='1238,436,454,88')
    add(rect(1238,436,88,88,C['purple'],14)); icon('list-details',1234,430,4)
    txt(1342,470,'Candidate checks',29,'bold')
    txt(1342,507,'Within-view + cross-view',28)
    add(path('M1684 440H1692V520H1684',C['rule_fill'],1.2)); end()
    group('development-data',data_kind='development-material',data_bounds='1238,552,454,116')
    add(rect(1238,552,88,116,C['purple'],14)); icon('files',1230,556,4.1)
    txt(1342,578,'Development data',29,'bold')
    txt(1342,615,'Controlled modifications',28)
    txt(1342,652,'Normal devices and settings',28); end()
    flow('candidate-to-selection','development-input','candidate-checks','rule-selection','M1692 480H1754V677H1610V694')
    flow('data-to-selection','development-input','development-data','rule-selection','M1498 668V694')
    group('rule-selection',data_kind='development-process',data_bounds=','.join(map(str,BOX['process'])))
    add(rect(*BOX['process'],C['purple'],14))
    txt(1244,729,'Select detection rules',32,'bold')
    for x,y,t in [(1244,768,'Improve detection'),(1540,768,'Limit false alarms'),
                  (1244,804,'Limit undecidable cases'),(1540,804,'Keep rules simple')]: txt(x,y,t,28)
    end()
    flow('selection-to-rules','development-output','rule-selection','selected-rules','M1405 822V848',model=True)
    group('selected-rules',data_kind='model-artifact',data_bounds='1360,848,314,79')
    add(rect(1360,848,88,79,C['purple'],14)); icon('file-text',1356,837,4)
    txt(1464,892,'Selected rules',29,'bold',C['rule_outline']); end(); end()

    # Current data bypass Offline. Only the paired data have a join.
    flow('current-app-only','current-input','app-observations','app-only-interface','M100 734V1084H210')
    flow('current-app-for-pair','current-input','app-observations','linked-pair','M150 734V963H965',arrow=False)
    flow('current-browser-for-pair','current-input','browser','linked-pair','M965 924V963',arrow=False)
    add('<circle id="linked-pair" cx="965" cy="963" r="3" fill="#343434"/>')
    flow('current-linked-pair','current-input','linked-pair','paired-interface','M965 963H1010V1204H960')
    group('current-detection',data_kind='current-rule-application',data_bounds=','.join(map(str,BOX['detection'])))
    add(rect(*BOX['detection'],radius=16,stroke=C['app_boundary'],width=1.7))
    txt(210,1032,'Apply selected rules',32,'bold')
    txt(650,1032,'Current observations only',28,color=C['muted'])
    for id_,y,title,rules,fill in [
        ('app-only-interface',1044,'App observations only','App rules','ice'),
        ('paired-interface',1164,'App + linked browser observations','App + browser rules','green')]:
        group(id_,data_kind='alternative-mode',data_bounds=f'210,{y},750,80')
        add(rect(210,y,750,80,C[fill],12))
        txt(234,y+33,title,29,'bold'); txt(234,y+67,rules,28,color=C['muted']); end()
    txt(585,1154,'or',28,color=C['muted'],anchor='middle',italic=True); end()
    flow('load-selected-rules','model-input','selected-rules','current-detection','M1405 927V963H1200V1026H1164',model=True)
    flow('selected-mode-result','decision-output','current-detection','decision-vocabulary','M1164 1144H1305')
    group('decision-vocabulary')
    txt(1340,1116,'Manipulation alert',29,'bold',C['red'])
    txt(1340,1154,'No alert',29); txt(1340,1192,'Insufficient evidence',29); end()
    group('research-evaluation',data_kind='evaluation-scope')
    txt(24,1310,'Research evaluation',29,'bold')
    txt(340,1310,'Detection · False alarms · Undecidable cases · Ablations',28); end()
    add('</svg>')
    result='\n'.join(parts)+'\n'; root=ET.fromstring(result)
    # Formal source is the content authority, not the saved pilot text.
    defs=original.find(f'{{{NS}}}defs')
    in_defs=set(defs.iter())
    expected=[''.join(t.itertext()) for t in original.iter(f'{{{NS}}}text') if t not in in_defs]
    assert Counter(expected)==Counter(content),(Counter(expected)-Counter(content),Counter(content)-Counter(expected))
    (HERE/'HybridGuard_overview_candidate.svg').write_text(result)
    (HERE/'CONTENT_MANIFEST.json').write_text(json.dumps({'source':'baseline/HybridGuard_overview_triangle.svg',
        'expected':expected,'candidate':content,'exact_copy_multiset_equal':True},ensure_ascii=False,indent=2)+'\n')
    (HERE/'layout.json').write_text(json.dumps({'size_mm':[180,133],'viewbox':[W,H],'boxes':BOX,'nodes':NODES,
        'palette':C,'type_units':TYPE,'line_units':LINE},ensure_ascii=False,indent=2)+'\n')
    # Export reusable new icon vectors beside the unchanged inherited assets.
    for name in ['browser','list-details','files','file-text']:
        body=browser_icon() if name=='browser' else material_icon(name)
        (HERE/'assets'/f'{name}_adapted.svg').write_text(f'<svg xmlns="{NS}" width="24" height="24" viewBox="0 0 24 24">{body}</svg>\n')
    print(f'Complete candidate: 180 x 133 mm; {len(content)} formal text entries preserved.')

if __name__=='__main__': main()
