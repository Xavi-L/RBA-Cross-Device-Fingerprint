"""Compile an isolated real ACM preview and audit the saved F01 artwork.

All writes remain under this file's directory. Never runs old plot or experiment
entrypoints. Automatic checks deliberately leave direct visual review pending.
"""
from pathlib import Path
from collections import Counter
import csv
import colorsys
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
DEST=HERE/'template_preview_rev3'
PREVIEWS=HERE/'previews_rev3'
NS={'s':'http://www.w3.org/2000/svg'}


def dump(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


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
    shutil.copy2(HERE/'F01_main_rev3.pdf',DEST/'figures/F01_main_rev3.pdf')
    original=(TEMPLATE/'figures/overview_figure.tex').read_text()
    text=original.replace('HybridGuard_overview_triangle.pdf','F01_main_rev3.pdf')
    cap=caption().replace('%',r'\%')
    text=re.sub(r'\\caption\{[^\n]*\}',lambda _:r'\caption{'+cap+'}',text)
    text=re.sub(r'\\Description\{[^\n]*\}',lambda _:r'\Description{Fourteen modification configurations in the original order and six App methods. Every cell shows the saved alarm count out of nine. Three discrete pale fills show full detection in cool blue, partial detection in gray-blue, and zero detection in warm gray; a compact three-swatch legend shares the title row. The numbers carry all values. Zero detections and partial detections remain explicit.}',text)
    # Keep the source slot/label to avoid changing adjacent manuscript prose.
    # This is a layout specimen, not a proposed semantic replacement of overview.
    text=text.replace(r'\label{fig:hybridguard-overview}',r'\label{fig:hybridguard-overview}\label{fig:app-modification-detection}')
    include=r'\includegraphics[width=\textwidth]{figures/F01_main_rev3.pdf}'
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
    console.write_text('\n'.join(line.rstrip() for line in console.read_text().splitlines()).rstrip()+'\n')
    require(result.returncode==0,'Real ACM preview compilation failed; see template_preview_rev3/build_console.txt')
    unchanged={rel:(TEMPLATE/rel).read_bytes()==(DEST/rel).read_bytes() for rel in copied if rel!='figures/overview_figure.tex'}
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
    svg=ET.parse(HERE/'F01_main_rev3.svg').getroot()
    texts=svg.findall('.//s:text',NS)
    svg_cells=[t for t in texts if t.get('data-role')=='count']
    require(len(svg_cells)==84 and len(expected)==84,'84 unique rendered cells')
    for node in svg_cells:
        row,col=node.get('data-cell').split('-'); ref=expected[(row,col)]
        require(node.text==ref['display'] and node.get('data-method')==ref['scheme']
                and node.get('data-config')==ref['configuration'],('Rendered cell mismatch',row,col))
    require(not svg.findall('.//s:image',NS),'SVG raster image')
    require(not svg.findall('.//s:linearGradient',NS) and not svg.findall('.//s:radialGradient',NS), 'Continuous gradient retained')
    require(not svg.findall('.//*[@data-role="colorbar"]'), 'Colorbar retained')
    palette=check['layout']['colors']['discrete_cell_fills']
    require(palette=={'9/9':'#DDE7F2','6/9':'#E8ECF1','0/9':'#F3F1EE'}, 'Unexpected discrete palette')
    rects=svg.findall('.//s:rect',NS)
    cells=[r for r in rects if r.get('data-cell')]
    require(len(cells)==84, 'Cell rectangle count')
    require(Counter(r.get('fill') for r in cells)=={palette['9/9']:62,palette['6/9']:4,palette['0/9']:18}, 'Unexpected cell fill counts')
    for rect in cells:
        row,col=rect.get('data-cell').split('-')
        require(rect.get('fill')==palette[expected[(row,col)]['display']], 'Wrong discrete fill mapping')
    legends=svg.findall('.//s:text[@data-role="legend"]',NS)
    swatches=svg.findall('.//s:rect[@data-role="legend-swatch"]',NS)
    require([t.text for t in legends]==['9/9','6/9','0/9'] and len(swatches)==3, 'Three-value legend missing')
    require(all(r.get('fill')==palette[r.get('data-value')] for r in swatches), 'Legend colors differ from cells')
    require(all(float(t.get('y'))==30 and float(t.get('font-size'))==31 for t in legends), 'Legend resized or added height')
    require(len(svg.findall('.//*[@data-role="table-rule"]'))==3, 'Expected three table rules')
    separators=svg.findall('.//*[@data-role="cell-separator"]')
    require(len(separators)==18 and all(s.get('stroke')=='#ffffff' and s.get('stroke-width')=='1.5' for s in separators), 'Cell separators changed')
    previous=ET.parse(HERE/'F01_main_rev2.svg').getroot()
    retained_roles={'title','row-heading','method','configuration','count'}
    signature=lambda root:[(dict(n.attrib),n.text) for n in root.findall('.//s:text',NS) if n.get('data-role') in retained_roles]
    require(signature(svg)==signature(previous), 'Original text, data, order, geometry or typography changed')
    old_cells={r.get('data-cell'):r for r in previous.findall('.//s:rect',NS) if r.get('data-cell')}
    for rect in cells:
        attrs={k:v for k,v in rect.attrib.items() if k!='fill'}
        require(attrs=={k:v for k,v in old_cells[rect.get('data-cell')].attrib.items() if k!='fill'}, 'Cell geometry or identity changed')
    require(svg.attrib==previous.attrib, 'Canvas dimensions changed')
    gray_values={v:ImageOps.grayscale(Image.new('RGB',(1,1),color)).getpixel((0,0)) for v,color in palette.items()}
    require(gray_values['9/9']+5<=gray_values['6/9'] and gray_values['6/9']+5<=gray_values['0/9'], '6/9 is not intermediate in grayscale')
    saturation={v:colorsys.rgb_to_hsv(*(int(color[k:k+2],16)/255 for k in (1,3,5)))[1] for v,color in palette.items()}
    require(max(saturation.values())<.1 and min(gray_values.values())>220, 'Palette too saturated or dark')
    require(check['layout']['cell_contrast_min']>9, 'Insufficient dark-gray text contrast')
    palette_audit={'exact_discrete_mapping':palette,'grayscale_8bit':gray_values,'hsv_saturation':saturation,
                   'all_classes_have_nonwhite_fill':True,'middle_value_has_middle_visual_weight':True,
                   'text_geometry_and_typography_equal_rev2':True,'cell_geometry_equal_rev2':True,
                   'three_swatch_legend_no_added_height':True,'white_hairlines_separate_cells':True}
    with pdfplumber.open(HERE/'F01_main_rev3.pdf') as pdf:
        require(len(pdf.pages)==1,'Standalone PDF is not one page')
        page=pdf.pages[0]; extract=page.extract_text(x_tolerance=1) or ''
        require(Counter(re.findall(r'\b\d+/9\b',extract))==Counter(r['display'] for r in data)+Counter(['9/9','6/9','0/9']),'PDF matrix and legend count text mismatch')
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
        clearances=[]
        for (row,col),ref in expected.items():
            i,j=int(row)-1,int(col)-1
            left,top=(gx+j*cw)*point_per_unit,(gy+i*rh)*point_per_unit
            right,bottom=left+cw*point_per_unit,top+rh*point_per_unit
            chars=page.crop((left,top,right,bottom)).chars
            require(chars, 'No cell glyphs')
            clearances.append(min(min(c['x0'] for c in chars)-left,
                                  right-max(c['x1'] for c in chars),
                                  min(c['top'] for c in chars)-top,
                                  bottom-max(c['bottom'] for c in chars)))
        # PDF character boxes include font ascent/descent, not visible ink.
        # Require containment here; measure actual rendered ink separately below.
        require(min(clearances)>0, ('PDF character box extends outside cell',min(clearances)))
        sizes=sorted({round(c['size'],5) for c in page.chars if c['text'].strip()})
        pdf_stats={'size_mm':[page.width*25.4/72,page.height*25.4/72],
                   'actual_font_sizes_pdf_pt':sizes,'raster_images':len(page.images),
                   'vector_rectangles':len(page.rects),'vector_curves':len(page.curves),
                   'all_84_cell_texts_spatially_match':True,'extractable_text':True,
                   'minimum_cell_font_metric_padding_pdf_pt':min(clearances),
                   'nonwhite_cells':84,'discrete_fill_counts':{'9/9':62,'6/9':4,'0/9':18},
                   'palette_audit':palette_audit,'continuous_gradient':False,'colorbar':False}
    resources=pdf_resources(PdfReader(HERE/'F01_main_rev3.pdf'))
    require(resources['fonts'] and all(f['embedded'] and f['to_unicode'] and 'TimesNewRoman' in f['name'] for f in resources['fonts']),
            ('PDF fonts',resources))
    require(not resources['images'],'Nested raster image in PDF')
    with Image.open(HERE/'F01_main_rev3.png') as source:
        rendered=source.convert('RGB')
        scale=rendered.width/check['layout']['viewbox'][0]
        ink_clearances=[]
        sampled_fills=Counter()
        for row,col in expected:
            i,j=int(row)-1,int(col)-1
            value=expected[(row,col)]['display']
            rgb=tuple(int(palette[value][k:k+2],16) for k in (1,3,5))
            actual=rendered.getpixel((round((gx+j*cw+10)*scale),round((gy+i*rh+17)*scale)))
            require(actual==rgb, ('Rendered background differs from mapping',row,col,actual,rgb))
            sampled_fills[value]+=1
            bounds=tuple(round(v*scale) for v in
                         (gx+j*cw,gy+i*rh,gx+(j+1)*cw,gy+(i+1)*rh))
            crop=rendered.crop(bounds)
            dark=crop.convert('L').point(lambda value:255 if value<140 else 0)
            ink=dark.getbbox()
            require(ink is not None, 'Missing rendered cell ink')
            ink_clearances.append(min(ink[0],ink[1],crop.width-ink[2],crop.height-ink[3]))
        require(min(ink_clearances)>=3, ('Visible numbers too close to cell boundary',min(ink_clearances)))
        pdf_stats['minimum_rendered_cell_ink_padding_pixels_at_300dpi']=min(ink_clearances)
        pdf_stats['png_size_pixels']=list(rendered.size)
        pdf_stats['actual_rendered_fill_counts']=dict(sampled_fills)
        rendered.save(HERE/'F01_main_rev3.png',dpi=(300,300))
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
    render_pdf(HERE/'F01_main_rev3.pdf',PREVIEWS/'actual_template_width_96dpi.png',width=width)
    with Image.open(PREVIEWS/'actual_template_width_96dpi.png') as im:
        new=im.convert('RGB'); new.save(PREVIEWS/'actual_template_width_96dpi.png',dpi=(96,96))
        ImageOps.grayscale(new).save(PREVIEWS/'grayscale_template_width_96dpi.png',dpi=(96,96))
    render_pdf(HERE/'F01_main_rev3.pdf',PREVIEWS/'pdf_render_180dpi.png',dpi=180)
    render_pdf(DEST/'hybridguard_draft.pdf',DEST/'figure_page.png',page=template['figure_page_one_based'],dpi=150)
    render_pdf(HERE/'F01_main_rev2.pdf',PREVIEWS/'rev2_template_width_96dpi.png',width=width)
    with Image.open(PREVIEWS/'rev2_template_width_96dpi.png') as image:
        old=image.convert('RGB').resize((width,round(image.height*width/image.width)),Image.Resampling.LANCZOS)
    comparison(old,new,PREVIEWS/'rev2_rev3_same_width_96dpi.png','Rev2 - same template width','Rev3 - same template width')
    overview=ROOT/'paper/figures/overview_triangle/style_full_v1/HybridGuard_overview_candidate.pdf'
    render_pdf(overview,PREVIEWS/'overview_template_width_96dpi.png',width=width)
    with Image.open(PREVIEWS/'overview_template_width_96dpi.png') as image:
        comparison(image.convert('RGB'),new,PREVIEWS/'overview_F01_same_width_96dpi.png',
                   'Approved overview - same physical width','F01 rev3 - same physical width')
    return {'dpi':96,'width_pixels':width,'physical_width_mm':template['textwidth_mm'],
            'comparison_opacity':1,'both_comparison_panels_same_width':True,
            'screen_calibration_note':'96 dpi physical-scale convention; actual monitor/display scaling is not calibrated.'}


def readonly_audit():
    manifest=json.loads((HERE/'SOURCE_MANIFEST_rev3.json').read_text())
    baseline=manifest['local_head_at_start']
    changed=[]
    for rel in manifest['preserved_candidate_head_paths']:
        expected=subprocess.check_output(['git','show',baseline+':'+rel],cwd=ROOT)
        if not (ROOT/rel).is_file() or (ROOT/rel).read_bytes()!=expected:
            changed.append(rel)
    raw=subprocess.check_output(['git','status','--porcelain=v1','-z'],cwd=ROOT).decode()
    external=lambda status:[r for r in status.split('\0') if r and not r[3:].startswith('paper/figures/f01_app_detection/')]
    current,before=external(raw),external(manifest['git_status_porcelain_v1_z_at_start'])
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    index_empty=not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT).strip()
    report={'preserved_existing_candidate_files':len(manifest['preserved_candidate_head_paths']),
            'changed_existing_candidate_files':changed,
            'outside_candidate_status_records':len(before),'outside_candidate_status_unchanged':current==before,
            'head_unchanged':head==baseline,'head':head,'index_empty':index_empty,
            'no_system_font_files_copied':not any(p.suffix.lower() in {'.ttf','.otf','.ttc'} for p in HERE.rglob('*')),
            'check_scope':'Direct byte comparison of prior committed candidate files; Git status protects unrelated work. Original CSV and aliases are included. No new hash scan.',
            'pass':not changed and current==before and head==baseline and index_empty}
    require(report['pass'],'Read-only scope failure: '+json.dumps(report))
    return report


def revision_comparison(check):
    old=json.loads((HERE/'rev2_snapshot/CHECK.json').read_text())
    new_template,old_template=check['template'],old['template']
    fields=['graphic_width_mm','graphic_height_mm','figure_caption_internal_spacing_height_mm',
            'caption_word_count','caption_internal_spacing_mm','fraction_of_textheight','minimum_actual_font_pdf_pt']
    metrics={key:{'rev2':old_template[key],'rev3':new_template[key],
                  'delta':new_template[key]-old_template[key]} for key in fields}
    metrics['nominal_artwork_size_mm']={'rev2':old['layout']['size_mm'],'rev3':check['layout']['size_mm']}
    metrics['same_source_body_font_units']=31
    metrics['source_row_pitch_mm']={'rev2':old['layout']['grid'][3]/10,'rev3':check['layout']['grid'][3]/10}
    require(old['layout']['size_mm']==check['layout']['size_mm'] and old['layout']['grid']==check['layout']['grid'], 'Source dimensions changed')
    require(abs(metrics['minimum_actual_font_pdf_pt']['delta'])<.002, 'Core font changed')
    require(abs(metrics['graphic_height_mm']['delta'])<.01 and abs(metrics['graphic_width_mm']['delta'])<.01, 'Inserted figure size changed')
    require(metrics['figure_caption_internal_spacing_height_mm']['delta']<=.01, 'Figure and caption became taller')
    metrics['compact_dimensions_preserved']=True
    metrics['pass']=True
    return metrics



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
             'candidate_stroke_units':{'top_bottom_table_rule':2.0,'header_table_rule':1.5},
             'reference':'Current approved candidate only; no historic baseline used as style target.'}
    check['revision_comparison']=revision_comparison(check)
    check['previews']=previews(check['template'])
    check['readonly']=readonly_audit()
    check['automated_checks_pass']=True
    check['visual_review']={'status':'PENDING','note':'Automatic checks are not visual acceptance. Open all required final previews before marking reviewed.'}
    dump(HERE/'CHECK.json',check)
    print(json.dumps({'automated_checks_pass':True,'template':check['template'],'readonly':check['readonly']},ensure_ascii=False))


if __name__=='__main__':
    main()
