import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../../web_probe/canonical_web_probe.js", import.meta.url), "utf8");
const gl1Field = "web_data.graphics_layer.webgl_renderer";
const gl2Field = "web_data.graphics_layer.webgl2_supported";

async function collect({ webgl = true, webgl2 = true, debugExtension = true } = {}) {
  const calls = [];
  let canvasId = 0;
  const gl = {
    MAX_TEXTURE_SIZE: 1, MAX_VIEWPORT_DIMS: 2, ALIASED_LINE_WIDTH_RANGE: 3,
    getExtension: () => debugExtension ? { UNMASKED_VENDOR_WEBGL: 4, UNMASKED_RENDERER_WEBGL: 5 } : null,
    getParameter: (key) => ({ 1: 4096, 2: [8192, 8192], 3: [1, 1], 4: "vendor", 5: "renderer" })[key],
    getSupportedExtensions: () => ["extension"],
  };
  const sandbox = {
    navigator: { plugins: [], mimeTypes: [] }, screen: { width: 100, height: 200 },
    performance: { now: () => 1 }, setTimeout, clearTimeout,
    Intl: { DateTimeFormat() { throw new Error("unrelated fixture probe unavailable"); } },
    document: {
      createElement(name) {
        if (name !== "canvas") return {};
        const id = ++canvasId;
        let mode = null;
        return {
          getContext(type) {
            calls.push({ id, type });
            if (type === "2d") return null;
            const requestedMode = type === "experimental-webgl" ? "webgl" : type;
            // Reproduce HTML canvas context-mode exclusion, not just canned booleans.
            if (mode && mode !== requestedMode) return null;
            const support = requestedMode === "webgl2" ? webgl2 : webgl;
            if (support === "throw") throw new Error("synthetic context failure");
            if (!support) return null;
            mode = requestedMode;
            return gl;
          },
        };
      },
    },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox);
  const result = await sandbox.HybridGuardWebProbe.collect();
  return { result, calls };
}

test("WebGL2 uses a fresh canvas after WebGL1 succeeds", async () => {
  const { result, calls } = await collect();
  assert.notEqual(calls.find((c) => c.type === "webgl").id, calls.find((c) => c.type === "webgl2").id);
  assert.equal(result.web_data.graphics_layer.webgl2_supported, true);
  assert.equal(result.web_data.graphics_layer.webgl_renderer, "renderer");
  assert.equal(result.collection_status.fields[gl2Field], "observed");
  assert.equal(Object.keys(result.collection_status.fields).length, 67);
});

for (const [name, options, gl1Status, gl2Status, supported] of [
  ["null WebGL2 is an observed false", { webgl2: false }, "observed", "observed", false],
  ["throwing WebGL2 is a collection error", { webgl2: "throw" }, "observed", "runtime_error", false],
  ["absent WebGL1 does not mask WebGL2", { webgl: false }, "not_applicable", "observed", true],
  ["WebGL1 failure remains an error", { webgl: "throw" }, "runtime_error", "observed", true],
  ["neither context is available", { webgl: false, webgl2: false }, "not_applicable", "observed", false],
  ["debug extension absence does not hide WebGL2", { debugExtension: false }, "observed", "observed", true],
]) {
  test(name, async () => {
    const { result } = await collect(options);
    assert.equal(result.collection_status.fields[gl1Field], gl1Status);
    assert.equal(result.collection_status.fields[gl2Field], gl2Status);
    assert.equal(result.web_data.graphics_layer.webgl2_supported, supported);
  });
}
