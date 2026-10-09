// Rasterize this editable SVG locally; never invoke an experiment entrypoint.
const fs = require('fs');
const os = require('os');
const path = require('path');
const deps = process.env.RBA_NODE_MODULES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const sharp = require(path.join(deps, 'sharp'));
const source = path.join(__dirname, 'HybridGuard_overview_triangle.svg');
const original = fs.readFileSync(source, 'utf8');
const viewBox = original.match(/<svg\b[^>]*\bviewBox="0 0 ([\d.]+) ([\d.]+)"/);
if (!viewBox) throw new Error('Expected a zero-origin SVG viewBox');
const svg = Buffer.from(original.replace(/<svg\b[^>]*>/, root => root
  .replace(/\bwidth="[^"]*"/, `width="${viewBox[1]}"`)
  .replace(/\bheight="[^"]*"/, `height="${viewBox[2]}"`)));
sharp(svg, {density:144}).png().toFile(path.join(__dirname, 'HybridGuard_overview_triangle.png'))
  .then(result => console.log(JSON.stringify(result)))
  .catch(error => {console.error(error);process.exitCode=1;});
