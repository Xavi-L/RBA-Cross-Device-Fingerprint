import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../public/browser-probe-adapter.js", import.meta.url), "utf8");
const pairId = "hgpair-v1-current-round";
const receiptId = "browser-receipt-current-round";
const storageKey = "hybridguard-browser-probe-v1";
const uploadUrl = "https://collector.example/api/collect/browser-fingerprint";

// Virtual time exercises the real adapter's full two-minute wait without sleeping.
async function createPage({ upload = {}, replies = [{}], storage = new Map() } = {}) {
  let now = 0;
  let nextTimer = 0;
  let start;
  let collections = 0;
  const timers = new Map();
  const queries = [];
  const uploads = [];
  const hanging = [];
  const elements = {
    status: { textContent: "", className: "" },
    log: { appendChild() {} },
    canvasBox: {},
  };
  const queue = replies.slice();
  const response = {
    status: "success", pair_id: pairId, receipt_id: receiptId,
    pair_status: "awaiting_app", ...upload,
  };
  const window = {
    setTimeout(callback, delay) {
      const id = ++nextTimer;
      timers.set(id, { callback, due: now + delay });
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
    addEventListener(name, callback) { if (name === "DOMContentLoaded") start = callback; },
    history: { replaceState() {} },
    location: {
      hash: "#" + new URLSearchParams({
        pair_id: pairId, browser_ticket: "this-round-ticket",
        browser_upload_url: uploadUrl,
        browser_stage_url: "https://collector.example/api/collect/browser-stage",
      }),
      pathname: "/browser-probe.html", search: "", origin: "https://probe.example",
    },
    crypto: { randomUUID: () => "browser-session" },
    sessionStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    },
    HybridGuardWebProbe: {
      REVISION: "expanded-web-67-v1", FIELD_PATHS: Array(67).fill("field"),
      collect: async () => {
        collections += 1;
        return {
          web_data: {}, probe_statuses: {},
          collection_status: { counts: { observed: 0 }, fixed_signal_count: 67, fields: {} },
        };
      },
      describeError: (error) => error.message,
    },
    XMLHttpRequest: class {
      headers = {};
      open(method, url) { this.method = method; this.url = url; }
      setRequestHeader(key, value) { this.headers[key] = value; }
      respond(body, status = 200) {
        this.status = status;
        this.readyState = 4;
        this.responseText = JSON.stringify(body);
        this.onreadystatechange();
      }
      send(body) {
        if (this.url.endsWith("/status")) {
          queries.push(this);
          const reply = queue.length > 1 ? queue.shift() : queue[0];
          if (reply === "hang") { hanging.push(this); return; }
          if (reply === "network-error") { this.onerror(); return; }
          this.respond(reply.body ?? {
            status: "success", pair_id: pairId, browser_receipt_id: receiptId,
            pair_status: "awaiting_app", ...reply,
          }, reply.httpStatus ?? 200);
        } else if (this.url === uploadUrl) {
          uploads.push(body);
          this.respond(response);
        } else {
          this.respond({});
        }
      }
    },
  };
  const context = vm.createContext({
    window, sessionStorage: window.sessionStorage, setTimeout: window.setTimeout,
    Date: class extends Date { static now() { return now; } },
    document: {
      getElementById: (id) => elements[id],
      createElement(tag) {
        if (tag !== "a") return {};
        const anchor = {};
        Object.defineProperty(anchor, "href", { set(value) {
          const url = new URL(value);
          anchor.protocol = url.protocol;
          anchor.hostname = url.hostname;
        } });
        return anchor;
      },
    },
  });
  async function flush() {
    for (let count = 0; count < 20; count += 1) await Promise.resolve();
  }
  vm.runInContext(source, context);
  start();
  await flush();
  return {
    status: () => elements.status.textContent,
    timers, queries, uploads, storage, hanging, collections: () => collections,
    async advance(ms) {
      const target = now + ms;
      while (true) {
        const next = [...timers.entries()].sort((a, b) => a[1].due - b[1].due)[0];
        if (!next || next[1].due > target) break;
        now = next[1].due;
        timers.delete(next[0]);
        next[1].callback();
        await flush();
      }
      now = target;
      await flush();
    },
  };
}

test("App-first completion uses the same final marker and never polls", async () => {
  const page = await createPage({ upload: { pair_status: "completed" } });
  assert.equal(page.status(), "本机采集完成");
  assert.equal(page.queries.length, 0);
  assert.equal(page.timers.size, 0);
  assert.equal(page.storage.size, 0);
});

test("browser-first page waits for this round's App then stops polling", async () => {
  const page = await createPage({ replies: [{}, { pair_status: "completed" }] });
  assert.match(page.status(), /waiting for app binding/);
  assert.ok(page.storage.has(storageKey + ":payload"));
  await page.advance(2000);
  assert.match(page.status(), /waiting for app binding/);
  await page.advance(2000);
  assert.equal(page.status(), "本机采集完成");
  assert.equal(page.queries[0].url, `${uploadUrl}/${pairId}/status`);
  assert.equal(page.queries[0].headers.Authorization, "Bearer this-round-ticket");
  assert.equal(page.queries[0].timeout, 12000);
  assert.equal(page.storage.size, 0);
  assert.equal(page.timers.size, 0);
  await page.advance(120000);
  assert.equal(page.queries.length, 2);
  assert.equal(page.uploads.length, 1);
});

test("refresh during pairing resends the cached payload without collecting again", async () => {
  const pending = await createPage();
  const refreshed = await createPage({
    storage: pending.storage, upload: { pair_status: "completed" },
  });
  assert.equal(refreshed.collections(), 0);
  assert.equal(refreshed.uploads[0], pending.uploads[0]);
  assert.equal(refreshed.status(), "本机采集完成");
});

test("missing App receipt times out and stops; it never reports success", async () => {
  const page = await createPage();
  await page.advance(120000);
  assert.match(page.status(), /^配对超时：/);
  assert.equal(page.timers.size, 0);
  const count = page.queries.length;
  await page.advance(120000);
  assert.equal(page.queries.length, count);
});

test("deadline fences a late completed response from a hung query", async () => {
  const page = await createPage({ replies: ["hang"] });
  await page.advance(120000);
  assert.match(page.status(), /^配对超时：/);
  page.hanging[0].respond({
    status: "success", pair_id: pairId, browser_receipt_id: receiptId, pair_status: "completed",
  });
  await page.advance(0);
  assert.match(page.status(), /^配对超时：/);
  assert.equal(page.timers.size, 0);
});

test("transient network errors recover; consecutive errors stop with a reason", async () => {
  const recovered = await createPage({ replies: ["network-error", { pair_status: "completed" }] });
  await recovered.advance(4000);
  assert.equal(recovered.status(), "本机采集完成");
  const failed = await createPage({ replies: ["network-error"] });
  await failed.advance(120000);
  assert.match(failed.status(), /^采集失败：无法确认配对状态/);
  assert.equal(failed.queries.length, 3);
  assert.equal(failed.timers.size, 0);
});

test("expired credentials and expired pairing have explicit timeout messages", async () => {
  for (const reply of [
    { httpStatus: 410, body: { detail: { code: "BROWSER_TOKEN_EXPIRED" } } },
    { pair_status: "expired" },
  ]) {
    const page = await createPage({ replies: [reply] });
    await page.advance(2000);
    assert.match(page.status(), /^配对超时：/);
    assert.equal(page.timers.size, 0);
  }
});

test("wrong round, wrong receipt, malformed and unknown states cannot complete", async () => {
  for (const reply of [
    { pair_id: "another-round", pair_status: "completed" },
    { browser_receipt_id: "another-receipt", pair_status: "completed" },
    { body: {} },
    { body: [] },
    { pair_status: "unknown" },
    { pair_status: "failed" },
    { httpStatus: 403, body: { detail: { code: "BROWSER_TOKEN_PAIR_MISMATCH" } } },
  ]) {
    const page = await createPage({ replies: [reply] });
    await page.advance(2000);
    assert.match(page.status(), /^采集失败：/);
    assert.equal(page.timers.size, 0);
  }
  for (const upload of [
    { pair_status: "unknown" },
    { pair_status: "completed", pair_id: "another-round" },
    { pair_status: "completed", receipt_id: null },
  ]) {
    const page = await createPage({ upload });
    assert.match(page.status(), /^采集失败：/);
    assert.equal(page.queries.length, 0);
  }
});
