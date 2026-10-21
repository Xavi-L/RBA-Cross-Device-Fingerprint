#!/usr/bin/env python3
"""Rebuild the approved HybridGuard system-design figure without changing it.

The default output is ./build next to this script. The frozen originals are
intentionally not overwritten. SVG generation uses only the Python standard
library; PDF and PNG export additionally requires Inkscape and Nimbus Sans.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import argparse
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', type=Path,
                    default=Path(__file__).resolve().parent / 'build')
parser.add_argument('--svg-only', action='store_true',
                    help='Generate the SVG without invoking Inkscape.')
args = parser.parse_args()
OUT = args.output_dir.resolve()
if OUT == Path(__file__).resolve().parent:
    parser.error('Use a separate output directory to preserve the frozen originals.')
OUT.mkdir(parents=True, exist_ok=True)

P = []
INK = '#26313B'
MUTED = '#596570'
LINE = '#65717B'
FRAME = '#A8B1BA'
BLUE = '#365C7F'
BLUE_FILL = '#EDF3F8'
GREEN = '#3D756C'
GREEN_FILL = '#EFF6F3'
PURPLE = '#72618D'
PURPLE_FILL = '#F4F0F8'
RED = '#B63236'

def add(s):
    P.append(s)

def text(x, y, s, size=28, weight=400, color=INK, anchor='start', ident=None):
    ident = f' id="{ident}"' if ident else ''
    add(f'<text{ident} x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(s)}</text>')

def rect(x, y, w, h, fill='white', stroke=LINE, sw=1.8, radius=3, dash=None):
    ds = f' stroke-dasharray="{dash}"' if dash else ''
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{ds}/>')

def path(d, color=LINE, sw=2.2, arrow=False, dash=None):
    marker = 'config' if color == PURPLE else 'flow'
    tail = f' marker-end="url(#{marker})"' if arrow else ''
    ds = f' stroke-dasharray="{dash}"' if dash else ''
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"{tail}{ds}/>')

def folded(x, y, w, h, color=LINE, fill='white', fold=18):
    add(f'<path d="M{x} {y}H{x+w-fold}L{x+w} {y+fold}V{y+h}H{x}Z" fill="{fill}" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>')
    path(f'M{x+w-fold} {y}V{y+fold}H{x+w}', color=color, sw=1.5)

def stage(x, y, number, label):
    add(f'<circle cx="{x+12}" cy="{y-10}" r="12" fill="{INK}"/>')
    text(x+12, y-1.5, str(number), 24, 700, 'white', 'middle')
    text(x+34, y, label, 29, 700)

def phone(x, y):
    rect(x, y, 32, 57, fill='white', stroke=BLUE, sw=2.2, radius=4)
    path(f'M{x+8} {y+7}H{x+24}M{x+4} {y+43}H{x+28}', color=BLUE, sw=1.8)
    add(f'<circle cx="{x+16}" cy="{y+50}" r="2" fill="{BLUE}"/>')

def browser(x, y):
    rect(x, y, 43, 34, fill='white', stroke=GREEN, sw=2, radius=2)
    path(f'M{x} {y+9}H{x+43}', color=GREEN, sw=1.5)
    for dx in (6, 12, 18):
        add(f'<circle cx="{x+dx}" cy="{y+4.5}" r="1.3" fill="{GREEN}"/>')

add('<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="66mm" viewBox="0 0 1800 660" role="img" aria-labelledby="title desc">')
add('<title id="title">HybridGuard system design</title>')
add('<desc id="desc">HybridGuard detects evidence of manipulated environment reports. An illustrative memory check uses valid, bound Native and App Web reports of 4 and 8 GiB: the Web report exceeds the 4 GiB upper bound and the check triggers. Current App observations and an optionally linked Browser are associated with their values, field status, and provenance. Fixed selected checks evaluate individual views, Native-Web relations, and an optional App Web-Browser UTC-offset comparison C1. For a nonempty selected set, execution or association errors take priority and produce an execution-failure status without a detection decision. Otherwise any triggered check produces a manipulation alert; all checks untriggered produce no alert; the remaining unresolved cases produce insufficient evidence. Candidate checks and development data independently feed constrained offline rule selection. App-only and App-plus-linked-Browser are alternative configurations. A no-alert result does not establish authenticity or safety.</desc>')
add('<style>text{font-family:"Nimbus Sans","Arial",sans-serif}</style>')
add('<defs><marker id="flow" viewBox="0 0 12 10" refX="10" refY="5" markerWidth="10" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto"><path d="M1 1L11 5L1 9Z" fill="#65717B"/></marker><marker id="config" viewBox="0 0 12 10" refX="10" refY="5" markerWidth="10" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto"><path d="M1 1L11 5L1 9Z" fill="#72618D"/></marker></defs>')
rect(0, 0, 1800, 660, fill='white', stroke='none', radius=0)

# One compact mechanism example in the previously unused corner. It is an
# illustration of a valid memory relation, not an additional pipeline input.
add('<g id="illustrative-memory-check">')
text(20, 30, 'Example: memory check', 29, 700, BLUE)
text(20, 81, 'Native: 4 GiB  ·  App Web: 8 GiB', 28)
text(20, 124, 'Web upper bound from Native: 4 GiB', 27, color=MUTED)
text(20, 168, '8 > 4  →  check triggers', 28, 700, BLUE)
add('</g>')

# Offline branch. Only the resulting artifact connects to the runtime detector.
add('<g id="offline-construction">')
text(625, 30, 'Offline construction', 29, 700, PURPLE)
folded(625, 43, 200, 68, color=PURPLE, fill=PURPLE_FILL, fold=14)
text(725, 71, 'Candidate', 27, anchor='middle')
text(725, 100, 'checks', 27, anchor='middle')
folded(625, 126, 200, 68, color=PURPLE, fill=PURPLE_FILL, fold=14)
text(725, 154, 'Development', 27, anchor='middle')
text(725, 183, 'data', 27, anchor='middle')
rect(900, 91, 245, 91, stroke=PURPLE)
text(1022.5, 129, 'Select rules', 29, 700, anchor='middle')
text(1022.5, 162, 'with constraints', 26, anchor='middle')
folded(1220, 86, 270, 104, color=PURPLE, fill=PURPLE_FILL, fold=20)
text(1355, 128, 'Fixed rules', 29, 700, anchor='middle')
text(1355, 163, '+ parameters', 28, anchor='middle')
path('M825 77H858V114H900', color=PURPLE, sw=2, arrow=True)
path('M825 160H900', color=PURPLE, sw=2, arrow=True)
path('M1145 138H1220', color=PURPLE, sw=2, arrow=True)
path('M1355 190V225', color=PURPLE, sw=2, arrow=True)
add('</g>')

# Common frozen boundary makes rule selection apply to both checking and aggregation.
rect(625, 225, 865, 350, fill='#FBFCFD', stroke=FRAME, sw=1.7, radius=9, dash='8 5')
rect(644, 207, 357, 33, fill='white', stroke='none', radius=0)
text(650, 232, 'Report integrity detector', 28, 700, MUTED)

# Stage 1: the three App views are inputs, not repeated as a triangle.
add('<g id="observation-binding">')
stage(20, 264, 1, 'Link observations')
rect(20, 285, 260, 174, fill=BLUE_FILL, stroke='#91A8BC', sw=1.6, radius=5)
phone(36, 303)
text(84, 319, 'Android App', 29, 700, BLUE)
text(84, 359, 'Native APIs', 28)
text(84, 397, 'WebView Host', 28)
text(84, 435, 'App Web (JS)', 28)
rect(20, 487, 260, 84, fill=GREEN_FILL, stroke='#7BA399', sw=1.6, radius=5, dash='6 4')
browser(36, 505)
text(92, 520, 'Browser', 29, 700, GREEN)
text(92, 553, 'linked · optional', 25)

rect(350, 344, 240, 161, stroke=BLUE, sw=2, radius=3)
text(470, 382, 'Link records', 30, 700, anchor='middle')
path('M362 399H578', color='#B5C5D3', sw=1.3)
text(470, 440, 'Values + status', 27, anchor='middle')
text(470, 478, 'Sources + context', 26, anchor='middle')
path('M280 372H315V406')
path('M280 529H315V406')
add(f'<circle cx="315" cy="406" r="3.3" fill="{LINE}"/>')
path('M315 406H350', arrow=True)
path('M590 406H632')
add(f'<circle cx="632" cy="406" r="3.1" fill="{LINE}"/>')
path('M632 316V487')
path('M632 316H650', arrow=True)
path('M632 387H650', arrow=True)
path('M632 487H650', arrow=True)
add('</g>')

# Stage 2: selected checks, with optional C1 as a local extension.
add('<g id="state-aware-checks">')
stage(650, 264, 2, 'Integrity checks')
rect(650, 289, 360, 53, fill=BLUE_FILL, stroke='#8BA4BA', sw=1.7)
text(670, 328, 'Single-view checks', 29, 700)
rect(650, 347, 360, 79, fill=BLUE_FILL, stroke='#8BA4BA', sw=1.7)
text(670, 378, 'Native–Web', 29, 700)
text(670, 411, 'Memory / timezone relations', 25, color=MUTED)
rect(650, 447, 360, 80, fill=GREEN_FILL, stroke='#7BA399', sw=1.7, dash='6 4')
text(670, 479, 'App Web–Browser', 28, 700)
text(670, 513, 'Compare timezone offsets', 26, color=MUTED)
path('M1010 316H1042V487H1010')
path('M1010 387H1042')
add(f'<circle cx="1042" cy="406" r="3.3" fill="{LINE}"/>')
path('M1042 406H1190', arrow=True)
text(1115, 385, 'Check', 27, anchor='middle')
text(1115, 437, 'results', 27, color=MUTED, anchor='middle')
text(650, 557, 'Modes: App only  or  App + linked Browser', 25, color=MUTED)
add('</g>')

# Stage 3: failure precedence is applied only to selected dependencies.
add('<g id="rule-aggregation">')
stage(1186, 264, 3, 'Combine results')
text(1325, 315, 'Execution errors first', 26, color=MUTED, anchor='middle')
rect(1190, 341, 270, 130, fill='white', stroke=LINE, sw=2)
text(1325, 376, 'Any triggered', 27, 700, anchor='middle')
text(1325, 416, 'All definitely false', 26, anchor='middle')
text(1325, 456, 'Otherwise', 27, anchor='middle')
path('M1460 367H1502', arrow=True)
path('M1460 407H1502', arrow=True)
path('M1460 447H1502', arrow=True)
path('M1325 471V623H1502', arrow=True)
text(1410, 610, 'Error', 25, color=MUTED, anchor='middle')
add('</g>')

# Outputs: a compact decision, plus a distinct failure record.
add('<g id="outputs">')
text(1519, 315, 'Decision', 29, 700)
rect(1502, 341, 286, 130, stroke=FRAME, sw=1.5)
text(1518, 376, 'Manipulation alert', 27, 700, RED)
text(1518, 416, 'No alert', 27)
text(1518, 456, 'Insufficient evidence', 27)
folded(1502, 582, 286, 72, color=FRAME, fill='white', fold=14)
text(1645, 611, 'Execution failure', 27, anchor='middle')
text(1645, 641, 'No decision', 25, color=MUTED, anchor='middle')
add('</g>')
add('</svg>')

dest = OUT / 'HybridGuard_system_design_layout.svg'
dest.write_text('\n'.join(P), encoding='utf-8')
print(dest)

if not args.svg_only:
    inkscape = shutil.which('inkscape')
    if not inkscape:
        parser.error('Inkscape is required for PDF/PNG export; SVG was generated.')
    subprocess.run([inkscape, str(dest), '--export-area-page',
                    '--export-type=pdf',
                    '--export-filename=' + str(dest.with_suffix('.pdf'))], check=True)
    subprocess.run([inkscape, str(dest), '--export-area-page',
                    '--export-type=png', '--export-width=2700',
                    '--export-background=white', '--export-background-opacity=1',
                    '--export-filename=' + str(dest.with_suffix('.png'))], check=True)
    print(dest.with_suffix('.pdf'))
    print(dest.with_suffix('.png'))
