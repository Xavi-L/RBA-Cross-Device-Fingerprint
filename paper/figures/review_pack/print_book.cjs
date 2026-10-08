// Print local, inline SVG at declared millimetre sizes. No network resources.
const fs = require('fs');
const path = require('path');
const os = require('os');
const {pathToFileURL} = require('url');
const root = process.env.RBA_NODE_MODULES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium} = require(path.join(root, 'playwright-core'));
(async () => {
  const [html, pdf, qa] = process.argv.slice(2);
  const browser = await chromium.launch({executablePath: process.env.RBA_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless:true,
    args:['--allow-file-access-from-files', '--disable-dev-shm-usage']});
  try {
    const context = await browser.newContext();
    await context.route(/^https?:/, route => route.abort());
    const page = await context.newPage();
    await page.goto(pathToFileURL(html).href);
    await page.evaluate(() => document.fonts.ready);
    const report = await page.evaluate(() => {
      const pages = [...document.querySelectorAll('.page')].map(el => {
        const bounds=el.getBoundingClientRect(), footer=el.querySelector('footer').getBoundingClientRect();
        const content=el.querySelector('.content').getBoundingClientRect();
        const svg=el.querySelector('.figure > svg');
        return {id:el.id, overflow:content.bottom>footer.top-8 || content.right>bounds.right+1,
          svg:svg?{width_mm:svg.getBoundingClientRect().width*25.4/96,height_mm:svg.getBoundingClientRect().height*25.4/96}:null};
      });
      return {pages, chinese_font:document.fonts.check('10pt "ReviewCJK"'),
        figure_font:document.fonts.check('8pt "DejaVu Sans"'), vector_svg_count:document.querySelectorAll('.figure > svg').length,
        raster_image_count:document.querySelectorAll('.figure image,.figure img').length};
    });
    fs.writeFileSync(qa,JSON.stringify(report,null,2));
    if(report.pages.some(p=>p.overflow)||!report.chinese_font||!report.figure_font)throw new Error('Page bounds/font check failed; see '+qa);
    await page.pdf({path:pdf,preferCSSPageSize:true,printBackground:true,tagged:true,outline:true});
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
