// Only renders this candidate; actual platform fonts are inspected through CDP.
const fs=require('fs'),path=require('path'),os=require('os');
const deps=process.env.RBA_NODE_MODULES||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(path.join(deps,'playwright'));
const HERE=__dirname;
async function main(){
 const layout=JSON.parse(fs.readFileSync(path.join(HERE,'layout_rev2.json'))),[W,H]=layout.viewbox;
 const browser=await chromium.launch({executablePath:process.env.RBA_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:W,height:H},deviceScaleFactor:300/254});
  const svg=fs.readFileSync(path.join(HERE,'F01_main_rev2.svg'),'utf8');
  await page.setContent(`<style>html,body{margin:0;padding:0;background:white}svg{width:${W}px;height:${H}px;display:block}</style>${svg}`);
  await page.evaluate(()=>document.fonts.ready);
  const report=await page.evaluate(({W,H})=>{
   const texts=[...document.querySelectorAll('svg text')].map(t=>{
    const b=t.getBoundingClientRect();return {text:t.textContent,role:t.dataset.role,cell:t.dataset.cell,
      method:t.dataset.method,config:t.dataset.config,x:b.x,y:b.y,w:b.width,h:b.height,
      size:parseFloat(getComputedStyle(t).fontSize)};
   });
   const overlaps=[];
   for(let i=0;i<texts.length;i++)for(let j=i+1;j<texts.length;j++){
    const a=texts[i],b=texts[j];
    if(a.x<b.x+b.w&&b.x<a.x+a.w&&a.y<b.y+b.h&&b.y<a.y+a.h)overlaps.push([a.text,b.text]);
   }
   // Font metric boxes may touch adjacent row slots; visible ink has measured padding.
   const cell_bounds_errors=[],cell_clearances=[];
   for(const t of texts.filter(t=>t.role==='count')){
    const r=document.querySelector(`rect[data-cell="${t.cell}"]`).getBoundingClientRect();
    const gaps=[t.x-r.x,r.right-t.x-t.w,t.y-r.y,r.bottom-t.y-t.h];
    cell_clearances.push(Math.min(...gaps));
    if(gaps.some(g=>g < -0.01))cell_bounds_errors.push({cell:t.cell,gaps});
   }
   return {texts,text_overlaps:overlaps,cell_bounds_errors,minimum_cell_text_clearance_units:Math.min(...cell_clearances),
    out_of_canvas:texts.filter(t=>t.x<0||t.y<0||t.x+t.w>W||t.y+t.h>H),
    raster_images:document.querySelectorAll('svg image').length,
    text_compression:document.querySelectorAll('text[textLength],text[lengthAdjust]').length,
    external_resources:[...document.querySelectorAll('[href],[src]')].map(t=>t.getAttribute('href')||t.getAttribute('src')),
    minimum_font_units:Math.min(...texts.map(t=>t.size))};
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
  await page.screenshot({path:path.join(HERE,'F01_main_rev2.png'),scale:'device'});
  const [wm,hm]=layout.size_mm;
  await page.addStyleTag({content:`@page{size:${wm}mm ${hm}mm;margin:0}html,body{width:${wm}mm;height:${hm}mm;margin:0}svg{width:${wm}mm;height:${hm}mm;display:block}`});
  await page.pdf({path:path.join(HERE,'F01_main_rev2.pdf'),preferCSSPageSize:true,printBackground:true,
                 margin:{top:0,bottom:0,left:0,right:0},scale:1});
  report.pass=!report.text_overlaps.length&&!report.cell_bounds_errors.length&&!report.out_of_canvas.length
    &&!report.raster_images&&!report.text_compression&&!report.external_resources.length&&!report.font_fallback_errors.length;
  const check=JSON.parse(fs.readFileSync(path.join(HERE,'CHECK.json')));
  check.svg_and_browser=report;
  fs.writeFileSync(path.join(HERE,'CHECK.json'),JSON.stringify(check,null,2)+'\n');
  console.log(JSON.stringify({browser_pass:report.pass,texts:report.texts.length,fonts:report.platform_font_names,
   overlaps:report.text_overlaps,cell_errors:report.cell_bounds_errors,clearance:report.minimum_cell_text_clearance_units}));
  if(!report.pass)process.exitCode=1;
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1});
