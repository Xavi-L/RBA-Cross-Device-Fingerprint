#!/usr/bin/env python3
"""Build HybridGuard's icon-led observation triangle."""
from pathlib import Path
import argparse
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
SOURCE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="86mm" height="50mm" viewBox="0 0 860 500" role="img" aria-labelledby="title desc">\n<title id="title">HybridGuard overview: cross-layer relations within the app</title>\n<desc id="desc">Layout proposal for splitting the existing overview. Native observations appear at left, App Web at upper right, and WebView Host at lower right within one app-execution scope. The selected Native–App Web memory and timezone comparison is a solid blue double-ended line. The separately studied Host–App Web geometry relation is a dashed ochre double-ended line and is not in the current detector. The dotted gray Native–Host link denotes shared context only and has no detection rule. The scope label means provenance-bound collection, not atomic synchronization. No observation point is designated trusted ground truth.</desc>\n<style>text {font-family:\'Times New Roman\',Times,serif} .body{font-size:28px;fill:#343434} .node-title{font-size:31px;font-weight:bold;fill:#343434}</style>\n<!-- Icons preserved from source overview: inherited pilot icons and adapted Tabler Icons v3.34.1; MIT notice in source repo assets/tabler/LICENSE. -->\n<defs>\n<marker id="compare-selected" markerWidth="13" markerHeight="13" refX="10" refY="6.5" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M2 2L10 6.5L2 11" stroke="#507cc4" stroke-width="2.3" fill="none" stroke-linecap="round" stroke-linejoin="round"/></marker>\n<marker id="compare-studied" markerWidth="13" markerHeight="13" refX="10" refY="6.5" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M2 2L10 6.5L2 11" stroke="#bd8b47" stroke-width="2.3" fill="none" stroke-linecap="round" stroke-linejoin="round"/></marker>\n</defs>\n<rect width="860" height="500" fill="white"/>\n<g id="app-observations" data-kind="inside-app-scope">\n<path d="M303 25H828Q841 25 841 38V472Q841 485 828 485H32Q19 485 19 472V38Q19 25 32 25H36" fill="none" stroke="#93938e" stroke-width="1.5" stroke-dasharray="6 6" stroke-linecap="round" stroke-linejoin="round"/>\n<text x="36" y="38" font-size="31" font-weight="bold" fill="#343434">Same app execution</text>\n<g id="core-action">\n<text x="36" y="88" font-size="32" font-weight="bold" fill="#D62828">Cross-check</text>\n<text x="36" y="122" class="body">reported properties</text>\n</g>\n<g id="native-app-web" data-kind="relation" data-source="native" data-target="app-web" data-status="selected">\n<path d="M290 241L472 117" stroke="#507cc4" stroke-width="3.2" fill="none" stroke-linecap="round" stroke-linejoin="round" marker-start="url(#compare-selected)" marker-end="url(#compare-selected)"/>\n</g>\n<g id="host-app-web" data-kind="relation" data-source="webview-host" data-target="app-web" data-status="studied">\n<path d="M510 376V168" stroke="#bd8b47" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="10 7" marker-start="url(#compare-studied)" marker-end="url(#compare-studied)"/>\n</g>\n<g id="native-host" data-kind="relation" data-source="native" data-target="webview-host" data-status="context">\n<path d="M270 364L472 410" stroke="#9a9a95" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1 7"/>\n</g>\n<g id="consistency-label" data-relation="native-app-web">\n<text x="36" y="166" font-size="30" font-weight="bold" fill="#507cc4">System–web consistency</text>\n<text x="36" y="200" font-size="28" fill="#507cc4">Memory and timezone</text>\n</g>\n<g id="geometry-label" data-relation="host-app-web">\n<text x="540" y="224" font-size="29" font-weight="bold" fill="#bd8b47">Container–web</text>\n<text x="540" y="257" font-size="29" font-weight="bold" fill="#bd8b47">geometry</text>\n<text x="540" y="292" font-size="28" fill="#bd8b47">Not in current detector</text>\n<path d="M510 250H529" stroke="#bd8b47" stroke-width="1.5" fill="none" stroke-linecap="round"/>\n</g>\n<g id="context-label" data-relation="native-host">\n<text x="36" y="414" font-size="30" font-weight="bold" fill="#666666">Shared context</text>\n<text x="36" y="448" font-size="28" fill="#666666">No detection rule</text>\n<path d="M242 401L323 376" stroke="#9a9a95" stroke-width="1.5" fill="none" stroke-linecap="round"/>\n</g>\n<g id="native" data-kind="observation">\n<g transform="translate(0 -119)"><rect xmlns="http://www.w3.org/2000/svg" x="46" y="374" width="78" height="94" fill="#faf0e2" rx="17" stroke="none" stroke-width="0" />\n<g xmlns="http://www.w3.org/2000/svg" transform="translate(36 370) scale(4.2)" data-icon="native">\n<path d="M6 5a2 2 0 0 1 2 -2h8a2 2 0 0 1 2 2v14a2 2 0 0 1 -2 2h-8a2 2 0 0 1 -2 -2v-14z" stroke="#806442" stroke-width="0.6" fill="#ecd8b9" stroke-linecap="round" stroke-linejoin="round" /><rect x="7.35" y="5.65" width="9.3" height="11.5" rx="0.7" fill="white" stroke="#806442" stroke-width="0.28" /><path d="M11 4h2" stroke="#806442" stroke-width="0.52" fill="none" stroke-linecap="round" stroke-linejoin="round" /><path d="M11.1 19h1.8" stroke="#806442" stroke-width="0.52" fill="none" stroke-linecap="round" stroke-linejoin="round" /><g transform="translate(7.65 7.2) scale(.36)"><path d="M14 6m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0" stroke="#806442" stroke-width="1.35" fill="none" stroke-linecap="round" stroke-linejoin="round" /><path d="M4 6l8 0" stroke="#806442" stroke-width="1.35" fill="none" stroke-linecap="round" stroke-linejoin="round" /><path d="M16 6l4 0" stroke="#806442" stroke-width="1.35" fill="none" stroke-linecap="round" stroke-linejoin="round" /><path d="M8 12m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0" stroke="#806442" stroke-width="1.35" fill="none" stroke-linecap="round" stroke-linejoin="round" /><path d="M4 12l2 0" stroke="#806442" stroke-width="1.35" fill="none" stroke-linecap="round" stroke-linejoin="round" /><path d="M10 12l10 0" stroke="#806442" stroke-width="1.35" fill="none" stroke-linecap="round" stroke-linejoin="round" /><path d="M17 18m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0" stroke="#806442" stroke-width="1.35" fill="none" stroke-linecap="round" stroke-linejoin="round" /><path d="M4 18l11 0" stroke="#806442" stroke-width="1.35" fill="none" stroke-linecap="round" stroke-linejoin="round" /><path d="M19 18l1 0" stroke="#806442" stroke-width="1.35" fill="none" stroke-linecap="round" stroke-linejoin="round" /></g>\n</g>\n</g>\n<text x="140" y="274" class="node-title">Device &amp; OS</text>\n<text x="140" y="307" class="body">(Native)</text>\n<text x="140" y="340" class="body">Memory and timezone</text>\n</g>\n<g id="app-web" data-kind="observation">\n<g transform="translate(32 -138)"><rect xmlns="http://www.w3.org/2000/svg" x="440" y="204" width="74" height="102" fill="#edf3e9" rx="17" stroke="none" stroke-width="0" />\n<g xmlns="http://www.w3.org/2000/svg" transform="translate(430 206) scale(4)" data-icon="app-web">\n<path d="M5 5a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2H7a2 2 0 0 1 -2 -2Z" stroke="#58734f" stroke-width="0.6" fill="white" stroke-linecap="round" stroke-linejoin="round" /><path d="M14 3v4a1 1 0 0 0 1 1h4Z" stroke="none" stroke-width="0" fill="#cfddc6" stroke-linecap="round" stroke-linejoin="round" /><path d="M14 3v4a1 1 0 0 0 1 1h4" stroke="#58734f" stroke-width="0.6" fill="none" stroke-linecap="round" stroke-linejoin="round" /><path d="M8 11h8M8 13.5h5.5" stroke="#58734f" stroke-width="0.36" fill="none" stroke-linecap="round" stroke-linejoin="round" /><text x="12" y="19.2" font-size="6.4" fill="#58734f" font-weight="bold" text-anchor="middle" data-icon-mark="JS">JS</text>\n</g>\n</g>\n<text x="563" y="94" class="node-title">Embedded webpage</text>\n<text x="563" y="127" class="body">(App Web)</text>\n<text x="563" y="160" class="body">Reported properties</text>\n</g>\n<g id="webview-host" data-kind="observation">\n<g transform="translate(42 -87)"><rect xmlns="http://www.w3.org/2000/svg" x="430" y="463" width="91" height="96" fill="#e9f0f9" rx="17" stroke="none" stroke-width="0" />\n<g xmlns="http://www.w3.org/2000/svg" transform="translate(426 465) scale(4.2)" data-icon="host">\n<path d="M3 5m0 2a2 2 0 0 1 2 -2h14a2 2 0 0 1 2 2v10a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2z" stroke="#43668e" stroke-width="0.64" fill="#c7d7e9" stroke-linecap="round" stroke-linejoin="round" /><rect x="4.1" y="8.65" width="15.8" height="9.2" rx="0.6" fill="white" stroke="none" stroke-width="0" /><path d="M5.5 6.85h2.3" stroke="#43668e" stroke-width="0.5" fill="none" stroke-linecap="round" stroke-linejoin="round" /><path d="M11 6.85h7.3" stroke="#43668e" stroke-width="0.32" fill="none" stroke-linecap="round" stroke-linejoin="round" /><g transform="translate(6.72 8.15) scale(.44)"><path d="M5 5a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2H7a2 2 0 0 1 -2 -2Z" stroke="#43668e" stroke-width="0.72" fill="white" stroke-linecap="round" stroke-linejoin="round" /><path d="M14 3v4a1 1 0 0 0 1 1h4Z" stroke="none" stroke-width="0" fill="#c7d7e9" stroke-linecap="round" stroke-linejoin="round" /><path d="M14 3v4a1 1 0 0 0 1 1h4" stroke="#43668e" stroke-width="0.72" fill="none" stroke-linecap="round" stroke-linejoin="round" /><path d="M8 11h8M8 13.5h5.5" stroke="#43668e" stroke-width="0.36" fill="none" stroke-linecap="round" stroke-linejoin="round" /><text x="12" y="19.2" font-size="6.4" fill="#43668e" font-weight="bold" text-anchor="middle" data-icon-mark="JS">JS</text></g>\n</g>\n</g>\n<text x="575" y="401" class="node-title">App container</text>\n<text x="575" y="434" class="body">(WebView Host)</text>\n<text x="575" y="467" class="body">Container settings</text>\n</g>\n</g>\n</svg>\n'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', type=Path, default=ROOT / 'build')
parser.add_argument('--svg-only', action='store_true')
args = parser.parse_args()
OUT = args.output_dir.resolve()
if OUT == ROOT:
    parser.error('Use a separate output directory to preserve the delivered originals.')
OUT.mkdir(parents=True, exist_ok=True)

NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
root = ET.fromstring(SOURCE_SVG)
def get(ident):
    return next(el for el in root.iter() if el.get('id') == ident)
def is_text(el):
    return el.tag == '{'+NS+'}text'
def clear_texts(group):
    for el in list(group):
        if is_text(el):
            group.remove(el)
def text(group, x, y, value, size=28, color='#343434', weight=None, klass=None, ident=None):
    attrs={'x':str(x),'y':str(y),'font-size':str(size),'fill':color}
    if weight:
        attrs['font-weight']=str(weight)
    if klass:
        attrs['class']=klass
    if ident:
        attrs['id']=ident
    el=ET.SubElement(group, '{'+NS+'}text', attrs)
    el.text=value
    return el

get('title').text='HybridGuard overview: complementary observations and cross-view consistency'
get('desc').text=('Three observation surfaces associated with one App execution form a triangle. '
    'Native APIs at left expose device and OS observations; App Web JavaScript at upper right '
    'reports webpage-visible properties; the WebView Host at lower right provides container '
    'context. The solid blue Native-App Web edge denotes memory and timezone consistency '
    'relations used by the current detector. The dashed Host-App Web geometry relation is '
    'implemented and evaluated as a separate study, outside the current Full App detector '
    'and its candidate pool. The dotted Native-Host edge denotes shared context only, not '
    'an independent detection rule. Open arrowheads indicate comparison, not communication '
    'or mutual authentication. The App-execution scope does not assert atomic sampling, '
    'and no surface is trusted ground truth. Single-view checks, the optional linked Browser, '
    'and the complete decision flow are described in the separate system-design figure.')
style=next(el for el in root if el.tag=='{'+NS+'}style')
style.text='text {font-family:"Nimbus Roman","Times New Roman",Times,serif} .body{font-size:28px;fill:#343434} .node-title{font-size:31px;font-weight:bold;fill:#343434}'

# Retain the original unboxed icons, colored icon backgrounds, edge geometry,
# open comparison arrowheads, and restrained dashed execution boundary.
# Node roles are now two compact lines, not card-shaped containers.
for ident,x,y,name,role in [
    ('native',140,288,'Native APIs','Device & OS'),
    ('app-web',563,107,'App Web (JS)','Embedded webpage'),
    ('webview-host',575,411,'WebView Host','App container'),
]:
    group=get(ident)
    clear_texts(group)
    text(group,x,y,name,31,weight='bold',ident=ident+'-title')
    text(group,x,y+36,role,28,ident=ident+'-role')

group=get('consistency-label')
ts=[el for el in group if is_text(el)]
ts[0].text='Native–web consistency'
ts[1].text='Memory and timezone'
ts[0].set('id','selected-relation-title')
ts[1].set('id','selected-relation-detail')

group=get('geometry-label')
clear_texts(group)
text(group,540,228,'Host–web geometry',29,'#bd8b47','bold',ident='study-relation-title')
text(group,540,264,'Separate study',28,'#bd8b47',ident='study-relation-status')

group=get('context-label')
clear_texts(group)
text(group,36,428,'Shared context only',28,'#757570',ident='context-relation-label')
leader=next(el for el in group if el.tag=='{'+NS+'}path')
leader.set('d','M277 412L323 353.941')

# Author-approved final adjustment: raise the gray edge's left endpoint by 3 mm.
context_edge = next(el for el in root.iter() if el.get('d') == 'M270 364L472 410')
context_edge.set('d', 'M270 334L472 410')

license_text='''MIT License
Copyright (c) 2020-2024 Paweł Kuna
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.'''
root.append(ET.Comment(' Icons inherited from the original overview and adapted Tabler Icons v3.34.1.\n'+license_text+' '))
svg=OUT/'HybridGuard_overview_layout.svg'
svg.write_text(ET.tostring(root,encoding='unicode')+'\n',encoding='utf-8')
print(svg)
if not args.svg_only:
    for suffix,export_args in [('pdf',[]),('png',['--export-width=2064','--export-background=white','--export-background-opacity=1'])]:
        dest=svg.with_suffix('.'+suffix)
        subprocess.run(['inkscape',str(svg),'--export-area-page','--export-type='+suffix,'--export-filename='+str(dest),*export_args],check=True)
        print(dest)
