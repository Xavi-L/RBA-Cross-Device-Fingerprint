"""Focused regression: actual SVG geometry, frozen copy, PDF and ACM layout.

Uses the bundled Python runtime (pdfplumber and pypdf). This is figure QA,
not a research experiment or an audit of manuscript scientific claims.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import re
import subprocess
import unicodedata
import xml.etree.ElementTree as ET
import pdfplumber
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BEFORE = HERE / 'finishing_baseline_55ca3bb'
NS = '{http://www.w3.org/2000/svg}'


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def polyline(d):
    tokens = re.findall(r'[MLHV]|-?\d+(?:\.\d+)?', d)
    points, pos, command = [], [0., 0.], None
    i = 0
    while i < len(tokens):
        if tokens[i] in 'MLHV':
            command = tokens[i]
            i += 1
        if command in ('M', 'L'):
            pos = [float(tokens[i]), float(tokens[i+1])]
            i += 2
        elif command == 'H':
            pos = [float(tokens[i]), pos[1]]
            i += 1
        elif command == 'V':
            pos = [pos[0], float(tokens[i])]
            i += 1
        else:
            raise ValueError(d)
        points.append(tuple(pos))
    return points


def segments(points):
    return list(zip(points, points[1:]))


def intersection(a, b):
    (x1,y1),(x2,y2) = a
    (x3,y3),(x4,y4) = b
    cross = lambda u,v: u[0]*v[1]-u[1]*v[0]
    r,s,q = (x2-x1,y2-y1),(x4-x3,y4-y3),(x3-x1,y3-y1)
    den = cross(r,s)
    if abs(den) < 1e-9:
        if abs(cross(q,r)) > 1e-9:
            return None
        axis = 0 if abs(r[0]) >= abs(r[1]) else 1
        lo = max(min(a[0][axis],a[1][axis]), min(b[0][axis],b[1][axis]))
        hi = min(max(a[0][axis],a[1][axis]), max(b[0][axis],b[1][axis]))
        if hi < lo:
            return None
        if hi > lo:
            return 'overlap'
        return (lo,y1) if axis == 0 else (x1,lo)
    t,u = cross(q,s)/den,cross(q,r)/den
    return (x1+t*r[0],y1+t*r[1]) if 0 <= t <= 1 and 0 <= u <= 1 else None


def font_resources(resources):
    result = []
    for _, obj in resources.get('/Font', {}).items():
        font = obj.get_object()
        desc = font.get('/DescendantFonts')
        desc = (desc[0].get_object() if desc else font).get('/FontDescriptor', {})
        desc = desc.get_object() if hasattr(desc, 'get_object') else desc
        result.append({'name': str(font.get('/BaseFont')),
                       'embedded': any(k in desc for k in ['/FontFile','/FontFile2','/FontFile3']),
                       'to_unicode': '/ToUnicode' in font})
    for _, obj in resources.get('/XObject', {}).items():
        form = obj.get_object()
        if form.get('/Subtype') == '/Form' and '/Resources' in form:
            result += font_resources(form['/Resources'])
    return result


def main():
    old = ET.parse(BEFORE / 'HybridGuard_overview_candidate.svg').getroot()
    new = ET.parse(HERE / 'HybridGuard_overview_candidate.svg').getroot()
    old_ids = {e.get('id'):e for e in old.iter() if e.get('id')}
    ids = {e.get('id'):e for e in new.iter() if e.get('id')}
    manifest = json.loads((BEFORE / 'CONTENT_MANIFEST.json').read_text())
    texts = [e for e in new.iter(NS+'text') if e.get('data-copy')]
    frozen_copy = Counter(''.join(e.itertext()) for e in texts) == Counter(manifest['candidate'])
    frozen_text_style = all({k:v for k,v in e.attrib.items() if k not in {'x','y'}} ==
                            {k:v for k,v in old_ids[e.get('id')].attrib.items() if k not in {'x','y'}}
                            and ''.join(e.itertext()) == ''.join(old_ids[e.get('id')].itertext()) for e in texts)
    frozen_objects = {n:ET.tostring(ids[n]) == ET.tostring(old_ids[n]) for n in ['native','webview-host','app-web','browser']}
    paths = {name:polyline(g.find(NS+'path').get('d')) for name,g in ids.items() if g.get('data-source')}
    old_paths = {name:polyline(g.find(NS+'path').get('d')) for name,g in old_ids.items() if g.get('data-source')}
    branch,join = (100.,963.),(965.,963.)
    unexpected = []
    flow_names = [name for name in paths if ids[name].get('data-kind') != 'relation']
    for i,a in enumerate(flow_names):
        for b in flow_names[i+1:]:
            for sa in segments(paths[a]):
                for sb in segments(paths[b]):
                    point = intersection(sa,sb)
                    if point is not None and point not in {branch,join}:
                        unexpected.append([a,b,point])
    rect = lambda name: tuple(float(ids[name].find(NS+'rect').get(k)) for k in ['x','y','width','height'])
    upper,lower,frame = rect('app-only-interface'),rect('paired-interface'),rect('current-detection')
    geometry = {
        'single_app_exit_at_actual_app_boundary': paths['current-app-exit'][0] == (100.,734.),
        'real_branch_before_browser_join': paths['current-app-exit'][-1] == paths['current-app-only'][0] == paths['current-app-for-pair'][0] == branch,
        'independent_app_only_reaches_upper_card': paths['current-app-only'][-1] == (upper[0],upper[1]+upper[3]/2),
        'browser_independent_outlet': paths['current-browser-for-pair'][0] == (965.,914.),
        'both_paired_inputs_meet_circle': paths['current-app-for-pair'][-1] == paths['current-browser-for-pair'][-1] == paths['current-linked-pair'][0] ==
                                         (float(ids['linked-pair'].get('cx')),float(ids['linked-pair'].get('cy'))) == join,
        'pair_reaches_lower_card': paths['current-linked-pair'][-1] == (lower[0]+lower[2],lower[1]+lower[3]/2),
        'model_reaches_separate_header_port': paths['load-selected-rules'][-1] == (frame[0]+frame[2],1026.) and 1026 < upper[1],
        'one_output_from_common_frame': paths['selected-mode-result'][0] == (frame[0]+frame[2],1144.),
        'no_unintended_flow_crossing_or_overlap': not unexpected,
        'no_mask_or_clip_to_hide_crossing': not any(e.tag in {NS+'mask',NS+'clipPath'} for e in new.iter()),
    }
    for name in ['native-host','native-app-web','host-app-web','app-browser']:
        a,b=ids[name].find(NS+'path'),old_ids[name].find(NS+'path')
        geometry[name+'_line_and_markers_preserved'] = all(a.get(k)==b.get(k) for k in ['stroke','stroke-width','stroke-dasharray','marker-start','marker-end'])
    length = lambda ps: sum(math.dist(a,b) for a,b in segments(ps))
    data_length = lambda tree,ps: sum(length(ps[n]) for n,g in tree.items() if g.get('data-kind') == 'current-input')
    anchor_length = lambda tree: sum(length(polyline(p.get('d'))) for e in tree.values() if e.get('data-kind')=='object-group-anchors' for p in e.findall(NS+'path'))
    snapshot=json.loads((BEFORE/'SNAPSHOT.json').read_text())
    snapshot_ok=all(hashlib.sha256((BEFORE/n).read_bytes()).hexdigest()==h for n,h in snapshot['sha256'].items())
    chrome=json.loads((HERE/'CHECK.json').read_text())
    captions=(HERE/'CAPTIONS.md').read_bytes()==(BEFORE/'CAPTIONS.md').read_bytes()
    report={'baseline':'55ca3bbadb6d4ca7aef3cb7e06b6356c86b02f52','snapshot_hashes_match':snapshot_ok,
            'body_text_count':len(texts),'copy_and_counts_preserved':frozen_copy,'text_style_preserved':frozen_text_style,
            'observation_objects_unchanged':frozen_objects,'captions_byte_preserved':captions,
            'size_mm':[180,133],'actual_geometry':geometry,'unexpected_intersections':unexpected,
            'object_anchor_total_length_before_after':[anchor_length(old_ids),anchor_length(ids)],
            'current_data_total_length_before_after':[data_length(old_ids,old_paths),data_length(ids,paths)],
            'current_data_bends_before_after':[sum(len(p)-2 for n,p in ps.items() if tree[n].get('data-kind')=='current-input') for tree,ps in [(old_ids,old_paths),(ids,paths)]],
            'actual_geometry_review_basis':'Parsed actual path coordinates and intersections, actual card rectangles, markers and join circle; also visually inspected.',
            'chrome_layout_checks_pass':chrome['automated_checks_pass']}
    report['pass']=all([snapshot_ok,frozen_copy,frozen_text_style,captions,all(frozen_objects.values()),all(geometry.values()),chrome['automated_checks_pass']])
    save('FINISHING_CHECK.json',report)

    with pdfplumber.open(HERE/'HybridGuard_overview_candidate.pdf') as pdf:
        page=pdf.pages[0]
        fonts=font_resources(PdfReader(HERE/'HybridGuard_overview_candidate.pdf').pages[0]['/Resources'])
        sizes=sorted(set(round(c['size'],5) for c in page.chars))
        pdf_report={'pages':len(pdf.pages),'actual_page_mm':[page.width*25.4/72,page.height*25.4/72],
                    'embedded_images':len(page.images),'extractable_characters':len(page.chars),
                    'vector_paths':len(page.curves)+len(page.lines)+len(page.rects),
                    'actual_fonts':fonts,'all_fonts_embedded_with_to_unicode':all(f['embedded'] and f['to_unicode'] for f in fonts),
                    'times_family_fonts_only':all('TimesNewRomanPS' in f['name'] for f in fonts),
                    'font_sizes_pdf_pt':sizes,'body_28_29_sizes_pdf_pt':[min(sizes,key=lambda x:abs(x-7.937)),min(sizes,key=lambda x:abs(x-8.2205))]}
    save('PDF_CHECK.json',pdf_report)

    template=HERE/'template_preview'
    log=(template/'hybridguard_draft.log').read_text()
    dims={k:float(v) for k,v in re.findall(r'HG-([A-Z-]+)=([\d.]+)pt',log)}
    assert dims['FLOAT-HEIGHT']>dims['GRAPHIC-HEIGHT']>0
    source_manifest=json.loads((template/'SOURCE_MANIFEST.json').read_text())
    source=ROOT/source_manifest['source']
    source_unchanged=all(hashlib.sha256((source/n).read_bytes()).hexdigest()==h for n,h in source_manifest['sha256'].items())
    copied_unchanged=all((template/n).read_bytes()==(source/n).read_bytes() for n in source_manifest['sha256'] if n!='figures/overview_figure.tex')
    with pdfplumber.open(template/'hybridguard_draft.pdf') as pdf:
        candidates=[(i,p) for i,p in enumerate(pdf.pages,1) if any('TimesNewRomanPS' in c['fontname'] for c in p.chars)]
        assert len(candidates)==1
        number,page=candidates[0]
        caption_chars=[c for c in page.chars if 'LinLibertineTB' in c['fontname'] and 450<c['top']<565]
        box=(min(c['x0'] for c in caption_chars),min(c['top'] for c in caption_chars),max(c['x1'] for c in caption_chars),max(c['bottom'] for c in caption_chars))
        caption_text=page.crop(box).extract_text(x_tolerance=1)
        normalize=lambda s: re.sub(r'\s+','',unicodedata.normalize('NFKC',s)).replace('--','–').replace("'",'’')
        expected=(HERE/'CAPTIONS.md').read_text().split('## English\n\n',1)[1].split('\n\n## 中文',1)[0].strip()
        caption_match=normalize(caption_text).removeprefix('Figure1:')==normalize(expected)
        (template/'caption_extracted.txt').write_text(caption_text+'\n')
        template_fonts=font_resources(PdfReader(template/'hybridguard_draft.pdf').pages[number-1]['/Resources'])
        tsizes=sorted(set(round(c['size'],5) for c in page.chars if 'TimesNewRomanPS' in c['fontname']))
        ratio=dims['GRAPHIC-WIDTH']/72.27*72/510
        layout={'source':source_manifest['source'],'documentclass':'acmart','class_options':'sigconf,anonymous,review',
                'compiled_pages':len(pdf.pages),'figure_page':number,'paper_page_mm':[page.width*25.4/72,page.height*25.4/72],
                'tex_measurements_pt':dims,'textwidth_mm':dims['TEXTWIDTH']*25.4/72.27,
                'graphic_height_mm':dims['GRAPHIC-HEIGHT']*25.4/72.27,
                'float_figure_caption_spacing_height_mm':dims['FLOAT-HEIGHT']*25.4/72.27,
                'caption_and_template_spacing_mm':(dims['FLOAT-HEIGHT']-dims['GRAPHIC-HEIGHT'])*25.4/72.27,
                'float_fraction_of_textheight':dims['FLOAT-HEIGHT']/dims['TEXTHEIGHT'],
                'scale_against_180mm_svg':dims['TEXTWIDTH']*25.4/72.27/180,
                'scale_against_exported_pdf_page_width':ratio,
                'body_28_29_actual_font_sizes_pdf_pt':[min(tsizes,key=lambda x:abs(x-7.85)),min(tsizes,key=lambda x:abs(x-8.13))],
                'caption_actual_font':sorted(set(c['fontname'] for c in caption_chars)),
                'caption_actual_font_sizes_pdf_pt':sorted(set(round(c['size'],5) for c in caption_chars)),
                'caption_ink_bbox_pdf_pt':box,'caption_matches_formal_text':caption_match,
                'figure_page_embedded_images':len(page.images),'figure_page_vector_paths':len(page.curves)+len(page.lines)+len(page.rects),
                'figure_page_fonts':template_fonts,'all_figure_page_fonts_embedded':all(f['embedded'] for f in template_fonts),
                'template_source_unchanged':source_unchanged,'copied_main_class_and_prose_unchanged':copied_unchanged,
                'overfull_hboxes':re.findall(r'Overfull \\hbox[^\n]*',log),'overfull_vboxes':re.findall(r'Overfull \\vbox[^\n]*',log),
                'font_or_character_errors':re.findall(r'(?:Missing character|LaTeX Font Warning|^!)[^\n]*',log,re.M),
                'unresolved_references':re.findall(r'LaTeX Warning: [^\n]*(?:undefined|Rerun)[^\n]*',log),
                'scope':'Layout check of the existing manuscript preview; historical body claims were not revised or revalidated.'}
    layout['pass']=caption_match and source_unchanged and copied_unchanged and not layout['overfull_hboxes'] and not layout['font_or_character_errors'] and not layout['unresolved_references'] and not layout['figure_page_embedded_images'] and layout['all_figure_page_fonts_embedded']
    save('TEMPLATE_CHECK.json',layout)
    status=subprocess.check_output(['git','status','--porcelain=v1','-z','--untracked-files=all'],cwd=ROOT)
    prefix=str(HERE.relative_to(ROOT)).encode()+b'/'
    outside=[r for r in status.split(b'\0') if r and not r[3:].startswith(prefix)]
    prior=Path('/tmp/hybridguard-finishing-outside-before.bin')
    workspace={'starting_head':snapshot['starting_head'],'head_unchanged':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==snapshot['starting_head'],
               'outside_candidate_status_unchanged':b'\0'.join(outside)==prior.read_bytes() if prior.exists() else None,
               'outside_status_records':len(outside),'formal_files_unchanged':chrome['formal_files_unchanged'],
               'pilot_status_unchanged':chrome['pilot_status_unchanged'],'formal_template_unchanged':source_unchanged,
               'existing_baseline_unchanged':not subprocess.check_output(['git','diff','--name-only','--',str(HERE/'baseline')],cwd=ROOT)}
    save('WORKSPACE_CHECK.json',workspace)
    print(json.dumps({'finishing_pass':report['pass'],'template_pass':layout['pass'],'paper_width_mm':layout['textwidth_mm'],
                      'figure_plus_caption_mm':layout['float_figure_caption_spacing_height_mm'],'body_font_pdf_pt':layout['body_28_29_actual_font_sizes_pdf_pt'],
                      'outside_candidate_unchanged':workspace['outside_candidate_status_unchanged']},ensure_ascii=False))
    assert report['pass'] and layout['pass'] and pdf_report['all_fonts_embedded_with_to_unicode']


if __name__ == '__main__':
    main()
