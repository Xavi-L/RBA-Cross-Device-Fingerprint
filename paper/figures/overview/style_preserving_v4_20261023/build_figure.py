#!/usr/bin/env python3
"""Restyle Figure 1 v3 without changing its text, foreground layout, or relations.

The baseline SVG is included in reference/. Python 3 and Inkscape are required.
All 65 visible text nodes retain their exact text and presentation attributes.
Run: python3 build_figure.py
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEM = 'HybridGuard_Fig1_surfaces_v4'
BASE = ROOT / 'reference/HybridGuard_Fig1_surfaces_v3.svg'
NS = 'http://www.w3.org/2000/svg'
XL = 'http://www.w3.org/1999/xlink'
INK = 'http://www.inkscape.org/namespaces/inkscape'
ET.register_namespace('', NS)
ET.register_namespace('xlink', XL)
ET.register_namespace('inkscape', INK)
C = dict(line='#718E9D', dark='#526E7F', fine='#9DB1BA', pale='#F4F7F9',
         panel='#FAFCFD', blue_fill='#EDF4F8', blue='#1976D2',
         green='#16A34A', red='#E53935', gold='#F4B52C')


def el(parent, tag, **attrs):
    n = ET.SubElement(parent, '{'+NS+'}'+tag)
    for k, v in attrs.items():
        if v is not None:
            n.set(k.replace('_', '-'), str(v))
    return n


def box(parent, x, y, w, h, fill='white', stroke=None, sw=1.6, rx=5, **attrs):
    return el(parent, 'rect', x=x, y=y, width=w, height=h, rx=rx, fill=fill,
              stroke=stroke or C['line'], stroke_width=sw, **attrs)


def glyph(parent, name, x, y, w, h=None, **attrs):
    n = el(parent, 'use', x=x, y=y, width=w, height=h or w, **attrs)
    n.set('{'+XL+'}href', '#'+name)
    return n


def find_id(svg, name):
    return next(n for n in svg.iter() if n.get('id') == name)


def foreground(group):
    return next(n for n in group if n.tag == '{'+NS+'}rect')


def under(group, node, after=None):
    group.remove(node)
    pos = list(group).index(after) + 1 if after is not None else 0
    group.insert(pos, node)
    return node


def stack(group, x, y, w, h, step=6, levels=2):
    g = el(group, 'g', id=group.get('id')+'-back-pages', data_role='decorative-page-depth')
    for depth in range(levels, 0, -1):
        box(g, x+depth*step, y-depth*step, w, h,
            fill=C['pale'], stroke=C['line'], sw=1.55, rx=5)
    under(group, g)


def symbol(defs, name, body, viewbox='0 0 32 32'):
    node = ET.fromstring(f'<symbol xmlns="{NS}" id="{name}" viewBox="{viewbox}">{body}</symbol>')
    defs.append(node)
    return node


def brand(defs, filename, name):
    src = ET.parse(ROOT / 'assets/brands' / filename).getroot()
    node = el(defs, 'symbol', id=name, viewBox=src.get('viewBox', '0 0 512 512'))
    for k, value in src.attrib.items():
        if k not in ['id', 'viewBox', 'width', 'height', 'x', 'y', 'version']:
            node.set(k, value)
    for child in src:
        node.append(copy.deepcopy(child))
    ids = {n.get('id'): name+'-'+n.get('id') for n in node.iter() if n is not node and n.get('id')}
    for n in node.iter():
        for k, value in list(n.attrib.items()):
            for old, new in ids.items():
                value = value.replace('url(#'+old+')', 'url(#'+new+')')
                if k.endswith('href') and value == '#'+old:
                    value = '#'+new
            n.set(k, ids.get(value, value) if k == 'id' else value)
        if n.get('href', '').startswith('#'):
            n.set('{'+XL+'}href', n.get('href'))


def original_text_snapshot(svg):
    return [(dict(n.attrib), n.text, [(dict(c.attrib), c.text) for c in n])
            for n in svg.iter('{'+NS+'}text')]


def relation_snapshot(svg):
    ids = ['integrated-native-web', 'standalone-host-web-geometry',
           'native-host-context', 'record-excerpt-leaders', 'optional-c1']
    keys = ['d', 'points', 'x1', 'x2', 'y1', 'y2', 'cx', 'cy', 'r',
            'marker-start', 'marker-end', 'stroke-dasharray', 'stroke-width']
    return {id_: [(n.tag.rsplit('}', 1)[-1], {k:n.get(k) for k in keys if n.get(k) is not None})
                   for n in find_id(svg, id_) if n.tag.rsplit('}', 1)[-1] in ['path', 'polygon', 'circle', 'line']]
            for id_ in ids}


def primary_boxes(svg):
    ids = ['same-app-execution', 'native-observation', 'webview-host',
           'app-web-observation', 'record-context', 'external-browser',
           'optional-c1', 'c1-app-excerpt', 'c1-browser-excerpt']
    return {id_: {k:foreground(find_id(svg, id_)).get(k) for k in ['x','y','width','height','rx']}
            for id_ in ids}


def build(export=True):
    baseline = ET.parse(BASE).getroot()
    svg = copy.deepcopy(baseline)
    original_text = original_text_snapshot(baseline)
    original_relations = relation_snapshot(baseline)
    original_boxes = primary_boxes(baseline)
    defs = next(n for n in svg if n.tag == '{'+NS+'}defs')

    # Change only presentation colors of the existing frame geometry. Text is untouched.
    frame_colors = {'#565b60': C['dark'], '#a6acb1': C['fine'], '#a7b7b3': C['fine'],
                    '#d7dde1': '#D6E1E7', '#999fa4': C['line'], '#9fa7ad': C['line']}
    for n in svg.iter():
        if n.tag == '{'+NS+'}text':
            continue
        if n.get('stroke') in frame_colors:
            n.set('stroke', frame_colors[n.get('stroke')])
        if n.get('fill') in ['#f3f6f7', '#f1f6f4']:
            n.set('fill', C['blue_fill'])
        if n.get('fill') == '#f5f6f7':
            n.set('fill', C['pale'])

    # Original geometry is retained; these new symbols replace monochrome technical glyphs.
    symbol(defs, 'color-memory', '''
      <path d="M5 24v4m5-4v4m5-4v4m5-4v4m5-4v4" stroke="#D99000" stroke-width="3"/>
      <rect x="2" y="7" width="28" height="18" rx="2.5" fill="#1976D2"/>
      <rect x="5" y="11" width="5" height="9" rx="1" fill="#EAF4FF"/>
      <rect x="13" y="11" width="5" height="9" rx="1" fill="#EAF4FF"/>
      <rect x="21" y="11" width="5" height="9" rx="1" fill="#EAF4FF"/>
      <path d="M3 22H29" stroke="#0A58A3" stroke-width="1.5"/>
    ''')
    symbol(defs, 'color-clock', '''
      <circle cx="16" cy="16" r="13" fill="#E8F3FF" stroke="#1976D2" stroke-width="2.7"/>
      <path d="M16 7V16L23 20" fill="none" stroke="#1976D2" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="16" cy="16" r="1.8" fill="#1976D2"/>
    ''')
    symbol(defs, 'color-dimensions', '''
      <rect x="3" y="12" width="17" height="17" rx="2" fill="#D9ECFF" stroke="#1976D2" stroke-width="1.8"/>
      <path d="M4 6H19M4 6L7 3M4 6L7 9M19 6L16 3M19 6L16 9M26 13V28M26 13L23 16M26 13L29 16M26 28L23 25M26 28L29 25"
            fill="none" stroke="#1976D2" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
      <rect x="6" y="15" width="11" height="4" rx="1" fill="#93C5FD"/>
    ''')
    symbol(defs, 'color-files', '''
      <path d="M5 2H18L23 7V24H5Z" fill="#D6EAFE" stroke="#1976D2" stroke-width="1.6"/>
      <path d="M11 8H23L28 13V30H11Z" fill="#FFFFFF" stroke="#1976D2" stroke-width="1.7"/>
      <path d="M23 8V13H28" fill="#93C5FD" stroke="#1976D2" stroke-width="1.3"/>
      <path d="M15 18H24M15 22H24M15 26H21" stroke="#1976D2" stroke-width="1.7" stroke-linecap="round"/>
    ''')
    symbol(defs, 'color-link', '''
      <g fill="none" stroke-width="3.6" stroke-linecap="round">
        <path d="M18 11L21 8A6 6 0 0 1 29 16L23 22A6 6 0 0 1 15 22" stroke="#16A34A"/>
        <path d="M14 21L11 24A6 6 0 0 1 3 16L9 10A6 6 0 0 1 17 10" stroke="#1976D2"/>
        <path d="M11 20L21 12" stroke="#1976D2"/>
      </g>
    ''')
    symbol(defs, 'color-browser', '''
      <rect x="5" y="2" width="26" height="24" rx="2" fill="#EDF4F8" stroke="#718E9D" stroke-width="1.3"/>
      <rect x="1" y="6" width="27" height="24" rx="2.5" fill="#FFFFFF" stroke="#1976D2" stroke-width="1.7"/>
      <path d="M2 9Q2 7 4 7H25Q27 7 27 9V13H2Z" fill="#1976D2"/>
      <circle cx="5" cy="10" r="1" fill="#FFFFFF"/><circle cx="8" cy="10" r="1" fill="#93C5FD"/>
      <rect x="5" y="17" width="8" height="8" rx="1" fill="#93C5FD"/>
      <path d="M17 18H23M17 22H23M17 26H21" stroke="#9DB1BA" stroke-width="1.7" stroke-linecap="round"/>
    ''')
    symbol(defs, 'color-host', '''
      <path d="M12 1H20L21 5L25 7L29 6L32 13L28 16L29 21L26 27L21 26L18 31L11 30L10 26L5 24L1 25L0 17L4 14L3 9L7 4L11 5Z" fill="#1976D2"/>
      <circle cx="16" cy="16" r="10" fill="#EAF4FF"/>
      <rect x="9" y="10" width="14" height="12" rx="1.5" fill="#FFFFFF" stroke="#1976D2" stroke-width="1.2"/>
      <path d="M9 13H23" stroke="#1976D2" stroke-width="1.2"/>
      <path d="M13 16L11 18L13 20M19 16L21 18L19 20" fill="none" stroke="#16A34A" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    ''')
    symbol(defs, 'color-interval', '''
      <rect x="3" y="5" width="26" height="24" rx="3" fill="#FFF7DF" stroke="#D99000" stroke-width="1.6"/>
      <path d="M4 8Q4 6 6 6H26Q28 6 28 8V12H4Z" fill="#F4B52C"/>
      <path d="M10 3V8M22 3V8" stroke="#D99000" stroke-width="2.6" stroke-linecap="round"/>
      <path d="M8 21H24M8 17V25M24 17V25" stroke="#1976D2" stroke-width="2" stroke-linecap="round"/>
      <circle cx="16" cy="21" r="2.3" fill="#1976D2"/>
    ''')
    symbol(defs, 'color-phone', '''
      <rect x="8" y="1" width="17" height="30" rx="3" fill="#526E7F"/>
      <rect x="10" y="5" width="13" height="21" rx="1" fill="#93C5FD"/>
      <path d="M14 3H19M15 28H18" stroke="#FFFFFF" stroke-width="1.2" stroke-linecap="round"/>
      <rect x="12" y="8" width="9" height="4" rx="1" fill="#FFFFFF"/>
      <circle cx="16.5" cy="19" r="4" fill="#16A34A"/>
      <rect x="14" y="17" width="5" height="4" rx="0.6" fill="none" stroke="#FFFFFF" stroke-width="0.9"/>
    ''')
    symbol(defs, 'mismatch-symbol', '''
      <circle cx="16" cy="16" r="14" fill="#E53935"/>
      <path d="M11 11L21 21M21 11L11 21" stroke="#FFFFFF" stroke-width="3.3" stroke-linecap="round"/>
    ''')
    for name, hx, hy, color in [('c1-clock-app', 8, 22, C['blue']), ('c1-clock-browser', 6, 16, C['blue'])]:
        symbol(defs, name, f'''
          <circle cx="16" cy="16" r="13" fill="white" stroke="{color}" stroke-width="2.4"/>
          <path d="M16 6V16L{hx} {hy}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="16" cy="16" r="1.6" fill="{color}"/>
        ''')

    for n in svg.iter('{'+NS+'}use'):
        href = n.get('{'+XL+'}href', '')
        if href.startswith('#icon-'):
            n.set('{'+XL+'}href', '#color-'+href.removeprefix('#icon-'))

    app = find_id(svg, 'same-app-execution')
    native = find_id(svg, 'native-observation')
    host = find_id(svg, 'webview-host')
    web = find_id(svg, 'app-web-observation')
    browser = find_id(svg, 'external-browser')
    c1 = find_id(svg, 'optional-c1')
    record = find_id(svg, 'record-context')

    # The existing card fronts and group nesting remain exactly where they were.
    foreground(app).set('fill', C['panel'])
    foreground(host).set('fill', '#F5F9FC')
    foreground(c1).set('fill', C['panel'])
    foreground(find_id(svg, 'native-host-context')).set('fill', C['panel'])
    for g in [native, web, browser, find_id(svg,'c1-app-excerpt'), find_id(svg,'c1-browser-excerpt')]:
        f = foreground(g)
        stack(g, *[float(f.get(k)) for k in ['x','y','width','height']],
              step=4 if g is native else 5, levels=2)

    # Header fills sit under all original glyphs, without changing their text boxes.
    b = box(native, 49, 212, 338, 102, fill=C['blue_fill'], stroke='none', sw=0, rx=2)
    under(native, b, foreground(native))
    b = box(browser, 1108, 43, 672, 66, fill=C['blue_fill'], stroke='none', sw=0, rx=4)
    under(browser, b, foreground(browser))
    for n in web:
        if n.tag == '{'+NS+'}rect' and n.get('x') == '645' and n.get('y') == '192':
            n.set('fill', '#F7DF1E')
            n.set('stroke', '#C5A91A')
    for n in host:
        if n.tag == '{'+NS+'}rect' and n.get('x') == '623' and n.get('y') == '506':
            n.set('fill', '#FFFBF2')

    # Replace the single embedded raster by an original, editable WebView pictogram.
    for parent in svg.iter():
        for child in list(parent):
            if child.tag == '{'+NS+'}image':
                at = list(parent).index(child)
                n = glyph(parent, 'color-host', child.get('x'), child.get('y'), child.get('width'), child.get('height'),
                          id='vector-webview-pictogram')
                parent.remove(n)
                parent.remove(child)
                parent.insert(at, n)

    # Six original Figure 2 brand assets share a single small tray in existing blank space.
    tray = el(app, 'g', id='app-brand-tray', data_role='illustrative-app-identities')
    box(tray, 58, 116, 331, 66, fill=C['pale'], stroke=C['fine'], sw=1.5, rx=7)
    box(tray, 53, 121, 331, 66, fill=C['blue_fill'], stroke=C['fine'], sw=1.5, rx=7)
    box(tray, 48, 126, 331, 66, fill='white', stroke=C['line'], sw=1.8, rx=7)
    for i, name in enumerate(['wechat','whatsapp','instagram','tiktok','youtube','alipay']):
        brand(defs, name+'.svg', 'app-logo-'+name)
        glyph(tray, 'app-logo-'+name, 62+i*52, 140, 38, id='app-logo-instance-'+name)

    # Small, meaningful symbols occupy existing icon gutters / record whitespace.
    glyph(native, 'color-interval', 73, 427, 29, id='collection-interval-icon')
    glyph(native, 'color-phone', 326, 271, 31, 35, id='device-os-icon')
    for g, name, x in [(find_id(svg,'c1-app-excerpt'),'c1-clock-app',1378),
                       (find_id(svg,'c1-browser-excerpt'),'c1-clock-browser',1704)]:
        glyph(g, name, x, 459, 36, id=name+'-instance')
    glyph(c1, 'mismatch-symbol', 1712, 660, 34, id='c1-condition-mismatch-icon')

    # Color the existing applicability box and add a chain pictogram, not a detector verdict.
    for n in c1:
        if n.tag == '{'+NS+'}rect' and n.get('x') == '1127' and n.get('y') == '601':
            n.set('fill', '#EFF6F0')
            n.set('stroke', C['green'])
    glyph(c1, 'color-link', 1136, 608, 25, id='valid-association-link-icon')

    labels = {
        'same-app-execution':'App execution — original geometry',
        'external-browser':'External Browser — original geometry',
        'optional-c1':'C1 comparison — original geometry',
    }
    for id_, label in labels.items():
        g = find_id(svg, id_)
        g.set('{'+INK+'}groupmode', 'layer')
        g.set('{'+INK+'}label', label)

    desc = find_id(svg, 'description')
    desc.text = (desc.text or '').replace(
        'Android, Chrome and WebView icons are official identity assets; technical symbols use Tabler Icons.',
        'Android and Chrome retain their source identity assets. Six app marks are illustrative identities reused from Figure 2; they do not expand the evaluated app list. The WebView and technical pictograms are original editable vector drawings. The page offsets decorate record cards and do not add executions. Clock hands schematically indicate different effective offsets, not collection times. The red mismatch icon denotes the illustrated C1 condition outcome, not a detector-wide alert.')

    # Hard checks target the user's actual constraints, not visual implementation details.
    assert original_text_snapshot(svg) == original_text, 'Visible text or text layout changed'
    assert primary_boxes(svg) == original_boxes, 'Primary card geometry changed'
    assert relation_snapshot(svg) == original_relations, 'Relation path geometry changed'
    assert not list(svg.iter('{'+NS+'}image')), 'Main SVG still has raster artwork'
    for n in svg.iter():
        for k,v in n.attrib.items():
            if k.endswith('href'):
                assert v.startswith('#'), 'External resource reference in main SVG'
    assert svg.get('viewBox') == baseline.get('viewBox')
    assert svg.get('width') == baseline.get('width') and svg.get('height') == baseline.get('height')

    output = ROOT / (STEM+'.svg')
    ET.ElementTree(svg).write(output, encoding='utf-8', xml_declaration=True)
    quality = {
        'base_commit':'9ac8037a953280689062f906f5762536c40e1851',
        'base_path':'paper/figures/overview/revision_v3_20261022/HybridGuard_Fig1_source_v3.zip',
        'style_reference':'paper/figures/system_design/semantic_vector_v1_20261023/HybridGuard_Fig2_semantic_v1.svg',
        'visible_text_nodes':len(original_text),
        'all_text_strings_and_attributes_unchanged':True,
        'all_primary_foreground_boxes_unchanged':True,
        'all_relation_paths_and_dash_patterns_unchanged':True,
        'original_canvas_and_physical_size_unchanged':True,
        'embedded_raster_images':0,
        'external_resource_references':0,
        'new_app_brand_assets':6,
        'primary_foreground_boxes':original_boxes,
        'relations':original_relations,
        'baseline_svg_sha256':hashlib.sha256(BASE.read_bytes()).hexdigest(),
        'output_svg_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'review_status':'Structurally checked; visual review is documented separately.',
    }
    if export:
        for width, name in [(3200, STEM+'.png'), (1500, 'Fig1_review_1500px.png')]:
            subprocess.run(['inkscape', str(output), '--export-area-page', '--export-type=png',
                            '--export-width='+str(width), '--export-filename='+str(ROOT/name)],
                           check=True, capture_output=True)
        quality['preview_width_px'] = 3200
    (ROOT/'QUALITY_CHECK.json').write_text(json.dumps(quality, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in quality.items() if k not in ['primary_foreground_boxes','relations']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--svg-only', action='store_true')
    args = parser.parse_args()
    build(export=not args.svg_only)
