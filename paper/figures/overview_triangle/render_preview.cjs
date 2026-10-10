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
const [width, height] = viewBox.slice(1).map(Number);
const svg = Buffer.from(original.replace(/<svg\b[^>]*>/, root => root
  .replace(/\bwidth="[^"]*"/, `width="${viewBox[1]}"`)
  .replace(/\bheight="[^"]*"/, `height="${viewBox[2]}"`)));
const previewDir = path.join(__dirname, 'previews');
const nodes = ['native', 'webview-host', 'app-web'];
const names = ['Native', 'WebView Host', 'App Web'];
const pixelScale = 2; // The existing 144-dpi raster uses two pixels per viewBox unit.

function attrs(tag) {
  return Object.fromEntries([...tag.matchAll(/([\w:-]+)="([^"]*)"/g)].map(m => [m[1], m[2]]));
}

function box(tag) {
  const a = attrs(tag);
  return {left: Math.round(Number(a.x) * pixelScale), top: Math.round(Number(a.y) * pixelScale),
    width: Math.round(Number(a.width) * pixelScale), height: Math.round(Number(a.height) * pixelScale)};
}

function labelSvg(w, h, lines) {
  return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">
    <rect width="100%" height="100%" fill="white"/>
    <g font-family="Arial, sans-serif" fill="#343434">${lines.map(({x, y, text, size = 20, anchor = 'start'}) =>
      `<text x="${x}" y="${y}" font-size="${size}" text-anchor="${anchor}">${text}</text>`).join('')}</g></svg>`);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length && (args.length !== 2 || args[0] !== '--before')) {
    throw new Error('Usage: node render_preview.cjs [--before original-first-triangle.png]');
  }
  const before = args.length ? fs.readFileSync(args[1]) : null;
  if (before) {
    const meta = await sharp(before).metadata();
    if (meta.width !== width * pixelScale || meta.height !== height * pixelScale) {
      throw new Error('Before preview must match the original 3600 x 2120 first triangle');
    }
  }
  const png = await sharp(svg, {density: 144}).png().toBuffer();
  fs.writeFileSync(path.join(__dirname, 'HybridGuard_overview_triangle.png'), png);
  fs.mkdirSync(previewDir, {recursive: true});

  // Read the final figure itself; no duplicate icon definitions in the previews.
  const actualScale = (180 / 25.4 * 96) / width;
  const actual = [], enlarged = [];
  const actualXs = [24, 252, 480];
  for (let i = 0; i < nodes.length; i++) {
    const group = original.match(new RegExp(`<g id="${nodes[i]}">([\\s\\S]*?)</g>`))[1];
    const nodeBox = box(group.match(/<rect\b[^>]*>/)[0]);
    const iconBox = box(group.match(/<use\b[^>]*>/)[0]);
    actual.push({input: await sharp(png).extract(nodeBox)
      .resize(Math.round(nodeBox.width / pixelScale * actualScale)).png().toBuffer(), left: actualXs[i], top: 44});
    const zoomWidth = iconBox.width * 2; // Four pixels per original viewBox unit.
    const zoomSvg = original.replace(/<svg\b[^>]*>/, root => root
      .replace(/\bwidth="[^"]*"/, `width="${zoomWidth}"`)
      .replace(/\bheight="[^"]*"/, `height="${iconBox.height * 2}"`)
      .replace(/\bviewBox="[^"]*"/, `viewBox="${iconBox.left / pixelScale} ${iconBox.top / pixelScale} ${iconBox.width / pixelScale} ${iconBox.height / pixelScale}"`));
    enlarged.push({input: await sharp(Buffer.from(zoomSvg), {density: 72}).png().toBuffer(),
      left: Math.round((i + 0.5) * 680 / 3 - zoomWidth / 2), top: 52});
  }
  await sharp(labelSvg(680, 118, [
    {x: 24, y: 25, text: 'Nodes at 180 mm figure width (96 px/in preview)', size: 17},
  ])).composite(actual).withMetadata({density: 96}).png()
    .toFile(path.join(previewDir, 'icons_actual_size.png'));
  await sharp(labelSvg(680, 320, [
    {x: 24, y: 25, text: 'Icon detail (4 pixels per viewBox unit)', size: 17},
    ...names.map((name, i) => ({x: (i + 0.5) * 680 / 3, y: 295, text: name, size: 20, anchor: 'middle'})),
  ])).composite(enlarged).png().toFile(path.join(previewDir, 'icons_enlarged.png'));

  if (before) {
    const header = 60, gap = 32;
    await sharp(labelSvg(width, 2 * (height + header) + gap, [
      {x: 24, y: 40, text: 'Before: first triangle (a6c9aa5)', size: 28},
      {x: 24, y: height + header + gap + 40, text: 'After: local revision, same size and layout', size: 28},
    ])).composite([
      {input: await sharp(before).resize(width, height).png().toBuffer(), left: 0, top: header},
      {input: await sharp(png).resize(width, height).png().toBuffer(), left: 0, top: height + 2 * header + gap},
    ]).png().toFile(path.join(previewDir, 'before_after.png'));
  }
  console.log(JSON.stringify({png: [width * pixelScale, height * pixelScale], previews: previewDir,
    comparisonGenerated: Boolean(before)}));
}

main().catch(error => {console.error(error);process.exitCode = 1;});
