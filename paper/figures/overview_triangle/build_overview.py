"""Render the triangle overview from fixed labels; no research entrypoints run."""
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1800, 1250
C = {'ink': '#343434', 'muted': '#666666', 'blue': '#507cc4',
     'warm': '#bd8b47', 'sage': '#65855a', 'context': '#9a9a95',
     'cream': '#faf0e2', 'ice': '#e9f0f9', 'green': '#edf3e9'}
offline_bg = '#EEE2FA'
browser_bg = '#E9F3F3'
accent_red = '#D62828'
relation_label_border = '#B9C0C8'
parts = []


def add(s):
    parts.append(s)


def rect(x, y, w, h, fill='white', stroke='none', r=16, sw=1.8, dash=None):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"'
        + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')


def text(x, y, value, size=29, weight='normal', anchor='middle', color=None, italic=False, emphasis=None):
    content = escape(value)
    if emphasis:
        before, phrase, after = value.partition(emphasis)
        if not phrase:
            raise ValueError(f'Emphasis not found: {emphasis}')
        content = f'{escape(before)}<tspan fill="{accent_red}">{escape(phrase)}</tspan>{escape(after)}'
    add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
        f'text-anchor="{anchor}" fill="{color or C["ink"]}"'
        + (' font-style="italic"' if italic else '')
        + (' xml:space="preserve"' if emphasis else '') + f'>{content}</text>')


def path(d, color, sw=2.2, dash=None, marker=None, both=False):
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" '
        'stroke-linecap="round" stroke-linejoin="round"'
        + (f' stroke-dasharray="{dash}"' if dash else '')
        + (f' marker-end="url(#{marker})"' if marker else '')
        + (f' marker-start="url(#{marker})"' if marker and both else '') + '/>')


def icon(name, x, y, size, color):
    add(f'<use href="#{name}" xlink:href="#{name}" x="{x}" y="{y}" '
        f'width="{size}" height="{size}" color="{color}"/>')


def relation(id_, source, target, d, status):
    colors = {'selected': C['blue'], 'studied': C['warm'], 'context': C['context']}
    dashes = {'selected': None, 'studied': '10 7', 'context': '3 7'}
    add(f'<g id="{id_}" data-kind="relation" data-status="{status}" '
        f'data-source="{source}" data-target="{target}">')
    marker = None if status == 'context' else 'relation-' + status
    path(d, colors[status], 3.2 if status == 'selected' else 2.6,
         dashes[status], marker, both=status != 'context')
    add('</g>')


def current(id_, source, target, d, arrow=True):
    add(f'<g id="{id_}" data-kind="current-input" data-source="{source}" data-target="{target}">')
    path(d, C['ink'], 2.0, marker='input-arrow' if arrow else None)
    add('</g>')


add(f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
width="180mm" height="125mm" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
<title id="title">HybridGuard: Detecting device-fingerprint manipulation</title>
<desc id="desc">Complementary observations from one device help check device-fingerprint reports for possible manipulation. Device and OS, app container, and embedded webpage form an App triangle. The standalone browser is outside the App but on the same device. Solid comparison edges denote selected system–web memory/timezone and App–browser timezone relations. Dashed container–web geometry remains a separate study; the dotted Native–Host link is context only. An independent timezone inset contrasts two illustrative current states. Offline selection evaluates within-view and cross-view candidates using controlled modifications and normal development data, under false-alarm, coverage and simplicity constraints. Selected rules and current data enter a shared detection area through separate paths. Vertically stacked alternative App-only and linked App–browser input modes use their corresponding fixed rules. One arrow from the common rule-application area denotes the selected mode's output: manipulation alert, no alert, or insufficient evidence. The evaluation strip denotes research scope, not an online processing stage. No observation point is trusted ground truth; no alert does not establish safety. Execution failures are recorded separately.</desc>
<style>text {{font-family:'Times New Roman',Times,serif}} use {{fill:none;stroke:currentColor;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round}}</style>
<defs>''')
for kind, color in [('selected', C['blue']), ('studied', C['warm'])]:
    add(f'<marker id="relation-{kind}" markerWidth="13" markerHeight="13" refX="10" refY="6.5" '
        f'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M2 2 L10 6.5 L2 11" '
        f'fill="none" stroke="{color}" stroke-width="2.3" stroke-linejoin="round"/></marker>')
add('''<marker id="input-arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L10 5 L0 10 L3 5Z" fill="#343434"/></marker>
<marker id="model-arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L10 5 L0 10 L3 5Z" fill="#80649b"/></marker>
<symbol id="native-phone" viewBox="0 0 48 48"><rect x="10" y="2" width="28" height="44" rx="4"/><path d="M10 10h28M10 37h28M21 41.5h6"/><g transform="translate(0 -1.5)" stroke-width="2.1"><path d="M22 15h4l.6 2.7 2.5 1.4 2.6-.8 2 3.4-2 1.9v2.8l2 1.9-2 3.4-2.6-.8-2.5 1.4L26 35h-4l-.6-2.7-2.5-1.4-2.6.8-2-3.4 2-1.9v-2.8l-2-1.9 2-3.4 2.6.8 2.5-1.4Z"/><circle cx="24" cy="25" r="3"/></g></symbol>
<symbol id="host" viewBox="0 0 48 48"><rect x="3" y="6" width="42" height="37" rx="4"/><path d="M3 15h42M9 10.5h9"/><path d="M12 20h17l7 6v11H12Z"/><path d="M29 20v6h7M17 31h13" stroke-width="1.8"/></symbol>
<symbol id="app-web-js" viewBox="0 0 48 48"><path d="M10 3h20l10 10v30q0 2-2 2H10q-2 0-2-2V5q0-2 2-2Z"/><path d="M30 3v10h10M15 39h18"/><text x="24" y="32" text-anchor="middle" font-family="'Times New Roman',Times,serif" font-size="20" font-weight="bold" fill="currentColor" stroke="none">JS</text></symbol>
<symbol id="web" viewBox="0 0 48 48"><rect x="4" y="7" width="40" height="34" rx="4"/><path d="M4 16h40M11 12h1m5 0h1M17 23l-6 6 6 6m14-12l6 6-6 6m-5-14l-4 16"/></symbol>
</defs>''')


def flow(id_, kind, source, target, d, model=False, arrow=True):
    """Directed development/model/output flow, distinct from comparison edges."""
    add(f'<g id="{id_}" data-kind="{kind}" data-source="{source}" data-target="{target}">')
    path(d, '#80649b' if model else C['ink'], 2.2,
         marker=('model-arrow' if model else 'input-arrow') if arrow else None)
    add('</g>')


rect(0, 0, W, H, r=0)
text(24, 45, 'HybridGuard: Detecting device-fingerprint manipulation', 40, 'bold', 'start')
text(24, 87, 'Manipulated reports may conflict across observation points.', 29, anchor='start')

# Same-device boundary includes the separate browser, not offline development.
add('<g id="device-observations">')
rect(24, 124, 1160, 734, stroke='#b9c0c8', sw=1.5)
rect(44, 110, 650, 40)
text(55, 144, 'One device, multiple observation points', 32, 'bold', 'start')
add('<g id="app-observations">')
rect(44, 178, 1120, 516, stroke='#93938e', sw=1.7, dash='6 6')
rect(64, 160, 210, 40)
text(75, 191, 'Inside the app', 32, 'bold', 'start')
# Intersections of the three relation lines extended beneath the opaque cards.
# The fill meets their centerlines; the visible relation paths stay unchanged.
add('<path d="M589.790576 230.109948 L229.894737 610 L993.673684 610Z" fill="#f8fafb"/>')
relation('native-host', 'native', 'webview-host', 'M480 346 L300 536', 'context')
relation('native-app-web', 'native', 'app-web', 'M713 346 L915 536', 'selected')
relation('host-app-web', 'webview-host', 'app-web', 'M430 610 H746', 'studied')

# Preserve all three approved icon definitions and sizes.
add('<g id="native">')
rect(420, 206, 360, 140, C['cream'], C['ink'], 20)
icon('native-phone', 444, 224, 52, C['warm'])
text(514, 249, 'Device & OS', 34, 'bold', 'start')
text(600, 288, '(Native)', 28)
text(600, 327, 'Memory and timezone', 29)
add('</g>')

for id_, x, w, title, term, detail, symbol, fill, color in [
    ('webview-host', 60, 370, 'App container', '(WebView Host)', 'Container settings', 'host', C['ice'], C['blue']),
    ('app-web', 746, 410, 'Embedded webpage', '(App Web)', 'Reported properties', 'app-web-js', C['green'], C['sage']),
]:
    add(f'<g id="{id_}">')
    rect(x, 536, w, 138, fill, C['ink'], 20)
    icon(symbol, x + 20, 554, 48, color)
    text(x + 77, 576, title, 34, 'bold', 'start')
    text(x + w / 2, 617, term, 28)
    text(x + w / 2, 654, detail, 29)
    add('</g>')

rect(105, 372, 335, 78, stroke=relation_label_border, sw=1.2)
text(272.5, 403, 'Shared context', 30, 'bold', color=C['muted'])
text(272.5, 438, 'No detection rule', 28, color=C['muted'])
rect(774, 372, 382, 78, stroke=relation_label_border, sw=1.2)
text(965, 403, 'System–web consistency', 30, 'bold', color=C['blue'])
text(965, 438, 'Memory and timezone', 29, color=C['blue'])
text(600, 442, 'Cross-check', 38, 'bold', color=accent_red)
text(600, 478, 'reported properties', 30)
rect(432, 489, 312, 86)
text(588, 522, 'Container–web geometry', 28, 'bold', color=C['warm'])
text(588, 560, 'Not in current detector', 28, color=C['warm'])
add('</g>')

# A comparison outside the App boundary; both endpoints are on this device.
relation('app-browser', 'app-web', 'browser', 'M965 674 V699 H640 V780 H746', 'selected')
rect(180, 719, 435, 90, stroke=relation_label_border, sw=1.2)
text(397.5, 754, 'App–browser consistency', 30, 'bold', color=C['blue'])
text(397.5, 791, 'Timezone reports', 29, color=C['blue'])
add('<g id="browser">')
rect(746, 714, 410, 132, browser_bg, C['ink'], 20)
icon('web', 766, 732, 48, C['sage'])
text(823, 754, 'Standalone browser', 32, 'bold', 'start')
text(951, 789, 'On the same device', 28)
text(951, 826, 'Separate web runtime', 29)
add('</g>')
add('</g>')

# Independent illustrative states; deliberately no flow arrows or input ports.
add('<g id="timezone-example" data-kind="illustration">')
rect(1214, 124, 562, 251, stroke=relation_label_border, sw=1.2)
text(1240, 162, 'Example: timezone', 32, 'bold', 'start')
text(1240, 208, 'Normal system change', 30, 'bold', 'start')
text(1240, 246, 'System and web remain compatible', 28, anchor='start')
path('M1238 264 H1752', relation_label_border, 1)
text(1240, 302, 'Web-only modification', 30, 'bold', 'start')
text(1240, 341, 'Reports may conflict', 28, anchor='start', emphasis='conflict')
add('</g>')

# Full-width independent inputs. The upper input bypasses the lower input.
add('<g id="offline-development">')
rect(1214, 397, 562, 461, offline_bg)
text(1238, 435, 'Select detection rules', 32, 'bold', 'start')
text(1753, 435, 'Offline', 28, anchor='end', color=C['muted'], italic=True)
add('<g id="candidate-checks">')
rect(1236, 450, 480, 78, r=12)
text(1260, 481, 'Candidate checks', 29, 'bold', 'start')
text(1260, 516, 'Within-view + cross-view', 28, anchor='start')
add('</g>')
add('<g id="development-data">')
rect(1236, 544, 480, 114, r=12)
text(1260, 575, 'Development data', 29, 'bold', 'start')
text(1260, 610, 'Controlled modifications', 28, anchor='start')
text(1260, 645, 'Normal devices and settings', 28, anchor='start')
add('</g>')
flow('candidates-to-selection', 'development-input', 'candidate-checks', 'selection-inputs', 'M1716 489 H1744 V677 H1497', arrow=False)
flow('data-to-selection', 'development-input', 'development-data', 'selection-inputs', 'M1497 658 V677', arrow=False)
flow('selection-input', 'development-input', 'selection-inputs', 'rule-selection', 'M1497 677 V693')
add('<g id="rule-selection">')
rect(1214, 693, 562, 84, fill='none', r=0)
for x, y, label in [
    (1240, 724, 'Improve detection'), (1540, 724, 'Limit false alarms'),
    (1240, 760, 'Limit undecidable cases'), (1540, 760, 'Keep rules simple'),
]:
    text(x, y, label, 28, anchor='start')
add('</g>')
flow('selection-output', 'development-output', 'rule-selection', 'selected-rules', 'M1497 777 V796')
add('<g id="selected-rules">')
rect(1364, 796, 266, 44, r=12)
text(1497, 827, 'Selected rules', 29, 'bold', color='#80649b')
add('</g>')
add('</g>')

# 50-unit channel (y=858..908). Only the linked observations share a join.
# App-only enters from the left; the linked pair enters the lower card from the right.
current('current-app-only', 'app-observations', 'app-only-interface', 'M100 694 V998 H210')
current('current-app-for-pair', 'app-observations', 'linked-pair', 'M150 694 V884 H965', arrow=False)
current('current-browser-for-pair', 'browser', 'linked-pair', 'M965 846 V884', arrow=False)
add('<circle id="linked-pair" cx="965" cy="884" r="3" fill="#343434"/>')
current('current-linked-pair', 'linked-pair', 'paired-interface', 'M965 884 H1010 V1118 H960')

# One common rule-application frame encloses alternative configurations.
# The shared result list sits outside that frame; there are no per-mode result paths.
add('<g id="current-detection">')
rect(24, 908, 1140, 270, fill='none', stroke='#93938e', sw=1.7)
text(210, 946, 'Apply selected rules', 32, 'bold', 'start')
text(650, 946, 'Current observations only', 28, anchor='start', color=C['muted'])
for id_, y, title, rules, fill in [
    ('app-only-interface', 958, 'App observations only', 'App rules', C['ice']),
    ('paired-interface', 1078, 'App + linked browser observations', 'App + browser rules', C['green']),
]:
    add(f'<g id="{id_}">')
    rect(210, y, 750, 80, fill, r=12)
    text(234, y + 33, title, 29, 'bold', 'start')
    text(234, y + 67, rules, 28, anchor='start', color=C['muted'])
    add('</g>')
text(585, 1068, 'or', 28, color=C['muted'], italic=True)
add('</g>')

# Fixed models load at the rule-application header, away from data and results.
flow('load-selected-rules', 'model-input', 'selected-rules', 'current-detection', 'M1497 840 V884 H1200 V940 H1164', model=True)
flow('selected-mode-result', 'decision-output', 'current-detection', 'decision-vocabulary', 'M1164 1058 H1305')
add('<g id="decision-vocabulary">')
text(1340, 1030, 'Manipulation alert', 29, 'bold', 'start', color=accent_red)
text(1340, 1068, 'No alert', 29, anchor='start')
text(1340, 1106, 'Insufficient evidence', 29, anchor='start')
add('</g>')

# Separate research scope, with no inference or feedback arrows.
add('<g id="research-evaluation" data-kind="evaluation-scope">')
text(24, 1224, 'Research evaluation', 29, 'bold', 'start')
text(340, 1224, 'Detection · False alarms · Undecidable cases · Ablations', 28, anchor='start')
add('</g>')
add('</svg>')
(HERE / 'HybridGuard_overview_triangle.svg').write_text('\n'.join(parts) + '\n', encoding='utf-8')
print('Wrote HybridGuard_overview_triangle.svg (180 × 125 mm)')
