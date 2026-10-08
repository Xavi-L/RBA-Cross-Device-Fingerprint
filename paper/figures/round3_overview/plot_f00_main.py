#!/usr/bin/env python3
"""Render the F00 layout variant. Reads only layout and existing evidence mapping."""
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OWNER = 'rba-f00-main-layout-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'rba-round3-mpl'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    from matplotlib.text import Text
    source = json.loads((HERE / 'F00_main_source.json').read_text())
    target = HERE / 'F00_main_MANIFEST.json'
    previous = json.loads(target.read_text()) if target.exists() else None
    owned = ['figures/F00_main.svg', 'figures/F00_main.png', 'data/F00_main_nodes.csv', 'data/F00_main_edges.csv']
    if previous and previous['owner'] != OWNER:
        raise ValueError('Unknown owner')
    if not previous and any((HERE / p).exists() for p in owned):
        raise ValueError('Refusing to overwrite an unowned F00_main output')
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':8, 'svg.fonttype':'none', 'svg.hashsalt':OWNER})
    w, h = source['size_mm']
    fig = plt.figure(figsize=(w/25.4, h/25.4), facecolor='white')
    ax = fig.add_axes([0,0,1,1]); ax.set(xlim=(0,w), ylim=(h,0)); ax.axis('off')
    ax.text(5,5,source['title'],fontsize=10,weight='bold',va='center')
    for e in source['edges']:
        kind = e['kind']; model = kind == 'model'; constraint = kind.startswith('constraint')
        color = '#a46725' if model else '#879197' if constraint else '#325c75'
        style = '-.' if model else ':' if constraint else '-'
        points = e['points']
        for a,b in zip(points[:-2],points[1:-1]):
            ax.plot([a[0],b[0]],[a[1],b[1]],lw=.85,color=color,ls=style,zorder=1)
        ax.add_patch(FancyArrowPatch(points[-2],points[-1],arrowstyle='-|>',mutation_scale=7,
            color=color,lw=.85,linestyle=style,shrinkA=0,shrinkB=0,zorder=1))
    for x,y in source['junctions']:
        ax.plot(x,y,'o',ms=2,color='#325c75' if x>80 else '#879197',zorder=2)
    for n in source['nodes']:
        x,y,nw,nh=n['box']; kind=n['kind']
        fill={'accepted':'#edf4f8','current':'#f3f7f9','constraint':'#f7f7f5'}.get(kind,'white')
        ax.add_patch(FancyBboxPatch((x,y),nw,nh,boxstyle='round,pad=0,rounding_size=1',
            facecolor=fill,edgecolor='#597483',lw=.8,ls='--' if kind=='diagnostic' else '-',zorder=3))
        ax.text(x+nw/2,y+nh/2,n['label'],ha='center',va='center',fontsize=8,linespacing=1.3,zorder=4)
    for label in source['labels']:
        ax.text(label['x'],label['y'],label['text'],ha=label.get('align','left'),va='center',
            fontsize=label.get('size',8),weight='bold' if label.get('bold') else 'normal',zorder=5)
    fig.canvas.draw(); renderer=fig.canvas.get_renderer(); outside=[]
    for t in fig.findobj(match=Text):
        if not t.get_visible() or not t.get_text(): continue
        b=t.get_window_extent(renderer)
        if b.x0<0 or b.y0<0 or b.x1>fig.bbox.width or b.y1>fig.bbox.height:outside.append(t.get_text())
    if outside:raise ValueError(('Canvas overflow',outside))
    with tempfile.TemporaryDirectory(prefix='rba-f00-main-') as tmp:
        stage=Path(tmp); (stage/'figures').mkdir(); (stage/'data').mkdir()
        fig.savefig(stage/owned[0],metadata={'Date':None});fig.savefig(stage/owned[1],dpi=300,metadata={'Software':OWNER})
        for name, rows in [('nodes',source['nodes']),('edges',source['edges']+source['caption_dependencies'])]:
            fields=list(dict.fromkeys(k for row in rows for k in row))
            with (stage/'data'/('F00_main_'+name+'.csv')).open('w',newline='') as fh:
                writer=csv.DictWriter(fh,fields);writer.writeheader()
                writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in rows)
        for p in owned:(stage/p).replace(HERE/p)
    qa=Path(os.environ.get('RBA_ROUND3_QA_DIR',str(Path(tempfile.gettempdir())/'rba_review_qa')))
    qa.mkdir(parents=True,exist_ok=True); fig.savefig(qa/'F00_main_96dpi.png',dpi=96); plt.close(fig)
    files={p:sha(HERE/p) for p in owned}
    visual=previous.get('visual_review',{}) if previous and previous['files']==files else {'png':'PENDING','svg':'NOT_EVALUATED'}
    manifest=dict(owner=OWNER,material_class='F00',variant='正文候选',size_mm=source['size_mm'],minimum_font_pt=8,dpi=300,
        main_boxes=8,diagnostic_notes=1,source='F00_main_source.json',source_sha256=sha(HERE/'F00_main_source.json'),
        files=files,text_canvas_bounds='PASS',visual_review=visual,
        operations=dict(collection=0,fit=0,selection=0,prediction=0,retiming=0))
    target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'variant':'F00_main','size_mm':source['size_mm'],'visual':visual},ensure_ascii=False))


if __name__ == '__main__':main()
