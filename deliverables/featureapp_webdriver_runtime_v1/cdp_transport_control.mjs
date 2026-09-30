// Same CDP attach/navigation surface as the low-level runner, with no injection.
import fs from "node:fs";

const [baseUrl, receiptPath] = process.argv.slice(2);
if (!baseUrl || !receiptPath) throw new Error("Usage: node cdp_transport_control.mjs <base-url> <new-receipt-path>");
const receipt = {schema_version: "cdp-transport-control-v1", status: "STARTED", started_at: new Date().toISOString(), commands: [], injection_performed: false};
fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + "\n", {flag: "wx"});
const save = () => fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + "\n");
let socket;
try {
  const url = new URL(baseUrl);
  if (url.hostname !== "127.0.0.1" || url.protocol !== "http:") throw new Error("Only the local forwarded CDP endpoint is supported");
  let targets;
  for (let attempt = 0; attempt < 30; attempt++) {
    try {
      targets = await fetch(`${baseUrl}/json/list`, {signal: AbortSignal.timeout(1000)}).then(response => response.json());
      if (targets.some(target => target.type === "page")) break;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  const pages = (targets || []).filter(target => target.type === "page");
  if (pages.length !== 1 || pages[0].url !== "about:blank") throw new Error("Expected exactly one waiting about:blank page");
  const target = pages[0];
  const wsUrl = new URL(target.webSocketDebuggerUrl);
  if (!["127.0.0.1", "localhost"].includes(wsUrl.hostname)) throw new Error("CDP socket is not local");
  receipt.target = {id: target.id, url: target.url};
  save();
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("WebSocket open timeout")), 10000);
    socket.addEventListener("open", () => { clearTimeout(timer); resolve(); }, {once: true});
    socket.addEventListener("error", () => { clearTimeout(timer); reject(new Error("WebSocket open failed")); }, {once: true});
  });
  for (const [index, command] of [
    {method: "Page.enable"},
    {method: "Page.navigate", params: {url: "file:///android_asset/expanded_probe.html"}},
  ].entries()) {
    const id = index + 1;
    const commandReceipt = {id, ...command, started_at: new Date().toISOString(), status: "STARTED"};
    receipt.commands.push(commandReceipt);
    save();
    const result = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => { socket.removeEventListener("message", onMessage); reject(new Error(`${command.method} timeout`)); }, 12000);
      function onMessage(event) {
        let message;
        try { message = JSON.parse(String(event.data)); } catch { return; }
        if (message.id !== id) return;
        clearTimeout(timer);
        socket.removeEventListener("message", onMessage);
        if (message.error || message.result?.errorText) reject(new Error(JSON.stringify(message.error || message.result)));
        else resolve(message.result || {});
      }
      socket.addEventListener("message", onMessage);
      socket.send(JSON.stringify({id, ...command}));
    });
    Object.assign(commandReceipt, {status: "COMPLETED", completed_at: new Date().toISOString(), result});
    save();
  }
  await new Promise(resolve => setTimeout(resolve, 1000));
  receipt.status = "COMPLETED_NO_INJECTION";
  receipt.completed_at = new Date().toISOString();
  save();
} catch (error) {
  receipt.status = "FAILED";
  receipt.error = String(error.stack || error);
  receipt.completed_at = new Date().toISOString();
  save();
  process.exitCode = 1;
} finally {
  socket?.close();
}
