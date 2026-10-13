"""Compile an isolated real ACM preview and audit the saved F01 artwork.

All writes remain under this file's directory. Never runs old plot or experiment
entrypoints. Automatic checks deliberately leave human visual review pending.
"""
from pathlib import Path
from collections import Counter
import csv
import hashlib
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


def dump(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def caption():
    return (HERE/'CAPTIONS.md').read_text().split('## English\n\n',1)[1].split('\n\n## 中文',1)[0].strip()


def build_template():
    DEST.mkdir(exist_ok=True)
    copied=[]
    for src in sorted(TEMPLATE.rglob('*')):
        if src.is_file() and src.suffix in {'.tex','.cls','.bst','.bib'}:
            rel=src.relative_to(TEMPLATE); target=DEST/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,target); copied.append(str(rel))
    shutil.copy2(HERE/'F01_main.pdf',DEST/'figures/F01_main.pdf')
    original=(TEMPLATE/'figures/overview_figure.tex').read_text()
    text=original.replace('HybridGuard_overview_triangle.pdf','F01_main.pdf')
    cap=caption().replace('%',r'\%')
    text=re.sub(r'\\caption\{[^\n]*\}',lambda _:r'\caption{'+cap+'}',text)
    text=re.sub(r'\\Description\{[^\n]*\}',lambda _:r'\Description{Fourteen modification configurations in the original order and six App methods. Every cell shows the saved alarm count out of nine. A shared blue scale encodes detection proportion. Zero detections and partial detections remain explicit.}',text)
    # Keep the source slot/label to avoid changing adjacent manuscript prose.
    # This is a layout specimen, not a proposed semantic replacement of overview.
    text=text.replace(r'\label{fig:hybridguard-overview}',r'\label{fig:hybridguard-overview}\label{fig:app-modification-detection}')
    include=r'\includegraphics[width=\textwidth]{figures/F01_main.pdf}'
    require(text.count(include)==1,'Expected one width-only figure include')
    measurement='\n'.join([
        r'\sbox{\FOnegraphicbox}{'+include+'}',
        r'\typeout{FONE-TEXTWIDTH=\the\textwidth}',
        r'\typeout{FONE-TEXTHEIGHT=\the\textheight}',
        r'\typeout{FONE-GRAPHIC-WIDTH=\the\wd\FOnegraphicbox}',
        r'\typeout{FONE-GRAPHIC-HEIGHT=\the\ht\FOnegraphicbox}',
        r'\typeout{FONE-GRAPHIC-DEPTH=\the\dp\FOnegraphicbox}',
        r'\usebox{\FOnegraphicbox}',
    ])
    hooks='\n'.join([
        r'\newsavebox{\FOnegraphicbox}',r'\begingroup',r'\makeatletter',
        r'\let\FOneoriginalendfloatbox\@endfloatbox',
        r'\def\@endfloatbox{\FOneoriginalendfloatbox',
        r'\typeout{FONE-FLOAT-HEIGHT=\the\ht\@currbox}',
        r'\typeout{FONE-FLOAT-DEPTH=\the\dp\@currbox}}',r'\makeatother','',
    ])
    text=hooks+text.replace(include,measurement)+'\\endgroup\n'
    (DEST/'figures/overview_figure.tex').write_text(text)
    command=['/Library/TeX/texbin/latexmk','-pdf','-bibtex','-interaction=nonstopmode','-halt-on-error','hybridguard_draft.tex']
    with (DEST/'build_console.txt').open('w') as stream:
        result=subprocess.run(command,cwd=DEST,stdout=stream,stderr=subprocess.STDOUT)
    console=DEST/'build_console.txt'
    console.write_text('\n'.join(line.rstrip() for line in console.read_text().splitlines())+'\n')
    require(result.returncode==0,'Real ACM preview compilation failed; see template_preview/build_console.txt')
    unchanged={rel:sha(TEMPLATE/rel)==sha(DEST/rel) for rel in copied if rel!='figures/overview_figure.tex'}
    require(all(unchanged.values()),'Copied manuscript/class/bibliography changed')
    dump(DEST/'SOURCE_MANIFEST.json',{'source':str(TEMPLATE.relative_to(ROOT)),
        'class_options':'sigconf,anonymous,review','copied_files':copied,
        'only_changed_source':'figures/overview_figure.tex', 'other_copied_files_byte_identical':unchanged,
        'scope':'Existing overview slot reused solely for layout. Retained manuscript prose is not revalidated or proposed for replacement.'})
    log=(DEST/'hybridguard_draft.log').read_text(errors='replace')
    measurements={k:float(v) for k,v in re.findall(r'FONE-([A-Z-]+)=([0-9.]+)pt',log)}
    require(len(measurements)==7,('Incomplete TeX measurements',measurements))
    errors={
        'overfull_hboxes':re.findall(r'Overfull \\hbox[^\n]*',log),
        'overfull_vboxes':re.findall(r'Overfull \\vbox[^\n]*',log),
        'font_or_character_errors':re.findall(r'(?:Missing character|LaTeX Font Warning)[^\n]*',log),
        'unresolved_references':re.findall(r'(?:LaTeX Warning:.*undefined|There were undefined references)[^\n]*',log),
        'retained_class_warnings':re.findall(r'Class acmart Warning[^\n]*',log)}
    return measurements,errors


def pdf_resources(reader, page_number=0):
    fonts=[]; images=[]; visited=set()
    def visit(resources):
        resources=resources.get_object()
        for _,font_ref in resources.get('/Font',{}).items():
            font=font_ref.get_object(); name=str(font.get('/BaseFont',''))
            identity=('font',name)
            if identity in visited: continue
            visited.add(identity)
            descendant=font.get('/DescendantFonts')
            base=descendant[0].get_object() if descendant else font
            desc=base.get('/FontDescriptor')
            desc=desc.get_object() if desc else {}
            fonts.append({'name':name,'embedded':any(key in desc for key in ['/FontFile','/FontFile2','/FontFile3']),
                          'to_unicode':'/ToUnicode' in font})
        for key,ref in resources.get('/XObject',{}).items():
            obj=ref.get_object()
            if obj.get('/Subtype')=='/Image': images.append(str(key))
            if obj.get('/Subtype')=='/Form' and '/Resources' in obj:
                identity=('form',getattr(ref,'idnum',id(obj)))
                if identity not in visited:
                    visited.add(identity);visit(obj['/Resources'])
    visit(reader.pages[page_number]['/Resources'])
    return dict(fonts=fonts,images=images)


def audit_artwork(check):
    with (HERE/'F01_plot_data.csv').open(newline='') as stream: data=list(csv.DictReader(stream))
    expected={(r['row_order'],r['column_order']):r for r in data}
    svg=ET.parse(HERE/'F01_main.svg').getroot()
    texts=svg.findall('.//s:text',NS)
    svg_cells=[t for t in texts if t.get('data-role')=='count']
    require(len(svg_cells)==84 and len(expected)==84,'84 unique rendered cells')
    for node in svg_cells:
        row,col=node.get('data-cell').split('-'); ref=expected[(row,col)]
        require(node.text==ref['display'] and node.get('data-method')==ref['scheme']
                and node.get('data-config')==ref['configuration'],('Rendered cell mismatch',row,col))
    require(not svg.findall('.//s:image',NS),'SVG raster image')
    with pdfplumber.open(HERE/'F01_main.pdf') as pdf:
        require(len(pdf.pages)==1,'Standalone PDF is not one page')
        page=pdf.pages[0]; extract=page.extract_text(x_tolerance=1) or ''
        require(Counter(re.findall(r'\b\d+/9\b',extract))==Counter(r['display'] for r in data),'PDF count text mismatch')
        require(len(page.images)==0 and len(page.rects)>=84,'Vector PDF geometry missing')
        # Spatial, not only aggregate, verification of all 84 PDF cells.
        point_per_unit=72/254
        gx,gy,cw,rh=check['layout']['grid']
        for (row,col),ref in expected.items():
            i,j=int(row)-1,int(col)-1
            box=((gx+j*cw+1)*point_per_unit,(gy+i*rh+1)*point_per_unit,
                 (gx+(j+1)*cw-1)*point_per_unit,(gy+(i+1)*rh-1)*point_per_unit)
            actual=(page.crop(box).extract_text() or '').strip()
            require(actual==ref['display'],('PDF spatial cell mismatch',row,col,actual,ref['display']))
        sizes=sorted({round(c['size'],5) for c in page.chars if c['text'].strip()})
        pdf_stats={'size_mm':[page.width*25.4/72,page.height*25.4/72],
                   'actual_font_sizes_pdf_pt':sizes,'raster_images':len(page.images),
                   'vector_rectangles':len(page.rects),'vector_curves':len(page.curves),
                   'all_84_cell_texts_spatially_match':True,'extractable_text':True}
    resources=pdf_resources(PdfReader(HERE/'F01_main.pdf'))
    require(resources['fonts'] and all(f['embedded'] and f['to_unicode'] and 'TimesNewRoman' in f['name'] for f in resources['fonts']),
            ('PDF fonts',resources))
    require(not resources['images'],'Nested raster image in PDF')
    pdf_stats.update(resources)
    pdf_stats['pass']=True
    return pdf_stats


def template_audit(measurements, errors, check):
    with pdfplumber.open(DEST/'hybridguard_draft.pdf') as pdf:
        pages=[i for i,p in enumerate(pdf.pages) if any('TimesNewRoman' in c['fontname'] for c in p.chars)]
        require(len(pages)==1,('F01 page lookup',pages))
        index=pages[0]; page=pdf.pages[index]
        chars=[c for c in page.chars if 'TimesNewRoman' in c['fontname']]
        require(chars,'Missing actual figure font glyphs in template')
        sizes=sorted({round(c['size'],5) for c in chars if c['text'].strip()})
        # Review line numbers live outside the text block; exclude them when
        # checking continuous caption copy, without cropping the delivered page.
        extracted=page.crop((45,0,page.width-45,page.height)).extract_text(x_tolerance=1) or ''
        normal=lambda s: re.sub(r'\s+','',s)
        require(normal(caption()) in normal(extracted),'Formal English caption not fully preserved in template')
        figure_min=min(sizes)
        require(figure_min>=7.84795,('Template font too small',figure_min))
        page_info={'compiled_pages':len(pdf.pages),'figure_page_one_based':index+1,
                   'page_size_mm':[page.width*25.4/72,page.height*25.4/72],
                   'figure_actual_font_sizes_pdf_pt':sizes,'minimum_actual_font_pdf_pt':figure_min,
                   'figure_page_raster_images':len(page.images),'caption_matches_formal_text':True,
                   'caption_word_count':len(caption().split())}
    resources=pdf_resources(PdfReader(DEST/'hybridguard_draft.pdf'),index)
    require(all(f['embedded'] for f in resources['fonts']) and not resources['images'],'Template embedding/raster check')
    height=measurements['FLOAT-HEIGHT']+measurements['FLOAT-DEPTH']
    gh=measurements['GRAPHIC-HEIGHT']+measurements['GRAPHIC-DEPTH']
    fraction=height/measurements['TEXTHEIGHT']
    require(fraction<.5,('Figure + caption + spacing exceeds half textheight',fraction))
    require(measurements['GRAPHIC-WIDTH']==measurements['TEXTWIDTH'],'Not textwidth insertion')
    no_errors=not any(errors[k] for k in ['overfull_hboxes','overfull_vboxes','font_or_character_errors','unresolved_references'])
    require(no_errors,('TeX diagnostics',errors))
    page_info.update({'source_template':str(TEMPLATE.relative_to(ROOT)),
                      'tex_measurements_pt':measurements,
                      'textwidth_mm':measurements['TEXTWIDTH']*25.4/72.27,
                      'textheight_mm':measurements['TEXTHEIGHT']*25.4/72.27,
                      'graphic_width_mm':measurements['GRAPHIC-WIDTH']*25.4/72.27,
                      'graphic_height_mm':gh*25.4/72.27,
                      'figure_caption_internal_spacing_height_mm':height*25.4/72.27,
                      'caption_internal_spacing_mm':(height-gh)*25.4/72.27,
                      'fraction_of_textheight':fraction,'less_than_half':fraction<.5,
                      'width_only_proportional_include':True,'no_spacing_font_margin_or_crop_hack':True,
                      'fonts':resources['fonts'],'diagnostics':errors,'pass':no_errors})
    return page_info


def render_pdf(pdf, output, page=1, width=None, dpi=150):
    command=['pdftoppm','-f',str(page),'-l',str(page),'-png','-singlefile']
    command+=['-scale-to-x',str(width),'-scale-to-y','-1'] if width else ['-r',str(dpi)]
    subprocess.run(command+[str(pdf),str(output.with_suffix(''))],check=True,stdout=subprocess.DEVNULL)


def comparison(a,b,target,label_a,label_b):
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Times New Roman.ttf',14)
    gap,heading=18,24
    canvas=Image.new('RGB',(max(a.width,b.width),a.height+b.height+2*heading+gap),'white')
    draw=ImageDraw.Draw(canvas)
    draw.text((4,3),label_a,font=font,fill='#343434');canvas.paste(a,(0,heading))
    y=heading+a.height+gap
    draw.text((4,y+3),label_b,font=font,fill='#343434');canvas.paste(b,(0,y+heading))
    canvas.save(target,dpi=(96,96))


def previews(template):
    PREVIEWS.mkdir(exist_ok=True)
    width=round(template['textwidth_mm']/25.4*96)
    render_pdf(HERE/'F01_main.pdf',PREVIEWS/'actual_template_width_96dpi.png',width=width)
    with Image.open(PREVIEWS/'actual_template_width_96dpi.png') as im:
        new=im.convert('RGB'); new.save(PREVIEWS/'actual_template_width_96dpi.png',dpi=(96,96))
        ImageOps.grayscale(new).save(PREVIEWS/'grayscale_template_width_96dpi.png',dpi=(96,96))
    render_pdf(HERE/'F01_main.pdf',PREVIEWS/'pdf_render_180dpi.png',dpi=180)
    render_pdf(DEST/'hybridguard_draft.pdf',DEST/'figure_page.png',page=template['figure_page_one_based'],dpi=150)
    with Image.open(ROOT/'paper/figures/round1_app/figures/F01.png') as image:
        old=image.convert('RGB').resize((width,round(image.height*width/image.width)),Image.Resampling.LANCZOS)
    comparison(old,new,PREVIEWS/'old_new_same_width_96dpi.png','Original F01 - same physical width','Candidate F01 - same physical width')
    overview=ROOT/'paper/figures/overview_triangle/style_full_v1/HybridGuard_overview_candidate.pdf'
    render_pdf(overview,PREVIEWS/'overview_template_width_96dpi.png',width=width)
    with Image.open(PREVIEWS/'overview_template_width_96dpi.png') as image:
        comparison(image.convert('RGB'),new,PREVIEWS/'overview_F01_same_width_96dpi.png',
                   'Approved overview - same physical width','Candidate F01 - same physical width')
    return {'dpi':96,'width_pixels':width,'physical_width_mm':template['textwidth_mm'],
            'comparison_opacity':1,'both_comparison_panels_same_width':True,
            'screen_calibration_note':'96 dpi physical-scale convention; actual monitor/display scaling is not calibrated.'}


def readonly_audit():
    manifest=json.loads((HERE/'SOURCE_MANIFEST.json').read_text())
    changed=[]
    for rel,before in manifest['protected_files_before'].items():
        file=ROOT/rel
        if not file.is_file() or sha(file)!=before['sha256']:
            changed.append(rel)
    raw=subprocess.check_output(['git','status','--porcelain=v1','-z'],cwd=ROOT).decode()
    current=[r for r in raw.split('\0') if r and not r[3:].startswith('paper/figures/f01_app_detection/')]
    before=[r for r in manifest['git_status_porcelain_v1_z_at_start'].split('\0') if r]
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    report={'protected_file_count':len(manifest['protected_files_before']),'changed_protected_files':changed,
            'existing_git_status_records':len(before),'outside_candidate_status_unchanged':current==before,
            'head_unchanged':head==manifest['local_head_at_start'],'head':head,
            'source_old_F01_round1_overview_and_template_digests_unchanged':not changed,
            'no_system_font_files_copied':not any(p.suffix.lower() in {'.ttf','.otf','.ttc'} for p in HERE.rglob('*')),
            'check_scope':'Byte digests cover the 281 enumerated source/old-figure/overview/template files; Git status covers pre-existing tracked/untracked work. No blanket rehash of unrelated research artifacts.',
            'pass':not changed and current==before and head==manifest['local_head_at_start']}
    require(report['pass'],'Read-only scope failure: '+json.dumps(report))
    return report


def main():
    check=json.loads((HERE/'CHECK.json').read_text())
    require(check['svg_and_browser']['pass'],'Fix browser layout/font issues first')
    check['pdf']=audit_artwork(check)
    measurements,errors=build_template()
    check['template']=template_audit(measurements,errors,check)
    overview_dir=ROOT/'paper/figures/overview_triangle/style_full_v1'
    overview_svg=ET.parse(overview_dir/'HybridGuard_overview_candidate.svg').getroot()
    core_sizes=sorted({float(t.get('font-size')) for t in overview_svg.findall('.//s:text',NS) if t.get('data-copy')})[:2]
    with pdfplumber.open(overview_dir/'HybridGuard_overview_candidate.pdf') as pdf:
        # Main copy is marked data-copy in the approved SVG. Icon-internal
        # microtext is not the comparable 28/29-unit body typography.
        actual_sizes=sorted({c['size'] for c in pdf.pages[0].chars if c['text'].strip() and 'TimesNewRoman' in c['fontname']})
        body=[size for size in actual_sizes if any(abs(size-units*72/254)<.02 for units in core_sizes)]
        require(body,'Cannot resolve approved overview body font sizes')
        width=pdf.pages[0].width
        factor=check['template']['textwidth_mm']/25.4*72/width
        check['overview_comparison']={'body_source_svg_units':core_sizes,
             'actual_same_width_body_fonts_pdf_pt':[round(size*factor,5) for size in body],
             'actual_same_width_min_body_font_pdf_pt':min(body)*factor,
             'candidate_min_font_pdf_pt':check['template']['minimum_actual_font_pdf_pt'],
             'reference_stroke_units':{'boundary':1.5,'flow':2.0},
             'candidate_stroke_units':{'outer_boundary':1.5,'internal_separators':1.25},
             'reference':'Current approved candidate only; no historic baseline used as style target.'}
    check['previews']=previews(check['template'])
    check['readonly']=readonly_audit()
    check['automated_checks_pass']=True
    check['visual_review']={'status':'PENDING','note':'Automatic checks are not visual acceptance. Open all required final previews before marking reviewed.'}
    dump(HERE/'CHECK.json',check)
    print(json.dumps({'automated_checks_pass':True,'template':check['template'],'readonly':check['readonly']},ensure_ascii=False))


if __name__=='__main__':
    main()
