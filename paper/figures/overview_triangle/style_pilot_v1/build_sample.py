"""Build only the review sample. Never import or run the formal figure builder.

Run from any directory: python3 -B /absolute/path/to/build_sample.py
The adjacent render_sample.cjs produces PNGs and review plates.
"""
from html import escape
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
W, H = 1160, 590
PALETTE = {
    'ink': '#343434', 'muted': '#666666', 'blue': '#507cc4',
    'warm': '#bd8b47', 'context': '#9a9a95', 'red': '#D62828',
    'cream': '#faf0e2', 'ice': '#e9f0f9', 'green': '#edf3e9',
    'native_outline': '#806442', 'native_fill': '#ecd8b9',
    'host_outline': '#43668e', 'host_fill': '#c7d7e9',
    'web_outline': '#58734f', 'web_fill': '#cfddc6',
    'boundary': '#B9C0C8', 'app_boundary': '#93938e',
}
FONT = "'Times New Roman',Times,serif"
TYPE = {'group': 32, 'title': 34, 'role': 28, 'body': 29,
        'relation': 30, 'geometry': 28, 'action': 38, 'action_body': 30}
STROKE = {'object': 3.5, 'detail': 2, 'selected': 3.2,
          'studied': 2.6, 'context': 2.6, 'leader': 1.5, 'group': 1.5}
ASSETS = HERE / 'assets' / 'tabler'
LAYOUT = {
    'native': {'bounds': [403, 102, 409, 139], 'text': [548, 145], 'icon': [398, 98, 6]},
    'webview-host': {'bounds': [30, 407, 404, 140], 'text': [180, 445], 'icon': [24, 410, 6.1]},
    'app-web': {'bounds': [727, 407, 413, 140], 'text': [834, 445], 'icon': [713, 410, 5.5]},
    'action': [577, 344], 'geometry': [563, 523],
}

def attrs(**kw):
    return ' '.join(f'{k.replace("_", "-")}="{escape(str(v), quote=True)}"'
                    for k, v in kw.items() if v is not None)

def path(d, stroke, width=2, fill='none', **kw):
    return f'<path {attrs(d=d, stroke=stroke, stroke_width=width, fill=fill, stroke_linecap="round", stroke_linejoin="round", **kw)}/>'

def rect(x, y, w, h, fill, radius=0, stroke='none', sw=0, **kw):
    return f'<rect {attrs(x=x,y=y,width=w,height=h,rx=radius,fill=fill,stroke=stroke,stroke_width=sw,**kw)}/>'

def text(x, y, label, size, color=None, weight='normal', anchor='start', **kw):
    return f'<text {attrs(x=x,y=y,font_size=size,fill=color or PALETTE["ink"],font_weight=weight,text_anchor=anchor,**kw)}>{escape(label)}</text>'

def library_paths(name):
    root = ET.parse(ASSETS / f'{name}.svg').getroot()
    return [p.attrib['d'] for p in root.findall('{http://www.w3.org/2000/svg}path')]

def svg(body, width=W, height=H, physical=True, label='HybridGuard triangle visual pilot'):
    unit = 'mm' if physical else ''
    w, h = (width / 10, height / 10) if physical else (width, height)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}{unit}" height="{h}{unit}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
            f'<title id="title">{escape(label)}</title><desc id="desc">'
            'Three observations in the same app on one device. Solid blue compares Native and App Web; '
            'dashed ochre Host–App Web geometry is not in the current detector; dotted gray Native–Host '
            'is shared context only and has no arrow. The observations are not trusted ground truth. '
            'A review sample only; the rest of the method remains in the unchanged formal figure.</desc>'
            f'<style>text {{font-family:{FONT}}}</style>'
            '<!-- Adapted Tabler Icons v3.34.1; MIT, Copyright (c) 2020-2024 Pawel Kuna. '
            'Full notice and modifications: assets/tabler/LICENSE and assets/SOURCES.md. -->'
            + body + '</svg>')

def native_icon():
    c = PALETTE['native_outline']
    p = library_paths('device-mobile')
    out = path(p[0], c, .60, PALETTE['native_fill'])
    out += rect(7.35, 5.65, 9.3, 11.5, 'white', .7, c, .28)
    out += path(p[1], c, .52)
    out += path('M11.1 19h1.8', c, .52)
    out += '<g transform="translate(7.65 7.2) scale(.36)">'
    for d in library_paths('adjustments-horizontal'):
        out += path(d, c, 1.35)
    return out + '</g>'

def page_icon(outline=None, fold=None, sw=.60):
    c = outline or PALETTE['web_outline']
    f = fold or PALETTE['web_fill']
    # Close the Tabler file outline; bring JS inside the sheet as editable text.
    out = path('M5 5a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2H7a2 2 0 0 1 -2 -2Z', c, sw, 'white')
    out += path('M14 3v4a1 1 0 0 0 1 1h4Z', 'none', 0, f)
    out += path(library_paths('file-type-js')[0], c, sw)
    out += path('M8 11h8M8 13.5h5.5', c, .36)
    out += text(12, 19.2, 'JS', 6.4, c, 'bold', 'middle', data_icon_mark='JS')
    return out

def host_icon():
    c = PALETTE['host_outline']
    out = path(library_paths('app-window')[0], c, .64, PALETTE['host_fill'])
    out += rect(4.1, 8.65, 15.8, 9.2, 'white', .6)
    # One application tab, not browser navigation or a measurement ruler.
    out += path('M5.5 6.85h2.3', c, .5)
    out += path('M11 6.85h7.3', c, .32)
    out += '<g transform="translate(6.72 8.15) scale(.44)">'
    out += page_icon(c, PALETTE['host_fill'], .72)
    return out + '</g>'

def place_icon(id_, fn):
    x, y, s = LAYOUT[id_]['icon']
    return f'<g id="icon-{id_}" transform="translate({x} {y}) scale({s})">{fn()}</g>'

def main():
    parts = [rect(0, 0, W, H, 'white')]
    defs = '<defs>'
    for status, color in [('selected', 'blue'), ('studied', 'warm')]:
        defs += (f'<marker id="compare-{status}" markerWidth="13" markerHeight="13" '
                 'refX="10" refY="6.5" orient="auto-start-reverse" markerUnits="userSpaceOnUse">'
                 + path('M2 2L10 6.5L2 11', PALETTE[color], 2.3) + '</marker>')
    parts.append(defs + '</defs>')
    # Two meaningful scope boundaries; gaps are in the strokes, not white masks.
    parts.append('<g id="device-scope" data-kind="same-device-scope">')
    parts.append(path('M591 21H1145Q1159 21 1159 35V574Q1159 589 1145 589H15Q1 589 1 574V35Q1 21 15 21H21', PALETTE['boundary'], 1.5))
    parts.append(text(30, 32, 'One device, multiple observation points', TYPE['group'], weight='bold'))
    parts.append('<g id="app-scope" data-kind="inside-app-scope">')
    parts.append(path('M253 74H1128Q1140 74 1140 86V564Q1140 576 1128 576H32Q20 576 20 564V86Q20 74 32 74H34', PALETTE['app_boundary'], 1.5, stroke_dasharray='6 6'))
    parts.append(text(40, 85, 'Inside the app', TYPE['group'], weight='bold'))

    for id_, source, target, d, state, color in [
        ('native-host', 'native', 'webview-host', 'M430 247L265 404', 'context', 'context'),
        ('native-app-web', 'native', 'app-web', 'M724 247L887 404', 'selected', 'blue'),
        ('host-app-web', 'webview-host', 'app-web', 'M438 477H718', 'studied', 'warm'),
    ]:
        mark = None if state == 'context' else f'url(#compare-{state})'
        parts.append(f'<g {attrs(id=id_,data_kind="relation",data_source=source,data_target=target,data_status=state)}>')
        parts.append(path(d, PALETTE[color], STROKE[state], stroke_dasharray={'context':'1 7','studied':'10 7'}.get(state), marker_start=mark, marker_end=mark))
        parts.append('</g>')

    parts.append('<g id="context-label" data-relation="native-host">')
    parts.append(text(325, 290, 'Shared context', TYPE['relation'], PALETTE['muted'], 'bold', 'end'))
    parts.append(text(325, 325, 'No detection rule', TYPE['role'], PALETTE['muted'], anchor='end'))
    parts.append(path('M343 302H372', PALETTE['context'], STROKE['leader']))
    parts.append('</g><g id="consistency-label" data-relation="native-app-web">')
    parts.append(text(815, 290, 'System–web consistency', TYPE['relation'], PALETTE['blue'], 'bold'))
    parts.append(text(815, 325, 'Memory and timezone', TYPE['body'], PALETTE['blue']))
    parts.append(path('M781 302H799', PALETTE['blue'], STROKE['leader']))
    parts.append('</g><g id="geometry-label" data-relation="host-app-web">')
    parts.append(text(563, 523, 'Container–web geometry', TYPE['geometry'], PALETTE['warm'], 'bold', 'middle'))
    parts.append(text(563, 558, 'Not in current detector', TYPE['role'], PALETTE['warm'], anchor='middle'))
    parts.append(path('M563 477V496', PALETTE['warm'], STROKE['leader']))
    parts.append('</g><g id="core-action">')
    parts.append(text(577, 344, 'Cross-check', TYPE['action'], PALETTE['red'], 'bold', 'middle'))
    parts.append(text(577, 382, 'reported properties', TYPE['action_body'], anchor='middle'))
    parts.append('</g>')

    nodes = [
        ('native', 'Device & OS', '(Native)', 'Memory and timezone', 'cream', native_icon, (413,104,112,134)),
        ('webview-host', 'App container', '(WebView Host)', 'Container settings', 'ice', host_icon, (30,407,132,140)),
        ('app-web', 'Embedded webpage', '(App Web)', 'Reported properties', 'green', page_icon, (727,407,102,140)),
    ]
    for id_, title, role, detail, color, fn, field in nodes:
        x, y = LAYOUT[id_]['text']
        parts.append(f'<g id="{id_}" data-kind="observation">')
        parts.append(rect(*field, PALETTE[color], 17))
        parts.append(place_icon(id_, fn))
        parts.append(text(x,y,title,TYPE['title'],weight='bold'))
        parts.append(text(x,y+39 if id_=='native' else y+37,role,TYPE['role']))
        parts.append(text(x,y+78 if id_=='native' else y+76,detail,TYPE['body']))
        parts.append('</g>')
    parts.append('</g></g>')
    result = svg(''.join(parts))
    ET.fromstring(result)
    (HERE/'triangle_style_sample.svg').write_text(result)
    for name, fn in [('native',native_icon),('host',host_icon),('app-web',page_icon)]:
        (HERE/'assets'/f'{name}_adapted.svg').write_text(svg(fn(),24,24,False,label=f'{name} adapted icon'))
    (HERE/'layout.json').write_text(json.dumps({'canvas_units':[W,H], 'sample_mm':[116,59],
        'full_figure_mm':[180,125], 'placement_in_formal_viewbox':[24,104],
        'original_crop_viewbox':[24,104,1160,590], 'nodes':LAYOUT,
        'palette':PALETTE, 'type_units':TYPE, 'stroke_units':STROKE},indent=2))
    print('Created triangle_style_sample.svg (116 x 59 mm); formal files untouched.')

if __name__ == '__main__':
    main()
