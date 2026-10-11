"""Check exactly two visible changes against the reviewed 393f0faa candidate."""
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET
from PIL import Image, ImageChops, ImageDraw
import check_compression as shared

HERE = Path(__file__).resolve().parent
BEFORE = HERE/'direction_fix_baseline_393f0faa'
NS = '{http://www.w3.org/2000/svg}'


def canonical(e):
    return (e.tag,tuple(sorted(e.attrib.items())),(e.text or '').strip(),tuple(canonical(c) for c in e))


def main():
    old=ET.parse(BEFORE/'HybridGuard_overview_candidate.svg').getroot()
    new=ET.parse(HERE/'HybridGuard_overview_candidate.svg').getroot()
    old_ids={e.get('id'):e for e in old.iter() if e.get('id')}
    new_ids={e.get('id'):e for e in new.iter() if e.get('id')}
    removed=0
    for p in list(old_ids['timezone-example']):
        if p.tag==NS+'path' and p.get('d')=='M1270 141H1782':
            old_ids['timezone-example'].remove(p);removed+=1
    additions=[]
    for group in new.iter(NS+'g'):
        for p in list(group):
            if p.get('data-direction-arrow')=='true':
                additions.append((group.get('id'),p.get('d')));group.remove(p)
    invariant=canonical(old)==canonical(new)
    assert removed==1 and len(additions)==2 and invariant
    chrome=json.loads((HERE/'CHECK.json').read_text())
    arrows={a['group']:a for a in chrome['visible_geometry']['direction_arrows']}
    direction={}
    for group,sign,lower,upper in [('current-app-for-pair',1,285,463),('current-browser-for-pair',-1,463,674)]:
        a=arrows[group];b=a['rendered_head_bbox_units'];x=a['endpoint']['x'];y=a['endpoint']['y']
        direction[group]={
            'actual_marker_auto_orientation':a['orientation']=='auto',
            'actual_direction_correct':abs(a['unit_direction'][0])<1e-8 and abs(a['unit_direction'][1]-sign)<1e-8,
            'reuses_existing_data_arrow':a['marker']=='input-arrow' and a['marker_shape']=='M0 0L10 5L0 10L3 5Z' and a['marker_units']=='userSpaceOnUse',
            'inside_original_input_segment':x==856 and lower+30<b['top']<b['bottom']<upper-30,
            'clear_of_join_and_turn':min(abs(y-lower),abs(y-upper))>60,
            'visible_without_text_contact':a['visible'] and not a['head_text_intersections'],
            'endpoint_units':[x,y],
        }
        assert all(v for k,v in direction[group].items() if k!='endpoint_units')
    shared.main(baseline=BEFORE,report_name='DIRECTION_FIX_CHECK.json',workspace_snapshot='/tmp/hybridguard-direction-fix-outside-before.bin')
    report=json.loads((HERE/'DIRECTION_FIX_CHECK.json').read_text())
    template=json.loads((HERE/'TEMPLATE_CHECK.json').read_text())
    old_template=json.loads((BEFORE/'TEMPLATE_CHECK.json').read_text())
    before_png=Image.open(BEFORE/'HybridGuard_overview_candidate.png').convert('RGB')
    after_png=Image.open(HERE/'HybridGuard_overview_candidate.png').convert('RGB')
    assert before_png.size==after_png.size==(3600,1460)
    difference=ImageChops.difference(before_png,after_png)
    mask=difference.convert('L').point(lambda x:255 if x else 0)
    allowed=Image.new('L',before_png.size,0)
    for box in [(846,353,866,380),(846,560,866,588),(1267,138,1786,144)]:
        ImageDraw.Draw(allowed).rectangle(tuple(v*2 for v in box),fill=255)
    outside=ImageChops.subtract(mask,allowed).getbbox()
    extra={
        'only_two_visible_changes':invariant,
        'removed_timezone_separator_count':removed,
        'unchanged_remainder_includes_text_positions_icons_paths_boundaries_and_55_copy_entries':invariant,
        'actual_input_direction_checks':direction,
        'baseline_separator_overlap_reproduced':any(v['group']=='timezone-example' and v['text']=='Normal system change' for v in chrome['baseline_auxiliary_text_intersections']),
        'visible_strokes_clear_of_unrelated_text':not chrome['visible_geometry']['text_intersections'],
        'no_new_close_contacts':not chrome['visible_geometry']['new_close_contacts'],
        'canvas_and_layout_preserved':template['svg_size_mm']==[180,73],
        'float_fraction_unchanged':math.isclose(template['float_fraction_of_textheight'],old_template['float_fraction_of_textheight'],abs_tol=1e-7),
        'template_figure_and_caption_source_identical':(HERE/'template_preview/figures/overview_figure.tex').read_bytes()==(BEFORE/'template_preview/figures/overview_figure.tex').read_bytes(),
        'template_included_pdf_in_sync':(HERE/'template_preview/figures/HybridGuard_overview_candidate.pdf').read_bytes()==(HERE/'HybridGuard_overview_candidate.pdf').read_bytes(),
        'png_pixels_changed_only_in_two_arrow_regions_and_deleted_line':outside is None and mask.getbbox() is not None,
        'png_matches_current_chrome_render':ImageChops.difference(after_png,Image.open(HERE/'previews/chrome_full_2x.png').convert('RGB')).getbbox() is None,
        'changed_png_pixels':sum(mask.histogram()[1:]),
        'arrow_head_nominal_width_mm_at_textwidth':10*template['textwidth_mm']/1800,
    }
    report['minimal_correction']=extra
    report['pass']=report['pass'] and all(extra[k] for k in ['only_two_visible_changes','baseline_separator_overlap_reproduced','visible_strokes_clear_of_unrelated_text','no_new_close_contacts','canvas_and_layout_preserved','float_fraction_unchanged','template_figure_and_caption_source_identical','template_included_pdf_in_sync','png_pixels_changed_only_in_two_arrow_regions_and_deleted_line','png_matches_current_chrome_render'])
    shared.save('DIRECTION_FIX_CHECK.json',report)
    print(json.dumps({'minimal_correction_pass':report['pass'],'float_fraction':template['float_fraction_of_textheight'],'body_font_pdf_pt':template['body_28_29_actual_font_sizes_pdf_pt'],'visible_changes':additions+[('timezone-example','removed separator')]},ensure_ascii=False))
    assert report['pass']


if __name__=='__main__':
    main()
