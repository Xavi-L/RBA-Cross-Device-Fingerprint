// Independent Chrome render + focused visual/semantic regression for this figure.
const fs=require('fs'),path=require('path'),os=require('os'),cp=require('child_process');
const deps=process.env.RBA_NODE_MODULES||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(path.join(deps,'playwright'));
const HERE=__dirname,ROOT=path.resolve(HERE,'../../../..');
async function main(){
 const browser=await chromium.launch({executablePath:process.env.RBA_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1800,height:1330},deviceScaleFactor:1});
  const source=fs.readFileSync(path.join(HERE,'HybridGuard_overview_candidate.svg'),'utf8');
  await page.setContent(`<html><head><title>HybridGuard overview - full visual candidate</title><style>html,body{margin:0;padding:0}svg{width:1800px;height:1330px;display:block}</style></head><body>${source}</body></html>`);
  await page.evaluate(()=>document.fonts.ready);
  const report=await page.evaluate(()=>{
   const entries=[...document.querySelectorAll('[data-copy]')].map(t=>{const b=t.getBoundingClientRect();return {id:t.id,text:t.textContent,x:b.x,y:b.y,w:b.width,h:b.height,size:parseFloat(getComputedStyle(t).fontSize)}});
   const overlap=[];
   for(let i=0;i<entries.length;i++)for(let j=i+1;j<entries.length;j++){
    const a=entries[i],b=entries[j];
    if(a.x<b.x+b.w&&b.x<a.x+a.w&&a.y<b.y+b.h&&b.y<a.y+a.h)overlap.push([a.text,b.text]);
   }
   const graph=[...document.querySelectorAll('g[data-source]')].map(g=>{
    const p=g.querySelector('path'); return {id:g.id,kind:g.dataset.kind,source:g.dataset.source,target:g.dataset.target,status:g.dataset.status||null,
     color:p.getAttribute('stroke'),dash:p.getAttribute('stroke-dasharray'),start:p.getAttribute('marker-start'),end:p.getAttribute('marker-end')};
   });
   const lineText=[];
   for(const g of document.querySelectorAll('g[data-source]')){
    const p=g.querySelector('path'),length=p.getTotalLength();
    for(const t of entries){for(let i=0;i<=Math.ceil(length);i++){
      const q=p.getPointAtLength(Math.min(i,length));
      if(q.x>t.x&&q.x<t.x+t.w&&q.y>t.y&&q.y<t.y+t.h){lineText.push([g.id,t.text]);break;}
    }}
   }
   const bounds=id=>document.getElementById(id).dataset.bounds.split(',').map(Number);
   const within=(a,b)=>a[0]>=b[0]&&a[1]>=b[1]&&a[0]+a[2]<=b[0]+b[2]&&a[1]+a[3]<=b[1]+b[3];
   const scopes={three_nodes_inside_app:['native','webview-host','app-web'].every(id=>within(bounds(id),bounds('app-observations'))),
    app_inside_device:within(bounds('app-observations'),bounds('device-observations')),
    browser_inside_device:within(bounds('browser'),bounds('device-observations')),
    browser_outside_app:!within(bounds('browser'),bounds('app-observations')),
    offline_outside_device:bounds('offline-development')[0]>bounds('device-observations')[0]+bounds('device-observations')[2],
    example_outside_device:bounds('timezone-example')[0]>bounds('device-observations')[0]+bounds('device-observations')[2]};
   const nodeOverflow=[];
   for(const g of document.querySelectorAll('[data-kind="observation"]')){
    const b=bounds(g.id);
    for(const t of g.querySelectorAll('[data-copy]')){
     const r=t.getBoundingClientRect();
     if(!within([r.x,r.y,r.width,r.height],b))nodeOverflow.push([g.id,t.textContent]);
    }
   }
   const ids=[...document.querySelectorAll('[id]')].map(n=>n.id);
   const duplicateIds=ids.filter((n,i)=>ids.indexOf(n)!==i);
   const missing=[];for(const n of document.querySelectorAll('[marker-start],[marker-end]'))for(const a of ['marker-start','marker-end']){
    const m=(n.getAttribute(a)||'').match(/^url\(#(.+)\)$/);if(m&&!document.getElementById(m[1]))missing.push(m[1]);
   }
   const right=document.querySelector('[data-kind="inside-app-scope"]').dataset.bounds.split(',').map(Number);
   const gapFor=s=>{const t=entries.find(t=>t.text===s);return right[0]+right[2]-(t.x+t.w);};
   const geom=entries.find(t=>t.text==='Not in current detector');
   const lowerHeads=entries.filter(t=>['App container','Embedded webpage'].includes(t.text));
   return {texts:entries,text_overlaps:overlap,flow_or_relation_text_intersections:lineText,
    out_of_canvas:entries.filter(t=>t.x<0||t.y<0||t.x+t.w>1800||t.y+t.h>1330),
    scopes,graph,node_text_overflow:nodeOverflow,duplicate_ids:duplicateIds,missing_marker_references:missing,
    embedded_rasters:document.querySelectorAll('svg image').length,nested_svgs:document.querySelectorAll('svg svg').length,
    text_compression:document.querySelectorAll('text[textLength],text[lengthAdjust]').length,
    effects:document.querySelectorAll('filter,linearGradient,radialGradient').length,
    right_margins_units:{system_web:gapFor('System–web consistency'),app_web:gapFor('Embedded webpage')},
    geometry_label_clearance_above_node_titles:Math.min(...lowerHeads.map(t=>t.y))-(geom.y+geom.h),
    min_body_font_units:Math.min(...entries.map(t=>t.size)),times_new_roman_available:document.fonts.check('29px "Times New Roman"')};
  });
  await page.screenshot({path:path.join(HERE,'previews/chrome_full.png')});
  const manifest=JSON.parse(fs.readFileSync(path.join(HERE,'CONTENT_MANIFEST.json')));
  const sorted=x=>[...x].sort();
  report.exact_visible_copy_preserved=JSON.stringify(sorted(manifest.expected))===JSON.stringify(sorted(report.texts.map(t=>t.text)));
  const g=report.graph;
  report.semantic_regression={
   four_relations:g.filter(e=>e.kind==='relation').length===4,
   context_without_arrows:g.filter(e=>e.status==='context').every(e=>e.start===null&&e.end===null),
   geometry_still_unintegrated:g.find(e=>e.id==='host-app-web').status==='studied'&&report.texts.some(t=>t.text==='Not in current detector'),
   independent_development_inputs:g.filter(e=>e.kind==='development-input').length===2&&g.filter(e=>e.kind==='development-input').every(e=>e.target==='rule-selection'),
   no_current_data_into_offline:g.filter(e=>e.kind==='current-input').every(e=>['app-only-interface','linked-pair','paired-interface'].includes(e.target)),
   one_model_load:g.filter(e=>e.kind==='model-input').length===1,
   one_shared_output:g.filter(e=>e.kind==='decision-output').length===1,
   modes_have_no_interconnection:!g.some(e=>['app-only-interface','paired-interface'].includes(e.source)),
   note_and_evaluation_have_no_arrows:!g.some(e=>['timezone-example','research-evaluation'].includes(e.source)||['timezone-example','research-evaluation'].includes(e.target))};
  report.formal_files_unchanged=Object.fromEntries(['HybridGuard_overview_triangle.svg','HybridGuard_overview_triangle.png','build_overview.py','COPY.md','README.md'].map(n=>[n,fs.readFileSync(path.join(HERE,'baseline',n)).equals(fs.readFileSync(path.join(HERE,'..',n)))]));
  report.pilot_status_unchanged=cp.execFileSync('git',['status','--porcelain=v1','--','paper/figures/overview_triangle/style_pilot_v1'],{cwd:ROOT,encoding:'utf8'}).trim()==='';
  report.automated_checks_pass=report.exact_visible_copy_preserved&&!report.text_overlaps.length&&!report.flow_or_relation_text_intersections.length&&!report.out_of_canvas.length&&
   !report.node_text_overflow.length&&!report.duplicate_ids.length&&!report.missing_marker_references.length&&!report.embedded_rasters&&!report.nested_svgs&&!report.text_compression&&!report.effects&&
   report.min_body_font_units>=28&&Object.values(report.scopes).every(Boolean)&&Object.values(report.semantic_regression).every(Boolean)&&Object.values(report.formal_files_unchanged).every(Boolean)&&report.pilot_status_unchanged;
  report.pdf={file:'HybridGuard_overview_candidate.pdf',requested_size_mm:[180,133],renderer:'Chrome headless print',paper_template_modified:false};
  // CSS page size keeps the 180 mm figure width; vector text is not a screenshot.
  await page.addStyleTag({content:'@page{size:180mm 133mm;margin:0}html,body{width:180mm;height:133mm;margin:0}svg{width:180mm;height:133mm;display:block}'});
  await page.pdf({path:path.join(HERE,'HybridGuard_overview_candidate.pdf'),preferCSSPageSize:true,printBackground:true,margin:{top:0,bottom:0,left:0,right:0},scale:1});
  fs.writeFileSync(path.join(HERE,'CHECK.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({...report,texts:report.texts.length},null,2));
  if(!report.automated_checks_pass)process.exitCode=1;
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1});
