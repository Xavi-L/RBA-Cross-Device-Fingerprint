"""Check only the F05a candidate and its isolated single-column ACM specimen."""
from pathlib import Path
from collections import Counter
import csv
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pdfplumber
from pypdf import PdfReader
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
TEMPLATE=ROOT/'output/pdf/hybridguard_triangle_template_preview'
DEST=HERE/'template_preview'
PREVIEWS=HERE/'previews'
NS={'s':'http://www.w3.org/2000/svg'}


def require(condition,message):
    if not condition:
        raise ValueError(message)


def dump(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')


def caption():
    return (HERE/'CAPTIONS.md').read_text().split('## English\n\n',1)[1].split('\n\n## 中文',1)[0].strip()


def pdf_resources(reader,page_number=0):
    fonts=[]; images=[]; visited=set()
    def visit(resources):
        resources=resources.get_object()
        for _,ref in resources.get('/Font',{}).items():
            font=ref.get_object(); name=str(font.get('/BaseFont',''))
            if ('font',name) in visited: continue
            visited.add(('font',name))
            children=font.get('/DescendantFonts'); base=children[0].get_object() if children else font
            descriptor=base.get('/FontDescriptor'); descriptor=descriptor.get_object() if descriptor else {}
            fonts.append({'name':name,'embedded':any(k in descriptor for k in ['/FontFile','/FontFile2','/FontFile3']),
                          'to_unicode':'/ToUnicode' in font})
        for key,ref in resources.get('/XObject',{}).items():
            obj=ref.get_object()
            if obj.get('/Subtype')=='/Image': images.append(str(key))
            if obj.get('/Subtype')=='/Form' and '/Resources' in obj:
                identity=('form',getattr(ref,'idnum',id(obj)))
                if identity not in visited:
                    visited.add(identity); visit(obj['/Resources'])
    visit(reader.pages[page_number]['/Resources'])
    return {'fonts':fonts,'images':images}


def render_pdf(pdf,output,page=1,width=None,dpi=150):
    command=['pdftoppm','-f',str(page),'-l',str(page),'-png','-singlefile']
    command+=['-scale-to-x',str(width),'-scale-to-y','-1'] if width else ['-r',str(dpi)]
    subprocess.run(command+[str(pdf),str(output.with_suffix(''))],check=True,stdout=subprocess.DEVNULL)


def audit_readonly(baseline):
    changes=[]
    for name,stat in baseline['protected_file_stats'].items():
        p=ROOT/name
        if not p.is_file() or {'size':p.stat().st_size,'mtime_ns':str(p.stat().st_mtime_ns)}!=stat: changes.append(name)
    raw=subprocess.check_output(['git','status','--porcelain=v1','-z','--untracked-files=all'],cwd=ROOT).decode()
    prefix=str(HERE.relative_to(ROOT))+'/'
    outside=lambda s: [r for r in s.split('\0') if r and not r[3:].startswith(prefix)]
    current,before=outside(raw),outside(baseline['status_porcelain_v1_z'])
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    index=subprocess.check_output(['git','diff','--cached','--name-status'],cwd=ROOT,text=True)
    result={'protected_existing_files':len(baseline['protected_file_stats']),'changed_existing_files':changes,
            'outside_status_records':len(before),'outside_status_unchanged':current==before,
            'head':head,'head_unchanged':head==baseline['head'],'index_unchanged':index==baseline['index_status'],
            'scope':'This generation run; subsequent user-authorized Git delivery is separate.',
            'commit_or_push_performed_during_generation':False,'system_fonts_copied':False,
            'pass':not changes and current==before and head==baseline['head'] and index==baseline['index_status']}
    require(not any(p.suffix.lower() in {'.ttf','.otf','.ttc'} for p in HERE.rglob('*')),'System font copy found')
    require(result['pass'],('Read-only scope check',result))
    return result


def cleanup_template_aux():
    # Only disposable files created in this candidate's isolated template.
    for suffix in ['.aux','.blg','.fdb_latexmk','.fls','.out']:
        (DEST/('hybridguard_draft'+suffix)).unlink(missing_ok=True)


def audit_artwork(check):
    with (HERE/'data/plot_data.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    expected = {r['family']+'-'+r['method']: r for r in rows}
    svg = ET.parse(HERE/'F05a_main.svg').getroot()
    markers = svg.findall('.//*[@data-role="data-marker"]')
    labels = svg.findall('.//*[@data-role="count"]')
    require(len(markers) == len(labels) == len(expected) == 8, 'Eight separate markers and labels required')
    require([t.get('data-family') for t in svg.findall('.//*[@data-role="row-label"]')] == check['data']['families'], 'Category order')
    require([t.text for t in svg.findall('.//*[@data-role="legend"]')] == ['Full App', 'App + C1'], 'Method legend semantics')
    require(not any(svg.findall('.//s:'+name, NS) for name in ['image', 'linearGradient', 'radialGradient', 'clipPath']), 'Raster/gradient/clipping is prohibited')
    require(len(svg.findall('.//s:text', NS)) == 18, 'Editable text count')
    layout = check['layout']
    for marker in markers:
        point = marker.get('data-point'); r = expected[point]; method = r['method']
        rate = int(r['T'])/int(r['N'])*100
        x = float(marker.get('cx')) if method == 'APP_FULL' else float(marker.get('x'))+float(marker.get('width'))/2
        y = float(marker.get('cy')) if method == 'APP_FULL' else float(marker.get('y'))+float(marker.get('height'))/2
        ex = layout['x0']+(layout['x1']-layout['x0'])*rate/100
        ey = layout['row_centers'][int(r['row_order'])-1]+(-1 if method == 'APP_FULL' else 1)*layout['series_vertical_offset']
        require(abs(x-ex) < 1e-9 and abs(y-ey) < 1e-9, ('Point geometry', point))
        require(marker.get('data-count') == r['display'] and float(marker.get('data-rate')) == rate, ('Point value', point))
        if method == 'APP_FULL':
            require(marker.tag.endswith('circle') and marker.get('fill') == '#ffffff'
                    and marker.get('stroke') == layout['method_colors'][method] and float(marker.get('r')) == 8.5, 'Full App style')
        else:
            require(marker.tag.endswith('rect') and marker.get('fill') == layout['method_colors'][method]
                    and float(marker.get('width')) == float(marker.get('height')) == 16, 'App + C1 style')
    for label in labels:
        r = expected[label.get('data-point')]
        require(label.text == r['display'] and layout['x0'] < float(label.get('x')) < layout['x1'], 'Count must match and face inward')
    require([t.text for t in svg.findall('.//*[@data-role="axis-label"]')] == ['Detection rate (%)'], 'Detection axis')
    require(not any('/46' in (t.text or '') for t in svg.findall('.//s:text', NS)), 'Normal alarms must remain outside detection plot')
    with pdfplumber.open(HERE/'F05a_main.pdf') as doc:
        require(len(doc.pages) == 1, 'One standalone page required'); page = doc.pages[0]
        extracted = page.extract_text(x_tolerance=1) or ''
        require(Counter(re.findall(r'\b\d+/(?:2|5)\b', extracted)) == Counter(r['display'] for r in rows), 'PDF counts')
        require(not page.images, 'PDF raster image')
        require(all(c['x0'] >= 0 and c['top'] >= 0 and c['x1'] <= page.width and c['bottom'] <= page.height
                    for c in page.chars), 'PDF text extends outside MediaBox')
        words = page.extract_words(x_tolerance=1, y_tolerance=1); scale = 72/254
        for t in check['svg_and_browser']['texts']:
            if t['role'] != 'count': continue
            bbox = ((t['x']-2)*scale, t['y']*scale, (t['x']+t['w']+2)*scale, (t['y']+t['h'])*scale)
            located = [w for w in words if bbox[0] < (w['x0']+w['x1'])/2 < bbox[2] and bbox[1] < (w['top']+w['bottom'])/2 < bbox[3]]
            require(len(located) == 1 and located[0]['text'] == expected[t['point']]['display'], ('PDF spatial count', t['point'], located))
        result = {'page_size_mm': [page.width*25.4/72, page.height*25.4/72],
                  'font_sizes_pdf_pt': sorted({round(c['size'], 5) for c in page.chars if c['text'].strip()}),
                  'spatially_verified_counts': 8, 'extractable_text': True, 'all_text_inside_page': True,
                  'vector_curves': len(page.curves), 'vector_rectangles': len(page.rects), 'raster_images': len(page.images)}
    reader = PdfReader(HERE/'F05a_main.pdf'); resources = pdf_resources(reader)
    require(resources['fonts'] and all(f['embedded'] and f['to_unicode'] and 'TimesNewRoman' in f['name'] for f in resources['fonts']), 'PDF font embedding/fallback')
    require(not resources['images'] and not reader.named_destinations and not any(p.get('/Annots') for p in reader.pages), 'PDF resource/annotation dependency')
    with Image.open(HERE/'F05a_main.png') as im:
        require(im.size == tuple(round(mm/25.4*300) for mm in layout['size_mm']), ('PNG dimensions', im.size))
        result['png_pixels'] = list(im.size)
    require('Both methods have 0/46 normal alarms.' in caption(), 'Normal result caption missing')
    require('60 saved development positions: 14 interventions, 46 normal' in caption(), 'Caption denominators')
    result.update(resources); result['pass'] = True
    return result


def audit_data_exports():
    # Only the explicitly requested selected cohorts are checked for accidental ID export.
    source = ROOT/'deliverables/app_resource_constrained_extension_v1/results/members.jsonl'
    identifiers = [r['sample_id'] for r in (json.loads(line) for line in source.read_text().splitlines() if line.strip())
                   if r['cohort'] in {'pilot18', 'b2b42'}]
    bad_keys = {'sample_id', 'session_id', 'group_id', 'source_meta', 'receipt', 'raw_fingerprint'}
    def walk(obj):
        if isinstance(obj, dict):
            require(not (set(obj) & bad_keys), ('Unnecessary source member fields', sorted(set(obj) & bad_keys)))
            for value in obj.values(): walk(value)
        elif isinstance(obj, list):
            for value in obj: walk(value)
    paths = sorted((HERE/'data').glob('*'))
    for path in paths:
        text = path.read_text()
        require(not any(key in text for key in identifiers), ('Source-local member ID exported', path.name))
        if path.suffix == '.json': walk(json.loads(text))
        elif path.suffix == '.csv':
            with path.open(newline='') as stream:
                require(not (set(csv.DictReader(stream).fieldnames) & bad_keys), ('Unnecessary CSV fields', path.name))
    return {'pass': True, 'data_files_checked': len(paths), 'selected_source_ids_checked': len(identifiers),
            'source_local_member_identifiers_exported': False, 'locators': 'File paths, one-based lines, method/configuration IDs and counts only.'}


def build_template():
    DEST.mkdir(exist_ok=True); copied = []
    for src in sorted(TEMPLATE.rglob('*')):
        if src.is_file() and src.suffix in {'.tex', '.cls', '.bst', '.bib'}:
            rel = src.relative_to(TEMPLATE); dst = DEST/rel
            dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst); copied.append(str(rel))
    shutil.copy2(HERE/'F05a_main.pdf', DEST/'figures/F05a_main.pdf')
    text = (TEMPLATE/'figures/overview_figure.tex').read_text()
    text = text.replace('figure*', 'figure').replace('HybridGuard_overview_triangle.pdf', 'F05a_main.pdf').replace(r'width=\textwidth', r'width=\linewidth')
    cap = caption().replace('%', r'\%')
    description = ('Four intervention rows compare Full App, shown as upper hollow gray circles, with App plus the accepted '
                   'cross-endpoint timezone check C1, shown as lower filled gray-green squares. Exact T/N labels accompany '
                   'eight points on a zero-to-one-hundred-percent detection axis. Browser timezone changes gain detection '
                   'from zero of five to five of five. App timezone detection remains two of two, and both language groups '
                   'remain undetected. Normal alarms are reported separately in the caption.')
    text = re.sub(r'\\caption\{[^\n]*\}', lambda _: r'\caption{'+cap+'}', text)
    text = re.sub(r'\\Description\{[^\n]*\}', lambda _: r'\Description{'+description+'}', text)
    text = text.replace(r'\label{fig:hybridguard-overview}', r'\label{fig:paired-timezone-gain}\label{fig:hybridguard-overview}')
    include = r'\includegraphics[width=\linewidth]{figures/F05a_main.pdf}'
    require(text.count(include) == 1 and r'\begin{figure}[t]' in text and 'figure*' not in text, 'Real single-column insertion')
    measure = '\n'.join([r'\sbox{\Fivemainbox}{'+include+'}',
        r'\typeout{FIVE-COLUMNWIDTH=\the\columnwidth}', r'\typeout{FIVE-LINEWIDTH=\the\linewidth}',
        r'\typeout{FIVE-TEXTWIDTH=\the\textwidth}', r'\typeout{FIVE-TEXTHEIGHT=\the\textheight}',
        r'\typeout{FIVE-GRAPHIC-WIDTH=\the\wd\Fivemainbox}', r'\typeout{FIVE-GRAPHIC-HEIGHT=\the\ht\Fivemainbox}',
        r'\typeout{FIVE-GRAPHIC-DEPTH=\the\dp\Fivemainbox}', r'\usebox{\Fivemainbox}'])
    hooks = '\n'.join([r'\newsavebox{\Fivemainbox}', r'\begingroup', r'\makeatletter',
        r'\let\Fiveoriginalendfloatbox\@endfloatbox', r'\def\@endfloatbox{\Fiveoriginalendfloatbox',
        r'\typeout{FIVE-FLOAT-HEIGHT=\the\ht\@currbox}', r'\typeout{FIVE-FLOAT-DEPTH=\the\dp\@currbox}}', r'\makeatother', ''])
    (DEST/'figures/overview_figure.tex').write_text(hooks+text.replace(include, measure)+'\\endgroup\n')
    (HERE/'F05a_figure.tex').write_text('\n'.join([r'\begin{figure}[t]', r'  \centering',
        r'  \includegraphics[width=\linewidth]{F05a_main.pdf}', r'  \caption{'+cap+'}',
        r'  \Description{'+description+'}', r'  \label{fig:paired-timezone-gain}', r'\end{figure}', '']))
    command = ['/Library/TeX/texbin/latexmk', '-gg', '-pdf', '-bibtex', '-interaction=nonstopmode', '-halt-on-error', 'hybridguard_draft.tex']
    with (DEST/'build_console.txt').open('w') as stream:
        process = subprocess.run(command, cwd=DEST, stdout=stream, stderr=subprocess.STDOUT)
    console = DEST/'build_console.txt'
    console.write_text('\n'.join(line.rstrip() for line in console.read_text().splitlines()).rstrip()+'\n')
    require(process.returncode == 0, 'Real ACM compile failed: see template_preview/build_console.txt')
    unchanged = {rel: (TEMPLATE/rel).read_bytes() == (DEST/rel).read_bytes() for rel in copied if rel != 'figures/overview_figure.tex'}
    require(all(unchanged.values()), 'Copied manuscript/class/font/margin source changed')
    dump(DEST/'SOURCE_MANIFEST.json', {'source': str(TEMPLATE.relative_to(ROOT)), 'class_options': 'sigconf,anonymous,review',
        'copied_files': copied, 'only_changed_source': 'figures/overview_figure.tex', 'other_sources_byte_identical': unchanged,
        'single_column_figure': True, 'width_only_proportional_include': True, 'layout_specimen_only': True,
        'temporary_alias': 'fig:hybridguard-overview retained only in isolated specimen for existing prose references',
        'integration_label': 'fig:paired-timezone-gain'})
    log = (DEST/'hybridguard_draft.log').read_text(errors='replace')
    measurements = {k: float(v) for k, v in re.findall(r'FIVE-([A-Z-]+)=([0-9.]+)pt', log)}
    require(len(measurements) == 9, ('Incomplete real template measurements', measurements))
    errors = {'overfull_hboxes': re.findall(r'Overfull \\hbox[^\n]*', log), 'overfull_vboxes': re.findall(r'Overfull \\vbox[^\n]*', log),
        'font_or_character_errors': re.findall(r'(?:Missing character|LaTeX Font Warning)[^\n]*', log),
        'unresolved_references': re.findall(r'(?:LaTeX Warning:.*undefined|There were undefined references)[^\n]*', log),
        'retained_class_warnings': re.findall(r'Class acmart Warning[^\n]*', log)}
    return measurements, errors


def audit_template(m, errors):
    with pdfplumber.open(DEST/'hybridguard_draft.pdf') as doc:
        pages = [i for i, p in enumerate(doc.pages) if any('TimesNewRoman' in c['fontname'] for c in p.chars)]
        require(len(pages) == 1, ('Figure page lookup', pages)); index = pages[0]; page = doc.pages[index]
        chars = [c for c in page.chars if 'TimesNewRoman' in c['fontname'] and c['text'].strip()]
        sizes = sorted({round(c['size'], 5) for c in chars}); minimum = min(sizes)
        require(minimum >= 7.84795, 'Actual core font below project lower bound')
        column_pt = m['COLUMNWIDTH']*72/72.27
        # Left-aligned row labels begin at x=8 in the source viewBox.
        left = min(c['x0'] for c in chars)-column_pt*8/860
        column = page.crop((left-1, 0, left+column_pt+1, page.height))
        text = column.extract_text(x_tolerance=1) or ''
        normalize = lambda s: re.sub(r'[\s-]', '', s)
        require(normalize(caption()) in normalize(text), 'Formal caption not found intact in actual figure column')
        result = {'compiled_pages': len(doc.pages), 'figure_page_one_based': index+1, 'font_sizes_pdf_pt': sizes,
                  'minimum_actual_font_pdf_pt': minimum, 'caption_word_count': len(caption().split()),
                  'caption_text_verified': True, 'figure_page_raster_images': len(page.images),
                  'figure_column': 'left' if left < page.width/2 else 'right'}
    resources = pdf_resources(PdfReader(DEST/'hybridguard_draft.pdf'), index)
    require(all(f['embedded'] for f in resources['fonts']) and not resources['images'], 'Template vector/font embedding')
    require(m['GRAPHIC-WIDTH'] == m['COLUMNWIDTH'] == m['LINEWIDTH'], 'Figure must use actual column width')
    require(m['COLUMNWIDTH'] < m['TEXTWIDTH']*.51, 'Accidental two-column figure')
    clear = not any(errors[k] for k in ['overfull_hboxes', 'overfull_vboxes', 'font_or_character_errors', 'unresolved_references'])
    require(clear, ('Template diagnostics', errors))
    total = (m['FLOAT-HEIGHT']+m['FLOAT-DEPTH'])*25.4/72.27
    graphic = (m['GRAPHIC-HEIGHT']+m['GRAPHIC-DEPTH'])*25.4/72.27
    result.update({'tex_measurements_pt': m, 'columnwidth_mm': m['COLUMNWIDTH']*25.4/72.27,
        'textwidth_mm': m['TEXTWIDTH']*25.4/72.27, 'textheight_mm': m['TEXTHEIGHT']*25.4/72.27,
        'graphic_width_mm': m['GRAPHIC-WIDTH']*25.4/72.27, 'graphic_height_mm': graphic,
        'figure_caption_internal_spacing_height_mm': total, 'caption_internal_spacing_mm': total-graphic,
        'fraction_of_one_column_height': (m['FLOAT-HEIGHT']+m['FLOAT-DEPTH'])/m['TEXTHEIGHT'],
        'height_fraction_is_not_page_area_fraction': True, 'total_height_at_most_75_mm': total <= 75,
        'preferred_core_font_8_5_to_9_pt': 8.5 <= minimum <= 9,
        'preferred_caption_75_to_95_words': 75 <= len(caption().split()) <= 95,
        'single_column': True, 'width_only_proportional_include': True, 'font_margin_spacing_or_crop_hacks': False,
        'diagnostics': errors, 'fonts': resources['fonts'], 'technical_pass': clear})
    return result


def make_previews(template):
    PREVIEWS.mkdir(exist_ok=True)
    width = round(template['columnwidth_mm']/25.4*96)
    render_pdf(HERE/'F05a_main.pdf', PREVIEWS/'actual_column_width_96dpi.png', width=width)
    with Image.open(PREVIEWS/'actual_column_width_96dpi.png') as im:
        im.convert('RGB').save(PREVIEWS/'actual_column_width_96dpi.png', dpi=(96, 96))
        ImageOps.grayscale(im).save(PREVIEWS/'grayscale_column_width_96dpi.png', dpi=(96, 96))
    render_pdf(HERE/'F05a_main.pdf', PREVIEWS/'pdf_render_180dpi.png', dpi=180)
    render_pdf(DEST/'hybridguard_draft.pdf', DEST/'figure_page.png', page=template['figure_page_one_based'], dpi=150)
    wide = round(template['textwidth_mm']/25.4*96)
    refs = [('Accepted F01 rev4', 'paper/figures/f01_app_detection/style_www_v1/F01_main_rev4.pdf', 'F01_96dpi.png'),
            ('Accepted F03a/F04', 'paper/figures/f03a_f04_mechanisms/style_www_v1/F03a_F04_main.pdf', 'mechanisms_96dpi.png'),
            ('Accepted overview', 'paper/figures/overview_triangle/style_full_v1/HybridGuard_overview_candidate.pdf', 'overview_96dpi.png')]
    for _, source, out in refs: render_pdf(ROOT/source, PREVIEWS/out, width=wide)
    items = [('F05a - actual single column', 'actual_column_width_96dpi.png')]+[(name+' - actual two columns', out) for name, _, out in refs]
    images = [Image.open(PREVIEWS/name).convert('RGB') for _, name in items]
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Times New Roman.ttf', 14)
    heading, gap = 24, 18
    canvas = Image.new('RGB', (wide, sum(im.height for im in images)+len(images)*heading+(len(images)-1)*gap), 'white')
    draw = ImageDraw.Draw(canvas); y = 0
    for (label, _), im in zip(items, images):
        draw.text((4, y+3), label, font=font, fill='#343434'); canvas.paste(im, (0, y+heading)); y += heading+im.height+gap
    canvas.save(PREVIEWS/'accepted_figures_same_physical_scale_96dpi.png', dpi=(96, 96))
    return {'dpi': 96, 'candidate_width_pixels': width, 'accepted_two_column_width_pixels': wide,
            'candidate_physical_width_mm': template['columnwidth_mm'], 'accepted_physical_width_mm': template['textwidth_mm'],
            'comparison_preserves_distinct_final_widths': True, 'candidate_resized_to_match_two_column_width': False,
            'screen_physical_calibration': 'Not performed; 96 dpi rendering convention.'}


def main():
    check = json.loads((HERE/'CHECK.json').read_text())
    check['data_exports'] = audit_data_exports()
    check['pdf'] = audit_artwork(check)
    m, errors = build_template(); check['template'] = audit_template(m, errors)
    check['previews'] = make_previews(check['template'])
    cleanup_template_aux(); check['readonly'] = audit_readonly(check['generation_baseline'])
    check['automated_checks_pass'] = all([check['data']['pass'], check['data_exports']['pass'], check['svg_and_browser']['pass'], check['pdf']['pass'],
                                         check['template']['technical_pass'], check['readonly']['pass']])
    check['visual_review'] = {'status': 'PENDING', 'actually_viewed': [], 'physical_print': 'NOT_VERIFIED'}
    dump(HERE/'CHECK.json', check)
    print(json.dumps({'automated_checks_pass': check['automated_checks_pass'],
        'columnwidth_mm': check['template']['columnwidth_mm'], 'graphic_height_mm': check['template']['graphic_height_mm'],
        'minimum_actual_font_pdf_pt': check['template']['minimum_actual_font_pdf_pt'], 'caption_words': check['template']['caption_word_count'],
        'total_height_mm': check['template']['figure_caption_internal_spacing_height_mm'],
        'fraction_of_one_column_height': check['template']['fraction_of_one_column_height'],
        'height_target_75_mm_met': check['template']['total_height_at_most_75_mm'], 'visual_review': 'PENDING'}))


if __name__ == '__main__':
    main()
