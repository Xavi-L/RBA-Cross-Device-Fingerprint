"""Check the horizontal candidate, its frozen content and real ACM float height.

Run after build_candidate, Chrome rendering and build_template_preview.
Geometry and PDF inspection only; no research code/data are imported or run.
"""
from collections import Counter
from pathlib import Path
import json
import math
import re
import subprocess
import unicodedata
import xml.etree.ElementTree as ET
import pdfplumber
from pypdf import PdfReader
from check_finishing import polyline, segments, intersection, font_resources

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BEFORE = HERE / 'compression_baseline_86aa74c'
NS = '{http://www.w3.org/2000/svg}'


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def normalize(s):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', s)).replace('--', '–').replace("'", '’')


def styles(root):
    return Counter(( ''.join(e.itertext()),
        # Text alignment, wrapping and coordinates are layout; type and color are frozen.
        tuple(sorted((k,v) for k,v in e.attrib.items() if k not in {'id','x','y','text-anchor'})),
        tuple((''.join(t.itertext()),t.get('fill')) for t in e if t.get('fill')))
        for e in root.iter(NS+'text') if e.get('data-copy'))


def shape(e):
    return (e.tag, tuple(sorted(e.attrib.items())), (e.text or '').strip(), tuple(shape(c) for c in e))


def main(*, baseline=BEFORE, report_name="COMPRESSION_CHECK.json", workspace_snapshot="/tmp/hybridguard-compression-outside-before.bin"):
    old = ET.parse(baseline/'HybridGuard_overview_candidate.svg').getroot()
    new = ET.parse(HERE/'HybridGuard_overview_candidate.svg').getroot()
    ids = {e.get('id'):e for e in new.iter() if e.get('id')}
    old_ids = {e.get('id'):e for e in old.iter() if e.get('id')}
    texts = [''.join(e.itertext()) for e in new.iter(NS+'text') if e.get('data-copy')]
    frozen = json.loads((baseline/'CONTENT_MANIFEST.json').read_text())['candidate']
    icons = lambda root: {g.get('data-icon'):tuple(shape(c) for c in g) for g in root.iter() if g.get('data-icon')}
    paths = {n:polyline(g.find(NS+'path').get('d')) for n,g in ids.items() if g.get('data-source')}
    old_paths = {n:polyline(g.find(NS+'path').get('d')) for n,g in old_ids.items() if g.get('data-source')}
    rect = lambda n: tuple(float(ids[n].find(NS+'rect').get(k)) for k in ['x','y','width','height'])
    bounds = lambda n: tuple(map(float,ids[n].get('data-bounds').split(',')))
    upper,lower,frame = rect('app-only-interface'),rect('paired-interface'),rect('current-detection')
    app,browser = bounds('app-observations'),bounds('browser')
    branch=tuple(map(float,ids['app-branch'].get('data-point').split(',')))
    join=(float(ids['linked-pair'].get('cx')),float(ids['linked-pair'].get('cy')))
    unexpected=[]
    for i,a in enumerate(paths):
        for b in list(paths)[i+1:]:
            if ids[a].get('data-kind')==ids[b].get('data-kind')=='relation':
                continue
            for sa in segments(paths[a]):
                for sb in segments(paths[b]):
                    q=intersection(sa,sb)
                    if q is not None and q not in {branch,join}:
                        unexpected.append([a,b,q])
    geometry={
        'native_left_app_web_above_host':bounds('native')[0]<bounds('app-web')[0] and bounds('app-web')[1]<bounds('webview-host')[1],
        'single_app_exit_at_right_boundary':paths['current-app-exit'][0][0]==app[0]+app[2] and app[1]<paths['current-app-exit'][0][1]<app[1]+app[3],
        'app_only_branches_before_browser_join':paths['current-app-exit'][-1]==paths['current-app-only'][0]==paths['current-app-for-pair'][0]==branch and branch[1]<join[1],
        'app_only_reaches_upper_card_left':paths['current-app-only'][-1]==(upper[0],upper[1]+upper[3]/2),
        'browser_independent_outlet':paths['current-browser-for-pair'][0][0]==browser[0]+browser[2] and browser[1]<paths['current-browser-for-pair'][0][1]<browser[1]+browser[3],
        'pair_joins_at_visible_circle':paths['current-app-for-pair'][-1]==paths['current-browser-for-pair'][-1]==paths['current-linked-pair'][0]==join,
        'pair_reaches_lower_card_left':paths['current-linked-pair'][-1]==(lower[0],lower[1]+lower[3]/2),
        'model_enters_common_frame_separate_from_modes_and_result':paths['load-selected-rules'][-1][1]==frame[1]+frame[3] and paths['load-selected-rules'][-1][0]>paths['selected-mode-result'][0][0]+100 and paths['load-selected-rules'][-1][1]>lower[1]+lower[3],
        'one_output_from_common_frame':paths['selected-mode-result'][0][1]==frame[1]+frame[3] and frame[0]<paths['selected-mode-result'][0][0]<frame[0]+frame[2],
        'no_unintended_flow_or_relation_crossing':not unexpected,
        'no_masks_or_clip_paths':not any(e.tag in {NS+'mask',NS+'clipPath'} for e in new.iter()),
    }
    for name in ['native-host','native-app-web','host-app-web','app-browser']:
        a,b=ids[name].find(NS+'path'),old_ids[name].find(NS+'path')
        geometry[name+'_state_and_markers_preserved']=all(a.get(k)==b.get(k) for k in ['stroke','stroke-width','stroke-dasharray','marker-start','marker-end']) and all(ids[name].get(k)==old_ids[name].get(k) for k in ['data-source','data-target','data-status'])
    length=lambda ps:sum(math.dist(a,b) for a,b in segments(ps))
    total=lambda tree,ps:sum(length(ps[n]) for n,g in tree.items() if g.get('data-kind')=='current-input')
    anchor=lambda tree:sum(length(polyline(p.get('d'))) for g in tree.values() if g.get('data-kind')=='object-group-anchors' for p in g.findall(NS+'path'))
    chrome=json.loads((HERE/'CHECK.json').read_text())
    snapshot=json.loads((baseline/'SNAPSHOT.json').read_text())
    snapshot_matches=all((baseline/n).read_bytes()==subprocess.check_output(['git','show',snapshot['starting_head']+':'+str(HERE.relative_to(ROOT)/n)],cwd=ROOT) for n in snapshot['files'])
    layout_data=json.loads((HERE/'layout.json').read_text())
    report={
        'baseline':snapshot['starting_head'],'saved_baseline_matches_reviewed_commit':snapshot_matches,
        'body_text_count':len(texts),'copy_and_counts_preserved':Counter(texts)==Counter(frozen),
        'text_style_and_red_emphasis_preserved':styles(old)==styles(new),
        'allowed_layout_changes':'position, line breaks and alignment; font family, size, weight, italics and color are frozen',
        'font_family_preserved':old.find(NS+'style').text==new.find(NS+'style').text,
        'icon_vectors_preserved':icons(old)==icons(new),
        'captions_byte_preserved':(HERE/'CAPTIONS.md').read_bytes()==(baseline/'CAPTIONS.md').read_bytes(),
        'size_mm':layout_data['size_mm'],'actual_geometry':geometry,'unexpected_intersections':unexpected,
        'object_anchor_length_before_after':[anchor(old_ids),anchor(ids)],
        'current_data_length_before_after':[total(old_ids,old_paths),total(ids,paths)],
        'model_input_length_before_after':[length(old_paths['load-selected-rules']),length(paths['load-selected-rules'])],
        'chrome_layout_checks_pass':chrome['automated_checks_pass'],
    }
    report['pass']=all(report[k] for k in ['saved_baseline_matches_reviewed_commit','copy_and_counts_preserved','text_style_and_red_emphasis_preserved','font_family_preserved','icon_vectors_preserved','captions_byte_preserved','chrome_layout_checks_pass']) and all(geometry.values())
    save(report_name,report)

    reader=PdfReader(HERE/'HybridGuard_overview_candidate.pdf')
    extracted=normalize(reader.pages[0].extract_text())
    with pdfplumber.open(HERE/'HybridGuard_overview_candidate.pdf') as pdf:
        page=pdf.pages[0]
        fonts=font_resources(reader.pages[0]['/Resources'])
        sizes=sorted(set(round(c['size'],5) for c in page.chars))
        pdf_report={
            'pages':len(pdf.pages),'actual_page_mm':[page.width*25.4/72,page.height*25.4/72],
            'embedded_images':len(page.images),'extractable_characters':len(page.chars),
            'all_body_strings_extractable':all(extracted.count(normalize(t))>=n for t,n in Counter(texts).items()),
            'vector_paths':len(page.curves)+len(page.lines)+len(page.rects),'actual_fonts':fonts,
            'all_fonts_embedded_with_to_unicode':all(f['embedded'] and f['to_unicode'] for f in fonts),
            'times_family_fonts_only':all('TimesNewRomanPS' in f['name'] for f in fonts),
            'font_sizes_pdf_pt':sizes,'body_28_29_sizes_pdf_pt':[min(sizes,key=lambda x:abs(x-7.937)),min(sizes,key=lambda x:abs(x-8.2205))],
            'aspect_ratio_preserved_with_export_rounding':abs((page.width/page.height)/(layout_data['viewbox'][0]/layout_data['viewbox'][1])-1)<.002,
        }
    pdf_report['pass']=pdf_report['pages']==1 and pdf_report['embedded_images']==0 and all(pdf_report[k] for k in ['all_body_strings_extractable','all_fonts_embedded_with_to_unicode','times_family_fonts_only','aspect_ratio_preserved_with_export_rounding'])
    save('PDF_CHECK.json',pdf_report)

    template=HERE/'template_preview'
    log=(template/'hybridguard_draft.log').read_text()
    dims={k:float(v) for k,v in re.findall(r'HG-([A-Z-]+)=([\d.]+)pt',log)}
    manifest=json.loads((template/'SOURCE_MANIFEST.json').read_text())
    source=ROOT/manifest['source']
    unchanged=all((template/n).read_bytes()==(source/n).read_bytes() for n in manifest['files'] if n!='figures/overview_figure.tex')
    figure=(template/'figures/overview_figure.tex').read_text()
    correct_include=r'\includegraphics[width=\textwidth]{figures/HybridGuard_overview_candidate.pdf}' in figure
    no_spacing_hack=not re.search(r'\\(?:vspace|vskip|enlargethispage|resizebox|scalebox|newgeometry)\b|height\s*=',figure)
    old_template=json.loads((baseline/'TEMPLATE_CHECK.json').read_text())
    with pdfplumber.open(template/'hybridguard_draft.pdf') as pdf:
        candidates=[(i,p) for i,p in enumerate(pdf.pages,1) if any('TimesNewRomanPS' in c['fontname'] for c in p.chars)]
        assert len(candidates)==1
        number,page=candidates[0]
        times=[c for c in page.chars if 'TimesNewRomanPS' in c['fontname']]
        end=max(c['bottom'] for c in times)
        caption_chars=[c for c in page.chars if 'LinLibertineTB' in c['fontname'] and end<c['top']<end+(dims['FLOAT-HEIGHT']-dims['GRAPHIC-HEIGHT'])*72/72.27+10]
        box=(min(c['x0'] for c in caption_chars),min(c['top'] for c in caption_chars),max(c['x1'] for c in caption_chars),max(c['bottom'] for c in caption_chars))
        caption_text=page.crop(box).extract_text(x_tolerance=1)
        expected=(HERE/'CAPTIONS.md').read_text().split('## English\n\n',1)[1].split('\n\n## 中文',1)[0].strip()
        caption_match=normalize(caption_text).removeprefix('Figure1:')==normalize(expected)
        (template/'caption_extracted.txt').write_text(caption_text+'\n')
        fonts=font_resources(PdfReader(template/'hybridguard_draft.pdf').pages[number-1]['/Resources'])
        tsizes=sorted(set(round(c['size'],5) for c in times))
        body_sizes=[min(tsizes,key=lambda x:abs(x-target)) for target in old_template['body_28_29_actual_font_sizes_pdf_pt']]
        fraction=(dims['FLOAT-HEIGHT']+dims['FLOAT-DEPTH'])/dims['TEXTHEIGHT']
        result={
            'source':manifest['source'],'documentclass':'acmart','class_options':'sigconf,anonymous,review',
            'compiled_pages':len(pdf.pages),'figure_page':number,'paper_page_mm':[page.width*25.4/72,page.height*25.4/72],
            'svg_size_mm':layout_data['size_mm'],'exported_pdf_size_mm':pdf_report['actual_page_mm'],
            'tex_measurements_pt':dims,'textwidth_mm':dims['TEXTWIDTH']*25.4/72.27,
            'graphic_height_mm':dims['GRAPHIC-HEIGHT']*25.4/72.27,
            'float_figure_caption_spacing_height_mm':dims['FLOAT-HEIGHT']*25.4/72.27,
            'caption_and_template_spacing_mm':(dims['FLOAT-HEIGHT']-dims['GRAPHIC-HEIGHT'])*25.4/72.27,
            'float_fraction_of_textheight':fraction,'baseline_float_fraction_of_textheight':old_template['float_fraction_of_textheight'],
            'hard_target_less_than_half_pass':fraction<.50,'ideal_target_at_most_48_percent_pass':fraction<=.48,
            'half_page_remaining_mm':(.50*dims['TEXTHEIGHT']-dims['FLOAT-HEIGHT'])*25.4/72.27,
            'ideal_target_excess_mm':max(0,dims['FLOAT-HEIGHT']-.48*dims['TEXTHEIGHT'])*25.4/72.27,
            'body_28_29_actual_font_sizes_pdf_pt':body_sizes,
            'baseline_body_28_29_actual_font_sizes_pdf_pt':old_template['body_28_29_actual_font_sizes_pdf_pt'],
            'body_fonts_not_reduced':all(abs(a-b)<.005 for a,b in zip(body_sizes,old_template['body_28_29_actual_font_sizes_pdf_pt'])),
            'caption_actual_font':sorted(set(c['fontname'] for c in caption_chars)),
            'caption_actual_font_sizes_pdf_pt':sorted(set(round(c['size'],5) for c in caption_chars)),
            'caption_ink_bbox_pdf_pt':box,'caption_matches_full_formal_text':caption_match,
            'caption_and_spacing_unchanged':abs((dims['FLOAT-HEIGHT']-dims['GRAPHIC-HEIGHT'])-(old_template['tex_measurements_pt']['FLOAT-HEIGHT']-old_template['tex_measurements_pt']['GRAPHIC-HEIGHT']))<.01,
            'figure_page_embedded_images':len(page.images),'figure_page_vector_paths':len(page.curves)+len(page.lines)+len(page.rects),
            'all_figure_page_fonts_embedded':all(f['embedded'] for f in fonts),
            'copied_main_class_and_prose_unchanged':unchanged,'width_only_proportional_include':correct_include,'no_spacing_or_height_hack':no_spacing_hack,
            'overfull_hboxes':re.findall(r'Overfull \\hbox[^\n]*',log),'overfull_vboxes':re.findall(r'Overfull \\vbox[^\n]*',log),
            'font_or_character_errors':re.findall(r'(?:Missing character|LaTeX Font Warning|^!)[^\n]*',log,re.M),
            'unresolved_references':re.findall(r'LaTeX Warning: [^\n]*(?:undefined|Rerun)[^\n]*',log),
            'retained_template_class_warnings':re.findall(r'Class acmart Warning:[^\n]*',log),
            'scope':'Actual layout check only; copied manuscript research claims were not revised or revalidated.'
        }
    result['pass']=all(result[k] for k in ['hard_target_less_than_half_pass','body_fonts_not_reduced','caption_matches_full_formal_text','caption_and_spacing_unchanged','all_figure_page_fonts_embedded','copied_main_class_and_prose_unchanged','width_only_proportional_include','no_spacing_or_height_hack']) and not any(result[k] for k in ['overfull_hboxes','overfull_vboxes','font_or_character_errors','unresolved_references','figure_page_embedded_images'])
    save('TEMPLATE_CHECK.json',result)
    status=subprocess.check_output(['git','status','--porcelain=v1','-z','--untracked-files=all'],cwd=ROOT)
    prefix=str(HERE.relative_to(ROOT)).encode()+b'/'
    outside=[r for r in status.split(b'\0') if r and not r[3:].startswith(prefix)]
    prior=Path(workspace_snapshot)
    workspace={
        'starting_head':snapshot['starting_head'],
        'head_unchanged':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==snapshot['starting_head'],
        'outside_candidate_status_unchanged':b'\0'.join(outside)==prior.read_bytes() if prior.exists() else None,
        'outside_status_records':len(outside),'formal_files_unchanged':chrome['formal_files_unchanged'],
        'pilot_status_unchanged':chrome['pilot_status_unchanged'],
        'previous_baselines_unchanged':not subprocess.check_output(['git','diff','--name-only','--',str(HERE/'baseline'),str(HERE/'finishing_baseline_55ca3bb'),str(HERE/'compression_baseline_86aa74c')],cwd=ROOT),
    }
    save('WORKSPACE_CHECK.json',workspace)
    print(json.dumps({'compression_pass':report['pass'],'pdf_pass':pdf_report['pass'],'template_pass':result['pass'],'fraction':fraction,'body_pdf_pt':body_sizes,'outside_candidate_unchanged':workspace['outside_candidate_status_unchanged']},ensure_ascii=False))
    assert report['pass'] and pdf_report['pass'] and result['pass']
    assert workspace['head_unchanged'] and workspace['outside_candidate_status_unchanged'] is not False


if __name__=='__main__':
    main()
