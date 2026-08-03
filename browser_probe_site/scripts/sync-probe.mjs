import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const canonicalUrl = new URL("../../web_probe/canonical_web_probe.js", import.meta.url);
const destinationUrl = new URL("../public/probe/canonical_web_probe.js", import.meta.url);
const manifestUrl = new URL("../public/probe/manifest.json", import.meta.url);
const canonicalBytes = await readFile(canonicalUrl);
const sha256 = createHash("sha256").update(canonicalBytes).digest("hex");

await mkdir(dirname(fileURLToPath(destinationUrl)), { recursive: true });
await copyFile(canonicalUrl, destinationUrl);
await writeFile(
  manifestUrl,
  `${JSON.stringify(
    {
      schema_version: "hybridguard-web-probe-bundle-v1",
      revision: "expanded-web-67-v1",
      signal_count: 67,
      sha256,
    },
    null,
    2,
  )}\n`,
  "utf8",
);

console.log(`Synchronized canonical Web probe ${sha256}`);
