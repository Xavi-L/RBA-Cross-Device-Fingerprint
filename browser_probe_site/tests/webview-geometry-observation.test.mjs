import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";
import { parse } from "acorn";

const source = fs.readFileSync(new URL("../../web_probe/webview_geometry_observer.js", import.meta.url), "utf8");
const asset = "../../android_app/HybridGuard/featureapp/src/main/assets/";
const adapter = fs.readFileSync(new URL(asset + "expanded_webview_adapter.js", import.meta.url), "utf8");
const request = {session_id: "session", webview_instance_id: "view", document_generation: 3,
  observation_id: "observation", attempt_id: "attempt"};

function world() {
  const w = {innerWidth: 393, innerHeight: 600, outerWidth: 393, outerHeight: 851, devicePixelRatio: 2.75,
    screen: {width: 393, height: 851, availWidth: 393, availHeight: 851, availLeft: 0, availTop: 0,
      orientation: {type: "portrait-primary", angle: 0}},
    visualViewport: {width: 393, height: 600, scale: 1, offsetLeft: 0, offsetTop: 0, pageLeft: 0, pageTop: 0},
    performance: {now: () => 20, timeOrigin: 1_800_000_000_000},
    document: {URL: "file:///android_asset/expanded_probe.html", readyState: "complete", compatMode: "CSS1Compat",
      documentElement: {clientWidth: 393, clientHeight: 600},
      querySelector: () => ({getAttribute: () => "width=device-width, initial-scale=1.0, viewport-fit=cover"})}};
  w.window = w;
  vm.runInNewContext(source, w);
  return w;
}

test("ES5 snapshot reads raw CSS values, identity and independent time domains synchronously", () => {
  assert.doesNotThrow(() => parse(source, {ecmaVersion: 5}));
  const w = world(), first = w.HybridGuardWebViewGeometry.capture(request);
  assert.equal(typeof first.then, "undefined");
  assert.deepEqual({...first.binding}, request);
  assert.equal(first.fields.inner_width.value, 393);
  assert.equal(first.fields.document_client_height.unit, "css_px");
  assert.equal(first.fields.device_pixel_ratio.value, 2.75);
  assert.equal(first.fields.visual_viewport_scale.unit, "ratio");
  assert.equal(first.fields.orientation_angle.value, 0);
  assert.equal(first.clock.performance_start_ms, 20);
  assert.equal(first.clock.time_origin_ms, 1_800_000_000_000);
  assert.equal(first.same_snapshot_as_legacy_screen_layer, false);
  assert.equal(first.document_id, w.HybridGuardWebViewGeometry.capture(request).document_id);
  assert.notEqual(first.document_id, world().HybridGuardWebViewGeometry.documentId);
});

test("missing, nonfinite, zero and throwing getters retain distinct states without normal defaults", () => {
  const w = world();
  delete w.visualViewport;
  w.innerWidth = 0;
  w.innerHeight = "600";
  w.devicePixelRatio = Infinity;
  Object.defineProperty(w.screen, "height", {get() {throw new Error("test_read_failure");}});
  const s = w.HybridGuardWebViewGeometry.capture(request);
  assert.equal(s.read_status, "partial");
  assert.equal(s.fields.inner_width.value, 0);
  assert.equal(s.fields.inner_width.status, "observed");
  assert.equal(s.fields.inner_height.status, "wrong_type");
  assert.equal(s.fields.inner_height.value, "600");
  assert.equal(s.fields.visual_viewport_scale.value, null);
  assert.equal(s.fields.visual_viewport_scale.status, "unsupported");
  assert.equal(s.fields.device_pixel_ratio.status, "non_finite");
  assert.equal(s.fields.screen_height.status, "runtime_error");
  assert.match(s.fields.screen_height.reason, /test_read_failure/);
  assert.doesNotThrow(() => JSON.stringify(s));
});

test("snapshot preserves stable contradictory values and does not use phase or target metadata", () => {
  const w = world();
  w.innerWidth = 1000;
  w.visualViewport.width = 1200;
  const s = w.HybridGuardWebViewGeometry.capture({...request, phase: "normal", target: 1});
  assert.equal(s.read_status, "observed");
  assert.equal(s.fields.inner_width.value, 1000);
  assert.equal(s.fields.visual_viewport_width.value, 1200);
  assert.equal("phase" in s.binding, false);
  assert.equal("target" in s.binding, false);
});

async function runAdapter({ready = () => true} = {}) {
  const w = world(), payloads = [], mutations = [];
  let onLoad, submitted = false, readinessCalls = 0;
  const el = {appendChild() {if (submitted) mutations.push("append");},
    set textContent(value) {if (submitted) mutations.push(value);}};
  w.Promise = Promise;
  w.setTimeout = fn => fn();
  w.document.getElementById = () => el;
  w.document.createElement = () => ({});
  w.AndroidBridge = {isGeometryReady: () => {readinessCalls++; return ready();},
    getSessionId: () => "session", getWebViewHostFeatures: () => "{}",
    submitExpandedPayload: text => {submitted = true; payloads.push(JSON.parse(text));}};
  w.HybridGuardWebProbe = {REVISION: "expanded-web-67-v2", describeError: String, defaultWebData: () => ({}),
    collect: async () => ({web_data: {navigator_layer: {user_agent: "fixture"}, screen_layer: {},
      graphics_layer: {canvas_hash: ""}, audio_layer: {}, font_layer: {}, execution_layer: {}},
      probe_statuses: {}, collection_observations: {webdriver: {boolean_value: false}}})};
  w.addEventListener = (name, fn) => {if (name === "load") onLoad = fn;};
  vm.runInNewContext(adapter, w);
  await onLoad();
  return {w, payloads, mutations, readinessCalls};
}

test("normal App path binds same document, freezes DOM during host sampling, preserves prior observations", async () => {
  const {w, payloads, mutations, readinessCalls} = await runAdapter();
  assert.equal(readinessCalls, 1);
  assert.equal(payloads.length, 1);
  const observations = payloads[0].collection_observations;
  const snapshot = w.HybridGuardProbe.captureWebViewGeometry(request);
  assert.equal(observations.geometry_document_id, snapshot.document_id);
  assert.equal(observations.geometry_readiness.status, "observed");
  assert.equal(observations.webdriver.boolean_value, false);
  assert.equal(observations.webgl_parameter.read_status, "unsupported");
  assert.deepEqual(mutations, []);
  w.HybridGuardProbe.updateResult("completed", "geometry done", "good");
  assert.ok(mutations.length > 0);
});

test("host readiness timeout has bounded attempts and still uploads old evidence exactly once", async () => {
  const {payloads, readinessCalls} = await runAdapter({ready: () => false});
  assert.equal(readinessCalls, 80);
  assert.equal(payloads.length, 1);
  assert.equal(payloads[0].collection_observations.geometry_readiness.status, "timeout");
  assert.equal(payloads[0].collection_observations.webdriver.boolean_value, false);
});
