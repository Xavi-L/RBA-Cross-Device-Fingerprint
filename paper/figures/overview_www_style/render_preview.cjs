// Render the editable SVG with the existing bundled Sharp runtime; no network.
const fs = require('fs');
const path = require('path');
const os = require('os');
const deps = process.env.RBA_NODE_MODULES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const sharp = require(path.join(deps, 'sharp'));
const source = path.join(__dirname, 'HybridGuard_overview.svg');
// Pixel dimensions in the rendering buffer avoid double density scaling of mm
// units in librsvg. The editable SVG retains its 180 mm physical dimensions.
const svg = Buffer.from(fs.readFileSync(source, 'utf8').replace('width="180mm" height="89.2mm"', 'width="1800" height="892"'));
sharp(svg, {density: 144}).png().toFile(path.join(__dirname, 'HybridGuard_overview.png'))
  .then(result => console.log(JSON.stringify(result)))
  .catch(error => { console.error(error); process.exitCode = 1; });
