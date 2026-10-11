// Independent Chrome render + focused visual/semantic regression for this figure.
const fs=require('fs'),path=require('path'),os=require('os'),cp=require('child_process');
const deps=process.env.RBA_NODE_MODULES||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(path.join(deps,'playwright'));
const HERE=__dirname,ROOT=path.resolve(HERE,'../../../..');
const layout=JSON.parse(fs.readFileSync(path.join(HERE,'layout.json'),'utf8'));
const [W,H]=layout.viewbox,[widthMM,heightMM]=layout.size_mm;
function auditVisibleGeometry(){
 const texts=[...document.querySelectorAll('[data-copy]')].map(t=>({node:t,text:t.textContent,b:t.getBoundingClientRect()}));
 const distance=(q,b)=>Math.hypot(Math.max(b.left-q.x,0,q.x-b.right),Math.max(b.top-q.y,0,q.y-b.bottom));
 const titleSlots={'device-observations':'One device, multiple observation points','app-observations':'Inside the app','offline-development':'Offline'};
 const paths=[],violations=[],near=[],exemptions=[],arrows=[];
 for(const p of document.querySelectorAll('svg path,svg line,svg polyline,svg polygon,svg rect')){
  if(p.closest('defs,[data-icon]'))continue;
  const style=getComputedStyle(p);
  if(style.stroke==='none'||+style.opacity===0||+style.strokeOpacity===0)continue;
  const parent=p.parentElement,flow=p.closest('[data-source]'),group=parent.id||parent.getAttribute('data-kind')||p.tagName;
  const role=p.hasAttribute('data-direction-arrow')?'direction-arrow':flow?flow.dataset.kind:titleSlots[group]||group==='current-detection'?'scope-boundary':'auxiliary';
  const n=p.getTotalLength(),ctm=p.getCTM(),points=[];
  for(let i=0;i<=Math.ceil(n);i++)points.push(p.getPointAtLength(Math.min(i,n)).matrixTransform(ctm));
  let closest={clearance_units:Infinity};
  for(const t of texts){
   const gap=Math.min(...points.map(q=>distance(q,t.b)))-parseFloat(style.strokeWidth)/2;
   if(titleSlots[group]===t.text){exemptions.push({group,text:t.text,reason:'intentional title slot in scope outline'});continue;}
   if(gap<closest.clearance_units)closest={text:t.text,clearance_units:gap};
   const hit={group,role,d:p.getAttribute('d'),text:t.text,clearance_units:gap};
   const target=flow&&document.getElementById(flow.dataset.target),targetRect=target?.querySelector(':scope > rect');
   const last=points[points.length-1];
   if(gap===0&&targetRect&&target.contains(t.node)&&last.y===+targetRect.getAttribute('y')&&last.x>=+targetRect.getAttribute('x')&&last.x<=+targetRect.getAttribute('x')+ +targetRect.getAttribute('width')){
    exemptions.push({...hit,reason:'intentional entry at target top boundary; stroke only tangent to conservative font box, with no centerline penetration'});continue;
   }
   if(gap<=0)violations.push(hit);else if(gap<2)near.push(hit);
  }
  paths.push({group,role,d:p.getAttribute('d'),nearest_text:closest});
  if(p.hasAttribute('data-direction-arrow')){
   const end=p.getPointAtLength(n),prev=p.getPointAtLength(Math.max(0,n-1)),angle=Math.atan2(end.y-prev.y,end.x-prev.x);
   const ref=(p.getAttribute('marker-end')||'').match(/^url\(#(.+)\)$/),marker=ref&&document.getElementById(ref[1]);
   const glyph=marker&&marker.querySelector('path'),refX=+marker.getAttribute('refX'),refY=+marker.getAttribute('refY');
   const glyphPoints=[];
   if(glyph)for(let i=0;i<=Math.ceil(glyph.getTotalLength());i++){
    const q=glyph.getPointAtLength(Math.min(i,glyph.getTotalLength())),x=q.x-refX,y=q.y-refY;
    glyphPoints.push(new DOMPoint(end.x+x*Math.cos(angle)-y*Math.sin(angle),end.y+x*Math.sin(angle)+y*Math.cos(angle)).matrixTransform(ctm));
   }
   const b={left:Math.min(...glyphPoints.map(q=>q.x)),right:Math.max(...glyphPoints.map(q=>q.x)),top:Math.min(...glyphPoints.map(q=>q.y)),bottom:Math.max(...glyphPoints.map(q=>q.y))};
   const glyphHits=texts.filter(t=>t.b.left<b.right&&t.b.right>b.left&&t.b.top<b.bottom&&t.b.bottom>b.top).map(t=>t.text);
   arrows.push({group,segment:p.getAttribute('d'),marker:ref?.[1],marker_shape:glyph?.getAttribute('d'),marker_units:marker?.getAttribute('markerUnits'),orientation:marker?.getAttribute('orient'),unit_direction:[Math.cos(angle),Math.sin(angle)],endpoint:{x:end.x,y:end.y},rendered_head_bbox_units:b,head_text_intersections:glyphHits,fill:glyph&&getComputedStyle(glyph).fill,visible:!!glyph&&style.visibility!=='hidden'&&getComputedStyle(glyph).fill!=='none'});
  }
 }
 return {audited_strokes:paths,text_intersections:violations,text_clearance_below_2_units:near,semantic_exemptions:exemptions,excluded:'icon-internal geometry, marker definitions and fill-only backgrounds; intentional title slots and boundary contacts are listed separately',direction_arrows:arrows};
}
async function main(){
 const browser=await chromium.launch({executablePath:process.env.RBA_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:W,height:H},deviceScaleFactor:2});
  const source=fs.readFileSync(path.join(HERE,'HybridGuard_overview_candidate.svg'),'utf8');
  await page.setContent(`<html><head><title>HybridGuard overview - full visual candidate</title><style>html,body{margin:0;padding:0}svg{width:${W}px;height:${H}px;display:block}</style></head><body>${source}</body></html>`);
  await page.evaluate(()=>document.fonts.ready);
  const report=await page.evaluate(({W,H})=>{
   const entries=[...document.querySelectorAll('[data-copy]')].map(t=>{const b=t.getBoundingClientRect();return {id:t.id,text:t.textContent,x:b.x,y:b.y,w:b.width,h:b.height,size:parseFloat(getComputedStyle(t).fontSize)}});
   const overlap=[];
   for(let i=0;i<entries.length;i++)for(let j=i+1;j<entries.length;j++){
    const a=entries[i],b=entries[j];
    if(a.x<b.x+b.w&&b.x<a.x+a.w&&a.y<b.y+b.h&&b.y<a.y+a.h)overlap.push([a.text,b.text]);
   }
   const graph=[...document.querySelectorAll('g[data-source]')].map(g=>{
    const p=g.querySelector('path'),xy=q=>({x:q.x,y:q.y}); return {id:g.id,kind:g.dataset.kind,source:g.dataset.source,target:g.dataset.target,status:g.dataset.status||null,
     d:p.getAttribute('d'),length:p.getTotalLength(),
     first:xy(p.getPointAtLength(0)),last:xy(p.getPointAtLength(p.getTotalLength())),
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
   return {texts:entries,text_overlaps:overlap,flow_or_relation_text_intersections:lineText,
    out_of_canvas:entries.filter(t=>t.x<0||t.y<0||t.x+t.w>W||t.y+t.h>H),
    scopes,graph,node_text_overflow:nodeOverflow,duplicate_ids:duplicateIds,missing_marker_references:missing,
    embedded_rasters:document.querySelectorAll('svg image').length,nested_svgs:document.querySelectorAll('svg svg').length,
    text_compression:document.querySelectorAll('text[textLength],text[lengthAdjust]').length,
    effects:document.querySelectorAll('filter,linearGradient,radialGradient').length,
    external_resources:[...document.querySelectorAll('[href],[src],[xlink\\:href]')].map(e=>e.getAttribute('href')||e.getAttribute('src')||e.getAttribute('xlink:href')).filter(v=>v&&!v.startsWith('#')),
    right_margins_units:{system_web:gapFor('System–web consistency'),app_web:gapFor('Embedded webpage')},
    min_body_font_units:Math.min(...entries.map(t=>t.size)),times_new_roman_available:document.fonts.check('29px "Times New Roman"')};
  },{W,H});
  report.visible_geometry=await page.evaluate(auditVisibleGeometry);
  const before=await browser.newPage({viewport:{width:W,height:H}});
  await before.setContent(`<style>html,body{margin:0}svg{width:${W}px;height:${H}px}</style>${fs.readFileSync(path.join(HERE,'direction_fix_baseline_393f0faa/HybridGuard_overview_candidate.svg'),'utf8')}`);
  await before.evaluate(()=>document.fonts.ready);
  const oldGeometry=await before.evaluate(auditVisibleGeometry);
  report.baseline_auxiliary_text_intersections=oldGeometry.text_intersections.filter(v=>v.role==='auxiliary');
  const contactKey=v=>JSON.stringify([v.group,v.d,v.text,v.clearance_units]);
  report.visible_geometry.new_close_contacts=report.visible_geometry.text_clearance_below_2_units.filter(v=>!oldGeometry.text_clearance_below_2_units.some(old=>contactKey(old)===contactKey(v)));
  await before.close();
  // Inspect actual platform fonts, not only CSS font-family or fonts.check.
  const cdp=await page.context().newCDPSession(page);
  await cdp.send('DOM.enable');await cdp.send('CSS.enable');
  const dom=await cdp.send('DOM.getDocument');
  const textNodes=await cdp.send('DOM.querySelectorAll',{nodeId:dom.root.nodeId,selector:'svg text'});
  report.actual_platform_fonts=[];
  for(const nodeId of textNodes.nodeIds){
   const fonts=await cdp.send('CSS.getPlatformFontsForNode',{nodeId});
   report.actual_platform_fonts.push(...fonts.fonts.filter(f=>f.glyphCount>0));
  }
  report.platform_font_names=[...new Set(report.actual_platform_fonts.map(f=>f.postScriptName))];
  report.no_platform_font_fallback=report.actual_platform_fonts.length>0&&report.actual_platform_fonts.every(f=>f.familyName==='Times New Roman');
  await page.screenshot({path:path.join(HERE,'previews/chrome_full.png'),scale:'css'});
  await page.screenshot({path:path.join(HERE,'previews/chrome_full_2x.png'),scale:'device'});
  const manifest=JSON.parse(fs.readFileSync(path.join(HERE,'CONTENT_MANIFEST.json')));
  const sorted=x=>[...x].sort();
  report.exact_visible_copy_preserved=JSON.stringify(sorted(manifest.expected))===JSON.stringify(sorted(report.texts.map(t=>t.text)));
  const g=report.graph;
  report.semantic_regression={
   four_relations:g.filter(e=>e.kind==='relation').length===4,
   context_without_arrows:g.filter(e=>e.status==='context').every(e=>e.start===null&&e.end===null),
   geometry_still_unintegrated:g.find(e=>e.id==='host-app-web').status==='studied'&&report.texts.some(t=>t.text==='Not in current detector'),
   independent_development_inputs:g.filter(e=>e.kind==='development-input').length===2&&g.filter(e=>e.kind==='development-input').every(e=>e.target==='rule-selection'),
   no_current_data_into_offline:g.filter(e=>e.kind==='current-input').every(e=>['app-branch','app-only-interface','linked-pair','paired-interface'].includes(e.target)),
   one_model_load:g.filter(e=>e.kind==='model-input').length===1,
   one_shared_output:g.filter(e=>e.kind==='decision-output').length===1,
   modes_have_no_interconnection:!g.some(e=>['app-only-interface','paired-interface'].includes(e.source)),
   note_and_evaluation_have_no_arrows:!g.some(e=>['timezone-example','research-evaluation'].includes(e.source)||['timezone-example','research-evaluation'].includes(e.target))};
  report.formal_files_unchanged=Object.fromEntries(['HybridGuard_overview_triangle.svg','HybridGuard_overview_triangle.png','build_overview.py','COPY.md','README.md'].map(n=>[n,fs.readFileSync(path.join(HERE,'baseline',n)).equals(fs.readFileSync(path.join(HERE,'..',n)))]));
  report.pilot_status_unchanged=cp.execFileSync('git',['status','--porcelain=v1','--','paper/figures/overview_triangle/style_pilot_v1'],{cwd:ROOT,encoding:'utf8'}).trim()==='';
  report.automated_checks_pass=report.exact_visible_copy_preserved&&!report.text_overlaps.length&&!report.flow_or_relation_text_intersections.length&&!report.out_of_canvas.length&&
   !report.node_text_overflow.length&&!report.duplicate_ids.length&&!report.missing_marker_references.length&&!report.embedded_rasters&&!report.nested_svgs&&!report.text_compression&&!report.effects&&
   report.min_body_font_units>=28&&Object.values(report.scopes).every(Boolean)&&Object.values(report.semantic_regression).every(Boolean)&&Object.values(report.formal_files_unchanged).every(Boolean)&&report.pilot_status_unchanged&&report.no_platform_font_fallback&&!report.external_resources.length;
  report.automated_checks_pass=report.automated_checks_pass&&!report.visible_geometry.text_intersections.length&&!report.visible_geometry.new_close_contacts.length&&report.visible_geometry.direction_arrows.length===2&&report.visible_geometry.direction_arrows.every(a=>a.visible&&!a.head_text_intersections.length);
  report.pdf={file:'HybridGuard_overview_candidate.pdf',requested_size_mm:[widthMM,heightMM],renderer:'Chrome headless print',paper_template_modified:false};
  // CSS page size keeps the 180 mm figure width; vector text is not a screenshot.
  await page.addStyleTag({content:`@page{size:${widthMM}mm ${heightMM}mm;margin:0}html,body{width:${widthMM}mm;height:${heightMM}mm;margin:0}svg{width:${widthMM}mm;height:${heightMM}mm;display:block}`});
  await page.pdf({path:path.join(HERE,'HybridGuard_overview_candidate.pdf'),preferCSSPageSize:true,printBackground:true,margin:{top:0,bottom:0,left:0,right:0},scale:1});
  fs.writeFileSync(path.join(HERE,'CHECK.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({...report,texts:report.texts.length,actual_platform_fonts:report.platform_font_names},null,2));
  if(!report.automated_checks_pass)process.exitCode=1;
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1});
