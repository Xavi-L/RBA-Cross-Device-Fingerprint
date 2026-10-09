"""Render the triangle overview from fixed labels; no research entrypoints run."""
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1800, 1060
C = {'ink': '#343434', 'muted': '#666666', 'blue': '#507cc4',
     'warm': '#bd8b47', 'sage': '#65855a', 'context': '#9a9a95',
     'cream': '#faf0e2', 'ice': '#e9f0f9', 'green': '#edf3e9'}
parts = []


def add(s):
    parts.append(s)


def rect(x, y, w, h, fill='white', stroke='none', r=16, sw=1.8, dash=None):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"'
        + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')


def text(x, y, value, size=29, weight='normal', anchor='middle', color=None, italic=False):
    add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
        f'text-anchor="{anchor}" fill="{color or C["ink"]}"'
        + (' font-style="italic"' if italic else '') + f'>{escape(value)}</text>')


def path(d, color, sw=2.2, dash=None, marker=None, both=False):
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" '
        'stroke-linecap="round" stroke-linejoin="round"'
        + (f' stroke-dasharray="{dash}"' if dash else '')
        + (f' marker-end="url(#{marker})"' if marker else '')
        + (f' marker-start="url(#{marker})"' if both else '') + '/>')


def icon(name, x, y, size, color):
    add(f'<use href="#{name}" xlink:href="#{name}" x="{x}" y="{y}" '
        f'width="{size}" height="{size}" color="{color}"/>')


def relation(id_, source, target, d, status):
    colors = {'selected': C['blue'], 'studied': C['warm'], 'context': C['context']}
    dashes = {'selected': None, 'studied': '10 7', 'context': '3 7'}
    add(f'<g id="{id_}" data-kind="relation" data-status="{status}" '
        f'data-source="{source}" data-target="{target}">')
    path(d, colors[status], 3.2 if status == 'selected' else 2.6,
         dashes[status], 'relation-' + status, True)
    add('</g>')


def current(id_, source, target, d, arrow=True):
    add(f'<g id="{id_}" data-kind="current-input" data-source="{source}" data-target="{target}">')
    path(d, C['ink'], 2.0, marker='input-arrow' if arrow else None)
    add('</g>')


add(f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
width="180mm" height="106mm" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
<title id="title">HybridGuard: a triangle of Native, WebView Host, and App Web observations</title>
<desc id="desc">The three App observation locations form a relation triangle. Native–App Web memory and timezone relations are selected in the fixed App models. Host–App Web geometry was studied separately and is not integrated. The Native–Host edge denotes observation context only and is outside the current App rule pool. Double-headed edges identify compared views, not bidirectional prediction, causation or ground truth. An independent Browser sits outside the triangle; selected C1 compares its numeric UTC offset with App Web after session/receipt association. Current App and bound-pair inputs enter separate fixed-model interfaces, without passing through offline development. Catalog counts do not imply completeness, independent contributions, or trust. The model also contains App Web base rules, not exhaustively drawn here. No Browser-resource increment was admitted. Missing evidence and selected-input failures retain their existing U and FAILED semantics.</desc>
<style>text {{font-family:'Times New Roman',Times,serif}} use {{fill:none;stroke:currentColor;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round}}</style>
<defs>''')
for kind, color in [('selected', C['blue']), ('studied', C['warm']), ('context', C['context'])]:
    add(f'<marker id="relation-{kind}" markerWidth="13" markerHeight="13" refX="10" refY="6.5" '
        f'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M2 2 L10 6.5 L2 11" '
        f'fill="none" stroke="{color}" stroke-width="2.3" stroke-linejoin="round"/></marker>')
add('''<marker id="input-arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L10 5 L0 10 L3 5Z" fill="#343434"/></marker>
<symbol id="chip" viewBox="0 0 48 48"><rect x="11" y="11" width="26" height="26" rx="4"/><rect x="17" y="17" width="14" height="14" rx="2"/><path d="M17 5v6m7-6v6m7-6v6M17 37v6m7-6v6m7-6v6M5 17h6m-6 7h6m-6 7h6M37 17h6m-6 7h6m-6 7h6"/></symbol>
<symbol id="host" viewBox="0 0 48 48"><rect x="5" y="7" width="38" height="33" rx="4"/><path d="M5 15h38M11 11h1m5 0h1"/><rect x="13" y="22" width="22" height="12" rx="1"/><path d="M9 27h4m22 0h4M24 18v4m0 12v3"/></symbol>
<symbol id="web" viewBox="0 0 48 48"><rect x="4" y="7" width="40" height="34" rx="4"/><path d="M4 16h40M11 12h1m5 0h1M17 23l-6 6 6 6m14-12l6 6-6 6m-5-14l-4 16"/></symbol>
</defs>''')
rect(0, 0, W, H, r=0)
text(24, 48, 'HybridGuard: cross-view corroboration', 40, 'bold', 'start')

# The triangle is a map of relations. It is not a circular data-processing flow.
add('<g id="app-observations">')
rect(24, 95, 1220, 680, 'white', '#93938e', 18, 1.7, '6 6')
rect(44, 77, 610, 40)
text(55, 107, 'App177 · three observation views', 32, 'bold', 'start')
add('<path d="M640 205 L252 650 L1008 650Z" fill="#f8fafb"/>')
relation('native-host', 'native', 'webview-host', 'M574 282 L318 573', 'context')
relation('native-app-web', 'native', 'app-web', 'M704 282 L947 573', 'selected')
relation('host-app-web', 'webview-host', 'app-web', 'M429 650 H830', 'studied')

# Native apex.
add('<g id="native">')
rect(460, 130, 360, 150, C['cream'], C['ink'], 20)
icon('chip', 484, 148, 52, C['warm'])
text(554, 179, 'Native', 38, 'bold', 'start')
text(640, 220, '84 catalog fields')
text(640, 258, 'Device / OS observations', 28)
add('</g>')

# Lower vertices and their field catalogs.
for id_, x, title, count, detail, symbol, fill, color in [
    ('webview-host', 77, 'WebView Host', 26, 'Container & layout', 'host', C['ice'], C['blue']),
    ('app-web', 833, 'App Web', 67, 'In-WebView JS', 'web', C['green'], C['sage']),
]:
    add(f'<g id="{id_}">')
    rect(x, 575, 350, 150, fill, C['ink'], 20)
    icon(symbol, x + 20, 599, 48, color)
    text(x + 77, 625, title, 34, 'bold', 'start')
    text(x + 175, 665, f'{count} catalog fields')
    text(x + 175, 703, detail, 28)
    add('</g>')

# Edge labels use explicit status wording, in addition to line style and color.
rect(250, 361, 335, 87)
text(418, 397, 'System context', 32, 'bold', color=C['muted'])
text(418, 434, 'Outside current model', 29, color=C['muted'])
rect(749, 361, 390, 87)
text(944, 397, 'Memory + timezone', 32, 'bold', color=C['blue'])
text(944, 434, 'Selected in fixed App', 29, color=C['blue'])

text(650, 477, 'Cross-view', 40, 'bold')
text(650, 524, 'corroboration', 40, 'bold')
rect(449, 542, 376, 80)
text(637, 573, 'Viewport geometry', 31, 'bold', color=C['warm'])
text(637, 611, 'Studied; not integrated', 29, color=C['warm'])
text(634, 760, 'Catalog counts; only selected dependencies enter inference', 29, color=C['muted'], italic=True)
add('</g>')

# Small status key and offline summary stay secondary to the relation triangle.
text(1320, 111, 'Relation status', 33, 'bold', 'start')
for y, label, kind, color, dash in [
    (158, 'Selected', 'selected', C['blue'], None),
    (208, 'Studied', 'studied', C['warm'], '10 7'),
    (258, 'Context only', 'context', C['context'], '3 7'),
]:
    path(f'M1320 {y-9} H1380', color, 2.6, dash, 'relation-' + kind, True)
    text(1403, y, label, 30, anchor='start')
add('<g id="offline-development">')
rect(1290, 298, 486, 184, C['cream'])
text(1533, 340, 'Offline rule development', 32, 'bold')
text(1533, 380, 'App: SPARSE → RETENTION', 29)
text(1533, 420, 'C1: 4-set macro selection', 29)
text(1533, 461, 'Budget · coverage · complexity', 29)
add('</g>')

# C1 is separate from the three App views, and compares App Web to Browser.
add('<g id="browser">')
rect(1460, 575, 316, 150, C['green'], C['ink'], 20)
icon('web', 1481, 599, 48, C['sage'])
text(1547, 625, 'Browser', 38, 'bold', 'start')
text(1618, 665, '67 catalog fields')
text(1618, 703, 'Independent JS runtime', 28)
add('</g>')
relation('app-web-browser-c1', 'app-web', 'browser', 'M1188 650 H1452', 'selected')
rect(1272, 509, 96, 44, C['ice'], r=11)
text(1320, 541, 'C1', 31, 'bold', color=C['blue'])
text(1320, 590, 'UTC-offset', 29, color=C['blue'])
text(1320, 627, 'mismatch', 29, color=C['blue'])
text(1320, 700, 'Selected', 29, color=C['blue'], italic=True)
text(1437, 756, 'Session / receipt association', 29, color=C['muted'], italic=True)

# Current input paths only. No edge feeds current observations into development.
current('current-app-only', 'app-observations', 'app-only-interface', 'M350 777 V833')
text(377, 817, 'Current App', 29, anchor='start')
current('current-app-to-pair', 'app-observations', 'pair-input-join', 'M1040 777 V800 H1310', False)
current('current-browser-to-pair', 'browser', 'pair-input-join', 'M1618 727 V800 H1310', False)
add('<circle id="pair-input-join" cx="1310" cy="800" r="4" fill="#343434"/>')
current('current-pair', 'pair-input-join', 'paired-interface', 'M1310 800 V833')
text(1340, 831, 'Current bound pair', 29, anchor='start')

for id_, x, w, title, fill, content in [
    ('app-only-interface', 24, 782, 'App-only · fixed App', C['ice'], 'Current App → loaded rules → T / F / U / FAILED'),
    ('paired-interface', 904, 872, 'Paired · fixed App + C1', C['green'], 'Current pair → loaded rules → T / F / U / FAILED'),
]:
    add(f'<g id="{id_}">')
    rect(x, 840, w, 112, fill, '#777777', 17, 1.5)
    text(x + 28, 881, title, 33, 'bold', 'start')
    text(x + 28, 926, content, 29, anchor='start')
    add('</g>')

text(24, 994, 'T: Manipulation alert · F: No alarm · U: Insufficient evidence', 29, anchor='start')
text(1776, 994, 'Paired: no automatic App-only fallback', 29, anchor='end', color=C['muted'])
text(24, 1033, 'Selected-input execution / binding failure → FAILED', 29, anchor='start', color=C['muted'])
text(1776, 1033, 'Association ≠ atomic synchronization', 29, anchor='end', color=C['muted'], italic=True)
add('</svg>')

out = HERE / 'HybridGuard_overview_triangle.svg'
out.write_text('\n'.join(parts) + '\n', encoding='utf-8')
print(out)
