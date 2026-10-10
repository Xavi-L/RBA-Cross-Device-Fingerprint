// Raster previews only. render_pdf_and_check.cjs exports the editable vector PDF.
const fs=require('fs'),path=require('path'),os=require('os');
const deps=process.env.RBA_NODE_MODULES||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const sharp=require(path.join(deps,'sharp'));
const HERE=__dirname, OUT=path.join(HERE,'previews');
const source=fs.readFileSync(path.join(HERE,'HybridGuard_overview_candidate.svg'),'utf8');
const [W,H]=JSON.parse(fs.readFileSync(path.join(HERE,'layout.json'))).viewbox;
function cropSvg(x,y,w,h,scale=1){
  return Buffer.from(source.replace(/<svg\b[^>]*>/,tag=>tag.replace(/\bwidth="[^"]*"/,`width="${w*scale}"`).replace(/\bheight="[^"]*"/,`height="${h*scale}"`).replace(/\bviewBox="[^"]*"/,`viewBox="${x} ${y} ${w} ${h}"`)));
}
function esc(s){return s.replaceAll('&','&amp;').replaceAll('<','&lt;');}
function plate(w,h,labels){return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><rect width="100%" height="100%" fill="white"/><g font-family="Arial,sans-serif" fill="#4a5058">${labels.map(l=>`<text x="24" y="${l.y}" font-size="${l.size||23}">${esc(l.text)}</text>`).join('')}</g></svg>`);}
async function main(){
  fs.mkdirSync(OUT,{recursive:true});
  const png=await sharp(cropSvg(0,0,W,H,2),{density:72}).png().toBuffer();
  await sharp(png).withMetadata({density:508}).png().toFile(path.join(HERE,'HybridGuard_overview_candidate.png'));
  const actual=await sharp(png).resize(Math.round(180/25.4*96)).withMetadata({density:96}).png().toBuffer();
  fs.writeFileSync(path.join(OUT,'actual_180mm_96dpi.png'),actual);
  await sharp(png).resize(W).greyscale().png().toFile(path.join(OUT,'grayscale_full.png'));
  await sharp(actual).greyscale().withMetadata({density:96}).png().toFile(path.join(OUT,'grayscale_180mm_96dpi.png'));
  const old=await sharp(path.join(HERE,'baseline/HybridGuard_overview_triangle.png')).resize(W).png().toBuffer();
  const now=await sharp(png).resize(W).png().toBuffer();
  await sharp(plate(W+48,1250+H+144,[
    {y:32,text:'CURRENT FORMAL FIGURE | 180 x 125 mm'},
    {y:1250+104,text:'COMPLETE CANDIDATE | 180 x 133 mm | identical width and opacity'}
  ])).composite([{input:old,left:24,top:50},{input:now,left:24,top:1250+122}]).png().toFile(path.join(OUT,'before_after_same_width.png'));
  const smallOld=await sharp(old).resize(680).png().toBuffer();
  await sharp(plate(728,472+503+120,[
    {y:28,text:'Formal | 180 mm width',size:18},
    {y:472+88,text:'Candidate | same 180 mm width',size:18}
  ])).composite([{input:smallOld,left:24,top:43},{input:actual,left:24,top:472+103}]).withMetadata({density:96}).png().toFile(path.join(OUT,'before_after_180mm_96dpi.png'));
  for(const [name,b,s] of [
    ['triangle_detail',[40,157,1128,582],1.5],
    ['browser_detail',[185,748,978,187],1.5],
    ['offline_detail',[1205,390,580,558],1.8],
    ['detection_detail',[20,947,1758,337],1.1],
    ['geometry_detail',[45,474,1120,250],1.7],
    ['timezone_detail',[1205,120,580,259],1.5]
  ]) await sharp(cropSvg(...b,s),{density:72}).png().toFile(path.join(OUT,name+'.png'));
  const ref=await sharp(path.join(HERE,'reference/figure1_enlarged.png')).resize(W).png().toBuffer();
  const rm=await sharp(ref).metadata();
  await sharp(plate(W+48,rm.height+H+156,[
    {y:28,text:'Supplied _WWW__Lower_Barriers__Greater_Threat_.pdf | p. 5, upper Figure 1',size:20},
    {y:55,text:'Complete reference figure | 180 mm width'},
    {y:rm.height+112,text:'Complete HybridGuard candidate | same 180 mm width; no region is faded'}
  ])).composite([{input:ref,left:24,top:68},{input:now,left:24,top:rm.height+136}]).png().toFile(path.join(OUT,'reference_same_width.png'));
  console.log(JSON.stringify({candidate_px:[W*2,H*2],candidate_mm:[180,133],actual_preview_px:[680,503],previews:OUT}));
}
main().catch(e=>{console.error(e);process.exitCode=1});
