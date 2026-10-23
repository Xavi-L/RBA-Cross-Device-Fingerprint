const fs = require('fs'), path = require('path');
const { chromium } = require('/Users/xavier/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const HERE = __dirname;
async function main() {
  const browser = await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1760,height:900},deviceScaleFactor:1.5});
    const svg = fs.readFileSync(path.join(HERE,'HybridGuard_Fig2_redesign_v6.svg'),'utf8');
    await page.setContent(`<title>HybridGuard Figure 2 - revision v6</title><style>html,body{margin:0;padding:0;background:white}body>svg{display:block;width:1760px;height:900px}</style>${svg}`);
    await page.evaluate(()=>document.fonts.ready);
    const check=await page.evaluate(()=>{
      const texts=[...document.querySelectorAll('text')].map(t=>{
        const b=t.getBoundingClientRect();
        return {text:t.textContent,x:b.x,y:b.y,w:b.width,h:b.height};
      });
      const overlaps=[];
      for(let i=0;i<texts.length;i++)for(let j=i+1;j<texts.length;j++){
        const a=texts[i],b=texts[j];
        if(a.x+1<b.x+b.w&&b.x+1<a.x+a.w&&a.y+1<b.y+b.h&&b.y+1<a.y+a.h)overlaps.push([a.text,b.text]);
      }
      return {textCount:texts.length,textOverlaps:overlaps,outOfCanvas:texts.filter(t=>t.x<0||t.y<0||t.x+t.w>1760||t.y+t.h>900),externalResources:[...document.querySelectorAll('[href],[src]')].map(n=>n.getAttribute('href')||n.getAttribute('src')).filter(u=>u&&!u.startsWith('#')),embeddedVectorAssets:document.querySelectorAll('svg[data-asset]').length,rasterImages:document.querySelectorAll('image').length};
    });
    await page.screenshot({path:path.join(HERE,'HybridGuard_Fig2_redesign_v6.png'),scale:'device'});
    await page.addStyleTag({content:'@page{size:180mm 92.04545mm;margin:0}html,body{width:180mm;height:92.04545mm;margin:0}body>svg{width:180mm;height:92.04545mm;display:block}'});
    await page.pdf({path:path.join(HERE,'HybridGuard_Fig2_redesign_v6.pdf'),preferCSSPageSize:true,printBackground:true,margin:{top:0,bottom:0,left:0,right:0}});
    check.visualReview='PENDING';
    fs.writeFileSync(path.join(HERE,'RENDER_CHECK.json'),JSON.stringify(check,null,2)+'\n');
    console.log(JSON.stringify(check));
  } finally { await browser.close(); }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
