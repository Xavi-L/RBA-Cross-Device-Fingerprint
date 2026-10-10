// Focused local-artifact checks, with a second SVG renderer (Chrome).
const fs=require('fs'), path=require('path'), os=require('os');
const deps=process.env.RBA_NODE_MODULES||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=require(path.join(deps,'playwright'));
const HERE=__dirname;
async function main(){
  const browser=await chromium.launch({executablePath:process.env.RBA_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1160,height:590},deviceScaleFactor:1});
    await page.setContent('<html><head><style>html,body {margin:0} svg {width:1160px;height:590px;display:block}</style></head><body>'+fs.readFileSync(path.join(HERE,'triangle_style_sample.svg'),'utf8')+'</body></html>');
    await page.evaluate(()=>document.fonts.ready);
    const result=await page.evaluate(()=>{
      const svg=document.documentElement;
      const all=[...document.querySelectorAll('text')];
      const texts=all.map(t=>{
        const b=t.getBoundingClientRect();
        return {text:t.textContent,x:b.x,y:b.y,w:b.width,h:b.height,
          icon:!!t.dataset.iconMark,size:parseFloat(getComputedStyle(t).fontSize)};
      });
      const body=texts.filter(t=>!t.icon);
      const overlaps=[];
      for(let i=0;i<texts.length;i++)for(let j=i+1;j<texts.length;j++){
        const a=texts[i],b=texts[j];
        if(a.x<b.x+b.w&&b.x<a.x+a.w&&a.y<b.y+b.h&&b.y<a.y+a.h)overlaps.push([a.text,b.text]);
      }
      const lineText=[];
      for(const g of document.querySelectorAll('[data-kind="relation"]')){
        const p=g.querySelector('path');
        for(const t of texts){
          for(let i=0;i<=400;i++){
            const q=p.getPointAtLength(p.getTotalLength()*i/400);
            if(q.x>t.x&&q.x<t.x+t.w&&q.y>t.y&&q.y<t.y+t.h){lineText.push([g.id,t.text]);break;}
          }
        }
      }
      const relations=[...document.querySelectorAll('[data-kind="relation"]')].map(g=>{
        const p=g.querySelector('path');return {id:g.id,status:g.dataset.status,color:p.getAttribute('stroke'),dash:p.getAttribute('stroke-dasharray'),start:p.getAttribute('marker-start'),end:p.getAttribute('marker-end')};
      });
      return {texts,body_text_count:body.length,min_body_font_units:Math.min(...body.map(t=>t.size)),
        text_overlaps:overlaps,relation_text_intersections:lineText,
        out_of_canvas:texts.filter(t=>t.x<0||t.y<0||t.x+t.w>1160||t.y+t.h>590),
        relations,embedded_rasters:document.querySelectorAll('image').length,
        compressed_text:document.querySelectorAll('text[textLength], text[lengthAdjust]').length,
        times_new_roman_available:document.fonts.check('29px "Times New Roman"')};
    });
    await page.screenshot({path:path.join(HERE,'previews','chrome_sample.png')});
    const expected=['One device, multiple observation points','Inside the app','Device & OS','(Native)','Memory and timezone','App container','(WebView Host)','Container settings','Embedded webpage','(App Web)','Reported properties','Cross-check','reported properties','System–web consistency','Memory and timezone','Shared context','No detection rule','Container–web geometry','Not in current detector'];
    const seen=result.texts.filter(t=>!t.icon).map(t=>t.text).sort();
    result.exact_copy_preserved=JSON.stringify(seen)===JSON.stringify(expected.sort());
    result.formal_files_unchanged=Object.fromEntries(['HybridGuard_overview_triangle.svg','HybridGuard_overview_triangle.png','build_overview.py','COPY.md','README.md'].map(n=>[n,fs.readFileSync(path.join(HERE,'baseline',n)).equals(fs.readFileSync(path.join(HERE,'..',n)))]));
    const ctx=result.relations.find(r=>r.status==='context');
    result.context_has_no_arrows=ctx.start===null&&ctx.end===null;
    // ViewBox geometry, not an inference from a no-overlap result.
    result.host_inner_page={bounds_in_shell_grid:[6.72+5*.44,8.15+3*.44,6.72+19*.44,8.15+21*.44],
      content_bounds:[4.1,8.65,19.9,17.85],minimum_clearance_grid:.46,
      outer_contour_units:.64*6.1,inner_contour_units:.72*.44*6.1};
    result.checked_scale={sample_mm:[116,59],parent_figure_mm:[180,125],width_fraction:116/180,screen_preview_px:[438,223],screen_dpi:96};
    result.automated_checks_pass=result.exact_copy_preserved&&result.context_has_no_arrows&&
      result.min_body_font_units>=28&&!result.text_overlaps.length&&!result.relation_text_intersections.length&&
      !result.out_of_canvas.length&&!result.embedded_rasters&&!result.compressed_text&&
      Object.values(result.formal_files_unchanged).every(Boolean);
    fs.writeFileSync(path.join(HERE,'CHECK.json'),JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result,null,2));
    if(!result.automated_checks_pass)process.exitCode=1;
  }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1});
