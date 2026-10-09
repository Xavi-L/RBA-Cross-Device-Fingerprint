// Render the editable SVG with the existing bundled Sharp runtime; no network.
const fs = require('fs');
const path = require('path');
const os = require('os');
const deps = process.env.RBA_NODE_MODULES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const sharp = require(path.join(deps, 'sharp'));
const source = path.join(__dirname, 'HybridGuard_overview.svg');
// Pixel dimensions in the rendering buffer avoid double density scaling of mm
// units in librsvg. The editable SVG retains its 180 mm physical dimensions.
const original = fs.readFileSync(source, 'utf8');
const viewBox = original.match(/<svg\b[^>]*\bviewBox="0 0 ([\d.]+) ([\d.]+)"/);
if (!viewBox) throw new Error('Expected a zero-origin SVG viewBox');
const svg = Buffer.from(original.replace(/<svg\b[^>]*>/, root => root
  .replace(/\bwidth="[^"]*"/, `width="${viewBox[1]}"`)
  .replace(/\bheight="[^"]*"/, `height="${viewBox[2]}"`)));
sharp(svg, {density: 144}).png().toFile(path.join(__dirname, 'HybridGuard_overview.png'))
  .then(result => console.log(JSON.stringify(result)))
  .catch(error => { console.error(error); process.exitCode = 1; });
