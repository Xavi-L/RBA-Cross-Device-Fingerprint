import { createServer } from 'node:http';
import { readFile, appendFile, mkdir, realpath, stat, writeFile } from 'node:fs/promises';
import { resolve, relative, isAbsolute, sep, dirname, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);
const HERE = dirname(fileURLToPath(import.meta.url));
const delay = (ms) => new Promise((done) => setTimeout(done, ms));
const now = () => new Date().toISOString();
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
const WARMUP_HTML = Buffer.from('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; base-uri \'none\'; form-action \'none\'"><title>Local Chrome startup</title><p>Local browser startup check.</p>');

export class PilotError extends Error {
  constructor(code, message = code) { super(message); this.code = code; }
}

export function makeStages(plan) {
  const stages = [];
  for (const control of plan.controls) {
    for (let repeat = 1; repeat <= plan.rounds_per_configuration; repeat++) {
      for (const stage of plan.stage_order) {
        const index = stages.length + 1;
        const captureId = `c${String(index).padStart(4, '0')}`;
        stages.push({ capture_id: captureId, configuration_id: control.configuration_id,
          repeat, stage, collection_round: index,
          runtime_context: `${plan.device_manifest_id}:${captureId}`, control });
      }
    }
  }
  return stages;
}

export async function readJsonl(file) {
  let bytes;
  try { bytes = await readFile(file); }
  catch (error) { if (error.code === 'ENOENT') return []; throw error; }
  const rows = [];
  // A backend append may be visible before its final newline: never parse it early.
  const lines = bytes.toString('utf8').split('\n');
  for (let index = 0; index < lines.length - 1; index++) {
    if (!lines[index].trim()) continue;
    try {
      rows.push({ line: index + 1, value: JSON.parse(lines[index]),
        line_sha256: sha256(Buffer.from(lines[index], 'utf8')) });
    } catch { throw new PilotError('INVALID_JSONL', `Invalid complete JSONL row ${index + 1}`); }
  }
  return rows;
}

export async function safeStaticPath(root, rawUrl) {
  let decoded;
  try { decoded = decodeURIComponent(String(rawUrl).split('?')[0]); }
  catch { throw new PilotError('INVALID_PATH'); }
  if (!decoded.startsWith('/') || /[\\\0:]/.test(decoded)) throw new PilotError('INVALID_PATH');
  const parts = decoded.split('/').filter(Boolean);
  if (parts.some((part) => part === '..' || part.startsWith('.'))) throw new PilotError('PATH_ESCAPE');
  const rootReal = await realpath(root);
  const candidate = resolve(rootReal, ...parts);
  const relativePath = relative(rootReal, candidate);
  if (relativePath.startsWith(`..${sep}`) || relativePath === '..' || isAbsolute(relativePath)) {
    throw new PilotError('PATH_ESCAPE');
  }
  const candidateReal = await realpath(candidate);
  const realRelative = relative(rootReal, candidateReal);
  if (realRelative === '..' || realRelative.startsWith(`..${sep}`) || isAbsolute(realRelative)) {
    throw new PilotError('PATH_ESCAPE');
  }
  if (!(await stat(candidateReal)).isFile()) throw new PilotError('NOT_A_FILE');
  return candidateReal;
}

export class AdapterGate {
  constructor(adapterBytes, record = async () => {}) {
    this.adapterBytes = adapterBytes;
    this.record = record;
    this.state = 'idle';
    this.pending = null;
    this.violation = null;
  }
  arm(captureId) {
    if (this.pending) throw new PilotError('GATE_PENDING');
    this.captureId = captureId;
    this.state = 'armed';
    this.violation = null;
  }
  async hold(req, res) {
    if (this.state !== 'armed' || this.pending) {
      this.violation = 'EXTRA_ADAPTER_REQUEST';
      await this.record({ kind: 'gate_rejected', capture_id: this.captureId, at: now() });
      res.writeHead(503); res.end('Pilot gate unavailable');
      return;
    }
    this.pending = { req, res };
    await this.record({ kind: 'gate_held', capture_id: this.captureId, at: now(),
      path: '/browser-probe-adapter.js', upstream_adapter_sha256: sha256(this.adapterBytes) });
  }
  async release() {
    if (!this.pending || this.state !== 'armed') throw new PilotError('GATE_NOT_PENDING');
    if (this.violation) throw new PilotError(this.violation);
    const { res } = this.pending;
    if (res.destroyed) throw new PilotError('GATE_REQUEST_CLOSED');
    this.state = 'released';
    await this.record({ kind: 'gate_released', capture_id: this.captureId, at: now(),
      upstream_adapter_sha256: sha256(this.adapterBytes), response_byte_count: this.adapterBytes.length });
    res.writeHead(200, { 'content-type': 'text/javascript; charset=utf-8',
      'content-length': this.adapterBytes.length, 'cache-control': 'no-store' });
    res.end(this.adapterBytes);
    this.pending = null;
  }
  abort() {
    this.state = 'aborted';
    if (this.pending) {
      this.pending.res.writeHead(503); this.pending.res.end('Pilot stage aborted');
      this.pending = null;
    }
  }
}

export async function createProbeServer(publicRoot, { host = '127.0.0.1', port = 8001,
  record = async () => {} } = {}) {
  const adapterPath = await safeStaticPath(publicRoot, '/browser-probe-adapter.js');
  const adapterBytes = await readFile(adapterPath);
  const gate = new AdapterGate(adapterBytes, record);
  const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8', '.css': 'text/css; charset=utf-8' };
  const server = createServer(async (req, res) => {
    try {
      if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return; }
      if (req.url.split('?')[0] === '/pilot-warmup.html') {
        await record({ kind: 'warmup_file_sent', at: now(), url: req.url,
          byte_count: WARMUP_HTML.length, sha256: sha256(WARMUP_HTML) });
        res.writeHead(200, { 'content-type': 'text/html; charset=utf-8',
          'content-length': WARMUP_HTML.length, 'cache-control': 'no-store' });
        res.end(req.method === 'HEAD' ? undefined : WARMUP_HTML);
        return;
      }
      const file = await safeStaticPath(publicRoot, req.url);
      if (file === adapterPath && req.method === 'GET') {
        await gate.hold(req, res); return;
      }
      const bytes = await readFile(file);
      await record({ kind: 'static_file_sent', at: now(), capture_id: gate.captureId || null,
        public_path: relative(await realpath(publicRoot), file).split(sep).join('/'),
        byte_count: bytes.length, sha256: sha256(bytes) });
      res.writeHead(200, { 'content-type': mime[extname(file)] || 'application/octet-stream',
        'content-length': bytes.length, 'cache-control': 'no-store' });
      res.end(req.method === 'HEAD' ? undefined : bytes);
    } catch (error) {
      await record({ kind: 'static_error', at: now(), code: error.code || 'STATIC_ERROR' });
      if (!res.headersSent) res.writeHead(error.code === 'ENOENT' ? 404 : 400);
      res.end();
    }
  });
  await new Promise((done, reject) => {
    server.once('error', reject); server.listen(port, host, done);
  });
  return { server, gate, adapterBytes };
}

function requireLocalUrl(value, port, path) {
  const url = new URL(value);
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname)
    || url.port !== String(port) || url.username || url.password || (path && url.pathname !== path)) {
    throw new PilotError('NONLOCAL_TARGET');
  }
  return url;
}

export function validateTarget(target, expectedPairId) {
  if (target.type !== 'page') throw new PilotError('NOT_PAGE_TARGET');
  const url = requireLocalUrl(target.url, 8001, '/browser-probe.html');
  const fragment = new URLSearchParams(url.hash.slice(1));
  if (fragment.get('pair_id') !== expectedPairId || !fragment.get('browser_ticket')) {
    throw new PilotError('TARGET_PAIR_MISMATCH');
  }
  requireLocalUrl(fragment.get('browser_upload_url'), 8000, '/api/collect/browser-fingerprint');
  requireLocalUrl(fragment.get('browser_stage_url'), 8000, '/api/collect/browser-stage');
  const ws = new URL(target.webSocketDebuggerUrl);
  if (ws.protocol !== 'ws:' || !['127.0.0.1', 'localhost'].includes(ws.hostname)
    || ws.port !== '9340' || !ws.pathname.startsWith('/devtools/page/') || ws.username || ws.password) {
    throw new PilotError('NONLOCAL_CDP');
  }
  return target;
}

export function selectNewTicket(rows, baselineLine, chromePackage) {
  const issued = rows.filter(({ line, value }) => line > baselineLine
    && ['ticket_issued', 'provisional_ticket_issued'].includes(value.event));
  const unique = new Map(issued.map(({ value }) => [value.pair_id, value]));
  if (unique.size > 1) throw new PilotError('MULTIPLE_STAGE_TICKETS');
  if (!unique.size) return null;
  const ticket = [...unique.values()][0];
  if (ticket.selected_browser_package !== chromePackage || ticket.resolved_browser_package !== chromePackage) {
    throw new PilotError('NON_CHROME_PAIR');
  }
  return ticket;
}

export function matchCompletedCapture(stage, plan, appRows, pairRows, browserRows, ticket) {
  const apps = appRows.filter(({ value }) => {
    const manifest = value.canonical_received_payload?.collection_manifest;
    return manifest?.runtime_context === stage.runtime_context;
  });
  if (apps.length > 1) throw new PilotError('MULTIPLE_APP_CAPTURES');
  if (!apps.length) return null;
  const app = apps[0];
  const manifest = app.value.canonical_received_payload.collection_manifest;
  if (manifest.device_manifest_id !== plan.device_manifest_id
    || manifest.collection_round !== stage.collection_round
    || app.value.session_id !== ticket.app_session_id
    || app.value.canonical_received_payload.session_id !== ticket.app_session_id) {
    throw new PilotError('APP_SLOT_MISMATCH');
  }
  const pairs = pairRows.filter(({ value }) => value.pair_id === ticket.pair_id);
  if (pairs.length > 1) throw new PilotError('MULTIPLE_COMPLETED_PAIRS');
  if (!pairs.length) return null;
  const pair = pairs[0];
  const p = pair.value;
  if (p.pair_status !== 'completed' || p.app_session_id !== app.value.session_id
    || p.app_receipt_id !== app.value.receipt_id || p.app_payload_sha256 !== app.value.payload_sha256
    || p.selected_browser_package !== plan.browser_package
    || p.resolved_browser_package !== plan.browser_package
    || p.collection_batch_id !== app.value.collection_batch_id) {
    throw new PilotError('PROVENANCE_MISMATCH');
  }
  const browsers = browserRows.filter(({ value }) => value.pair_id === p.pair_id);
  if (browsers.length > 1) throw new PilotError('MULTIPLE_BROWSER_CAPTURES');
  if (!browsers.length) return null;
  const browser = browsers[0];
  const b = browser.value;
  const raw = b.canonical_received_payload;
  if (b.app_session_id !== p.app_session_id || b.app_receipt_id !== p.app_receipt_id
    || b.browser_session_id !== p.browser_session_id || b.browser_receipt_id !== p.browser_receipt_id
    || b.browser_payload_sha256 !== p.browser_payload_sha256 || b.collection_batch_id !== p.collection_batch_id
    || raw?.pair_id !== p.pair_id || raw?.browser_session_id !== p.browser_session_id) {
    throw new PilotError('RAW_BROWSER_MISMATCH');
  }
  return { app, pair, browser };
}

export function observedValues(raw) {
  return { language: raw.web_data?.navigator_layer?.language,
    languages: raw.web_data?.navigator_layer?.languages,
    timezone_id: raw.web_data?.execution_layer?.timezone_id,
    timezone_offset: raw.web_data?.execution_layer?.timezone_offset };
}

export function verifyObservation(stage, observed, preValues) {
  const keys = Object.keys(stage.control.expected);
  const expected = stage.stage === 'attack_active' ? stage.control.expected
    : (stage.stage === 'clean_post' ? preValues : null);
  if (keys.some((key) => observed[key] === undefined || observed[key] === null)) {
    throw new PilotError('CONTROL_FIELD_UNOBSERVED');
  }
  if (stage.stage === 'clean_pre' && keys.every((key) =>
    JSON.stringify(observed[key]) === JSON.stringify(stage.control.expected[key]))) {
    throw new PilotError('BASELINE_EQUALS_ATTACK');
  }
  if (expected && keys.some((key) => JSON.stringify(observed[key]) !== JSON.stringify(expected[key]))) {
    throw new PilotError(stage.stage === 'clean_post' ? 'RESTORATION_MISMATCH' : 'CONTROL_NOT_OBSERVED');
  }
}

class Ledger {
  constructor(file) { this.file = file; this.chain = Promise.resolve(); }
  append(row) {
    this.chain = this.chain.then(() => appendFile(this.file, `${JSON.stringify(row)}\n`, { mode: 0o600 }));
    return this.chain;
  }
}

export class CdpClient {
  constructor(socket, record) {
    this.socket = socket; this.record = record; this.sequence = 0; this.pending = new Map();
    socket.addEventListener('message', (event) => {
      let msg;
      try { msg = JSON.parse(String(event.data)); }
      catch { this.failAll(new PilotError('INVALID_CDP_MESSAGE')); return; }
      void this.record({ kind: 'cdp_received', at: now(), message: msg });
      if (msg.id) {
        const pending = this.pending.get(msg.id);
        if (pending) {
          clearTimeout(pending.timer); this.pending.delete(msg.id);
          if (msg.error) pending.reject(new PilotError('CDP_COMMAND_FAILED', JSON.stringify(msg.error)));
          else pending.resolve(msg.result);
        }
      }
    });
    socket.addEventListener('close', () => this.failAll(new PilotError('CDP_CLOSED')));
    socket.addEventListener('error', () => this.failAll(new PilotError('CDP_SOCKET_ERROR')));
  }
  failAll(error) {
    for (const item of this.pending.values()) { clearTimeout(item.timer); item.reject(error); }
    this.pending.clear();
  }
  static async connect(url, record) {
    const socket = new WebSocket(url);
    await new Promise((done, reject) => {
      const timer = setTimeout(() => { socket.close(); reject(new PilotError('CDP_CONNECT_TIMEOUT')); }, 10000);
      socket.addEventListener('open', () => { clearTimeout(timer); done(); }, { once: true });
      socket.addEventListener('error', () => { clearTimeout(timer); reject(new PilotError('CDP_CONNECT_FAILED')); }, { once: true });
    });
    return new CdpClient(socket, (row) => record({ ...row, cdp_channel: url }));
  }
  async command(method, params = {}) {
    const id = ++this.sequence;
    const sent = { id, method, params };
    await this.record({ kind: 'cdp_sent', at: now(), command: sent });
    return new Promise((done, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id); reject(new PilotError('CDP_COMMAND_TIMEOUT', method));
      }, 10000);
      this.pending.set(id, { resolve: done, reject, timer });
      try { this.socket.send(JSON.stringify(sent)); }
      catch (error) { clearTimeout(timer); this.pending.delete(id); reject(error); }
    });
  }
  close() { this.socket.close(); }
}

export async function evaluateChecked(cdp, params) {
  const result = await cdp.command('Runtime.evaluate', params);
  if (result?.exceptionDetails) {
    throw new PilotError('REALM_EXECUTION_EXCEPTION',
      result.exceptionDetails.exception?.description || result.exceptionDetails.text || 'Realm execution failed');
  }
  return result;
}

async function waitForCommittedRealm(cdp, target, ticket, gate) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    if (gate.violation) throw new PilotError(gate.violation);
    const result = await evaluateChecked(cdp, { returnByValue: true,
      expression: "({href:location.href,readyState:document.readyState,coreRevision:globalThis.HybridGuardWebProbe?.REVISION,languageHasOwn:Object.prototype.hasOwnProperty.call(navigator,'language'),languagesHasOwn:Object.prototype.hasOwnProperty.call(navigator,'languages')})" });
    const realm = result?.result?.value;
    if (realm?.readyState === 'interactive' && realm.coreRevision) {
      validateTarget({ ...target, url: realm.href }, ticket.pair_id);
      return realm;
    }
    if (realm?.readyState === 'complete') throw new PilotError('ADAPTER_GATE_TOO_LATE');
    await delay(100);
  }
  throw new PilotError('COMMITTED_REALM_WAIT_TIMEOUT');
}

export async function installControl(cdp, stage, realm) {
  if (stage.stage !== 'attack_active') {
    const result = await cdp.command('Emulation.setTimezoneOverride', { timezoneId: '' });
    return { method: 'none', fresh_chrome_process: true, timezone_reset_result: result };
  }
  if (stage.control.method === 'Runtime.evaluate') {
    if (realm.languageHasOwn || realm.languagesHasOwn) throw new PilotError('UNEXPECTED_NAVIGATOR_OWN_PROPERTY');
    return { method: stage.control.method, params: stage.control.params,
      original_own_property_proof: { language: realm.languageHasOwn, languages: realm.languagesHasOwn },
      result: await evaluateChecked(cdp, stage.control.params) };
  }
  return { method: stage.control.method, params: stage.control.params,
    result: await cdp.command(stage.control.method, stage.control.params) };
}

export async function restoreControl(cdp, stage, target, pairCompleted, closeClient = cdp) {
  const restoration = [];
  if (stage.stage === 'attack_active' && stage.control.method === 'Runtime.evaluate') {
    restoration.push({ method: 'Runtime.evaluate', params: stage.control.restoration,
      result: await evaluateChecked(cdp, stage.control.restoration) });
    const proof = await evaluateChecked(cdp, { returnByValue: true,
      expression: "({languageHasOwn:Object.prototype.hasOwnProperty.call(navigator,'language'),languagesHasOwn:Object.prototype.hasOwnProperty.call(navigator,'languages')})" });
    if (proof.result?.value?.languageHasOwn !== false || proof.result?.value?.languagesHasOwn !== false) {
      throw new PilotError('REALM_RESTORATION_FAILED');
    }
    restoration.push({ method: 'Runtime.evaluate', own_property_restoration_proof: proof.result.value });
  }
  restoration.push({ method: 'Emulation.setTimezoneOverride', params: { timezoneId: '' },
    result: await cdp.command('Emulation.setTimezoneOverride', { timezoneId: '' }) });
  if (pairCompleted && target) {
    const params = { targetId: target.id };
    const result = await closeClient.command('Target.closeTarget', params);
    if (result?.success !== true) throw new PilotError('TARGET_CLOSE_FAILED');
    restoration.push({ method: 'Target.closeTarget', params, result });
  }
  return restoration;
}

async function adb(options, args, record) {
  await record({ kind: 'adb_sent', at: now(), args: ['-s', options.plan.serial, ...args] });
  const result = await execFileAsync(options.adb, ['-s', options.plan.serial, ...args],
    { windowsHide: true, timeout: 15000, maxBuffer: 1024 * 1024 });
  await record({ kind: 'adb_received', at: now(), args, stdout: result.stdout, stderr: result.stderr });
  return result.stdout;
}

export function verifyChromeDiscovery(discovery, browserPackage) {
  if (discovery['Android-Package'] !== browserPackage
    || !/^(Chrome|HeadlessChrome)\//.test(discovery.Browser || '')) {
    throw new PilotError('CDP_NOT_CHROME');
  }
  const ws = new URL(discovery.webSocketDebuggerUrl);
  if (ws.protocol !== 'ws:' || !['127.0.0.1', 'localhost'].includes(ws.hostname)
    || ws.port !== '9340' || ws.pathname !== '/devtools/browser' || ws.username || ws.password) {
    throw new PilotError('NONLOCAL_CDP');
  }
  return discovery;
}

export async function waitForChromeReady(options, record, prewarmUrl) {
  const end = Date.now() + options.plan.debug_wait_ms;
  let lastTransportFailure = null;
  while (Date.now() < end) {
    try {
      const response = await fetch(`${options.plan.cdp_origin}/json/version`,
        { signal: AbortSignal.timeout(2000) });
      if (response.ok) {
        const discovery = verifyChromeDiscovery(await response.json(), options.plan.browser_package);
        await record({ kind: 'fresh_chrome_ready', at: now(), discovery,
          prewarm_url: prewarmUrl, rationale: 'Complete fresh Chrome startup before holding any probe adapter.' });
        return discovery;
      }
    } catch (error) {
      if (error instanceof PilotError) throw error;
      lastTransportFailure = error.cause?.code || error.name;
    }
    await delay(150);
  }
  await record({ kind: 'chrome_startup_timeout', at: now(), last_transport_failure: lastTransportFailure });
  throw new PilotError('CHROME_STARTUP_TIMEOUT');
}

export function managedProbeTarget(target) {
  if (target.type !== 'page') return false;
  try {
    const url = requireLocalUrl(target.url, 8001);
    return ['/browser-probe.html', '/pilot-warmup.html'].includes(url.pathname);
  } catch { return false; }
}

async function closeExactWarmupTarget(options, prewarmUrl, record, browserClient) {
  const end = Date.now() + options.plan.debug_wait_ms;
  while (Date.now() < end) {
    const response = await fetch(`${options.plan.cdp_origin}/json/list`,
      { signal: AbortSignal.timeout(2000) });
    if (response.ok) {
      const allTargets = await response.json();
      const targets = allTargets.filter((target) => target.type === 'page' && target.url === prewarmUrl);
      if (targets.length > 1) throw new PilotError('MULTIPLE_WARMUP_TARGETS');
      if (targets.length === 1) {
        const target = targets[0];
        // Keep the inert warmup selected while closing only our old loopback experiment
        // tabs. Otherwise Chrome selects a stale probe and reloads it into the next gate.
        const staleTargets = allTargets.filter((item) => item.id !== target.id && managedProbeTarget(item));
        const staleCleanup = [];
        for (const stale of staleTargets) {
          const result = await browserClient.command('Target.closeTarget', { targetId: stale.id });
          if (result.success !== true) throw new PilotError('STALE_PROBE_CLOSE_FAILED');
          const item = { target_id: stale.id, url: stale.url, result };
          staleCleanup.push(item);
          await record({ kind: 'stale_managed_target_closed', at: now(), ...item });
        }
        const ws = new URL(target.webSocketDebuggerUrl);
        if (ws.protocol !== 'ws:' || !['127.0.0.1', 'localhost'].includes(ws.hostname)
          || ws.port !== '9340' || !ws.pathname.startsWith('/devtools/page/') || ws.username || ws.password) {
          throw new PilotError('NONLOCAL_CDP');
        }
        const pid = (await adb(options, ['shell', 'pidof', options.plan.browser_package], record)).trim();
        if (!/^\d+(?: \d+)*$/.test(pid)) throw new PilotError('CHROME_NOT_RUNNING');
        const result = await browserClient.command('Target.closeTarget', { targetId: target.id });
        if (result.success !== true) throw new PilotError('WARMUP_TARGET_CLOSE_FAILED');
        const remaining = await (await fetch(`${options.plan.cdp_origin}/json/list`,
          { signal: AbortSignal.timeout(2000) })).json();
        if (remaining.some(managedProbeTarget)) throw new PilotError('MANAGED_PROBE_REMAINING');
        const proof = { url: prewarmUrl, target_id: target.id, chrome_pid: pid, close_result: result,
          command_channel: 'browser', stale_cleanup: staleCleanup,
          remaining_managed_probe_count: 0 };
        await record({ kind: 'warmup_target_closed', at: now(), ...proof });
        return proof;
      }
    }
    await delay(150);
  }
  throw new PilotError('WARMUP_TARGET_WAIT_TIMEOUT');
}

export function validateInstalledApkPaths(stdout) {
  const paths = stdout.trim().split(/\r?\n/).filter(Boolean).map((line) => {
    if (!/^package:\/data\/app\/[^\s]+\.apk$/.test(line) || line.includes('..')) {
      throw new PilotError('INSTALLED_APK_PATH_INVALID');
    }
    return line.slice('package:'.length);
  });
  // The local debug build is a monolithic APK. A split install is a different collector.
  if (paths.length !== 1 || !paths[0].endsWith('/base.apk')) throw new PilotError('INSTALLED_APK_SPLITS');
  return paths[0];
}

async function waitForTarget(options, stage, gate, record, baselineLine) {
  const end = Date.now() + options.plan.debug_wait_ms;
  while (Date.now() < end) {
    if (gate.violation) throw new PilotError(gate.violation);
    const rows = await readJsonl(resolve(options.data, 'browser_pair_events.jsonl'));
    const ticket = selectNewTicket(rows, baselineLine, options.plan.browser_package);
    if (ticket && gate.pending) {
      try {
        const response = await fetch(`${options.plan.cdp_origin}/json/list`,
          { signal: AbortSignal.timeout(2000) });
        if (response.ok) {
          const targets = await response.json();
          const selected = targets.filter((target) => {
            try { validateTarget(target, ticket.pair_id); return true; } catch { return false; }
          });
          if (selected.length > 1) throw new PilotError('MULTIPLE_PAIR_TARGETS');
          if (selected.length === 1) {
            if (targets.filter(managedProbeTarget).length !== 1) throw new PilotError('MULTIPLE_MANAGED_PROBE_TARGETS');
            await record({ kind: 'target_selected', at: now(), capture_id: stage.capture_id,
              ticket, target: selected[0] });
            return { target: selected[0], ticket };
          }
        }
      } catch (error) {
        if (error instanceof PilotError) throw error;
        // Chrome's socket appears after process startup. Poll only the loopback forward.
      }
    }
    await delay(150);
  }
  throw new PilotError('TARGET_WAIT_TIMEOUT');
}

async function waitForPair(options, stage, ticket, gate) {
  const end = Date.now() + options.plan.collection_wait_ms;
  while (Date.now() < end) {
    if (gate.violation) throw new PilotError(gate.violation);
    const [apps, pairs, browsers] = await Promise.all([
      readJsonl(resolve(options.data, 'raw_expanded_payloads.jsonl')),
      readJsonl(resolve(options.data, 'browser_pair_provenance.jsonl')),
      readJsonl(resolve(options.data, 'raw_browser_payloads.jsonl')),
    ]);
    const matched = matchCompletedCapture(stage, options.plan, apps, pairs, browsers, ticket);
    if (matched) {
      if (gate.violation) throw new PilotError(gate.violation);
      return matched;
    }
    await delay(200);
  }
  throw new PilotError('PAIR_WAIT_TIMEOUT');
}

async function fileIdentity(file) {
  const bytes = await readFile(file);
  return { path: resolve(file), byte_count: bytes.length, sha256: sha256(bytes) };
}

export function verifyCanonicalProbeIdentity(plan, descriptor, browserCore, canonicalCore, buildManifest, apkIdentity) {
  const expected = plan.canonical_probe_sha256;
  const packaged = buildManifest?.probe_source_identity;
  const packagedCore = buildManifest?.packaged_probe_assets?.find((item) => item.asset === 'assets/canonical_web_probe.js');
  if (!/^[a-f0-9]{64}$/.test(expected || '') || descriptor.sha256 !== expected
    || browserCore.sha256 !== expected || canonicalCore.sha256 !== expected
    || packaged?.git_blob_sha256 !== expected || packaged?.apk_asset_sha256 !== expected
    || packaged?.canonical_source_sha256 !== expected || packaged?.browser_core_sha256 !== expected
    || packaged?.all_equal !== true || packagedCore?.sha256 !== expected
    || packagedCore?.matches_source !== true || packagedCore?.bytes !== canonicalCore.byte_count
    || !apkIdentity?.sha256
    || buildManifest?.apk?.sha256 !== apkIdentity.sha256) {
    throw new PilotError('PROBE_SOURCE_IDENTITY_MISMATCH');
  }
  return { sha256: expected, descriptor_revision: descriptor.revision,
    browser_core: browserCore, canonical_core: canonicalCore, packaged_apk_core: packaged };
}

export async function preflight(options) {
  const plan = JSON.parse(await readFile(options.planPath, 'utf8'));
  const stages = makeStages(plan);
  if (plan.planned_stage_count !== 18 || stages.length !== 18
    || plan.rounds_per_configuration !== 3 || plan.controls.length !== 2
    || plan.controls.map((c) => c.configuration_id).join(',') !== 'language_fr,timezone_tokyo') {
    throw new PilotError('PLAN_INVALID');
  }
  if (typeof WebSocket !== 'function') throw new PilotError('NODE_WEBSOCKET_UNAVAILABLE');
  requireLocalUrl(plan.static_origin, 8001);
  requireLocalUrl(plan.collect_endpoint, 8000, '/api/collect/fingerprint');
  requireLocalUrl(plan.cdp_origin, 9340);
  const files = ['browser-probe.html', 'browser-probe-bootstrap.js', 'browser-probe-adapter.js',
    'probe/canonical_web_probe.js', 'probe/manifest.json'];
  const sourceFiles = [];
  for (const name of files) sourceFiles.push(await fileIdentity(resolve(options.publicRoot, name)));
  const buildManifest = options.buildManifest ? JSON.parse(await readFile(options.buildManifest, 'utf8')) : null;
  const descriptor = JSON.parse(await readFile(resolve(options.publicRoot, 'probe/manifest.json'), 'utf8'));
  const canonicalCore = await fileIdentity(resolve(HERE, 'upstream/web_probe/canonical_web_probe.js'));
  const browserCore = sourceFiles.find((item) => item.path === resolve(options.publicRoot, 'probe/canonical_web_probe.js'));
  const apkIdentity = options.apk ? await fileIdentity(options.apk) : null;
  const coreIdentity = verifyCanonicalProbeIdentity(plan, descriptor, browserCore, canonicalCore, buildManifest, apkIdentity);
  const identity = { schema_version: 'browser67-pilot-run-manifest-v1', created_at: now(),
    plan_sha256: (await fileIdentity(options.planPath)).sha256,
    runner_sha256: (await fileIdentity(fileURLToPath(import.meta.url))).sha256,
    source_commit: plan.source_commit, stages: stages.map(({ control, ...stage }) => stage),
    planned_stage_count: 18, source_files: sourceFiles,
    inert_warmup_response: { public_path: '/pilot-warmup.html', byte_count: WARMUP_HTML.length, sha256: sha256(WARMUP_HTML), no_scripts_or_collection: true },
    raw_hash_policy: 'Backend canonical_received_payload hashes are retained; immutable UTF-8 archive row SHA256 is also recorded. Independent canonicalization verification is required.',
    build_manifest: buildManifest, core_probe_identity: coreIdentity,
    apk: apkIdentity };
  return { plan, stages, identity };
}

export async function runPilot(options) {
  const checked = await preflight(options);
  options.plan = checked.plan;
  if (!checked.identity.apk) throw new PilotError('APK_IDENTITY_REQUIRED');
  await mkdir(options.output, { recursive: false });
  const captures = new Ledger(resolve(options.output, 'captures.jsonl'));
  const ledger = new Ledger(resolve(options.output, 'private_command_events.jsonl'));
  const record = (row) => ledger.append(row);
  const installedPath = validateInstalledApkPaths(await adb(options,
    ['shell', 'pm', 'path', options.plan.app_package], record));
  const installedFile = resolve(options.output, 'installed_collector.apk');
  // Never replace an existing attempt's build evidence.
  await writeFile(installedFile, Buffer.alloc(0), { flag: 'wx' });
  await adb(options, ['pull', installedPath, installedFile], record);
  checked.identity.installed_apk = { ...(await fileIdentity(installedFile)),
    device_path: installedPath, serial: options.plan.serial,
    matches_local_apk: (await fileIdentity(installedFile)).sha256 === checked.identity.apk.sha256 };
  if (!checked.identity.installed_apk.matches_local_apk) throw new PilotError('INSTALLED_APK_MISMATCH');
  await writeFile(resolve(options.output, 'run_manifest.json'), `${JSON.stringify(checked.identity, null, 2)}\n`, { flag: 'wx' });
  const site = await createProbeServer(options.publicRoot, { record });
  const preValues = new Map();
  let abortReason = null;
  let completedCount = 0;
  let failedCount = 0;
  try {
    for (const stage of checked.stages) {
      const { control, ...stageMetadata } = stage;
      const capture = { schema_version: 'browser67-pilot-capture-v1', ...stageMetadata,
        started_at: now(), result: 'failed', pair_completed: false };
      if (abortReason) {
        await captures.append({ ...capture, result: 'skipped', failure_code: 'PREVIOUS_STAGE_ABORT',
          previous_failure_code: abortReason, finished_at: now() });
        continue;
      }
      let cdp = null;
      let browserCdp = null;
      let controlInstalled = false;
      let languageControlSafeToRestore = false;
      let target = null;
      let ticket = null;
      try {
        await adb(options, ['shell', 'am', 'force-stop', options.plan.app_package], record);
        await adb(options, ['shell', 'am', 'force-stop', options.plan.browser_package], record);
        await adb(options, ['forward', 'tcp:9340', 'localabstract:chrome_devtools_remote'], record);
        // Android Chrome enables DevTools after initial browser startup. A held first-page
        // script response blocks that startup, so commit an inert page before the App ticket.
        const prewarmUrl = `${options.plan.static_origin}/pilot-warmup.html?context=${encodeURIComponent(stage.runtime_context)}`;
        await adb(options, ['shell', 'am', 'start', '-W', '-a', 'android.intent.action.VIEW',
          '-d', prewarmUrl, '-p', options.plan.browser_package], record);
        capture.fresh_chrome_startup = await waitForChromeReady(options, record, prewarmUrl);
        browserCdp = await CdpClient.connect(capture.fresh_chrome_startup.webSocketDebuggerUrl, record);
        capture.warmup_target = await closeExactWarmupTarget(options, prewarmUrl, record, browserCdp);
        const eventRows = await readJsonl(resolve(options.data, 'browser_pair_events.jsonl'));
        const baselineLine = eventRows.at(-1)?.line || 0;
        capture.browser_pair_event_baseline_line = baselineLine;
        site.gate.arm(stage.capture_id);
        await record({ kind: 'stage_started', ...stageMetadata, at: now() });
        const prefix = options.plan.app_package;
        await adb(options, ['shell', 'am', 'start', '-W', '-n', options.plan.app_activity,
          '--es', `${prefix}.DEVICE_MANIFEST_ID`, options.plan.device_manifest_id,
          '--es', `${prefix}.RUNTIME_CONTEXT`, stage.runtime_context,
          '--ei', `${prefix}.COLLECTION_ROUND`, String(stage.collection_round),
          '--es', `${prefix}.COLLECT_ENDPOINT`, options.plan.collect_endpoint], record);
        ({ target, ticket } = await waitForTarget(options, stage, site.gate, record, baselineLine));
        const chromePid = (await adb(options, ['shell', 'pidof', options.plan.browser_package], record)).trim();
        if (!/^\d+(?: \d+)*$/.test(chromePid)) throw new PilotError('CHROME_NOT_RUNNING');
        cdp = await CdpClient.connect(target.webSocketDebuggerUrl, record);
        const version = await cdp.command('Browser.getVersion');
        if (!/^(Chrome|HeadlessChrome)\//.test(version.product || '')) throw new PilotError('CDP_NOT_CHROME');
        capture.browser_version = version;
        await cdp.command('Page.enable');
        await cdp.command('Runtime.enable');
        const realm = await waitForCommittedRealm(cdp, target, ticket, site.gate);
        const realmUrl = new URL(realm.href);
        capture.committed_realm = { page_origin: realmUrl.origin, page_path: realmUrl.pathname,
          readyState: realm.readyState, coreRevision: realm.coreRevision,
          languageHasOwn: realm.languageHasOwn, languagesHasOwn: realm.languagesHasOwn };
        languageControlSafeToRestore = stage.stage === 'attack_active'
          && stage.control.method === 'Runtime.evaluate'
          && realm.languageHasOwn === false && realm.languagesHasOwn === false;
        capture.control_installation = await installControl(cdp, stage, realm);
        controlInstalled = true;
        await site.gate.release();
        const matched = await waitForPair(options, stage, ticket, site.gate);
        capture.pair_completed = true;
        const p = matched.pair.value;
        capture.binding = { pair_id: p.pair_id, app_session_id: p.app_session_id,
          app_receipt_id: p.app_receipt_id, app_payload_sha256: p.app_payload_sha256,
          browser_session_id: p.browser_session_id, browser_receipt_id: p.browser_receipt_id,
          browser_payload_sha256: p.browser_payload_sha256, collection_batch_id: p.collection_batch_id };
        capture.archives = {
          app: { file: 'raw_expanded_payloads.jsonl', line: matched.app.line, line_sha256: matched.app.line_sha256 },
          browser: { file: 'raw_browser_payloads.jsonl', line: matched.browser.line, line_sha256: matched.browser.line_sha256 },
          provenance: { file: 'browser_pair_provenance.jsonl', line: matched.pair.line, line_sha256: matched.pair.line_sha256 },
        };
        capture.app_manifest = matched.app.value.canonical_received_payload.collection_manifest;
        capture.observed = observedValues(matched.browser.value.canonical_received_payload);
        const key = `${stage.configuration_id}:${stage.repeat}`;
        verifyObservation(stage, capture.observed, preValues.get(key));
        if (stage.stage === 'clean_pre') preValues.set(key, capture.observed);
        capture.result = 'completed';
        completedCount++;
      } catch (error) {
        capture.failure_code = error.code || 'PILOT_STAGE_ERROR';
        capture.failure_detail = error.message;
        capture.ticket_pair_id = ticket?.pair_id || null;
        failedCount++;
        // Never kill an App which may still be working on an incomplete pair.
        if (!capture.pair_completed) abortReason = capture.failure_code;
        if (stage.stage === 'clean_pre') abortReason = capture.failure_code;
      } finally {
        let restoration = [];
        if (cdp) {
          try {
            // A failed installation must never delete a pre-existing, unknown own property.
            const restorationStage = controlInstalled || languageControlSafeToRestore
              ? stage : { ...stage, stage: 'clean_pre' };
            restoration = await restoreControl(cdp, restorationStage, target, capture.pair_completed, browserCdp);
            if (site.gate.violation) throw new PilotError(site.gate.violation);
          } catch (error) {
            capture.restoration_failure_code = error.code || 'RESTORATION_COMMAND_ERROR';
            abortReason = capture.restoration_failure_code;
            if (capture.result === 'completed') {
              capture.result = 'failed';
              completedCount--;
              failedCount++;
            }
          }
          cdp.close();
        }
        if (browserCdp) browserCdp.close();
        capture.restoration = restoration;
        site.gate.abort();
        capture.finished_at = now();
        await captures.append(capture);
        await ledger.chain;
        console.log(`Pilot ${stage.capture_id}: ${capture.result}; ${completedCount}/18 completed, ${failedCount} failed`);
      }
    }
  } finally {
    site.gate.abort();
    site.server.closeAllConnections();
    await new Promise((done) => site.server.close(done));
    await Promise.all([captures.chain, ledger.chain]);
  }
  const rows = await readJsonl(resolve(options.output, 'captures.jsonl'));
  const summary = { schema_version: 'browser67-pilot-summary-v1', finished_at: now(), planned: 18,
    completed: rows.filter(({ value }) => value.result === 'completed').length,
    failed: rows.filter(({ value }) => value.result === 'failed').length,
    skipped: rows.filter(({ value }) => value.result === 'skipped').length,
    source_commit: options.plan.source_commit, interpretation: 'Fixed pilot only; no population rates or old denominator changes.' };
  await writeFile(resolve(options.output, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
  return summary;
}

function parseOptions(argv) {
  const options = { adb: process.env.ADB_PATH || 'adb',
    planPath: resolve(HERE, 'pilot_plan.json'), publicRoot: resolve(HERE, 'upstream/browser_probe_site/public'),
    data: resolve(HERE, 'data'), output: resolve(HERE, 'pilot_r7') };
  const args = new Map([['--adb', 'adb'], ['--plan', 'planPath'], ['--public', 'publicRoot'],
    ['--data', 'data'], ['--output', 'output'], ['--apk', 'apk'], ['--build-manifest', 'buildManifest']]);
  for (let index = 0; index < argv.length; index++) {
    const arg = argv[index];
    if (['--run', '--preflight', '--self-test'].includes(arg)) options[arg.slice(2)] = true;
    else if (args.has(arg) && argv[index + 1]) options[args.get(arg)] = argv[++index];
    else throw new PilotError('UNKNOWN_ARGUMENT');
  }
  return options;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const options = parseOptions(process.argv.slice(2));
    if (options['self-test']) {
      const result = await execFileAsync(process.execPath, ['--test', resolve(HERE, 'test_paired_browser_pilot.mjs')],
        { windowsHide: true });
      console.log(result.stdout);
    } else if (options.run) console.log(JSON.stringify(await runPilot(options)));
    else if (options.preflight) {
      const checked = await preflight(options);
      console.log(JSON.stringify({ stages: checked.stages.length, source_files: checked.identity.source_files.length,
        plan_sha256: checked.identity.plan_sha256, apk_sha256: checked.identity.apk?.sha256 || null }));
    } else console.log('Use --preflight or --self-test (no device operations); --run --apk PATH explicitly starts the fixed 18-slot pilot.');
  } catch (error) {
    console.error(`Pilot failed: ${error.code || 'PILOT_ERROR'}`);
    process.exitCode = 1;
  }
}
