import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";
import {parse} from "acorn";
import {examples, harness, observerSource, plain, realmBinding} from "./helpers/webgl-parameter-fixtures.mjs";

test("ES5 standalone observer is inert until explicitly called", () => {
  assert.doesNotThrow(() => parse(observerSource, {ecmaVersion: 5, sourceType: "script"}));
  const h = harness();
  assert.deepEqual(h.events, []);
  assert.throws(() => h.observer.observe(), /realm_binding_required/);
  assert.deepEqual(h.events, []);
});

test("fresh contexts preserve number/string/number order and fixed metadata", () => {
  const h = harness();
  const result = plain(h.observer.observe({realmBinding, observerRevision: "ignored"}));
  assert.equal(result.observer_revision, "webgl-parameter-observer-v1");
  assert.equal(result.realm_binding, realmBinding);
  assert.deepEqual(result.contexts.map(c => c.context_type), ["webgl", "webgl2"]);
  assert.equal(h.contexts.length, 2);
  assert.notEqual(h.contexts[0], h.contexts[1]);
  for (const type of ["webgl", "webgl2"]) {
    const calls = h.events.filter(e => e[0] === type && e[1] === "getParameter");
    assert.deepEqual(calls.map(c => c[2]), [34921, "34921", 34921, 37445, "37445", 37445, 37446, "37446", 37446]);
    const context = result.contexts.find(c => c.context_type === type);
    assert.equal(context.parameters.renderer.numeric_string.argument_kind, "string");
    assert.equal(context.parameters.renderer.numeric_string.read_status, "observed");
  }
});

test("observations retain conflicting values without deciding an alarm", () => {
  const result = plain(harness({conflict: true}).observer.observe({realmBinding}));
  const reads = result.contexts[0].parameters.renderer;
  assert.equal(reads.numeric_before.value, reads.numeric_after.value);
  assert.notEqual(reads.numeric_before.value, reads.numeric_string.value);
  assert.equal("outcome" in result, false);
});

test("missing contexts and extensions remain explicit", () => {
  const absent = plain(harness({unavailable: "webgl2"}).observer.observe({realmBinding}));
  assert.equal(absent.contexts[1].context_creation_status, "unavailable");
  assert.deepEqual(absent.contexts[1].parameters, {});
  const noExtension = plain(harness({noExtension: true}).observer.observe({realmBinding}));
  assert.equal(noExtension.contexts[0].extension_available, false);
  assert.deepEqual(noExtension.contexts[0].parameters, {});
});

test("exceptions stay failed reads and do not produce substitute renderer values", () => {
  const create = plain(harness({createError: true}).observer.observe({realmBinding}));
  assert.equal(create.contexts[0].context_creation_status, "runtime_error");
  const extension = plain(harness({extensionError: true}).observer.observe({realmBinding}));
  assert.equal(extension.contexts[0].extension_read_status, "runtime_error");
  const query = plain(harness({queryError: true}).observer.observe({realmBinding}));
  const sample = query.contexts[0].parameters.renderer.numeric_before;
  assert.equal(sample.read_status, "runtime_error");
  assert.equal("value" in sample, false);
});

test("preflight errors are retained; context loss and non-draining queues stop reads", () => {
  const dirty = plain(harness({initialError: true}).observer.observe({realmBinding}));
  assert.deepEqual(dirty.contexts[0].preflight.errors, [1280]);
  assert.equal(dirty.contexts[0].preflight.drained, true);
  for (const options of [{contextLost: true}, {permanentError: true}]) {
    const h = harness(options);
    const result = plain(h.observer.observe({realmBinding}));
    assert.equal(h.events.filter(e => e[1] === "getParameter").length, 0);
    assert.deepEqual(result.contexts[0].parameters, {});
    assert.ok(h.events.filter(e => e[1] === "getError").length <= 18);
  }
});

test("cross-language fixtures match the actual observer output", async () => {
  const saved = JSON.parse(await readFile(new URL(
    "../../hybridguard_agent/tests/fixtures/webgl_parameter_equivalence_v1/observer_examples.json", import.meta.url), "utf8"));
  assert.deepEqual(saved, examples());
});
