// Render only this SVG. Verify actual platform fonts and geometry with Chromium.
const fs=require('fs'),path=require('path'),os=require('os');
const deps=process.env.RBA_NODE_MODULES||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(path.join(deps,'playwright'));
const HERE=__dirname;
async function main(){
 const layout=JSON.parse(fs.readFileSync(path.join(HERE,'layout.json'))),[W,H]=layout.viewbox;
 const browser=await chromium.launch({executablePath:process.env.RBA_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:W,height:H},deviceScaleFactor:300/254});
  const svg=fs.readFileSync(path.join(HERE,'F05a_main.svg'),'utf8');
  await page.setContent(`<style>html,body{margin:0;padding:0;background:white}svg{width:${W}px;height:${H}px;display:block}</style>${svg}`);
  await page.evaluate(()=>document.fonts.ready);
  const report=await page.evaluate(({W,H})=>{
   const box=t=>{const b=t.getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height}};
   const texts=[...document.querySelectorAll('svg text')].map(t=>({text:t.textContent,role:t.dataset.role,
     point:t.dataset.point,method:t.dataset.method,family:t.dataset.family,
     ...box(t),size:parseFloat(getComputedStyle(t).fontSize)}));
   const markers=[...document.querySelectorAll('[data-role="data-marker"]')].map(t=>({
     point:t.dataset.point,shape:t.tagName,...box(t)}));
   const intersect=(a,b)=>a.x<b.x+b.w-.01&&b.x<a.x+a.w-.01&&a.y<b.y+b.h-.01&&b.y<a.y+a.h-.01;
   const overlaps=[];
   for(let i=0;i<texts.length;i++)for(let j=i+1;j<texts.length;j++){
    if(intersect(texts[i],texts[j]))overlaps.push([texts[i],texts[j]]);
   }
   const markerOverlaps=[];
   for(let i=0;i<markers.length;i++)for(let j=i+1;j<markers.length;j++){
    if(intersect(markers[i],markers[j]))markerOverlaps.push([markers[i].point,markers[j].point]);
   }
   const labelMarkerOverlaps=[];
   for(const t of texts)for(const m of markers)if(intersect(t,m))labelMarkerOverlaps.push([t.text,m.point]);
   const out=[...texts,...markers].filter(t=>t.x<0||t.y<0||t.x+t.w>W||t.y+t.h>H);
   return {texts,markers,text_overlaps:overlaps,marker_overlaps:markerOverlaps,label_marker_overlaps:labelMarkerOverlaps,
    out_of_canvas:out,minimum_font_units:Math.min(...texts.map(t=>t.size)),
    raster_images:document.querySelectorAll('svg image').length,
    text_compression:document.querySelectorAll('text[textLength],text[lengthAdjust]').length,
    external_resources:[...document.querySelectorAll('[href],[src]')].map(t=>t.getAttribute('href')||t.getAttribute('src'))};
  },{W,H});
  const cdp=await page.context().newCDPSession(page);
  await cdp.send('DOM.enable');await cdp.send('CSS.enable');
  const dom=await cdp.send('DOM.getDocument');
  const nodes=await cdp.send('DOM.querySelectorAll',{nodeId:dom.root.nodeId,selector:'svg text'});
  report.platform_fonts_by_text=[];
  for(let i=0;i<nodes.nodeIds.length;i++){
   const {fonts}=await cdp.send('CSS.getPlatformFontsForNode',{nodeId:nodes.nodeIds[i]});
   report.platform_fonts_by_text.push({text:report.texts[i].text,role:report.texts[i].role,fonts:fonts.filter(f=>f.glyphCount>0)});
  }
  report.font_fallback_errors=report.platform_fonts_by_text.filter(r=>!r.fonts.length||r.fonts.some(f=>f.familyName!=='Times New Roman'));
  report.platform_font_names=[...new Set(report.platform_fonts_by_text.flatMap(r=>r.fonts.map(f=>f.postScriptName)))];
  await page.screenshot({path:path.join(HERE,'F05a_main.png'),scale:'device'});
  const [wm,hm]=layout.size_mm;
  await page.addStyleTag({content:`@page{size:${wm}mm ${hm}mm;margin:0}html,body{width:${wm}mm;height:${hm}mm;margin:0}svg{width:${wm}mm;height:${hm}mm;display:block}`});
  await page.pdf({path:path.join(HERE,'F05a_main.pdf'),preferCSSPageSize:true,printBackground:true,
                 margin:{top:0,bottom:0,left:0,right:0},scale:1});
  report.pass=!report.text_overlaps.length&&!report.marker_overlaps.length&&!report.label_marker_overlaps.length
    &&!report.out_of_canvas.length&&!report.raster_images&&!report.text_compression
    &&!report.external_resources.length&&!report.font_fallback_errors.length&&report.markers.length===8;
  const check=JSON.parse(fs.readFileSync(path.join(HERE,'CHECK.json')));
  check.svg_and_browser=report;
  fs.writeFileSync(path.join(HERE,'CHECK.json'),JSON.stringify(check,null,2)+'\n');
  console.log(JSON.stringify({browser_pass:report.pass,texts:report.texts.length,data_markers:report.markers.length,
   fonts:report.platform_font_names,text_overlaps:report.text_overlaps,
   label_marker_overlaps:report.label_marker_overlaps,out_of_canvas:report.out_of_canvas}));
  if(!report.pass)process.exitCode=1;
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1});
