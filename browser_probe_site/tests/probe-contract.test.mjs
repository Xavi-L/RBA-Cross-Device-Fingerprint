import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import { parse } from "acorn";

const canonicalUrl = new URL("../../web_probe/canonical_web_probe.js", import.meta.url);
const deployedCopyUrl = new URL("../public/probe/canonical_web_probe.js", import.meta.url);
const bootstrapUrl = new URL("../public/browser-probe-bootstrap.js", import.meta.url);
const adapterUrl = new URL("../public/browser-probe-adapter.js", import.meta.url);
const catalogUrl = new URL(
  "../../android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv",
  import.meta.url,
);

async function loadCore() {
  const source = await readFile(canonicalUrl, "utf8");
  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(source, context);
  return { core: context.window.HybridGuardWebProbe, source };
}

function createAdapterHarness({
  uploadResponse = {
    pair_status: "completed",
    receipt_id: "browser-receipt-1",
  },
  abortUploads = false,
  useXhr = false,
} = {}) {
  const elements = {
    status: { textContent: "", className: "" },
    log: {
      children: [],
      appendChild(element) {
        this.children.push(element);
      },
      scrollHeight: 0,
      scrollTop: 0,
    },
    canvasBox: {},
  };
  const storage = new Map();
  const uploadBodies = [];
  const stageBodies = [];
  const xhrRequestHeaders = [];
  let domContentLoaded;
  let abortedUploadCount = 0;

  class FakeAbortController {
    constructor() {
      const listeners = [];
      this.signal = {
        aborted: false,
        addEventListener(name, listener) {
          if (name === "abort") {
            listeners.push(listener);
          }
        },
      };
      this.abort = () => {
        this.signal.aborted = true;
        abortedUploadCount += 1;
        for (const listener of listeners) {
          listener();
        }
      };
    }
  }

  const window = {
    AbortController: FakeAbortController,
    HybridGuardWebProbe: {
      REVISION: "expanded-web-67-v1",
      FIELD_PATHS: Array.from({ length: 67 }, (_, index) => `field-${index}`),
      collect: async () => ({
        web_data: { navigator_layer: { user_agent: "test" } },
        probe_statuses: {},
        collection_status: {
          fixed_signal_count: 67,
          counts: { observed: 67 },
          fields: {},
        },
      }),
      describeError: (error) => String(error?.message ?? error),
    },
    addEventListener(name, listener) {
      if (name === "DOMContentLoaded") {
        domContentLoaded = listener;
      }
    },
    clearTimeout,
    crypto: {
      randomUUID: () => "00000000-0000-4000-8000-000000000001",
    },
    history: {
      replaceState() {},
    },
    location: {
      hash:
        "#pair_id=hgpair-v1-test" +
        "&browser_ticket=browser-ticket-abcdefghijklmnopqrstuvwxyz" +
        "&browser_upload_url=https%3A%2F%2Fcollector.example%2Fapi%2Fcollect%2Fbrowser-fingerprint" +
        "&browser_stage_url=https%3A%2F%2Fcollector.example%2Fapi%2Fcollect%2Fbrowser-stage" +
        "&launch_attempt=1",
      origin: "https://xavi-l.github.io",
      pathname: "/RBA-Cross-Device-Fingerprint/",
      search: "",
    },
    sessionStorage: {
      getItem(key) {
        return storage.get(key) ?? null;
      },
      removeItem(key) {
        storage.delete(key);
      },
      setItem(key, value) {
        storage.set(key, value);
      },
    },
    setTimeout(callback, delay) {
      if (abortUploads || delay < 12000) {
        return setTimeout(callback, 0);
      }
      return setTimeout(callback, delay);
    },
  };

  if (!useXhr) {
    window.fetch = async (url, options = {}) => {
      if (options.method !== "POST") {
        return {
          ok: true,
          json: async () => ({ sha256: "a".repeat(64) }),
        };
      }
      uploadBodies.push(options.body);
      if (abortUploads) {
        return new Promise((_resolve, reject) => {
          options.signal.addEventListener("abort", () => {
            reject(new Error("upload aborted by timeout"));
          });
        });
      }
      return {
        ok: true,
        text: async () => JSON.stringify(uploadResponse),
      };
    };
  } else {
    window.XMLHttpRequest = class FakeXMLHttpRequest {
      constructor() {
        this.headers = {};
        this.readyState = 0;
        this.responseText = "";
        this.status = 0;
        xhrRequestHeaders.push(this.headers);
      }

      open(method, url) {
        this.method = method;
        this.url = url;
      }

      setRequestHeader(name, value) {
        this.headers[name] = value;
      }

      send(body) {
        if (this.method === "POST") {
          if (this.url.includes("/browser-stage")) {
            stageBodies.push(body);
          } else {
            uploadBodies.push(body);
          }
          this.responseText = JSON.stringify(uploadResponse);
        } else {
          this.responseText = JSON.stringify({ sha256: "a".repeat(64) });
        }
        this.status = 200;
        this.readyState = 4;
        window.setTimeout(() => this.onreadystatechange?.(), 0);
      }
    };
  }

  const context = {
    URL,
    document: {
      createElement(tagName) {
        if (tagName === "a") {
          const anchor = {};
          Object.defineProperty(anchor, "href", {
            set(value) {
              const parsed = new URL(value);
              anchor.protocol = parsed.protocol;
              anchor.hostname = parsed.hostname;
            },
          });
          return anchor;
        }
        return { className: "", textContent: "" };
      },
      getElementById(id) {
        return elements[id];
      },
    },
    sessionStorage: window.sessionStorage,
    setTimeout: window.setTimeout,
    window,
  };
  vm.createContext(context);

  return {
    abortedUploadCount: () => abortedUploadCount,
    elements,
    run: async (source) => {
      vm.runInContext(source, context);
      assert.equal(typeof domContentLoaded, "function");
      domContentLoaded();
      for (let index = 0; index < 20; index += 1) {
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
    },
    runBootstrap: async (source) => {
      vm.runInContext(source, context);
      for (let index = 0; index < 5; index += 1) {
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
    },
    uploadBodies,
    stageBodies,
    xhrRequestHeaders,
  };
}

test("all deployed probe scripts retain ES5 syntax compatibility", async () => {
  const scripts = await Promise.all([
    readFile(bootstrapUrl, "utf8"),
    readFile(adapterUrl, "utf8"),
    readFile(canonicalUrl, "utf8"),
  ]);
  for (const source of scripts) {
    assert.doesNotThrow(() => parse(source, { ecmaVersion: 5, sourceType: "script" }));
  }
});

test("canonical core exports the exact cataloged Web 67 paths", async () => {
  const [{ core }, catalog] = await Promise.all([
    loadCore(),
    readFile(catalogUrl, "utf8"),
  ]);
  const catalogFields = catalog
    .split(/\r?\n/)
    .slice(1)
    .map((line) => line.split(",", 1)[0].trim())
    .filter((field) => field.startsWith("web_data."));
  assert.equal(catalogFields.length, 67);
  assert.deepEqual(Array.from(core.FIELD_PATHS), catalogFields);
});

test("deployed core is byte-identical and SHA-256 remains stable", async () => {
  const [{ core, source }, deployedCopy, manifestText] = await Promise.all([
    loadCore(),
    readFile(deployedCopyUrl),
    readFile(new URL("../public/probe/manifest.json", import.meta.url), "utf8"),
  ]);
  const sourceBytes = Buffer.from(source);
  assert.deepEqual(deployedCopy, sourceBytes);
  assert.equal(
    core.sha256("abc"),
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  );
  const manifest = JSON.parse(manifestText);
  assert.equal(
    manifest.sha256,
    createHash("sha256").update(sourceBytes).digest("hex"),
  );
  assert.equal(manifest.signal_count, 67);
  assert.equal(manifest.revision, core.REVISION);
});

test("browser adapter keeps secrets in the URL fragment and skips ngrok warning", async () => {
  const [adapter, html] = await Promise.all([
    readFile(new URL("../public/browser-probe-adapter.js", import.meta.url), "utf8"),
    readFile(new URL("../public/browser-probe.html", import.meta.url), "utf8"),
  ]);
  assert.match(adapter, /location\.hash/);
  assert.doesNotMatch(adapter, /URLSearchParams\(global\.location\.search/);
  assert.doesNotMatch(adapter, /new\s+URLSearchParams|URLSearchParams\s*\(/);
  assert.match(adapter, /XMLHttpRequest/);
  assert.match(adapter, /ngrok-skip-browser-warning/);
  assert.match(adapter, /browser_stage_url/);
  assert.match(adapter, /Retrying the exact cached browser payload/);
  assert.match(adapter, /collector_app:\s*"browserprobe"/);
  assert.match(adapter, /schema_version:\s*"browser-web-v1-status"/);
  assert.match(html, /canonical_web_probe\.js/);
  assert.match(html, /browser-probe-bootstrap\.js/);
});

test("ES5 bootstrap reports page_loaded before the adapter executes", async () => {
  const bootstrap = await readFile(bootstrapUrl, "utf8");
  const harness = createAdapterHarness({ useXhr: true });

  await harness.runBootstrap(bootstrap);

  assert.equal(harness.stageBodies.length, 1);
  const stage = JSON.parse(harness.stageBodies[0]);
  assert.equal(stage.pair_id, "hgpair-v1-test");
  assert.equal(stage.stage, "page_loaded");
  assert.equal(stage.launch_attempt, 1);
  assert.equal(typeof stage.client_stage_at_ms, "number");
});

test("awaiting app statuses are reported as saved, not fully paired", async (t) => {
  const adapter = await readFile(
    new URL("../public/browser-probe-adapter.js", import.meta.url),
    "utf8",
  );
  for (const pairStatus of ["awaiting_app", "awaiting_app_receipt"]) {
    await t.test(pairStatus, async () => {
      const harness = createAdapterHarness({
        uploadResponse: {
          pair_status: pairStatus,
          receipt_id: "browser-receipt-pending",
        },
      });

      await harness.run(adapter);

      assert.match(
        harness.elements.status.textContent,
        /Browser payload saved, waiting for app binding\./,
      );
      assert.doesNotMatch(harness.elements.status.textContent, /collection complete/i);
      assert.equal(harness.uploadBodies.length, 1);
    });
  }
});

test("upload timeout retries the exact same serialized payload three times", async () => {
  const adapter = await readFile(
    new URL("../public/browser-probe-adapter.js", import.meta.url),
    "utf8",
  );
  const harness = createAdapterHarness({ abortUploads: true });

  await harness.run(adapter);

  assert.equal(harness.uploadBodies.length, 3);
  assert.equal(new Set(harness.uploadBodies).size, 1);
  assert.equal(harness.abortedUploadCount(), 3);
  assert.match(
    harness.elements.status.textContent,
    /Browser collection could not be uploaded/,
  );
});

test("legacy browser path parses the fragment and uploads through XHR", async () => {
  const adapter = await readFile(
    new URL("../public/browser-probe-adapter.js", import.meta.url),
    "utf8",
  );
  const harness = createAdapterHarness({
    useXhr: true,
    uploadResponse: {
      pair_status: "awaiting_app",
      receipt_id: "browser-receipt-xhr",
    },
  });

  await harness.run(adapter);

  assert.equal(harness.uploadBodies.length, 1);
  assert.ok(harness.stageBodies.length >= 3);
  assert.equal(
    JSON.parse(harness.uploadBodies[0]).pair_id,
    "hgpair-v1-test",
  );
  const uploadHeaders = harness.xhrRequestHeaders.find(
    (headers) => headers.Authorization,
  );
  assert.equal(
    uploadHeaders.Authorization,
    "Bearer browser-ticket-abcdefghijklmnopqrstuvwxyz",
  );
  assert.equal(uploadHeaders["ngrok-skip-browser-warning"], "1");
  assert.match(
    harness.elements.status.textContent,
    /Browser payload saved, waiting for app binding\./,
  );
});
