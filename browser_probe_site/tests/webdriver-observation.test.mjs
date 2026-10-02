import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import { parse } from "acorn";

const canonicalSource = await readFile(
  new URL("../../web_probe/canonical_web_probe.js", import.meta.url), "utf8",
);
const appAdapterSource = await readFile(new URL(
  "../../android_app/HybridGuard/featureapp/src/main/assets/expanded_webview_adapter.js",
  import.meta.url,
), "utf8");
const catalog = await readFile(new URL(
  "../../android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv",
  import.meta.url,
), "utf8");
const realmBinding = "featureapp:fixture-session:main-frame";
const appOptions = { webdriverObservation: { realmBinding } };
const plain = (value) => JSON.parse(JSON.stringify(value));

// All browser/bridge values here are synthetic. Unrelated expensive probes are
// deliberately unavailable; tests exercise the public collector and adapter.
function harness(navigator, { hostError = false } = {}) {
  const elements = Object.fromEntries(["status", "subtitle", "log", "canvasBox"].map(
    (id) => [id, { textContent: "", appendChild() {}, scrollTop: 0, scrollHeight: 0 }],
  ));
  const payloads = [];
  let onLoad;
  const sandbox = {
    navigator,
    screen: { width: 100, height: 200 },
    performance: { now: () => 1 },
    Intl: { DateTimeFormat() { throw new Error("unrelated synthetic probe unavailable"); } },
    document: {
      getElementById: (id) => elements[id],
      createElement: (name) => name === "canvas" ? { getContext: () => null } : {},
    },
    setTimeout: (callback, delay) => setTimeout(callback, delay === 100 ? 0 : delay),
    clearTimeout,
    AndroidBridge: {
      getSessionId: () => "fixture-session",
      getWebViewHostFeatures() {
        if (hostError) throw new Error("synthetic host failure");
        return "{}";
      },
      submitExpandedPayload: (body) => payloads.push(JSON.parse(body)),
    },
    addEventListener(name, listener) {
      if (name === "load") onLoad = listener;
    },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(canonicalSource, sandbox);
  return {
    core: sandbox.HybridGuardWebProbe,
    payloads,
    async runAdapter() {
      vm.runInContext(appAdapterSource, sandbox);
      await onLoad();
    },
  };
}

function navigatorWithGetter(getter, { presence = true, presenceError = false } = {}) {
  const events = [];
  const target = { userAgent: "synthetic", plugins: [], mimeTypes: [] };
  const navigator = new Proxy(target, {
    has(object, key) {
      if (key !== "webdriver") return key in object;
      events.push("presence");
      if (presenceError) throw new Error("synthetic presence failure");
      return presence;
    },
    get(object, key) {
      if (key !== "webdriver") return object[key];
      events.push("getter");
      return getter();
    },
  });
  return { navigator, target, events };
}

function expectedObservation(overrides = {}) {
  return {
    api_present: true,
    presence_read_status: "observed",
    value_read_status: "observed",
    value_type: "boolean",
    boolean_value: true,
    observer_revision: "app-webdriver-observer-v1",
    realm_binding: realmBinding,
    ...overrides,
  };
}

function observed(result) {
  assert.equal(result.collection_observations.observation_schema_version,
    "app-web-observations-v1");
  return plain(result.collection_observations.webdriver);
}

test("App and shared probe retain ES5 syntax and exact 177/67 field catalogs", () => {
  for (const source of [canonicalSource, appAdapterSource]) {
    assert.doesNotThrow(() => parse(source, { ecmaVersion: 5, sourceType: "script" }));
  }
  const fields = catalog.trim().split(/\r?\n/).slice(1).map((line) => line.split(",")[0]);
  const { core } = harness({});
  assert.equal(fields.filter((field) => /^(android_native_data|webview_data|web_data)\./.test(field)).length, 177);
  assert.deepEqual(Array.from(core.FIELD_PATHS), fields.filter((field) => field.startsWith("web_data.")));
  assert.equal(core.FIELD_PATHS.length, 67);
  assert.equal(core.REVISION, "expanded-web-67-v2");
});

test("Browser67 default does not check presence or return App observation metadata", async () => {
  const fixture = navigatorWithGetter(() => true, { presenceError: true });
  const result = await harness(fixture.navigator).core.collect();
  assert.deepEqual(fixture.events, ["getter"]);
  assert.deepEqual(Object.keys(result).sort(), ["collection_status", "probe_statuses", "web_data"]);
  assert.equal(result.web_data.automation_surface_layer.webdriver, true);
  assert.equal(result.collection_status.fixed_signal_count, 67);
  assert.equal(Object.keys(result.collection_status.fields).length, 67);
});

test("App captures booleans and derives strict-true from the same single read", async (t) => {
  for (const value of [true, false]) {
    await t.test(String(value), async () => {
      let reads = 0;
      const fixture = navigatorWithGetter(() => ++reads === 1 ? value : !value);
      const result = await harness(fixture.navigator).core.collect({
        webdriverObservation: { realmBinding, observerRevision: "ignored-caller-revision" },
      });
      assert.deepEqual(fixture.events, ["presence", "getter"]);
      assert.deepEqual(observed(result), expectedObservation({ boolean_value: value }));
      assert.equal(result.web_data.automation_surface_layer.webdriver, value);
      assert.equal(result.collection_status.fixed_signal_count, 67);
      assert.equal(Object.keys(result.web_data.automation_surface_layer).length, 6);
    });
  }
});

test("nonboolean getter types serialize with explicit null and never become true", async (t) => {
  const circular = {};
  circular.self = circular;
  const cases = [undefined, null, 1, "true", new Boolean(true), circular, Symbol("fixture"), 1n, () => true];
  for (const [index, value] of cases.entries()) {
    await t.test(`${index}: ${typeof value}`, async () => {
      const fixture = navigatorWithGetter(() => value);
      const result = await harness(fixture.navigator).core.collect(appOptions);
      assert.deepEqual(fixture.events, ["presence", "getter"]);
      assert.deepEqual(observed(result), expectedObservation({
        value_type: typeof value, boolean_value: null,
      }));
      assert.equal(result.web_data.automation_surface_layer.webdriver, false);
    });
  }
});

test("API absence and presence error skip the getter and preserve distinct states", async (t) => {
  for (const presenceError of [false, true]) {
    await t.test(presenceError ? "presence error" : "absent", async () => {
      const fixture = navigatorWithGetter(() => { throw new Error("must not run"); }, {
        presence: false, presenceError,
      });
      const result = await harness(fixture.navigator).core.collect(appOptions);
      assert.deepEqual(fixture.events, ["presence"]);
      assert.deepEqual(observed(result), expectedObservation({
        api_present: presenceError ? null : false,
        presence_read_status: presenceError ? "runtime_error" : "observed",
        value_read_status: "not_attempted", value_type: null, boolean_value: null,
      }));
      assert.equal(result.web_data.automation_surface_layer.webdriver, false);
      assert.equal(result.probe_statuses.automation, presenceError ? "runtime_error" : "observed");
    });
  }
});

test("getter failure survives the legacy Automation fallback without a retry", async () => {
  const fixture = navigatorWithGetter(() => { throw new Error("synthetic getter failure"); });
  const result = await harness(fixture.navigator).core.collect(appOptions);
  assert.deepEqual(fixture.events, ["presence", "getter"]);
  assert.deepEqual(observed(result), expectedObservation({
    value_read_status: "runtime_error", value_type: null, boolean_value: null,
  }));
  assert.equal(result.probe_statuses.automation, "runtime_error");
  assert.equal(result.web_data.automation_surface_layer.webdriver, false);
});

test("later plugin or mime failure cannot erase the independent raw observation", async (t) => {
  for (const failingField of ["plugins", "mimeTypes"]) {
    await t.test(failingField, async () => {
      const fixture = navigatorWithGetter(() => true);
      Object.defineProperty(fixture.target, failingField, {
        get() { throw new Error("synthetic plugin property failure"); },
      });
      const result = await harness(fixture.navigator).core.collect(appOptions);
      assert.deepEqual(fixture.events, ["presence", "getter"]);
      assert.deepEqual(observed(result), expectedObservation());
      assert.equal(result.probe_statuses.automation, "runtime_error");
      // Preserve the pre-existing whole-group fallback for the legacy field.
      assert.equal(result.web_data.automation_surface_layer.webdriver, false);
    });
  }
});

test("App opt-in rejects missing context before reading webdriver", () => {
  const fixture = navigatorWithGetter(() => true);
  const { core } = harness(fixture.navigator);
  for (const options of [{}, { realmBinding: " " }, { realmBinding: 42 }]) {
    assert.throws(() => core.collect({ webdriverObservation: options }),
      /webdriver_observation_realm_binding_required/);
  }
  assert.deepEqual(fixture.events, []);
});

test("FeatureApp adapter opts in and hands off metadata outside the fixed field tree", async () => {
  const fixture = navigatorWithGetter(() => undefined);
  const app = harness(fixture.navigator);
  await app.runAdapter();
  assert.equal(app.payloads.length, 1);
  const payload = app.payloads[0];
  assert.deepEqual(observed(payload), expectedObservation({ value_type: "undefined", boolean_value: null }));
  assert.equal(payload.session_id, "fixture-session");
  assert.equal(payload.web_data.automation_surface_layer.webdriver, false);
  assert.equal(Object.keys(payload.web_data.automation_surface_layer).length, 6);
  assert.deepEqual(fixture.events, ["presence", "getter"]);
});

test("App bridge fallback does not fabricate a raw observation", async () => {
  const fixture = navigatorWithGetter(() => true);
  const app = harness(fixture.navigator, { hostError: true });
  await app.runAdapter();
  assert.equal(app.payloads.length, 1);
  assert.equal("collection_observations" in app.payloads[0], false);
  assert.equal(app.payloads[0].collection_diagnostics.probe_statuses.webgl2, "runtime_error");
  assert.equal(app.payloads[0].collection_diagnostics.probe_statuses.webgl, "runtime_error");
  assert.deepEqual(fixture.events, []);
});
