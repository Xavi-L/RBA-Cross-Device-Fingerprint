// Synthetic browser API only: these records are not collected device evidence.
import {readFile, writeFile, mkdir} from "node:fs/promises";
import {dirname} from "node:path";
import {fileURLToPath} from "node:url";
import vm from "node:vm";

export const observerSource = await readFile(new URL("../../../web_probe/webgl_parameter_observer.js", import.meta.url), "utf8");
export const realmBinding = "synthetic:parameter-test:main-frame";
export const plain = value => JSON.parse(JSON.stringify(value));

export function harness(options = {}) {
  const events = [];
  const contexts = [];
  const sandbox = {
    document: {createElement(name) {
      events.push(["createElement", name]);
      if (options.createError) throw new Error("synthetic canvas error");
      return {getContext(type) {
        events.push(["getContext", type]);
        if (options.unavailable === type) return null;
        const queue = [];
        let count = 0;
        const gl = {
          getExtension(name) {
            events.push([type, "getExtension", name]);
            if (options.extensionError) throw new Error("synthetic extension error");
            if (options.initialError) queue.push(1280);
            return options.noExtension ? null : {UNMASKED_VENDOR_WEBGL: 37445, UNMASKED_RENDERER_WEBGL: 37446};
          },
          isContextLost: () => options.contextLost === true,
          getError() {
            events.push([type, "getError"]);
            return options.permanentError ? 1280 : queue.shift() || 0;
          },
          getParameter(arg) {
            count += 1;
            events.push([type, "getParameter", arg]);
            if (options.queryHook) return options.queryHook(arg, count);
            if (Number(arg) === 34921) return 16;
            if (options.queryError && Number(arg) === 37446) throw new Error("synthetic query error");
            if (options.conflict && (arg === 37445 || arg === 37446)) return "synthetic changed value";
            return Number(arg) === 37445 ? "synthetic vendor" : "synthetic renderer";
          },
        };
        contexts.push(gl);
        return gl;
      }};
    }},
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(observerSource, sandbox);
  return {events, contexts, observer: sandbox.HybridGuardWebGLParameterObserver};
}

export function examples() {
  return {
    kind: "SYNTHETIC_ONLY_NOT_DEVICE_SAMPLES",
    producer: "Actual standalone observer executed against an explicit fake WebGL API in Node vm",
    expected_realm_binding: realmBinding,
    cases: [
      ["normal", {}, "MATCH"],
      ["numeric_string_conflict", {conflict: true}, "COUNTEREXAMPLE"],
      ["preflight_error", {initialError: true}, "UNKNOWN"],
      ["extension_unavailable", {noExtension: true}, "UNKNOWN"],
    ].map(([id, options, expected]) => ({id, expected,
      observation: plain(harness(options).observer.observe({realmBinding}))})),
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  if (process.argv[2] !== "--write" || !process.argv[3]) throw new Error("Expected --write FILE");
  await mkdir(dirname(process.argv[3]), {recursive: true});
  await writeFile(process.argv[3], JSON.stringify(examples(), null, 2) + "\n");
}
