import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";
import { parse } from "acorn";

const asset = "../../android_app/HybridGuard/featureapp/src/main/assets/";
const source = fs.readFileSync(new URL(asset + "expanded_webview_adapter.js", import.meta.url), "utf8");
const html = fs.readFileSync(new URL(asset + "expanded_probe.html", import.meta.url), "utf8");
const fixture = JSON.parse(fs.readFileSync(new URL("../../hybridguard_agent/tests/fixtures/webgl_parameter_equivalence_v1/observer_examples.json", import.meta.url)));
const raw = fixture.cases.find(c => c.id === "normal").observation;

async function collect(observer, sessionId = "fixture-session") {
  const payloads = [], calls = [];
  const el = {appendChild() {}, textContent: ""};
  let onLoad;
  const world = {Promise, performance: {now: () => 0}, setTimeout: fn => fn(),
    document: {getElementById: () => el, createElement: () => ({})},
    HybridGuardWebGLParameterObserver: observer,
    AndroidBridge: {getSessionId: () => sessionId, getWebViewHostFeatures: () => "{}",
      submitExpandedPayload: value => payloads.push(JSON.parse(value))},
    HybridGuardWebProbe: {REVISION: "expanded-web-67-v2", describeError: String, defaultWebData: () => ({}),
      collect: async () => {
        calls.push("canonical");
        return {web_data: {navigator_layer: {user_agent: "fixture"}, screen_layer: {},
          graphics_layer: {canvas_hash: ""}, audio_layer: {}, font_layer: {}, execution_layer: {}},
          probe_statuses: {webgl: "observed"}, collection_observations: {
            observation_schema_version: "app-web-observations-v1", webdriver: {boolean_value: false}}};
      }},
    addEventListener: (event, fn) => { if (event === "load") onLoad = fn; }};
  world.window = world;
  vm.runInNewContext(source, world);
  await onLoad();
  assert.equal(payloads.length, sessionId ? 1 : 0);
  return {payload: payloads[0], calls};
}

test("App asset load order and ES5 adapter", () => {
  assert.doesNotThrow(() => parse(source, {ecmaVersion: 5}));
  assert.ok(html.indexOf('src="canonical_web_probe.js"') < html.indexOf('src="webgl_parameter_observer.js"'));
  assert.ok(html.indexOf('src="webgl_parameter_observer.js"') < html.indexOf('src="expanded_webview_adapter.js"'));
});

test("App collects once, preserves both raw contexts, webdriver and field trees", async () => {
  const observation = structuredClone(raw);
  observation.contexts[1].preflight.errors = [1280];
  let count = 0;
  const {payload} = await collect({observe: options => {
    count++;
    assert.equal(options.realmBinding, "featureapp:fixture-session:main-frame");
    return observation;
  }});
  assert.equal(count, 1);
  const bundle = payload.collection_observations;
  assert.deepEqual(bundle.webgl_parameter, {collection_revision: "featureapp-webgl-parameter-collection-v1",
    read_status: "observed", observation, reason: null});
  assert.deepEqual(bundle.webdriver, {boolean_value: false});
  assert.deepEqual(payload.collection_diagnostics.probe_statuses, {webgl: "observed"});
  assert.equal("webgl_parameter" in payload.web_data, false);
});

test("missing module, observer exception and empty session preserve unknown evidence", async () => {
  const cases = [[undefined, "fixture-session", "unsupported"],
    [{observe() {throw new Error("synthetic failure");}}, "fixture-session", "runtime_error"],
    [{observe() {throw new Error("must not run");}}, "", "not_collected"]];
  for (const [observer, session, status] of cases) {
    const {payload} = await collect(observer, session);
    if (!session) {
      assert.equal(payload, undefined); // Existing uploader refuses unbound sessions.
      continue;
    }
    assert.equal(payload.collection_observations.webgl_parameter.read_status, status);
    assert.equal(payload.collection_observations.webgl_parameter.observation, null);
    assert.deepEqual(payload.collection_observations.webdriver, {boolean_value: false});
  }
});
