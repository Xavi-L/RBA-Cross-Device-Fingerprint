// Run render_pdf_and_check.cjs first. All current PNGs use the same verified
// Chrome fonts as the SVG view and vector PDF. Historical previews stay intact.
const fs=require('fs'),path=require('path'),os=require('os'),cp=require('child_process');
const deps=process.env.RBA_NODE_MODULES||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const sharp=require(path.join(deps,'sharp'));
const HERE=__dirname, OUT=path.join(HERE,'previews');
const {viewbox:[W,H],size_mm:[widthMM,heightMM]}=JSON.parse(fs.readFileSync(path.join(HERE,'layout.json')));
async function cropRaster(buffer,x,y,w,h,scale=1){
  return sharp(buffer).extract({left:x*2,top:y*2,width:w*2,height:h*2}).resize(Math.round(w*scale),Math.round(h*scale)).png().toBuffer();
}
function esc(s){return s.replaceAll('&','&amp;').replaceAll('<','&lt;');}
function plate(w,h,labels){return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><rect width="100%" height="100%" fill="white"/><g font-family="Arial,sans-serif" fill="#4a5058">${labels.map(l=>`<text x="24" y="${l.y}" font-size="${l.size||23}">${esc(l.text)}</text>`).join('')}</g></svg>`);}
async function localComparison(before,after,box,file){
  const width=Math.round(177.942341/25.4*96),k=width/W;
  const [x,y,w,h]=box.map(v=>Math.round(v*k));
  const crop=async input=>sharp(await sharp(input).resize(width).png().toBuffer()).extract({left:x,top:y,width:w,height:h}).png().toBuffer();
  const a=await crop(before),z=await crop(after);
  const labels=Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${2*w+42}" height="${h+42}"><rect width="100%" height="100%" fill="white"/><g font-family="Arial,sans-serif" font-size="13" fill="#444"><text x="10" y="19">Before 393f0faa</text><text x="${w+32}" y="19">After | same scale</text></g></svg>`);
  await sharp(labels).composite([{input:a,left:10,top:32},{input:z,left:w+32,top:32}]).withMetadata({density:96}).png().toFile(path.join(OUT,file));
}
async function main(){
  fs.mkdirSync(OUT,{recursive:true});
  const chrome=path.join(OUT,'chrome_full_2x.png');
  if(fs.statSync(chrome).mtimeMs<fs.statSync(path.join(HERE,'HybridGuard_overview_candidate.svg')).mtimeMs)throw Error('Run the Chrome renderer after the SVG builder.');
  const png=fs.readFileSync(chrome);
  await sharp(png).withMetadata({density:508}).png().toFile(path.join(HERE,'HybridGuard_overview_candidate.png'));
  const actual=await sharp(png).resize(Math.round(widthMM/25.4*96)).withMetadata({density:96}).png().toBuffer();
  fs.writeFileSync(path.join(OUT,'actual_180mm_96dpi.png'),actual);
  await sharp(png).resize(Math.round(177.942341/25.4*96)).withMetadata({density:96}).png().toFile(path.join(OUT,'actual_template_width_96dpi.png'));
  await sharp(png).resize(W).greyscale().png().toFile(path.join(OUT,'grayscale_full.png'));
  await sharp(actual).greyscale().withMetadata({density:96}).png().toFile(path.join(OUT,'grayscale_180mm_96dpi.png'));
  for(const [name,b,s] of [
    ['triangle_detail',[18,134,806,438],1.5],
    ['browser_detail',[25,573,805,135],1.5],
    ['offline_detail',[1240,284,549,390],1.5],
    ['detection_detail',[836,106,418,570],1.5],
    ['geometry_detail',[420,285,355,280],1.7],
    ['timezone_detail',[1264,100,525,174],1.5]
  ])fs.writeFileSync(path.join(OUT,name+'.png'),await cropRaster(png,...b,s));
  const before=path.join(HERE,'direction_fix_baseline_393f0faa/HybridGuard_overview_candidate.png');
  await localComparison(before,png,[780,180,456,505],'direction_fix_inputs_before_after_96dpi.png');
  await localComparison(before,png,[1264,100,525,176],'direction_fix_timezone_before_after_96dpi.png');
  // Re-render both actual ACM PDF pages at the same DPI, then compare full pages.
  // Run after build_template_preview.py; check_direction_fix.py validates the
  // regenerated rasters and unchanged template page layout afterward.
  const tc=JSON.parse(fs.readFileSync(path.join(HERE,'TEMPLATE_CHECK.json')));
  if(tc.pass&&tc.svg_size_mm?.[1]===heightMM){
    const oldCheck=JSON.parse(fs.readFileSync(path.join(HERE,'direction_fix_baseline_393f0faa/TEMPLATE_CHECK.json')));
    const pageName=`figure_page_${String(tc.figure_page).padStart(2,'0')}`;
    for(const [pdf,page,out] of [
      ['template_preview/hybridguard_draft.pdf',tc.figure_page,`template_preview/${pageName}`],
      ['direction_fix_baseline_393f0faa/template_preview/hybridguard_draft.pdf',oldCheck.figure_page,'previews/direction_fix_baseline_template_page_07']
    ])cp.execFileSync('pdftoppm',['-f',String(page),'-singlefile','-r','150','-png',path.join(HERE,pdf),path.join(HERE,out)]);
    cp.execFileSync('pdftoppm',['-singlefile','-r','200','-png',path.join(HERE,'HybridGuard_overview_candidate.pdf'),path.join(OUT,'pdf_180mm_render')]);
    const a=fs.readFileSync(path.join(OUT,'direction_fix_baseline_template_page_07.png'));
    const z=fs.readFileSync(path.join(HERE,`template_preview/${pageName}.png`));
    const am=await sharp(a).metadata(),zm=await sharp(z).metadata();
    if(am.width!==zm.width||am.height!==zm.height)throw Error('Template page dimensions must match');
    const w=am.width,h=am.height;
    const header=Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${2*w+36}" height="${h+56}"><rect width="100%" height="100%" fill="white"/><g font-family="Arial,sans-serif" font-size="23" fill="#444"><text x="20" y="32">BEFORE | reviewed 393f0faa | ACM page ${oldCheck.figure_page}</text><text x="${w+32}" y="32">AFTER | identical full-page scale and opacity</text></g></svg>`);
    await sharp(header).composite([{input:a,left:0,top:50},{input:z,left:w+36,top:50}]).withMetadata({density:150}).png().toFile(path.join(OUT,'direction_fix_template_pages_same_scale.png'));
  }
  console.log(JSON.stringify({candidate_px:[W*2,H*2],candidate_mm:[widthMM,heightMM],actual_preview_px:[Math.round(widthMM/25.4*96),Math.round(heightMM/25.4*96)],comparison_template_width_mm:177.942341,previews:OUT}));
}
main().catch(e=>{console.error(e);process.exitCode=1});
