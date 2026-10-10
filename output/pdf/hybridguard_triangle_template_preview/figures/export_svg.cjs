// Export the editable SVG to a vector PDF before compiling with pdfLaTeX.
const fs = require('fs');
const path = require('path');
const os = require('os');
const deps = process.env.RBA_NODE_MODULES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium} = require(path.join(deps, 'playwright-core'));
(async () => {
  const browser = await chromium.launch({executablePath: process.env.RBA_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true});
  try {
    const page = await browser.newPage();
    await page.route('**/*', route => route.abort());
    const svg = fs.readFileSync(path.join(__dirname, 'HybridGuard_overview_triangle.svg'), 'utf8');
    const root = svg.match(/<svg\b[^>]*>/)[0];
    const dimension = name => {
      const match = root.match(new RegExp('\\b' + name + '="([0-9.]+)mm"'));
      if (!match) throw new Error('SVG must declare physical ' + name + ' in mm');
      return Number(match[1]);
    };
    const width = dimension('width'), height = dimension('height');
    await page.setContent(`<html><head><style>@page{size:${width}mm ${height}mm;margin:0}html,body{margin:0;padding:0;width:${width}mm;height:${height}mm}svg{display:block;width:${width}mm;height:${height}mm}</style></head><body>${svg}</body></html>`);
    await page.evaluate(() => document.fonts.ready);
    await page.pdf({path: path.join(__dirname, 'HybridGuard_overview_triangle.pdf'), preferCSSPageSize: true, printBackground: true, displayHeaderFooter: false, margin:{top:'0',bottom:'0',left:'0',right:'0'}});
    console.log('Exported figures/HybridGuard_overview_triangle.pdf');
  } finally {await browser.close();}
})().catch(e => {console.error(e);process.exitCode=1;});
