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
async function comparison(before,after,width,file){
  const a=await sharp(before).resize({width}).png().toBuffer();
  const z=await sharp(after).resize({width}).png().toBuffer();
  const am=await sharp(a).metadata(),zm=await sharp(z).metadata();
  await sharp(plate(width+48,am.height+zm.height+150,[
    {y:30,text:'BEFORE | 86aa74c | identical 177.942 mm template width',size:20},
    {y:am.height+100,text:'AFTER | same width, opacity and body type size',size:20}
  ])).composite([{input:a,left:24,top:45},{input:z,left:24,top:am.height+116}]).withMetadata({density:Math.round(width*25.4/177.942341)}).png().toFile(path.join(OUT,file));
}
async function main(){
  fs.mkdirSync(OUT,{recursive:true});
  const chrome=path.join(OUT,'chrome_full_2x.png');
  if(fs.statSync(chrome).mtimeMs<fs.statSync(path.join(HERE,'HybridGuard_overview_candidate.svg')).mtimeMs)throw Error('Run the Chrome renderer after the SVG builder.');
  const png=fs.readFileSync(chrome);
  await sharp(png).withMetadata({density:508}).png().toFile(path.join(HERE,'HybridGuard_overview_candidate.png'));
  const actual=await sharp(png).resize(Math.round(widthMM/25.4*96)).withMetadata({density:96}).png().toBuffer();
  fs.writeFileSync(path.join(OUT,'actual_180mm_96dpi.png'),actual);
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
  const before=path.join(HERE,'compression_baseline_86aa74c/HybridGuard_overview_candidate.png');
  await comparison(before,png,W,'compression_before_after_same_width.png');
  await comparison(before,png,Math.round(177.942341/25.4*96),'compression_before_after_template_width_96dpi.png');
  // Re-render both actual ACM PDF pages at the same DPI, then compare full pages.
  // Run after build_template_preview.py and check_compression.py for current data.
  const tc=JSON.parse(fs.readFileSync(path.join(HERE,'TEMPLATE_CHECK.json')));
  if(tc.pass&&tc.svg_size_mm?.[1]===heightMM){
    const oldCheck=JSON.parse(fs.readFileSync(path.join(HERE,'compression_baseline_86aa74c/TEMPLATE_CHECK.json')));
    const pageName=`figure_page_${String(tc.figure_page).padStart(2,'0')}`;
    for(const [pdf,page,out] of [
      ['template_preview/hybridguard_draft.pdf',tc.figure_page,`template_preview/${pageName}`],
      ['compression_baseline_86aa74c/template_preview/hybridguard_draft.pdf',oldCheck.figure_page,'previews/compression_baseline_template_page_07']
    ])cp.execFileSync('pdftoppm',['-f',String(page),'-singlefile','-r','150','-png',path.join(HERE,pdf),path.join(HERE,out)]);
    cp.execFileSync('pdftoppm',['-singlefile','-r','200','-png',path.join(HERE,'HybridGuard_overview_candidate.pdf'),path.join(OUT,'pdf_180mm_render')]);
    const a=fs.readFileSync(path.join(OUT,'compression_baseline_template_page_07.png'));
    const z=fs.readFileSync(path.join(HERE,`template_preview/${pageName}.png`));
    const am=await sharp(a).metadata(),zm=await sharp(z).metadata();
    if(am.width!==zm.width||am.height!==zm.height)throw Error('Template page dimensions must match');
    const w=am.width,h=am.height;
    const header=Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${2*w+36}" height="${h+56}"><rect width="100%" height="100%" fill="white"/><g font-family="Arial,sans-serif" font-size="23" fill="#444"><text x="20" y="32">BEFORE | reviewed 86aa74c | ACM page ${oldCheck.figure_page}</text><text x="${w+32}" y="32">AFTER | identical full-page scale and opacity</text></g></svg>`);
    await sharp(header).composite([{input:a,left:0,top:50},{input:z,left:w+36,top:50}]).withMetadata({density:150}).png().toFile(path.join(OUT,'compression_template_pages_same_scale.png'));
  }
  console.log(JSON.stringify({candidate_px:[W*2,H*2],candidate_mm:[widthMM,heightMM],actual_preview_px:[Math.round(widthMM/25.4*96),Math.round(heightMM/25.4*96)],comparison_template_width_mm:177.942341,previews:OUT}));
}
main().catch(e=>{console.error(e);process.exitCode=1});
