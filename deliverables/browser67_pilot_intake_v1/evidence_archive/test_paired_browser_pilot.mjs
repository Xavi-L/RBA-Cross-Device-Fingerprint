import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { request } from 'node:http';
import { createHash } from 'node:crypto';
import { makeStages, readJsonl, safeStaticPath, createProbeServer, validateTarget,
  selectNewTicket, matchCompletedCapture, verifyObservation, CdpClient,
  evaluateChecked, installControl, restoreControl, verifyChromeDiscovery, validateInstalledApkPaths, managedProbeTarget, verifyCanonicalProbeIdentity } from './run_paired_browser_pilot.mjs';

function httpGet(port, path = '/browser-probe-adapter.js') {
  return new Promise((done, reject) => {
    const req = request({ hostname: '127.0.0.1', port, path }, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => done({ status: res.statusCode, bytes: Buffer.concat(chunks) }));
    });
    req.on('error', reject); req.end();
  });
}

async function temporarySite(t) {
  const root = await mkdtemp(join(tmpdir(), 'rba-gate-test-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const html = Buffer.from('<!doctype html>\r\n<script src="probe.js" defer></script>\r\n<script src="browser-probe-adapter.js" defer></script>\r\n✓');
  const adapter = Buffer.from("window.addEventListener('DOMContentLoaded', function () { sample(); });\r\n");
  await writeFile(join(root, 'browser-probe.html'), html);
  await writeFile(join(root, 'browser-probe-adapter.js'), adapter);
  await writeFile(join(root, 'probe.js'), 'globalThis.sampleStarted = true;');
  let held;
  const heldPromise = new Promise((done) => { held = done; });
  const records = [];
  const site = await createProbeServer(root, { port: 0,
    record: async (row) => { records.push(row); if (row.kind === 'gate_held') held(); } });
  t.after(async () => {
    site.gate.abort(); site.server.closeAllConnections();
    await new Promise((done) => site.server.close(done));
  });
  return { root, html, adapter, ...site, records, heldPromise, port: site.server.address().port };
}

test('pre-registered design has exactly 18 unique neutral App contexts in fixed order', async () => {
  const plan = JSON.parse(await readFile(new URL('./pilot_plan.json', import.meta.url), 'utf8'));
  const stages = makeStages(plan);
  assert.equal(stages.length, 18);
  assert.equal(new Set(stages.map((s) => s.runtime_context)).size, 18);
  assert.deepEqual(stages.slice(0, 3).map((s) => s.stage), ['clean_pre', 'attack_active', 'clean_post']);
  assert.deepEqual(stages.map((s) => s.collection_round), Array.from({ length: 18 }, (_, i) => i + 1));
  assert.ok(stages.every((s) => !/attack|clean|language|timezone/.test(s.runtime_context)));
});

test('HTML commits immediately, but adapter bytes wait until current-realm control succeeds', async (t) => {
  const site = await temporarySite(t);
  site.gate.arm('c0001');
  assert.deepEqual((await httpGet(site.port, '/browser-probe.html')).bytes, site.html);
  let responseFinished = false;
  const response = httpGet(site.port).then((result) => { responseFinished = true; return result; });
  await site.heldPromise;
  assert.equal(responseFinished, false);
  assert.equal(site.gate.state, 'armed');
  // The deferred adapter cannot run or allow DOMContentLoaded while its response is held.
  assert.equal(site.gate.pending.res.headersSent, false);
  const plan = JSON.parse(await readFile(new URL('./pilot_plan.json', import.meta.url), 'utf8'));
  const stage = makeStages(plan)[1];
  let installed = false;
  const client = { command: async (method, params) => {
    assert.equal(method, 'Runtime.evaluate');
    assert.equal(params.expression, stage.control.params.expression);
    assert.equal(site.gate.pending.res.headersSent, false);
    installed = true;
    return { result: { type: 'object' } };
  } };
  await installControl(client, stage, { languageHasOwn: false, languagesHasOwn: false });
  assert.equal(installed, true);
  await site.gate.release();
  const result = await response;
  assert.equal(result.status, 200);
  assert.deepEqual(result.bytes, site.adapter);
  assert.deepEqual(site.records.map((r) => r.kind), ['static_file_sent', 'gate_held', 'gate_released']);
  assert.equal(site.records[2].upstream_adapter_sha256,
    createHash('sha256').update(site.adapter).digest('hex'));
});

test('a second adapter request including an encoded alias fails closed before or after release', async (t) => {
  const site = await temporarySite(t);
  site.gate.arm('c0001');
  const held = httpGet(site.port);
  await site.heldPromise;
  assert.equal((await httpGet(site.port, '/browser%2Dprobe-adapter.js')).status, 503);
  await assert.rejects(site.gate.release(), { code: 'EXTRA_ADAPTER_REQUEST' });
  site.gate.abort();
  assert.equal((await held).status, 503);
  site.gate.arm('c0002');
  const next = httpGet(site.port);
  while (!site.gate.pending) await new Promise((done) => setTimeout(done, 1));
  await site.gate.release();
  assert.equal((await next).status, 200);
  assert.equal((await httpGet(site.port)).status, 503);
  assert.equal(site.gate.violation, 'EXTRA_ADAPTER_REQUEST');
});

test('static assets remain identical and encoded traversal/backslashes are rejected', async (t) => {
  const site = await temporarySite(t);
  const asset = await httpGet(site.port, '/probe.js');
  assert.equal(asset.status, 200);
  assert.equal(asset.bytes.toString(), 'globalThis.sampleStarted = true;');
  for (const path of ['/../secret', '/%2e%2e/secret', '/x/%2e%2e/secret', '/x%5csecret', '/%00', '/probe.js:secret']) {
    await assert.rejects(safeStaticPath(site.root, path));
    assert.equal((await httpGet(site.port, path)).status, 400);
  }
});

test('JSONL reader ignores a partial append but rejects corrupt complete evidence rows', async (t) => {
  const root = await mkdtemp(join(tmpdir(), 'rba-jsonl-test-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const file = join(root, 'rows.jsonl');
  await writeFile(file, '{"pair_id":"first"}\n{"pair_id":');
  assert.equal((await readJsonl(file)).length, 1);
  await writeFile(file, '{"pair_id":"first"}\ninvalid\n');
  await assert.rejects(readJsonl(file), { code: 'INVALID_JSONL' });
});

function target(pair = 'pair-new') {
  const fragment = new URLSearchParams({ pair_id: pair, browser_ticket: 'test-private-ticket',
    browser_upload_url: 'http://127.0.0.1:8000/api/collect/browser-fingerprint',
    browser_stage_url: 'http://127.0.0.1:8000/api/collect/browser-stage' });
  return { id: 'test-target', type: 'page', url: `http://localhost:8001/browser-probe.html#${fragment}`,
    webSocketDebuggerUrl: 'ws://127.0.0.1:9340/devtools/page/test-target' };
}

test('target requires exact ticket pair, local endpoints, and forwarded Chrome page socket', () => {
  assert.equal(validateTarget(target(), 'pair-new').id, 'test-target');
  assert.throws(() => validateTarget(target('old-pair'), 'pair-new'), { code: 'TARGET_PAIR_MISMATCH' });
  assert.throws(() => validateTarget({ ...target(), url: 'https://example.com/browser-probe.html' }, 'pair-new'),
    { code: 'NONLOCAL_TARGET' });
  assert.throws(() => validateTarget({ ...target(), webSocketDebuggerUrl: 'ws://remote:9340/devtools/page/x' }, 'pair-new'),
    { code: 'NONLOCAL_CDP' });
  const bad = target();
  bad.url = bad.url.replace('127.0.0.1%3A8000', 'evil.example%3A8000');
  assert.throws(() => validateTarget(bad, 'pair-new'), { code: 'NONLOCAL_TARGET' });
});

test('ticket selection uses a ledger row boundary and exact Chrome package, never most recent time', () => {
  const event = { event: 'provisional_ticket_issued', pair_id: 'pair-new', app_session_id: 'app-new',
    selected_browser_package: 'com.android.chrome', resolved_browser_package: 'com.android.chrome' };
  assert.equal(selectNewTicket([{ line: 1, value: { ...event, pair_id: 'old' } },
    { line: 2, value: event }], 1, 'com.android.chrome').pair_id, 'pair-new');
  assert.throws(() => selectNewTicket([{ line: 2, value: event },
    { line: 3, value: { ...event, pair_id: 'another' } }], 1, 'com.android.chrome'),
    { code: 'MULTIPLE_STAGE_TICKETS' });
  assert.throws(() => selectNewTicket([{ line: 2, value: { ...event, selected_browser_package: 'unknown' } }],
    1, 'com.android.chrome'), { code: 'NON_CHROME_PAIR' });
});

function fixture() {
  const stage = { runtime_context: 'rba-browser-pilot-api36:c0001', collection_round: 1 };
  const plan = { device_manifest_id: 'rba-browser-pilot-api36', browser_package: 'com.android.chrome' };
  const app = { session_id: 'app-new', receipt_id: 'app-receipt', payload_sha256: 'app-hash', collection_batch_id: 'batch',
    canonical_received_payload: { session_id: 'app-new', collection_manifest: {
      runtime_context: stage.runtime_context, device_manifest_id: plan.device_manifest_id, collection_round: 1 } } };
  const pair = { pair_id: 'pair-new', pair_status: 'completed', app_session_id: 'app-new', app_receipt_id: 'app-receipt',
    app_payload_sha256: 'app-hash', browser_session_id: 'browser-new', browser_receipt_id: 'browser-receipt',
    browser_payload_sha256: 'browser-hash', collection_batch_id: 'batch',
    selected_browser_package: plan.browser_package, resolved_browser_package: plan.browser_package };
  const browser = { ...pair, canonical_received_payload: { pair_id: 'pair-new', browser_session_id: 'browser-new' } };
  const wrap = (value) => ({ line: 1, value, line_sha256: 'row-hash' });
  return { stage, plan, apps: [wrap(app)], pairs: [wrap(pair)], browsers: [wrap(browser)],
    ticket: { pair_id: 'pair-new', app_session_id: 'app-new' } };
}

test('completed capture binds opaque context, round, App session/receipt/hash and browser exact pair', () => {
  const f = fixture();
  const matched = matchCompletedCapture(f.stage, f.plan, f.apps, f.pairs, f.browsers, f.ticket);
  assert.equal(matched.browser.value.browser_session_id, 'browser-new');
  f.browsers[0].value.browser_payload_sha256 = 'different-hash';
  assert.throws(() => matchCompletedCapture(f.stage, f.plan, f.apps, f.pairs, f.browsers, f.ticket),
    { code: 'RAW_BROWSER_MISMATCH' });
});

test('wrong slot and duplicate App captures are errors; incomplete pairs stay pending', () => {
  const f = fixture();
  assert.equal(matchCompletedCapture(f.stage, f.plan, f.apps, [], [], f.ticket), null);
  f.apps[0].value.canonical_received_payload.collection_manifest.collection_round = 2;
  assert.throws(() => matchCompletedCapture(f.stage, f.plan, f.apps, f.pairs, f.browsers, f.ticket),
    { code: 'APP_SLOT_MISMATCH' });
  f.apps.push(f.apps[0]);
  assert.throws(() => matchCompletedCapture(f.stage, f.plan, f.apps, f.pairs, f.browsers, f.ticket),
    { code: 'MULTIPLE_APP_CAPTURES' });
});

test('active and post are evaluated against fixed intervention and same-round baseline', () => {
  const control = { expected: { timezone_id: 'Asia/Tokyo', timezone_offset: -540 } };
  const baseline = { timezone_id: 'Asia/Shanghai', timezone_offset: -480 };
  verifyObservation({ stage: 'clean_pre', control }, baseline);
  verifyObservation({ stage: 'attack_active', control }, control.expected, baseline);
  verifyObservation({ stage: 'clean_post', control }, baseline, baseline);
  assert.throws(() => verifyObservation({ stage: 'attack_active', control }, baseline, baseline),
    { code: 'CONTROL_NOT_OBSERVED' });
  assert.throws(() => verifyObservation({ stage: 'clean_post', control }, control.expected, baseline),
    { code: 'RESTORATION_MISMATCH' });
  assert.throws(() => verifyObservation({ stage: 'clean_pre', control }, control.expected),
    { code: 'BASELINE_EQUALS_ATTACK' });
});

test('CDP records complete method/params and errors and rejects commands when socket closes', async () => {
  class FakeSocket {
    listeners = new Map();
    addEventListener(name, handler) { this.listeners.set(name, handler); }
    send(message) {
      const command = JSON.parse(message);
      queueMicrotask(() => this.listeners.get('message')({ data: JSON.stringify({ id: command.id,
        error: { code: -32602, message: 'invalid control' } }) }));
    }
    close() { this.listeners.get('close')(); }
  }
  const records = [];
  const socket = new FakeSocket();
  const client = new CdpClient(socket, async (record) => records.push(record));
  await assert.rejects(client.command('Emulation.setTimezoneOverride', { timezoneId: 'Asia/Tokyo' }),
    { code: 'CDP_COMMAND_FAILED' });
  assert.deepEqual(records[0].command.params, { timezoneId: 'Asia/Tokyo' });
  assert.equal(records[1].message.error.code, -32602);
  socket.send = () => queueMicrotask(() => socket.close());
  await assert.rejects(client.command('Page.enable'), { code: 'CDP_CLOSED' });
});

test('JavaScript exceptions and unknown original navigator properties refuse control installation', async () => {
  await assert.rejects(evaluateChecked({ command: async () => ({ exceptionDetails: { text: 'ReferenceError' } }) },
    { expression: 'invalid' }), { code: 'REALM_EXECUTION_EXCEPTION' });
  const plan = JSON.parse(await readFile(new URL('./pilot_plan.json', import.meta.url), 'utf8'));
  const stage = makeStages(plan)[1];
  let commands = 0;
  await assert.rejects(installControl({ command: async () => { commands++; } }, stage,
    { languageHasOwn: true, languagesHasOwn: false }), { code: 'UNEXPECTED_NAVIGATOR_OWN_PROPERTY' });
  assert.equal(commands, 0);
});

test('restoration refuses realm exceptions, remaining language properties, and closeTarget.success=false', async () => {
  const plan = JSON.parse(await readFile(new URL('./pilot_plan.json', import.meta.url), 'utf8'));
  const stage = makeStages(plan)[1];
  await assert.rejects(restoreControl({ command: async () => ({ exceptionDetails: { text: 'failed delete' } }) },
    stage, { id: 'own-target' }, true), { code: 'REALM_EXECUTION_EXCEPTION' });
  const badProof = { command: async () => ({ result: { value: { languageHasOwn: true, languagesHasOwn: false } } }) };
  await assert.rejects(restoreControl(badProof, stage, { id: 'own-target' }, true),
    { code: 'REALM_RESTORATION_FAILED' });
  const methods = [];
  const failedClose = { command: async (method) => {
    methods.push(method);
    if (method === 'Runtime.evaluate') return { result: { value: { languageHasOwn: false, languagesHasOwn: false } } };
    if (method === 'Target.closeTarget') return { success: false };
    return {};
  } };
  await assert.rejects(restoreControl(failedClose, stage, { id: 'own-target' }, true),
    { code: 'TARGET_CLOSE_FAILED' });
  assert.deepEqual(methods, ['Runtime.evaluate', 'Runtime.evaluate', 'Emulation.setTimezoneOverride', 'Target.closeTarget']);
});


test('fresh Chrome discovery rejects a wrong package or nonlocal browser debug socket', () => {
  const ready = { 'Android-Package': 'com.android.chrome', Browser: 'Chrome/133.0.6943.137',
    webSocketDebuggerUrl: 'ws://127.0.0.1:9340/devtools/browser' };
  assert.equal(verifyChromeDiscovery(ready, 'com.android.chrome'), ready);
  assert.throws(() => verifyChromeDiscovery({ ...ready, 'Android-Package': 'other.browser' },
    'com.android.chrome'), { code: 'CDP_NOT_CHROME' });
  assert.throws(() => verifyChromeDiscovery({ ...ready, webSocketDebuggerUrl: 'ws://remote:9340/devtools/browser' },
    'com.android.chrome'), { code: 'NONLOCAL_CDP' });
});


test('installed collector proof accepts one base APK and rejects split or escaped paths', () => {
  assert.equal(validateInstalledApkPaths('package:/data/app/~~opaque/com.example/base.apk\n'),
    '/data/app/~~opaque/com.example/base.apk');
  assert.throws(() => validateInstalledApkPaths('package:/data/app/../base.apk\n'),
    { code: 'INSTALLED_APK_PATH_INVALID' });
  assert.throws(() => validateInstalledApkPaths('package:/data/app/p/base.apk\npackage:/data/app/p/split.apk\n'),
    { code: 'INSTALLED_APK_SPLITS' });
});


test('unique loopback warmup is inert and never requests or arms the probe gate', async (t) => {
  const site = await temporarySite(t);
  const result = await httpGet(site.port, '/pilot-warmup.html?context=opaque');
  assert.equal(result.status, 200);
  assert.doesNotMatch(result.bytes.toString(), /<script|fetch\(|collect\(/);
  assert.match(result.bytes.toString(), /default-src 'none'/);
  assert.equal(site.gate.state, 'idle');
  assert.equal(site.gate.pending, null);
  assert.equal(site.records[0].kind, 'warmup_file_sent');
});


test('restoration closes the exact page on a separate surviving browser CDP channel', async () => {
  const pageMethods = [];
  const browserMethods = [];
  const page = { command: async (method) => { pageMethods.push(method); return {}; } };
  const browser = { command: async (method, params) => { browserMethods.push({ method, params }); return { success: true }; } };
  const result = await restoreControl(page, { stage: 'clean_pre', control: {} },
    { id: 'exact-owned-page' }, true, browser);
  assert.deepEqual(pageMethods, ['Emulation.setTimezoneOverride']);
  assert.deepEqual(browserMethods, [{ method: 'Target.closeTarget', params: { targetId: 'exact-owned-page' } }]);
  assert.equal(result.at(-1).result.success, true);
});


test('stale cleanup only owns loopback experiment probe and inert warmup pages', () => {
  assert.equal(managedProbeTarget({ type: 'page', url: 'http://127.0.0.1:8001/browser-probe.html#old' }), true);
  assert.equal(managedProbeTarget({ type: 'page', url: 'http://localhost:8001/pilot-warmup.html?old=1' }), true);
  for (const url of ['https://example.com/browser-probe.html', 'http://127.0.0.1:8000/browser-probe.html',
    'about:blank', 'http://127.0.0.1:8001/unrelated.html']) {
    assert.equal(managedProbeTarget({ type: 'page', url }), false);
  }
  assert.equal(managedProbeTarget({ type: 'worker', url: 'http://127.0.0.1:8001/browser-probe.html' }), false);
});


test('canonical source check rejects CRLF bytes even when semantic code and declared revision match', () => {
  const lfHash = 'a'.repeat(64);
  const plan = { canonical_probe_sha256: lfHash };
  const descriptor = { sha256: lfHash, revision: 'expanded-web-67-v2' };
  const core = { sha256: lfHash, byte_count: 37674 };
  const build = { apk: { sha256: 'c'.repeat(64) }, packaged_probe_assets: [{ asset: 'assets/canonical_web_probe.js', sha256: lfHash, bytes: 37674, matches_source: true }], probe_source_identity: { git_blob_sha256: lfHash, apk_asset_sha256: lfHash,
    canonical_source_sha256: lfHash, browser_core_sha256: lfHash, all_equal: true } };
  assert.equal(verifyCanonicalProbeIdentity(plan, descriptor, core, core, build, build.apk).sha256, lfHash);
  assert.throws(() => verifyCanonicalProbeIdentity(plan, descriptor, { sha256: 'b'.repeat(64) }, core, build, build.apk),
    { code: 'PROBE_SOURCE_IDENTITY_MISMATCH' });
  assert.throws(() => verifyCanonicalProbeIdentity(plan, descriptor, core, core,
    { ...build, probe_source_identity: { ...build.probe_source_identity, apk_asset_sha256: 'b'.repeat(64) } }, build.apk),
    { code: 'PROBE_SOURCE_IDENTITY_MISMATCH' });
  assert.throws(() => verifyCanonicalProbeIdentity(plan, descriptor, core, core, build, { sha256: 'd'.repeat(64) }),
    { code: 'PROBE_SOURCE_IDENTITY_MISMATCH' });
  assert.throws(() => verifyCanonicalProbeIdentity(plan, descriptor, core, core,
    { ...build, packaged_probe_assets: [{ ...build.packaged_probe_assets[0], sha256: 'b'.repeat(64) }] }, build.apk),
    { code: 'PROBE_SOURCE_IDENTITY_MISMATCH' });
});
