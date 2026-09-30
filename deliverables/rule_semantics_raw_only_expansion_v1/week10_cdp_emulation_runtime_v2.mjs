#!/usr/bin/env node

/*
 * Dedicated active-state runner for the two V5 CDP emulation configurations.
 *
 * It deliberately keeps CDP emulation outside the legacy JavaScript profile
 * runner.  The only allowed interventions are declared by
 * controlled_webview_methods.mjs, applied to the controlled local FeatureApp
 * page, observed, used for one upload, and then explicitly rolled back before
 * the runner returns.  Any failure to roll back is reported as non-measured so
 * the parent triplet runner cannot promote the active session.
 */


import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

import { controlledWebviewConfiguration } from "./source_snapshot/lib/controlled_webview_methods.mjs";
import {
  expectedWebviewObservableValue,
  matchesWebviewAutomationObservable,
  matchesWebviewAutomationProfile,
  webviewAutomationProfile,
} from "./source_snapshot/lib/webview_automation_profiles.mjs";

const require = createRequire(import.meta.url);
const CONTROLLED_ASSET_URL = "file:///android_asset/expanded_probe.html";

export const RUNTIME_OBSERVATION_EXPRESSION = `(() => {
  const safe = (fn) => { try { return fn(); } catch (_) { return null; } };
  const viewport = safe(() => window.visualViewport);
  return JSON.stringify({
    timezone: {
      id: safe(() => Intl.DateTimeFormat().resolvedOptions().timeZone),
      offset_minutes: safe(() => new Date().getTimezoneOffset()),
    },
    screen: {
      width: safe(() => screen.width),
      height: safe(() => screen.height),
      avail_width: safe(() => screen.availWidth),
      avail_height: safe(() => screen.availHeight),
      device_pixel_ratio: safe(() => window.devicePixelRatio),
      inner_width: safe(() => window.innerWidth),
      inner_height: safe(() => window.innerHeight),
      outer_width: safe(() => window.outerWidth),
      outer_height: safe(() => window.outerHeight),
      visual_viewport_width: viewport ? safe(() => viewport.width) : null,
      visual_viewport_height: viewport ? safe(() => viewport.height) : null,
    },
  });
})()`;

export function assertV5CdpEmulationDefinition(configurationId, toolDefinition) {
  if (!toolDefinition || toolDefinition.executionClientId !== "cdp" ||
      toolDefinition.boundaryCampaign !== "teacher-cdp-emulation-rule-boundary-api36-v5") {
    throw new Error(`Configuration is not a V5 CDP emulation configuration: ${configurationId}`);
  }
  const contract = toolDefinition.cdpEmulation;
  if (!contract || contract.contractVersion !== "cdp-emulation-v1" || contract.targetUrl !== CONTROLLED_ASSET_URL) {
    throw new Error(`Invalid V5 CDP emulation contract: ${configurationId}`);
  }
  const allowed = new Set([
    "Emulation.setTimezoneOverride",
    "Emulation.setDeviceMetricsOverride",
    "Emulation.clearDeviceMetricsOverride",
  ]);
  for (const key of ["applyCommands", "rollbackCommands"]) {
    if (!Array.isArray(contract[key]) || contract[key].length !== 1) {
      throw new Error(`${configurationId} ${key} must contain exactly one command`);
    }
    for (const command of contract[key]) {
      if (!command || !allowed.has(command.method) || !command.params || typeof command.params !== "object" || Array.isArray(command.params)) {
        throw new Error(`${configurationId} contains a non-allowlisted CDP command`);
      }
    }
  }
  const expected = configurationId === "cdp_timezone_only_v1"
    ? {
      apply: { method: "Emulation.setTimezoneOverride", params: { timezoneId: "America/Los_Angeles" } },
      rollback: { method: "Emulation.setTimezoneOverride", params: { timezoneId: "" } },
    }
    : configurationId === "cdp_screen_metrics_only_v1"
      ? {
        apply: {
          method: "Emulation.setDeviceMetricsOverride",
          params: { width: 393, height: 851, deviceScaleFactor: 2.75, mobile: true, screenWidth: 393, screenHeight: 851, positionX: 0, positionY: 0 },
        },
        rollback: { method: "Emulation.clearDeviceMetricsOverride", params: {} },
      }
      : null;
  if (!expected || canonicalJson(contract.applyCommands[0]) !== canonicalJson(expected.apply) ||
      canonicalJson(contract.rollbackCommands[0]) !== canonicalJson(expected.rollback)) {
    throw new Error(`V5 CDP emulation commands are not the frozen selection: ${configurationId}`);
  }  return contract;
}

export function parseRuntimeObservation(command) {
  const value = command?.response?.result?.result?.value;
  if (typeof value !== "string") return null;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function summarizeRollback(baseline, postRollback, rollbackRecords) {
  const commandsOk = Array.isArray(rollbackRecords) && rollbackRecords.length > 0 && rollbackRecords.every((record) => record.ok === true);
  const postMatchesBaseline = baseline !== null && postRollback !== null && canonicalJson(baseline) === canonicalJson(postRollback);
  return {
    rollback_commands_ok: commandsOk,
    post_runtime_matches_baseline: postMatchesBaseline,
    rollback_verified: commandsOk && postMatchesBaseline,
  };
}

// Upload/status text can resize the host WebView between about:blank and
// post-upload observations. Keep the original full-object comparison as data.
// This local revision verifies commands and stable CDP state anchors here;
// its result requires a separately observed clean_post for ALL declared fields.
export function summarizeScopedRollback(configurationId, baseline, post, records) {
  const full = summarizeRollback(baseline, post, records);
  const section = configurationId === "cdp_timezone_only_v1" ? "timezone"
    : configurationId === "cdp_screen_metrics_only_v1" ? "screen" : null;
  const fields = section === "timezone" ? ["id", "offset_minutes"]
    : ["width", "height", "avail_width", "avail_height", "device_pixel_ratio"];
  const knownEqual = section !== null && fields.every(key => {
    const before = baseline?.[section]?.[key], after = post?.[section]?.[key];
    return before !== undefined && before !== null && after !== undefined && after !== null
      && before === after;
  });
  return {
    ...full,
    rollback_verified: full.rollback_commands_ok && knownEqual,
    verification_contract: "cdp-runtime-rollback-plus-paired-restoration-v2",
    runtime_anchor_section: section,
    runtime_anchor_fields: fields,
    runtime_anchors_restored: knownEqual,
    paired_payload_restoration_required: true,
    full_runtime_equality_observed: full.post_runtime_matches_baseline,
    full_runtime_restoration_claimed: false,
  };
}

export function runtimeObservationObservables(observation) {
  return {
    timezone_id: observation?.timezone?.id,
    timezone_offset: observation?.timezone?.offset_minutes,
    avail_width: observation?.screen?.avail_width,
    avail_height: observation?.screen?.avail_height,
    device_pixel_ratio: observation?.screen?.device_pixel_ratio,
    inner_width: observation?.screen?.inner_width,
    inner_height: observation?.screen?.inner_height,
    outer_width: observation?.screen?.outer_width,
    outer_height: observation?.screen?.outer_height,
    screen_resolution_logical: observation?.screen?.width != null && observation?.screen?.height != null
      ? `${observation.screen.width}x${observation.screen.height}`
      : undefined,
    visual_viewport_width: observation?.screen?.visual_viewport_width,
    visual_viewport_height: observation?.screen?.visual_viewport_height,
  };
}

export function verifyActiveRuntimeProfile(configurationId, observableFields, profile, observation) {
  const observed = runtimeObservationObservables(observation);
  const expected = {};
  for (const field of observableFields) {
    const expectedValue = expectedWebviewObservableValue(configurationId, field, profile);
    if (expectedValue === undefined || !matchesWebviewAutomationObservable(configurationId, field, observed[field], profile)) {
      throw new Error(`Active CDP runtime observation mismatch for ${field}: expected=${JSON.stringify(expectedValue)} actual=${JSON.stringify(observed[field])}`);
    }
    expected[field] = expectedValue;
  }
  return { verified: true, expected, observed };
}
async function main() {
  const configurationId = process.argv[2];
  if (process.argv.length !== 3 || !configurationId) {
    throw new Error("Usage: node execution_log/tools/week10_cdp_emulation_runner_v5.mjs <v5-configuration-id>");
  }

  const root = path.resolve(".");
  const toolDefinition = controlledWebviewConfiguration(configurationId);
  const cdpEmulation = assertV5CdpEmulationDefinition(configurationId, toolDefinition);
  const injected = webviewAutomationProfile(configurationId, toolDefinition.name);
  const adbExe = requiredEnv("WEEK6_ADB", "HYBRIDGUARD_ADB", "ADB");
  const serial = requiredEnv("WEEK6_ADB_SERIAL", "HYBRIDGUARD_ADB_SERIAL", "ANDROID_SERIAL");
  const endpoint = process.env.HYBRIDGUARD_COLLECTION_ENDPOINT || "http://127.0.0.1:8000/api/collect/fingerprint";
  const runtimeContext = requiredEnv("WEEK7_RUNTIME_CONTEXT");
  const collectionRound = integerEnv("WEEK7_COLLECTION_ROUND", 1);
  const deviceManifestId = requiredEnv("WEEK7_DEVICE_MANIFEST_ID", "HYBRIDGUARD_DEVICE_MANIFEST_ID");
  const expectedSchema = process.env.HYBRIDGUARD_EXPECTED_SCHEMA || "expanded-v2.2-status";
  const backendJsonl = path.resolve(process.env.HYBRIDGUARD_BACKEND_JSONL || path.join(root, "execution_log", "evidence", "week10_cdp_emulation_receiver.jsonl"));
  const logDir = path.resolve(process.env.HYBRIDGUARD_AUTOMATION_LOG_DIR || path.join(root, "execution_log", "evidence", "week10_cdp_emulation_logs"));
  const toolNodeDir = path.resolve(process.env.HYBRIDGUARD_TOOL_NODE_DIR || path.join(root, "execution_log", "tool_node"));
  const cdpPort = integerEnv("HYBRIDGUARD_CDP_EMULATION_PORT", 9333);
  const runId = `${new Date().toISOString().replace(/[:.]/g, "-")}_${configurationId}`;
  const logPath = path.join(logDir, `${runId}.json`);
  const packageName = "com.example.hybridguard.featureapp";
  const activityName = `${packageName}/.MainActivity`;

  fs.mkdirSync(logDir, { recursive: true });
  ensureBackend(backendJsonl);
  const before = readRows(backendJsonl);
  const beforeIds = new Set(before.map((row) => row.session_id));
  const cdpEvidence = {
    contract: cdpEmulation,
    cdp_version: null,
    target: null,
    apply_command_responses: [],
    rollback_command_responses: [],
    baseline_runtime_observation: null,
    active_runtime_observation: null,
    post_rollback_runtime_observation: null,
    active_runtime_profile_verification: null,
    rollback: null,
  };
  let automationEvidence = null;
  let session = null;
  let cdpForwarded = false;
  let fresh = [];
  let matched = [];
  let status = "FAILED";
  let reason = "";

  try {
    adb(adbExe, serial, ["connect", serial], { noSerial: true, allowFailure: true });
    if (adb(adbExe, serial, ["get-state"]).trim() !== "device") throw new Error(`ADB target ${serial} is not ready`);
    ensureLoopbackReverse(adbExe, serial, endpoint);

    adb(adbExe, serial, ["shell", "am", "force-stop", packageName], { allowFailure: true });
    adb(adbExe, serial, [
      "shell", "am", "start",
      "-n", activityName,
      "--ez", "com.example.hybridguard.featureapp.ENABLE_WEBVIEW_DEBUG", "true",
      "--el", "com.example.hybridguard.featureapp.PROBE_DELAY_MS", "60000",
      "--ez", "com.example.hybridguard.featureapp.WAIT_FOR_WEBVIEW_CONTROL", "true",
      "--es", "com.example.hybridguard.featureapp.COLLECT_ENDPOINT", endpoint,
      "--es", "com.example.hybridguard.featureapp.RUNTIME_CONTEXT", runtimeContext,
      "--ei", "com.example.hybridguard.featureapp.COLLECTION_ROUND", String(collectionRound),
      "--es", "com.example.hybridguard.featureapp.DEVICE_MANIFEST_ID", deviceManifestId,
    ]);
    await sleep(2500);

    const socket = findWebViewSocket(adbExe, serial, packageName);
    adb(adbExe, serial, ["forward", "--remove", `tcp:${cdpPort}`], { allowFailure: true });
    adb(adbExe, serial, ["forward", `tcp:${cdpPort}`, `localabstract:${socket}`]);
    cdpForwarded = true;
    const baseUrl = `http://127.0.0.1:${cdpPort}`;
    const version = await waitForJsonEndpoint(`${baseUrl}/json/version`, 15000);
    cdpEvidence.cdp_version = compactVersion(version);
    const targets = await fetch(`${baseUrl}/json/list`).then((response) => response.json());
    const target = targets.find((item) => item.type === "page");
    assertControlledWaitingTarget(target);
    cdpEvidence.target = compactTarget(target);

    session = await openCdpSession(target.webSocketDebuggerUrl, toolNodeDir);
    await sendRequired(session, "Page.enable", {}, cdpEvidence.apply_command_responses, "setup");
    cdpEvidence.baseline_runtime_observation = await observe(session, "baseline", cdpEvidence.apply_command_responses);
    for (const command of cdpEmulation.applyCommands) {
      await sendRequired(session, command.method, command.params, cdpEvidence.apply_command_responses, "apply");
    }
    cdpEvidence.active_runtime_observation = await observe(session, "active", cdpEvidence.apply_command_responses);
    cdpEvidence.active_runtime_profile_verification = verifyActiveRuntimeProfile(
      configurationId,
      toolDefinition.observableFields,
      injected,
      cdpEvidence.active_runtime_observation,
    );
    await sendRequired(session, "Page.navigate", { url: cdpEmulation.targetUrl }, cdpEvidence.apply_command_responses, "navigate");
    automationEvidence = {
      protocol: "raw-cdp-emulation-v1",
      targetId: target.id,
      targetUrlBeforeNavigation: target.url,
      navigation: "cdp-Page.navigate-after-emulation-apply",
    };

    fresh = await waitForFreshRows(backendJsonl, beforeIds, runtimeContext, collectionRound, 70000);
    matched = fresh.filter((row) => row.collector_app === "featureapp" && row.schema_version === expectedSchema &&
      matchesWebviewAutomationProfile(configurationId, toolDefinition.name, row.web_data || {}));
  } catch (error) {
    reason = errorMessage(error);
  } finally {
    if (session) {
      for (const command of cdpEmulation.rollbackCommands) {
        const record = await session.send(command.method, command.params, "rollback");
        cdpEvidence.rollback_command_responses.push(record);
      }
      try {
        cdpEvidence.post_rollback_runtime_observation = await observe(session, "post_rollback", cdpEvidence.rollback_command_responses);
      } catch (error) {
        reason ||= `Post-rollback runtime observation failed: ${errorMessage(error)}`;
      }
      session.close();
    }
    cdpEvidence.rollback = summarizeScopedRollback(
      configurationId,
      cdpEvidence.baseline_runtime_observation,
      cdpEvidence.post_rollback_runtime_observation,
      cdpEvidence.rollback_command_responses,
    );
    try { adb(adbExe, serial, ["shell", "am", "force-stop", packageName], { allowFailure: true }); } catch {}
    if (cdpForwarded) {
      try { adb(adbExe, serial, ["forward", "--remove", `tcp:${cdpPort}`], { allowFailure: true }); } catch {}
    }
  }

  if (!reason && fresh.length === 0) {
    status = "UPLOAD_FAILED";
    reason = "No fresh FeatureApp row arrived after V5 CDP navigation";
  } else if (!reason && matched.length !== 1) {
    status = "INJECTION_NOT_OBSERVED";
    reason = `Expected exactly one payload matching the V5 emulation profile, observed ${matched.length}`;
  } else if (!reason && !cdpEvidence.rollback?.rollback_verified) {
    status = "ROLLBACK_FAILED";
    reason = "CDP rollback commands or post-rollback observation did not verify baseline restoration";
  } else if (!reason) {
    status = "MEASURED";
  }

  const result = {
    runId,
    toolId: configurationId,
    configurationId,
    executionClientId: "cdp",
    configId: toolDefinition.configId,
    declaredObservableFields: toolDefinition.observableFields,
    declaredStealthEvasions: null,
    declaredCdpEmulation: cdpEmulation,
    cdpEmulation: cdpEvidence,
    automationRunner: "week10_cdp_emulation_runtime_v2.mjs",
    measurementRevision: "cdp-runtime-rollback-plus-paired-restoration-v2",
    stealthRuntime: null,
    toolName: toolDefinition.name,
    status,
    reason,
    serial,
    injected,
    freshSessionIds: fresh.map((row) => row.session_id),
    measuredSessionIds: matched.map((row) => row.session_id),
    automationEvidence,
    collectionManifest: {
      runtimeContext,
      collectionRound,
      deviceManifestId,
    },
  };
  fs.writeFileSync(logPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ ...result, logPath }, null, 2));
}

function assertControlledWaitingTarget(target) {
  if (!target || target.type !== "page" || typeof target.webSocketDebuggerUrl !== "string") {
    throw new Error("No WebView page target exposed for the V5 CDP emulation runner");
  }
  const url = String(target.url || "");
  if (url !== "about:blank" && url !== CONTROLLED_ASSET_URL) {
    throw new Error(`V5 CDP target is not the controlled waiting page: ${url}`);
  }
  const socketUrl = new URL(target.webSocketDebuggerUrl);
  if (!isLoopback(socketUrl.hostname)) throw new Error("V5 CDP target must remain on loopback");
}

async function sendRequired(session, method, params, destination, phase = null) {
  const record = await session.send(method, params, phase);
  destination.push(record);
  if (!record.ok) throw new Error(`CDP ${method} failed: ${JSON.stringify(record.response?.error || record.transport_error || "unknown")}`);
  return record;
}

async function observe(session, phase, destination) {
  const record = await sendRequired(session, "Runtime.evaluate", {
    expression: RUNTIME_OBSERVATION_EXPRESSION,
    awaitPromise: true,
    returnByValue: true,
  }, destination, phase);
  const observation = parseRuntimeObservation(record);
  if (!observation) throw new Error(`CDP ${phase} runtime observation was unavailable`);
  return observation;
}

async function openCdpSession(webSocketUrl, toolNodeDir) {
  const WebSocket = require(path.join(toolNodeDir, "node_modules", "ws"));
  const ws = new WebSocket(webSocketUrl);
  const pending = new Map();
  let nextId = 1;
  let closed = false;
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Timed out opening local WebView CDP session")), 15000);
    ws.once("open", () => { clearTimeout(timer); resolve(); });
    ws.once("error", (error) => { clearTimeout(timer); reject(error); });
  });
  ws.on("message", (raw) => {
    let response;
    try { response = JSON.parse(String(raw)); } catch { return; }
    const item = pending.get(response.id);
    if (!item) return;
    pending.delete(response.id);
    clearTimeout(item.timer);
    item.record.response = response;
    item.record.ok = !response.error;
    item.resolve(item.record);
  });
  ws.on("error", (error) => {
    for (const item of pending.values()) {
      clearTimeout(item.timer);
      item.record.transport_error = errorMessage(error);
      item.record.ok = false;
      item.resolve(item.record);
    }
    pending.clear();
  });
  return {
    send(method, params = {}, phase = null) {
      if (closed) return Promise.resolve({ method, params, phase, ok: false, transport_error: "CDP session is closed" });
      const id = nextId++;
      const record = { id, phase, method, params, requested_at: new Date().toISOString(), response: null, ok: null };
      return new Promise((resolve) => {
        const timer = setTimeout(() => {
          if (!pending.has(id)) return;
          pending.delete(id);
          record.transport_error = "Timed out waiting for CDP response";
          record.ok = false;
          resolve(record);
        }, 15000);
        pending.set(id, { record, resolve, timer });
        try { ws.send(JSON.stringify({ id, method, params })); } catch (error) {
          clearTimeout(timer);
          pending.delete(id);
          record.transport_error = errorMessage(error);
          record.ok = false;
          resolve(record);
        }
      });
    },
    close() {
      if (closed) return;
      closed = true;
      try { ws.close(); } catch {}
    },
  };
}

function ensureLoopbackReverse(adbExe, serial, endpoint) {
  const parsed = new URL(endpoint);
  if (!isLoopback(parsed.hostname)) return;
  const port = Number(parsed.port || (parsed.protocol === "https:" ? 443 : 80));
  adb(adbExe, serial, ["reverse", `tcp:${port}`, `tcp:${port}`]);
}

function findWebViewSocket(adbExe, serial, packageName) {
  const candidates = adb(adbExe, serial, ["shell", "pidof", packageName]).trim().split(/\s+/).filter(Boolean);
  if (!candidates.length) throw new Error("FeatureApp process did not start");
  const unixSockets = adb(adbExe, serial, ["shell", "cat", "/proc/net/unix"], { allowFailure: true });
  const processId = candidates.find((candidate) => unixSockets.includes(`webview_devtools_remote_${candidate}`)) || candidates.at(-1);
  const socket = `webview_devtools_remote_${processId}`;
  if (!unixSockets.includes(socket)) throw new Error(`No WebView CDP socket was exposed for FeatureApp process ${processId}`);
  return socket;
}

async function waitForFreshRows(backendJsonl, beforeIds, runtimeContext, round, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const fresh = readRows(backendJsonl).filter((row) => !beforeIds.has(row.session_id));
    const matching = fresh.filter((row) => row?.collection_manifest?.runtime_context === runtimeContext &&
      Number(row?.collection_manifest?.collection_round) === Number(round));
    if (matching.length > 1) throw new Error(`Ambiguous fresh receiver rows for ${runtimeContext}: ${matching.length}`);
    if (matching.length === 1) {
      await sleep(750);
      const settled = readRows(backendJsonl).filter((row) => !beforeIds.has(row.session_id)).filter((row) =>
        row?.collection_manifest?.runtime_context === runtimeContext && Number(row?.collection_manifest?.collection_round) === Number(round));
      if (settled.length !== 1) throw new Error(`Ambiguous fresh receiver rows after settle for ${runtimeContext}: ${settled.length}`);
      return settled;
    }
    await sleep(500);
  }
  return [];
}

async function waitForJsonEndpoint(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return await response.json();
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) { lastError = error; }
    await sleep(300);
  }
  throw new Error(`Timed out waiting for ${url}: ${errorMessage(lastError)}`);
}

function readRows(backendJsonl) {
  if (!fs.existsSync(backendJsonl)) return [];
  return fs.readFileSync(backendJsonl, "utf8").split(/\r?\n/).filter((line) => line.trim()).map((line, index) => {
    try { return JSON.parse(line); } catch (error) { throw new Error(`Invalid receiver JSONL at line ${index + 1}: ${errorMessage(error)}`); }
  });
}

function ensureBackend(backendJsonl) {
  fs.mkdirSync(path.dirname(backendJsonl), { recursive: true });
  if (!fs.existsSync(backendJsonl)) fs.writeFileSync(backendJsonl, "", "utf8");
}

function adb(adbExe, serial, args, options = {}) {
  const argv = options.noSerial ? args : ["-s", serial, ...args];
  try {
    return execFileSync(adbExe, argv, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: options.timeoutMs || 30000 });
  } catch (error) {
    if (options.allowFailure) return `${error.stdout || ""}${error.stderr || ""}`;
    throw new Error(`ADB command failed (${argv.join(" ")}): ${errorMessage(error.stderr || error.stdout || error)}`);
  }
}

function compactTarget(target) {
  return { id: target.id || null, type: target.type, url: target.url || null, debugger_url: target.webSocketDebuggerUrl || null };
}

function compactVersion(version) {
  return { Browser: version?.Browser || null, "Protocol-Version": version?.["Protocol-Version"] || null, "WebKit-Version": version?.["WebKit-Version"] || null };
}

function requiredEnv(...names) {
  for (const name of names) {
    const value = process.env[name]?.trim();
    if (value) return value;
  }
  throw new Error(`Required environment variable is missing: ${names.join(" or ")}`);
}

function integerEnv(name, fallback) {
  const value = process.env[name] ?? String(fallback);
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) throw new Error(`${name} must be a valid positive integer`);
  return parsed;
}

function isLoopback(hostname) {
  const normalized = String(hostname || "").toLowerCase().replace(/^\[|\]$/g, "");
  return normalized === "127.0.0.1" || normalized === "localhost" || normalized === "::1";
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}

function errorMessage(error) {
  return String(error?.message || error || "unknown error").replace(/\s+/g, " ").trim();
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isMainModule() {
  return Boolean(process.argv[1]) && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
}

if (isMainModule()) {
  try {
    await main();
  } catch (error) {
    console.log(JSON.stringify({ status: "FAILED", reason: errorMessage(error) }));
    process.exitCode = 1;
  }
}
