// Only reads the frozen baseline and writes within this pilot directory.
const fs = require('fs');
const path = require('path');
const os = require('os');
const deps = process.env.RBA_NODE_MODULES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const sharp = require(path.join(deps, 'sharp'));
const HERE = __dirname;
const OUT = path.join(HERE, 'previews');
const svg = fs.readFileSync(path.join(HERE, 'triangle_style_sample.svg'), 'utf8');
const basePath = path.join(HERE, 'baseline', 'HybridGuard_overview_triangle.png');
const layout = JSON.parse(fs.readFileSync(path.join(HERE, 'layout.json')));
const sourceNote = '_WWW__Lower_Barriers__Greater_Threat_.pdf | p. 5, Figure 1 (top) | supplied reference';

function rootUnits(s, w, h, vb) {
  return s.replace(/<svg\b[^>]*>/, tag => tag.replace(/\bwidth="[^"]*"/,`width="${w}"`)
    .replace(/\bheight="[^"]*"/,`height="${h}"`)
    .replace(/\bviewBox="[^"]*"/,`viewBox="${vb}"`));
}
function escape(s) { return s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'); }
function plate(w,h, labels) {
  return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><rect width="100%" height="100%" fill="white"/>
  <g fill="#434951" font-family="Arial,sans-serif">${labels.map(l=>`<text x="${l.x||24}" y="${l.y}" font-size="${l.size||20}">${escape(l.text)}</text>`).join('')}</g></svg>`);
}
async function raster(s,w,h,vb) {return sharp(Buffer.from(rootUnits(s,w,h,vb)),{density:72}).png().toBuffer();}
async function compose(name,w,h,labels,imgs,density) {
  let s=sharp(plate(w,h,labels)).composite(imgs);
  if(density) s=s.withMetadata({density});
  await s.png().toFile(path.join(OUT,name));
}
async function main() {
  fs.mkdirSync(OUT,{recursive:true});
  const png=await raster(svg,2320,1180,'0 0 1160 590');
  await sharp(png).withMetadata({density:508}).png().toFile(path.join(HERE,'triangle_style_sample.png'));
  const original=await sharp(basePath).resize(1800).png().toBuffer();
  const before=await sharp(basePath).extract({left:48,top:208,width:2320,height:1180}).resize(1160).png().toBuffer();
  const after=await sharp(png).resize(1160).png().toBuffer();
  await compose('old_new_same_scale.png',1208,1358,[
    {y:31,text:'CURRENT WORKSPACE BASELINE | crop = 116 x 59 mm of the 180 mm full figure'},
    {y:705,text:'RECOMMENDED PILOT | same 116 x 59 mm | unchanged body text size'}
  ],[{input:before,left:24,top:55},{input:after,left:24,top:729}]);
  const actualW=Math.round(116/25.4*96),actualH=Math.round(59/25.4*96);
  await sharp(png).resize(actualW,actualH).withMetadata({density:96}).png().toFile(path.join(OUT,'sample_116mm_96dpi.png'));
  const smallBefore=await sharp(before).resize(actualW,actualH).png().toBuffer();
  const smallAfter=await sharp(png).resize(actualW,actualH).png().toBuffer();
  await compose('old_new_print_scale_96dpi.png',actualW+32,actualH*2+128,[
    {x:16,y:22,size:14,text:'Current | 116 mm crop of a 180 mm full figure'},
    {x:16,y:actualH+86,size:14,text:'Pilot | identical physical scale; 96 px/in preview'}
  ],[{input:smallBefore,left:16,top:39},{input:smallAfter,left:16,top:actualH+103}],96);

  const detailNodes=[['Native',[400,97,420,148]],['Host',[25,400,410,155]],['App Web',[725,400,420,155]]];
  const isolatedNodes=svg.replace('</svg>','<style>[data-kind="relation"], #context-label, #consistency-label, #geometry-label, #core-action, #device-scope > path, #device-scope > text, #app-scope > path, #app-scope > text {display:none}</style></svg>');
  const nodeImages=[];
  for(let i=0;i<detailNodes.length;i++){
    const [name,b]=detailNodes[i];
    nodeImages.push({input:await raster(isolatedNodes,b[2]*2,b[3]*2,b.join(' ')),left:150,top:55+i*370});
  }
  await compose('node_details.png',1040,1120,detailNodes.map(([name],i)=>({x:20,y:90+i*370,text:name,size:24})),nodeImages);
  const iconCrops=[[421,104,98,133],[35,431,126,103],[736,419,91,116]];
  const iconImages=[];
  for(let i=0;i<iconCrops.length;i++){
    const b=iconCrops[i];
    iconImages.push({input:await raster(svg,b[2]*3,b[3]*3,b.join(' ')),left:35+i*420,top:65});
  }
  await compose('icon_details.png',1270,515,[
    {x:35,y:33,text:'PHONE + SYSTEM SETTINGS'},
    {x:455,y:33,text:'SHELL CONTAINS PAGE'},
    {x:875,y:33,text:'PAGE REPORTS PROPERTIES'},
    {x:35,y:492,text:'Detail crops from the sample itself; 3 px per viewBox unit. Not a print-size readability test.',size:19}
  ],iconImages);
  const faded=await sharp(original).composite([{input:Buffer.from('<svg width="1800" height="1250"><rect width="1800" height="1250" fill="white" opacity="0.65"/></svg>')}]).png().toBuffer();
  const placed=await sharp(faded).composite([{input:after,left:24,top:104}]).png().toBuffer();
  await compose('full_figure_position.png',1848,1360,[
    {y:31,text:'POSITION STUDY ONLY | full figure = 180 x 125 mm; pilot = 116 x 59 mm',size:24},
    {y:63,text:'Unredrawn regions are faded context. This composite is not a finished method figure.',size:21}
  ],[{input:placed,left:24,top:90}]);
  await sharp(placed).resize(Math.round(180/25.4*96)).withMetadata({density:96}).png().toFile(path.join(OUT,'position_180mm_96dpi.png'));

  // Reference is first normalized as a complete Figure 1 to the SAME 180 mm.
  // Related-region crops below inherit this single scale; no fit-to-crop scaling.
  const ref=await sharp(path.join(HERE,'reference','figure1_enlarged.png')).resize(1800).png().toBuffer();
  const rm=await sharp(ref).metadata();
  await compose('reference_full_figures_same_width.png',1848,rm.height+1250+150,[
    {y:25,text:sourceNote,size:19},
    {y:52,text:'Complete reference Figure 1 | normalized to 180 mm wide',size:21},
    {y:rm.height+100,text:'Complete current HybridGuard figure | the same 180 mm width',size:21}
  ],[{input:ref,left:24,top:65},{input:original,left:24,top:rm.height+115}]);
  const refCrop=await sharp(ref).extract({left:50,top:15,width:300,height:rm.height-30}).png().toBuffer();
  await compose('reference_regions_same_scale.png',1584,775,[
    {y:26,text:sourceNote,size:17},
    {y:55,text:'Both parent figures = 180 mm. Crops retain parent scale (10 px/mm); reference is not shrunk.',size:20},
    {x:24,y:90,text:'Reference left region',size:20},
    {x:390,y:90,text:'Recommended 116 mm pilot in its planned full-figure scale',size:20}
  ],[{input:refCrop,left:24,top:112},{input:after,left:390,top:112}]);
  console.log(JSON.stringify({sample:[2320,1180],physical_mm:[116,59],actual_preview:[actualW,actualH],previews:OUT},null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1});
