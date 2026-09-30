import fs from "node:fs";
import crypto from "node:crypto";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";
import { execFileSync, spawnSync } from "node:child_process";
import { matchesWebviewAutomationProfile, webviewAutomationProfile } from "./lib/webview_automation_profiles.mjs";
import {
  CONTROLLED_WEBVIEW_CONFIGURATION_IDS,
  controlledWebviewConfiguration,
} from "./lib/controlled_webview_methods.mjs";

const require = createRequire(import.meta.url);
const root = path.resolve(".");
const configurationId = String(process.argv[2] || "").toLowerCase();
const supportedConfigurations = new Set(CONTROLLED_WEBVIEW_CONFIGURATION_IDS);
if (!supportedConfigurations.has(configurationId)) {
  console.error("Usage: node execution_log/tools/week6_webview_automation_runner.mjs <" + CONTROLLED_WEBVIEW_CONFIGURATION_IDS.join("|") + ">");
  process.exit(2);
}
const toolDefinition = controlledWebviewConfiguration(configurationId);
const executionClientId = toolDefinition.executionClientId;

const toolMeta = {
  cdp: { name: "Chrome DevTools Protocol", port: 9222 },
  playwright: { name: "Playwright", port: 9223 },
  puppeteer: { name: "Puppeteer", port: 9224 },
  selenium: { name: "Selenium", port: 9225 },
  stealth: { name: "puppeteer-extra-plugin-stealth", port: 9226 },
}[executionClientId];
if (!toolMeta) throw new Error(`Unsupported controlled WebView execution client: ${executionClientId}`);
const adbExe = process.env.WEEK6_ADB || "D:\\Program Files\\Netease\\MuMuPlayer\\nx_main\\adb.exe";
const serial = process.env.WEEK6_ADB_SERIAL || "127.0.0.1:7555";
const backendJsonl = path.resolve(
  process.env.HYBRIDGUARD_BACKEND_JSONL ||
  path.join(root, "RBA-Cross-Device-Fingerprint-week6-featureapp", "backend_server", "expanded_collected_data.jsonl"),
);
const expectedSchema = process.env.HYBRIDGUARD_EXPECTED_SCHEMA || "expanded-v2";
const pairedMode = process.env.HYBRIDGUARD_PAIRED_MODE === "1";
const mappingPath = path.join(root, "execution_log", "evidence", "week6_tool_session_mapping.csv");
const logDir = path.resolve(
  process.env.HYBRIDGUARD_AUTOMATION_LOG_DIR ||
  path.join(root, "execution_log", "evidence", "week6_webview_automation_logs"),
);
const toolNodeDir = path.resolve(process.env.HYBRIDGUARD_TOOL_NODE_DIR || path.join(root, "execution_log", "tool_node"));
const stealthRuntime = executionClientId === "stealth" ? readStealthRuntime(toolNodeDir) : null;
const probeUrl = "file:///android_asset/expanded_probe.html";
const endpoint = process.env.HYBRIDGUARD_COLLECTION_ENDPOINT || "http://127.0.0.1:8000/api/collect/fingerprint";
const week7RuntimeContext = process.env.WEEK7_RUNTIME_CONTEXT || "";
const week7CollectionRound = Number.parseInt(process.env.WEEK7_COLLECTION_ROUND || "1", 10);
const week7DeviceManifestId = process.env.WEEK7_DEVICE_MANIFEST_ID || "";
const runId = `${new Date().toISOString().replace(/[:.]/g, "-")}_${configurationId}`;

fs.mkdirSync(logDir, { recursive: true });
ensureBackend();
adb("connect", serial, { noSerial: true, allowFailure: true });
if (adb("get-state").trim() !== "device") throw new Error(`ADB target ${serial} is not ready`);
if (["127.0.0.1", "localhost"].includes(new URL(endpoint).hostname)) {
  adb("reverse", "tcp:8000", "tcp:8000");
}

const before = readRows();
const beforeIds = new Set(before.map((row) => row.session_id));
adb("shell", "am", "force-stop", "com.example.hybridguard.featureapp", { allowFailure: true });
const launchArgs = [
  "shell", "am", "start",
  "-n", "com.example.hybridguard.featureapp/.MainActivity",
  "--ez", "com.example.hybridguard.featureapp.ENABLE_WEBVIEW_DEBUG", "true",
  "--el", "com.example.hybridguard.featureapp.PROBE_DELAY_MS", "60000",
  "--ez", "com.example.hybridguard.featureapp.WAIT_FOR_WEBVIEW_CONTROL", "true",
  "--es", "com.example.hybridguard.featureapp.COLLECT_ENDPOINT", endpoint,
];
if (week7RuntimeContext) launchArgs.push("--es", "com.example.hybridguard.featureapp.RUNTIME_CONTEXT", week7RuntimeContext);
if (Number.isInteger(week7CollectionRound)) launchArgs.push("--ei", "com.example.hybridguard.featureapp.COLLECTION_ROUND", String(week7CollectionRound));
if (week7DeviceManifestId) launchArgs.push("--es", "com.example.hybridguard.featureapp.DEVICE_MANIFEST_ID", week7DeviceManifestId);
adb(...launchArgs);
sleep(2500);

const pidCandidates = adb("shell", "pidof", "com.example.hybridguard.featureapp").trim().split(/\s+/).filter(Boolean);
if (!pidCandidates.length) throw new Error("FeatureApp process did not start");
const unixSockets = adb("shell", "cat", "/proc/net/unix", { allowFailure: true });
const pid = pidCandidates.find((candidate) => unixSockets.includes(`webview_devtools_remote_${candidate}`)) || pidCandidates.at(-1);
const socket = `webview_devtools_remote_${pid}`;
adb("forward", `tcp:${toolMeta.port}`, `localabstract:${socket}`);
const baseUrl = `http://127.0.0.1:${toolMeta.port}`;
waitForJsonEndpoint(`${baseUrl}/json/version`, 15000);

const injected = webviewAutomationProfile(configurationId, toolMeta.name);

const initScript = `(() => {
  const values = ${JSON.stringify(injected)};
  for (const [key, value] of Object.entries(values)) {
    try { Object.defineProperty(Navigator.prototype, key, { configurable: true, get: () => value }); } catch (_) {}
    try { Object.defineProperty(navigator, key, { configurable: true, get: () => value }); } catch (_) {}
  }
  window.__hybridGuardControlledProfile = true;
})();`;

const automationEvidence = await runAutomation(baseUrl, initScript);
const fresh = await waitForFreshRows(beforeIds, pairedMode ? 70000 : 20000);
const matched = fresh.filter((row) => {
  const web = row.web_data || {};
  const common = row.collector_app === "featureapp" &&
    (pairedMode ? row.schema_version === expectedSchema : String(row.schema_version || "").startsWith(expectedSchema));
  return common && matchesWebviewAutomationProfile(configurationId, toolMeta.name, web);
});
adb("shell", "am", "force-stop", "com.example.hybridguard.featureapp", { allowFailure: true });

let status = "MEASURED";
let reason = "";
if (!fresh.length) {
  status = "UPLOAD_FAILED";
  reason = "No fresh expanded-v2 backend row arrived";
} else if (!matched.length) {
  status = "INJECTION_NOT_OBSERVED";
  reason = `Fresh rows arrived but injected values were not observed: ${fresh.map((row) => row.session_id).join(",")}`;
} else {
  if (!pairedMode) {
    for (const row of matched) appendMapping(row, automationEvidence);
  }
}

adb("forward", "--remove", `tcp:${toolMeta.port}`, { allowFailure: true });
if (!pairedMode) rebuildDerived();
const result = {
  runId,
  toolId: configurationId,
  configurationId,
  executionClientId,
  configId: toolDefinition.configId,
  declaredObservableFields: toolDefinition.observableFields,
  declaredStealthEvasions: toolDefinition.stealthEvasions || null,
  stealthRuntime,
  toolName: toolMeta.name,
  status,
  reason,
  serial,
  pid,
  socket,
  injected,
  freshSessionIds: fresh.map((row) => row.session_id),
  measuredSessionIds: matched.map((row) => row.session_id),
  automationEvidence,
  collectionManifest: {
    runtimeContext: week7RuntimeContext,
    collectionRound: week7CollectionRound,
    deviceManifestId: week7DeviceManifestId,
  },
};
const logPath = path.join(logDir, `${runId}.json`);
fs.writeFileSync(logPath, JSON.stringify(result, null, 2), "utf8");
console.log(JSON.stringify({ ...result, logPath }, null, 2));

async function runAutomation(baseUrl, script) {
  if (executionClientId === "cdp") {
    const targets = await fetch(`${baseUrl}/json/list`).then((response) => response.json());
    const target = targets.find((item) => item.type === "page");
    if (!target) throw new Error("No WebView page target exposed by CDP");
    await sendRawCdp(target.webSocketDebuggerUrl, [
      { method: "Page.enable" },
      { method: "Page.addScriptToEvaluateOnNewDocument", params: { source: script } },
      { method: "Page.navigate", params: { url: probeUrl } },
    ]);
    return { protocol: "raw-cdp-websocket", targetId: target.id, targetUrl: target.url, navigation: "cdp-Page.navigate-after-control-wait" };
  }
  if (executionClientId === "playwright") {
    const { _android } = require(path.join(toolNodeDir, "node_modules", "playwright"));
    const devices = await _android.devices();
    const device = devices.find((candidate) => candidate.serial() === serial);
    if (!device) {
      for (const candidate of devices) await candidate.close().catch(() => {});
      throw new Error(`Playwright Android API did not detect ${serial}; detected=${devices.map((candidate) => candidate.serial()).join(",")}`);
    }
    try {
      const webView = await device.webView({ pkg: "com.example.hybridguard.featureapp", socketName: socket });
      const page = await webView.page();
      await page.addInitScript({ content: script });
      await page.goto(probeUrl, { waitUntil: "domcontentloaded" });
      return {
        protocol: "playwright-android-webview",
        deviceSerial: device.serial(),
        webViewPid: webView.pid(),
        pageUrl: page.url(),
        navigation: "playwright-page-goto",
      };
    } finally {
      for (const candidate of devices) await candidate.close().catch(() => {});
    }
  }
  if (executionClientId === "selenium") {
    const { Builder } = require(path.join(toolNodeDir, "node_modules", "selenium-webdriver"));
    const chrome = require(path.join(toolNodeDir, "node_modules", "selenium-webdriver", "chrome"));
    const driverPath = path.join(root, "downloads", "week6_ready", "chromedriver_110", "chromedriver.exe");
    if (!fs.existsSync(driverPath)) throw new Error(`Matching ChromeDriver is missing: ${driverPath}`);
    const service = new chrome.ServiceBuilder(driverPath)
      .loggingTo(path.join(logDir, `${runId}_chromedriver.log`))
      .enableVerboseLogging();
    const options = new chrome.Options()
      .androidPackage("com.example.hybridguard.featureapp")
      .androidActivity(".MainActivity")
      .androidProcess("com.example.hybridguard.featureapp")
      .androidDeviceSerial(serial)
      .androidUseRunningApp(true);
    const driver = await new Builder()
      .forBrowser("chrome")
      .setChromeService(service)
      .setChromeOptions(options)
      .build();
    try {
      const session = await driver.getSession();
      await driver.sendDevToolsCommand("Page.addScriptToEvaluateOnNewDocument", { source: script });
      await driver.get(probeUrl);
      return {
        protocol: "selenium-chromedriver-android-webview",
        webdriverSessionId: session.getId(),
        chromeDriverVersion: "110.0.5481.77",
        pageUrl: await driver.getCurrentUrl(),
        navigation: "selenium-driver-get",
      };
    } finally {
      await driver.quit().catch(() => {});
    }
  }
  if (executionClientId === "stealth") {
    const targets = await fetch(`${baseUrl}/json/list`).then((response) => response.json());
    const target = targets.find((item) => item.type === "page");
    if (!target) throw new Error("No WebView page target exposed for stealth plugin");
    const puppeteerCoreDir = path.join(toolNodeDir, "node_modules", "puppeteer-core", "lib", "puppeteer");
    const [{ Connection }, { NodeWebSocketTransport }] = await Promise.all([
      import(pathToFileURL(path.join(puppeteerCoreDir, "cdp", "Connection.js")).href),
      import(pathToFileURL(path.join(puppeteerCoreDir, "node", "NodeWebSocketTransport.js")).href),
    ]);
    const transport = await NodeWebSocketTransport.create(target.webSocketDebuggerUrl);
    const connection = new Connection(target.webSocketDebuggerUrl, transport, 0, 15000);
    const client = { send: (method, params = {}) => connection.send(method, params) };
    // Needed only for the plugin's internal initialization; UA is not part of
    // the fixed-WebView Stealth effect contract.
    const pluginUserAgent = injected.userAgent || "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36";
    const pageAdapter = {
      evaluateOnNewDocument: async (fn, ...args) => {
        const source = `(${fn.toString()})(${args.map((arg) => JSON.stringify(arg)).join(",")});`;
        await connection.send("Page.addScriptToEvaluateOnNewDocument", { source });
        const immediate = await connection.send("Runtime.evaluate", { expression: source, awaitPromise: true, returnByValue: true });
        if (immediate.exceptionDetails) {
          throw new Error(`Stealth evasion failed in current WebView context: ${JSON.stringify(immediate.exceptionDetails)}`);
        }
        return immediate;
      },
      browser: () => ({
        userAgent: async () => pluginUserAgent,
        version: async () => "Chrome/110.0.5481.154",
      }),
      _client: () => client,
    };
    // Legacy `stealth` preserves its historical composite set. V4 boundary
    // configurations provide a checked one-evasion selector so each run has
    // a single, hashable intervention surface.
    const defaultStealthEvasions = [
      { id: "navigator.webdriver", options: {} },
      { id: "navigator.hardwareConcurrency", options: { hardwareConcurrency: injected.hardwareConcurrency } },
      { id: "navigator.languages", options: { languages: ["en-US", "en"] } },
      { id: "navigator.plugins", options: {} },
      { id: "webgl.vendor", options: { vendor: injected.webglVendor, renderer: injected.webglRenderer } },
      { id: "user-agent-override", options: { userAgent: pluginUserAgent, locale: "en-US,en", maskLinux: true } },
    ];
    const evasionSpecs = (toolDefinition.stealthEvasions || defaultStealthEvasions)
      .map((evasion) => [evasion.id, evasion.options]);
    try {
      await connection.send("Page.enable");
      for (const [evasion, options] of evasionSpecs) {
        const createPlugin = require(path.join(toolNodeDir, "node_modules", "puppeteer-extra-plugin-stealth", "evasions", evasion));
        const plugin = createPlugin(options);
        if (typeof plugin.beforeConnect === "function") await plugin.beforeConnect();
        await plugin.onPageCreated(pageAdapter);
      }
      await connection.send("Page.navigate", { url: probeUrl });
      return {
        protocol: "puppeteer-extra-stealth-evasions-over-cdp",
        targetId: target.id,
        enabledEvasions: evasionSpecs.map(([name]) => name),
        navigation: "puppeteer-Connection-Page.navigate",
      };
    } finally {
      connection.dispose();
    }
  }
  const targets = await fetch(`${baseUrl}/json/list`).then((response) => response.json());
  const target = targets.find((item) => item.type === "page");
  if (!target) throw new Error("No WebView page target exposed for Puppeteer");
  const puppeteerCoreDir = path.join(toolNodeDir, "node_modules", "puppeteer-core", "lib", "puppeteer");
  const [{ Connection }, { NodeWebSocketTransport }] = await Promise.all([
    import(pathToFileURL(path.join(puppeteerCoreDir, "cdp", "Connection.js")).href),
    import(pathToFileURL(path.join(puppeteerCoreDir, "node", "NodeWebSocketTransport.js")).href),
  ]);
  const transport = await NodeWebSocketTransport.create(target.webSocketDebuggerUrl);
  const connection = new Connection(target.webSocketDebuggerUrl, transport, 0, 15000);
  try {
    await connection.send("Page.enable");
    await connection.send("Page.addScriptToEvaluateOnNewDocument", { source: script });
    await connection.send("Page.navigate", { url: probeUrl });
    return {
      protocol: "puppeteer-cdp-connection",
      targetId: target.id,
      targetUrl: target.url,
      navigation: "puppeteer-Connection-Page.navigate",
    };
  } finally {
    connection.dispose();
  }
}

async function sendRawCdp(webSocketUrl, commands) {
  const WebSocket = require(path.join(toolNodeDir, "node_modules", "ws"));
  await new Promise((resolve, reject) => {
    const ws = new WebSocket(webSocketUrl);
    let nextId = 1;
    let commandIndex = 0;
    const timer = setTimeout(() => {
      try { ws.close(); } catch {}
      reject(new Error("Timed out sending raw CDP commands"));
    }, 12000);
    ws.on("open", () => {
      ws.send(JSON.stringify({ id: nextId++, ...commands[commandIndex] }));
    });
    ws.on("message", (data) => {
      try {
        const message = JSON.parse(String(data));
        if (message.id && message.error) throw new Error(JSON.stringify(message.error));
        if (!message.id) return;
        commandIndex += 1;
        if (commandIndex >= commands.length) {
          clearTimeout(timer);
          ws.close();
          resolve();
          return;
        }
        ws.send(JSON.stringify({ id: nextId++, ...commands[commandIndex] }));
      } catch (error) {
        clearTimeout(timer);
        try { ws.close(); } catch {}
        reject(error);
      }
    });
    ws.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
  });
}

function appendMapping(row, evidence) {
  const values = [
    toolMeta.name,
    "Web Fingerprint Spoofing / Browser Automation",
    row.session_id,
    "featureapp",
    "expanded-v2",
    "measured_raw_session",
    serial,
    `FeatureApp Android WebView controlled by ${toolMeta.name}; configuration=${configurationId}; declared fields injected before probe execution`,
    "RBA-Cross-Device-Fingerprint-week6-featureapp/backend_server/expanded_collected_data.jsonl",
    `WebView debugging explicitly enabled for this controlled run; evidence=${JSON.stringify(evidence)}`,
    new Date().toISOString().slice(0, 10),
  ];
  fs.appendFileSync(mappingPath, values.map(csvEscape).join(",") + "\n", "utf8");
}

function readStealthRuntime(runtimeRoot) {
  const packagePath = path.join(runtimeRoot, "node_modules", "puppeteer-extra-plugin-stealth", "package.json");
  if (!fs.existsSync(packagePath)) {
    throw new Error(`Stealth runtime package manifest is missing: ${packagePath}`);
  }
  const manifest = JSON.parse(fs.readFileSync(packagePath, "utf8"));
  if (manifest.name !== "puppeteer-extra-plugin-stealth" || typeof manifest.version !== "string" || !manifest.version) {
    throw new Error(`Invalid Stealth runtime package manifest: ${packagePath}`);
  }
  return {
    package_name: manifest.name,
    package_version: manifest.version,
    package_json_sha256: crypto.createHash("sha256").update(fs.readFileSync(packagePath)).digest("hex"),
  };
}

function readRows() {
  return fs.existsSync(backendJsonl)
    ? fs.readFileSync(backendJsonl, "utf8").split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line))
    : [];
}

async function waitForFreshRows(beforeIds, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const fresh = readRows().filter((row) => !beforeIds.has(row.session_id));
    if (fresh.length) return fresh;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return readRows().filter((row) => !beforeIds.has(row.session_id));
}

function ensureBackend() {
  const output = sh("curl.exe", ["-s", "-m", "3", "http://127.0.0.1:8000/health"], { allowFailure: true });
  if (!output.includes("healthy")) throw new Error("Backend is not healthy on port 8000");
}

function waitForJsonEndpoint(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const output = sh("curl.exe", ["-s", "-m", "2", url], { allowFailure: true });
    if (output.includes("Protocol-Version")) return;
    sleep(500);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

function rebuildDerived() {
  for (const script of [
    "week6_build_82_tool_execution_matrix.mjs",
    "week6_build_featureapp_measured_dataset.mjs",
    "build_week6_runner_dashboard.mjs",
  ]) {
    const fullPath = path.join(root, "execution_log", "tools", script);
    const result = spawnSync(process.execPath, [fullPath], { cwd: root, encoding: "utf8", timeout: 120000 });
    if (result.status !== 0) throw new Error(`Failed rebuilding ${script}: ${result.stderr || result.stdout}`);
  }
}

function adb(...args) {
  let options = {};
  if (args.length && typeof args.at(-1) === "object") options = args.pop();
  const argv = options.noSerial ? args : ["-s", serial, ...args];
  return sh(adbExe, argv, options);
}

function sh(command, argv, options = {}) {
  try {
    return execFileSync(command, argv, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: options.timeoutMs || 30000 });
  } catch (error) {
    if (options.allowFailure) return `${error.stdout || ""}${error.stderr || ""}`;
    throw error;
  }
}

function csvEscape(value) {
  const text = String(value ?? "");
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function sleep(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}
