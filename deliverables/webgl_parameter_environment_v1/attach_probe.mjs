// Same installed webgl.vendor evasion and page adapter as the existing runner.
// Clean stages use the same Connection/navigation without loading any plugin.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const protocol = JSON.parse(fs.readFileSync(path.join(here, "PROTOCOL.json"), "utf8"));
const toolDir = path.join(root, "deliverables/rule_semantics_raw_only_expansion_v1/runtime/tool_node/node_modules");
const require = createRequire(import.meta.url);
const [mode, receiptPath] = process.argv.slice(2);
if (!["clean", "attack"].includes(mode) || !receiptPath) throw new Error("Expected clean|attack and receipt path");
const receipt = {status: "STARTED", mode, started_at: new Date().toISOString(),
  adapter: "parameter-observer-puppeteer-connection-v1", commands: [], enabled_evasions: []};
fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + "\n", {flag: "wx"});
const save = () => fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + "\n");
let connection;
try {
  for (const [name, expected] of [["puppeteer-core", protocol.intervention.puppeteer_core_version],
                                [protocol.intervention.plugin, protocol.intervention.version]]) {
    const version = JSON.parse(fs.readFileSync(path.join(toolDir, name, "package.json"), "utf8")).version;
    if (version !== expected) throw new Error(`${name} version differs from protocol`);
    receipt[name] = version;
  }
  const baseUrl = `http://127.0.0.1:${protocol.runtime.cdp_port}`;
  let targets = [];
  for (let i = 0; i < 30; i++) {
    try { targets = await fetch(`${baseUrl}/json/list`, {signal: AbortSignal.timeout(1000)}).then(r => r.json()); }
    catch { targets = []; }
    if (targets.some(t => t.type === "page")) break;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  const pages = targets.filter(t => t.type === "page");
  if (pages.length !== 1 || pages[0].url !== "about:blank") throw new Error("Expected one waiting about:blank target");
  const target = pages[0];
  const socketUrl = new URL(target.webSocketDebuggerUrl);
  if (!["127.0.0.1", "localhost"].includes(socketUrl.hostname)) throw new Error("Only local forwarded target allowed");
  receipt.target = {id: target.id, url: target.url};
  const core = path.join(toolDir, "puppeteer-core/lib/puppeteer");
  const [{Connection}, {NodeWebSocketTransport}] = await Promise.all([
    import(pathToFileURL(path.join(core, "cdp/Connection.js")).href),
    import(pathToFileURL(path.join(core, "node/NodeWebSocketTransport.js")).href),
  ]);
  const transport = await NodeWebSocketTransport.create(target.webSocketDebuggerUrl);
  connection = new Connection(target.webSocketDebuggerUrl, transport, 0, 15000);
  async function send(method, params = {}) {
    const result = await connection.send(method, params);
    if (result.errorText || result.exceptionDetails) throw new Error(`${method}: ${JSON.stringify(result)}`);
    receipt.commands.push({method, status: "COMPLETED"});
    save();
    return result;
  }
  await send("Page.enable");
  if (mode === "attack") {
    const pageAdapter = {
      evaluateOnNewDocument: async (fn, ...args) => {
        const source = `(${fn.toString()})(${args.map(arg => JSON.stringify(arg)).join(",")});`;
        await send("Page.addScriptToEvaluateOnNewDocument", {source});
        return send("Runtime.evaluate", {expression: source, awaitPromise: true, returnByValue: true});
      },
    };
    const createPlugin = require(path.join(toolDir, protocol.intervention.plugin, "evasions", protocol.intervention.evasion));
    const plugin = createPlugin(protocol.intervention.options);
    if (typeof plugin.beforeConnect === "function") await plugin.beforeConnect();
    await plugin.onPageCreated(pageAdapter);
    receipt.enabled_evasions = [protocol.intervention.evasion];
    receipt.options = protocol.intervention.options;
  }
  receipt.navigation = await send("Page.navigate", {url: "file:///android_asset/expanded_probe.html"});
  let ready = false;
  for (let i = 0; i < protocol.limits.observer_ready_seconds * 5; i++) {
    const state = await send("Runtime.evaluate", {expression:
      "location.href === 'file:///android_asset/expanded_probe.html' && document.readyState === 'complete' && !!window.HybridGuardWebProbe && !!window.AndroidBridge", returnByValue: true});
    if (state.result.value === true) { ready = true; break; }
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  if (!ready) throw new Error("Observer target did not become ready");
  const observer = fs.readFileSync(path.join(here, "source_snapshot/webgl_parameter_observer.js"), "utf8");
  const expression = observer + `
    (function () {
      var before = window.AndroidBridge.getSessionId();
      var urlBefore = location.href;
      var measured = window.HybridGuardWebGLParameterObserver.observe({
        realmBinding: "featureapp:" + before + ":main-frame"
      });
      return {observation: measured, binding: {
        session_id_before: before, session_id_after: window.AndroidBridge.getSessionId(),
        url_before: urlBefore, url_after: location.href,
        canonical_probe_revision: window.HybridGuardWebProbe.REVISION
      }};
    })();`;
  const measured = await send("Runtime.evaluate", {expression, returnByValue: true,
    awaitPromise: true, timeout: protocol.limits.observer_call_ms});
  const result = measured.result.value;
  if (!result || result.observation?.observation_schema_version !== protocol.observer.schema)
    throw new Error("Versioned observation missing or invalid");
  for (const [name, value] of [["OBSERVATION.json", result.observation], ["BINDING.json", result.binding]]) {
    fs.writeFileSync(path.join(path.dirname(receiptPath), name),
      JSON.stringify(value, null, 2) + "\n", {flag: "wx"});
  }
  receipt.observation_session_id = result.binding.session_id_before;
  receipt.status = "MEASURED_AND_NAVIGATED";
  receipt.note = "Command completion alone is not measured effect; raw payload and post restoration checked separately";
} catch (error) {
  receipt.status = "FAILED";
  receipt.error = String(error.stack || error);
  process.exitCode = 1;
} finally {
  connection?.dispose();
  receipt.finished_at = new Date().toISOString();
  save();
}
