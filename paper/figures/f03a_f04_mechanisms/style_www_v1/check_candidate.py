"""Audit this candidate and compile one isolated real ACM template.

Uses saved counts only. Direct visual review remains PENDING after generation.
"""
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


def audit_artwork(check):
    with (HERE/'data/plot_data.csv').open(newline='') as stream: rows=list(csv.DictReader(stream))
    expected={f'{r["panel"]}-{r["scheme"]}-{r["series"]}':r for r in rows}
    svg=ET.parse(HERE/'F03a_F04_main.svg').getroot()
    markers=svg.findall('.//*[@data-role="data-marker"]')
    labels=svg.findall('.//*[@data-role="count"]')
    require(len(markers)==len(labels)==len(expected)==24,'24 markers and counts required')
    require(len(svg.findall('.//*[@data-role="method"]'))==6,'Shared method labels must appear once')
    require(not svg.findall('.//s:image',NS),'SVG must remain vector')
    require(not svg.findall('.//s:linearGradient',NS) and not svg.findall('.//s:radialGradient',NS),'No continuous scale')
    require(not svg.findall('.//s:clipPath',NS),'No clipping to hide endpoint markers')
    methods=[t.get('data-method') for t in svg.findall('.//*[@data-role="method"]')]
    require(methods==check['data']['method_ids'],'Method order mismatch')
    positions={}; layout=check['layout']
    for marker in markers:
        id_=marker.get('data-point'); r=expected[id_]; series=r['series']; panel=layout['panels'][r['panel']]
        rate=int(r['T'])/int(r['N'])*100
        x=float(marker.get('cx')) if series=='intervention' else float(marker.get('x'))+float(marker.get('width'))/2
        y=float(marker.get('cy')) if series=='intervention' else float(marker.get('y'))+float(marker.get('height'))/2
        expected_x=panel['x0']+(panel['x1']-panel['x0'])*rate/100
        center=layout['first_row_y']+(int(r['row_order'])-1)*layout['row_pitch']
        expected_y=center+(-1 if series=='intervention' else 1)*layout['series_vertical_offset']
        require(abs(x-expected_x)<1e-9 and abs(y-expected_y)<1e-9,(id_,'Plot position differs from T/N'))
        require(float(marker.get('data-rate'))==rate and marker.get('data-count')==r['display'],'Marker attributes mismatch')
        if series=='intervention':
            require(marker.tag.endswith('circle') and marker.get('fill')==layout['series_colors'][series],'Intervention shape/color')
        else:
            require(marker.tag.endswith('rect') and marker.get('stroke')==layout['series_colors'][series] and marker.get('fill')=='#ffffff','Normal shape/color')
        positions[id_]=(x,y)
    for label in labels:
        id_=label.get('data-point'); r=expected[id_]; panel=layout['panels'][r['panel']]
        require(label.text==r['display'],'SVG count differs from data')
        require(panel['x0']<float(label.get('x'))<panel['x1'],'Endpoint label must face inward')
    # Use browser-measured text regions to verify every PDF count spatially.
    pdf=HERE/'F03a_F04_main.pdf'
    with pdfplumber.open(pdf) as doc:
        require(len(doc.pages)==1,'Standalone PDF must be one page')
        page=doc.pages[0]; text=page.extract_text(x_tolerance=1) or ''
        require(Counter(re.findall(r'\b\d+/(?:18|48|6)\b',text))==Counter(r['display'] for r in rows),'PDF count text mismatch')
        require(not page.images,'Standalone PDF contains a raster image')
        scale=72/254
        words=page.extract_words(x_tolerance=1,y_tolerance=1)
        for t in check['svg_and_browser']['texts']:
            if t['role']!='count': continue
            bbox=((t['x']-2)*scale,t['y']*scale,(t['x']+t['w']+2)*scale,(t['y']+t['h'])*scale)
            # A crop includes any touching glyph from an adjacent line. Assign
            # words by their centers inside each disjoint browser text region.
            located=[w for w in words if bbox[0]<(w['x0']+w['x1'])/2<bbox[2]
                     and bbox[1]<(w['top']+w['bottom'])/2<bbox[3]]
            require(len(located)==1 and located[0]['text']==expected[t['point']]['display'],
                    ('PDF label location',t['point'],located))
        sizes=sorted({round(c['size'],5) for c in page.chars if c['text'].strip()})
        result={'page_size_mm':[page.width*25.4/72,page.height*25.4/72],
                'font_sizes_pdf_pt':sizes,'extractable_text':True,'spatially_verified_counts':24,
                'vector_rectangles':len(page.rects),'vector_curves':len(page.curves),'raster_images':len(page.images)}
    resources=pdf_resources(PdfReader(pdf))
    require(resources['fonts'] and all(f['embedded'] and f['to_unicode'] and 'TimesNewRoman' in f['name'] for f in resources['fonts']),'PDF font embedding/fallback')
    require(not resources['images'],'Nested PDF image found')
    result.update(resources); result['pass']=True
    with Image.open(HERE/'F03a_F04_main.png') as im:
        result['png_pixels']=list(im.size)
        require(im.size==tuple(round(mm/25.4*300) for mm in layout['size_mm']),'PNG dimensions')
    require('Counts hold separately for all three frozen configurations.' in caption(),'Configuration caption missing')
    require('0/6' in caption() and '18 effective interventions' in caption() and '48 normal controls' in caption() and '30 normal records' in caption(),'Caption denominators')
    return result


def build_template():
    DEST.mkdir(exist_ok=True); copied=[]
    for src in sorted(TEMPLATE.rglob('*')):
        if src.is_file() and src.suffix in {'.tex','.cls','.bst','.bib'}:
            rel=src.relative_to(TEMPLATE); dst=DEST/rel
            dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst); copied.append(str(rel))
    shutil.copy2(HERE/'F03a_F04_main.pdf',DEST/'figures/F03a_F04_main.pdf')
    original=(TEMPLATE/'figures/overview_figure.tex').read_text()
    text=original.replace('HybridGuard_overview_triangle.pdf','F03a_F04_main.pdf')
    cap=caption().replace('%',r'\%')
    description=('Six shared method rows compare saved complete App methods in two aligned panels. '
                 'Each row has a filled green intervention-detection circle and a hollow blue normal-false-alarm square. '
                 'Positions encode alarm rates on the same zero-to-one-hundred-percent scale, with exact T/N counts. '
                 'Symbols are offset vertically, never horizontally. Memory uses eighteen interventions and forty-eight normal controls; '
                 'timezone uses six App Web changes and six normal system changes. Counts hold separately for three frozen configurations.')
    text=re.sub(r'\\caption\{[^\n]*\}',lambda _:r'\caption{'+cap+'}',text)
    text=re.sub(r'\\Description\{[^\n]*\}',lambda _:r'\Description{'+description+'}',text)
    # Preserve the old slot alias only in the isolated specimen so copied prose is unchanged.
    text=text.replace(r'\label{fig:hybridguard-overview}',r'\label{fig:app-reference-mechanisms}\label{fig:hybridguard-overview}')
    include=r'\includegraphics[width=\textwidth]{figures/F03a_F04_main.pdf}'
    require(text.count(include)==1,'Expected width-only inclusion')
    measurement='\n'.join([r'\sbox{\Mechanismgraphicbox}{'+include+'}',
        r'\typeout{MECH-TEXTWIDTH=\the\textwidth}',r'\typeout{MECH-TEXTHEIGHT=\the\textheight}',
        r'\typeout{MECH-GRAPHIC-WIDTH=\the\wd\Mechanismgraphicbox}',
        r'\typeout{MECH-GRAPHIC-HEIGHT=\the\ht\Mechanismgraphicbox}',
        r'\typeout{MECH-GRAPHIC-DEPTH=\the\dp\Mechanismgraphicbox}',r'\usebox{\Mechanismgraphicbox}'])
    hooks='\n'.join([r'\newsavebox{\Mechanismgraphicbox}',r'\begingroup',r'\makeatletter',
        r'\let\Mechanismoriginalendfloatbox\@endfloatbox',
        r'\def\@endfloatbox{\Mechanismoriginalendfloatbox',
        r'\typeout{MECH-FLOAT-HEIGHT=\the\ht\@currbox}',
        r'\typeout{MECH-FLOAT-DEPTH=\the\dp\@currbox}}',r'\makeatother',''])
    (DEST/'figures/overview_figure.tex').write_text(hooks+text.replace(include,measurement)+'\\endgroup\n')
    # Portable integration fragment: only the new label, no temporary slot alias/hooks.
    (HERE/'F03a_F04_figure.tex').write_text('\n'.join([r'\begin{figure*}[t]',r'  \centering',
        r'  \includegraphics[width=\textwidth]{F03a_F04_main.pdf}',r'  \caption{'+cap+'}',
        r'  \Description{'+description+'}',r'  \label{fig:app-reference-mechanisms}',r'\end{figure*}','']))
    # A delivered log/bbl without disposable aux files is not a reusable build state.
    command=['/Library/TeX/texbin/latexmk','-gg','-pdf','-bibtex','-interaction=nonstopmode','-halt-on-error','hybridguard_draft.tex']
    with (DEST/'build_console.txt').open('w') as stream:
        process=subprocess.run(command,cwd=DEST,stdout=stream,stderr=subprocess.STDOUT)
    console=DEST/'build_console.txt'
    console.write_text('\n'.join(line.rstrip() for line in console.read_text().splitlines()).rstrip()+'\n')
    require(process.returncode==0,'Real ACM compile failed; see template_preview/build_console.txt')
    unchanged={rel:(TEMPLATE/rel).read_bytes()==(DEST/rel).read_bytes() for rel in copied if rel!='figures/overview_figure.tex'}
    require(all(unchanged.values()),'Manuscript/class/font/margin source changed')
    dump(DEST/'SOURCE_MANIFEST.json',{'source':str(TEMPLATE.relative_to(ROOT)),
        'class_options':'sigconf,anonymous,review','copied_files':copied,'only_changed_source':'figures/overview_figure.tex',
        'other_sources_byte_identical':unchanged,'layout_specimen_only':True,
        'temporary_alias':'fig:hybridguard-overview retained only to keep copied prose references resolved',
        'integration_label':'fig:app-reference-mechanisms'})
    log=(DEST/'hybridguard_draft.log').read_text(errors='replace')
    measurements={key:float(value) for key,value in re.findall(r'MECH-([A-Z-]+)=([0-9.]+)pt',log)}
    require(len(measurements)==7,('Incomplete real template dimensions',measurements))
    errors={'overfull_hboxes':re.findall(r'Overfull \\hbox[^\n]*',log),
            'overfull_vboxes':re.findall(r'Overfull \\vbox[^\n]*',log),
            'font_or_character_errors':re.findall(r'(?:Missing character|LaTeX Font Warning)[^\n]*',log),
            'unresolved_references':re.findall(r'(?:LaTeX Warning:.*undefined|There were undefined references)[^\n]*',log),
            'retained_class_warnings':re.findall(r'Class acmart Warning[^\n]*',log)}
    return measurements,errors


def audit_template(measurements,errors):
    with pdfplumber.open(DEST/'hybridguard_draft.pdf') as doc:
        pages=[i for i,p in enumerate(doc.pages) if any('TimesNewRoman' in c['fontname'] for c in p.chars)]
        require(len(pages)==1,('Figure page lookup',pages))
        index=pages[0]; page=doc.pages[index]
        chars=[c for c in page.chars if 'TimesNewRoman' in c['fontname'] and c['text'].strip()]
        sizes=sorted({round(c['size'],5) for c in chars}); minimum=min(sizes)
        require(minimum>=7.84795,'Actual template font below overview lower bound')
        # Review line numbers lie outside the text block. Only text extraction is cropped.
        extracted=page.crop((45,0,page.width-45,page.height)).extract_text(x_tolerance=1) or ''
        normalize=lambda s: re.sub(r'\s+','',s)
        require(normalize(caption()) in normalize(extracted),'Formal caption text changed in template')
        result={'compiled_pages':len(doc.pages),'figure_page_one_based':index+1,
                'font_sizes_pdf_pt':sizes,'minimum_actual_font_pdf_pt':minimum,
                'caption_word_count':len(caption().split()),'caption_text_verified':True,
                'figure_page_raster_images':len(page.images)}
    resources=pdf_resources(PdfReader(DEST/'hybridguard_draft.pdf'),index)
    require(all(f['embedded'] for f in resources['fonts']) and not resources['images'],'Template vector/font embedding')
    total=measurements['FLOAT-HEIGHT']+measurements['FLOAT-DEPTH']
    graphic=measurements['GRAPHIC-HEIGHT']+measurements['GRAPHIC-DEPTH']
    fraction=total/measurements['TEXTHEIGHT']
    require(measurements['GRAPHIC-WIDTH']==measurements['TEXTWIDTH'],'Insertion width changed')
    errors_clear=not any(errors[k] for k in ['overfull_hboxes','overfull_vboxes','font_or_character_errors','unresolved_references'])
    require(errors_clear,('Template diagnostics',errors))
    result.update({'tex_measurements_pt':measurements,'textwidth_mm':measurements['TEXTWIDTH']*25.4/72.27,
                   'textheight_mm':measurements['TEXTHEIGHT']*25.4/72.27,
                   'graphic_width_mm':measurements['GRAPHIC-WIDTH']*25.4/72.27,
                   'graphic_height_mm':graphic*25.4/72.27,
                   'figure_caption_internal_spacing_height_mm':total*25.4/72.27,
                   'caption_internal_spacing_mm':(total-graphic)*25.4/72.27,
                   'fraction_of_textheight':fraction,'preferred_35_percent_target_met':fraction<=.35,
                   'maximum_40_percent_target_met':fraction<=.40,
                   'width_only_proportional_include':True,'font_margin_spacing_or_crop_hacks':False,
                   'diagnostics':errors,'fonts':resources['fonts'],'technical_pass':errors_clear})
    return result


def render_pdf(pdf,output,page=1,width=None,dpi=150):
    command=['pdftoppm','-f',str(page),'-l',str(page),'-png','-singlefile']
    command+=['-scale-to-x',str(width),'-scale-to-y','-1'] if width else ['-r',str(dpi)]
    subprocess.run(command+[str(pdf),str(output.with_suffix(''))],check=True,stdout=subprocess.DEVNULL)


def make_previews(template):
    PREVIEWS.mkdir(exist_ok=True)
    width=round(template['textwidth_mm']/25.4*96)
    render_pdf(HERE/'F03a_F04_main.pdf',PREVIEWS/'actual_template_width_96dpi.png',width=width)
    with Image.open(PREVIEWS/'actual_template_width_96dpi.png') as im:
        im.convert('RGB').save(PREVIEWS/'actual_template_width_96dpi.png',dpi=(96,96))
        ImageOps.grayscale(im).save(PREVIEWS/'grayscale_template_width_96dpi.png',dpi=(96,96))
    render_pdf(HERE/'F03a_F04_main.pdf',PREVIEWS/'pdf_render_180dpi.png',dpi=180)
    render_pdf(DEST/'hybridguard_draft.pdf',DEST/'figure_page.png',page=template['figure_page_one_based'],dpi=150)
    references=[('Accepted F01 rev4','paper/figures/f01_app_detection/style_www_v1/F01_main_rev4.pdf','F01_template_width_96dpi.png'),
                ('Accepted overview','paper/figures/overview_triangle/style_full_v1/HybridGuard_overview_candidate.pdf','overview_template_width_96dpi.png')]
    for _,source,dest in references: render_pdf(ROOT/source,PREVIEWS/dest,width=width)
    items=[('F03a/F04 candidate','actual_template_width_96dpi.png')]+[(name,dest) for name,_,dest in references]
    images=[Image.open(PREVIEWS/name).convert('RGB') for _,name in items]
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Times New Roman.ttf',14)
    heading,gap=24,18
    canvas=Image.new('RGB',(width,sum(im.height for im in images)+heading*len(images)+gap*(len(images)-1)),'white')
    draw=ImageDraw.Draw(canvas); y=0
    for (label,_),im in zip(items,images):
        draw.text((4,y+3),label+' - same paper width',font=font,fill='#343434')
        canvas.paste(im,(0,y+heading)); y+=heading+im.height+gap
    canvas.save(PREVIEWS/'accepted_figures_same_scale_96dpi.png',dpi=(96,96))
    return {'width_pixels':width,'dpi':96,'physical_width_mm':template['textwidth_mm'],
            'all_comparison_panels_same_width':True,'screen_physical_calibration':'Not performed; 96 dpi rendering convention.'}


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


def main():
    check=json.loads((HERE/'CHECK.json').read_text())
    check['pdf']=audit_artwork(check)
    measurements,errors=build_template()
    check['template']=audit_template(measurements,errors)
    check['previews']=make_previews(check['template'])
    cleanup_template_aux()
    check['readonly']=audit_readonly(check['generation_baseline'])
    check['automated_checks_pass']=all([check['data']['pass'],check['svg_and_browser']['pass'],
        check['pdf']['pass'],check['template']['technical_pass'],check['readonly']['pass']])
    check['layout_targets']={'preferred_35_percent':check['template']['preferred_35_percent_target_met'],
                             'maximum_40_percent':check['template']['maximum_40_percent_target_met']}
    check['visual_review']={'status':'PENDING','actually_viewed':[],'physical_print':'NOT_VERIFIED'}
    dump(HERE/'CHECK.json',check)
    print(json.dumps({'automated_checks_pass':check['automated_checks_pass'],
        'caption_words':check['template']['caption_word_count'],
        'minimum_actual_font_pdf_pt':check['template']['minimum_actual_font_pdf_pt'],
        'graphic_height_mm':check['template']['graphic_height_mm'],
        'total_height_mm':check['template']['figure_caption_internal_spacing_height_mm'],
        'fraction_of_textheight':check['template']['fraction_of_textheight'],
        'layout_targets':check['layout_targets'],'visual_review':'PENDING'}))


if __name__=='__main__':
    main()
