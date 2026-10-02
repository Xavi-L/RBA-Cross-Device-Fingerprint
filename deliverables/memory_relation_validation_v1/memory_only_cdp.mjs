// Reuses the week6 raw-CDP attach/new-document/navigation mechanism. The new
// configuration writes one navigator property only; normal stages use void 0.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';

export function injectionSource(target) {
  if (target === null) return 'void 0;';
  if (![2, 4, 8, 16].includes(target)) throw new Error('Fixed target required');
  return `(() => { const value = ${target};
    Object.defineProperty(Navigator.prototype, 'deviceMemory', {configurable:true, get:() => value});
    Object.defineProperty(navigator, 'deviceMemory', {configurable:true, get:() => value});
  })();`;
}

export async function run(baseUrl, receiptPath, target) {
  const source = injectionSource(target);
  const receipt = {version:'memory-only-cdp-v1', status:'STARTED', target_gib:target,
    injected_properties:target===null ? [] : ['navigator.deviceMemory'],
    source, started_at:new Date().toISOString(), commands:[]};
  fs.writeFileSync(receiptPath, JSON.stringify(receipt,null,2)+'\n', {flag:'wx'});
  const save=()=>fs.writeFileSync(receiptPath, JSON.stringify(receipt,null,2)+'\n');
  let socket, identifier;
  try {
    const u=new URL(baseUrl);
    if (u.hostname!=='127.0.0.1' || u.protocol!=='http:') throw new Error('Local CDP only');
    let pages=[];
    for (let i=0;i<30;i++) {
      try { pages=(await fetch(baseUrl+'/json/list',{signal:AbortSignal.timeout(1000)}).then(r=>r.json())).filter(t=>t.type==='page'); } catch {}
      if (pages.length) break;
      await new Promise(r=>setTimeout(r,500));
    }
    if (pages.length!==1 || pages[0].url!=='about:blank') throw new Error('Expected one waiting App page');
    const ws=new URL(pages[0].webSocketDebuggerUrl);
    if (!['127.0.0.1','localhost'].includes(ws.hostname)) throw new Error('Nonlocal CDP socket');
    receipt.target={id:pages[0].id,url:pages[0].url};save();
    socket=new WebSocket(ws);
    await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error('CDP open timeout')),10000);
      socket.addEventListener('open',()=>{clearTimeout(timer);resolve();},{once:true});
      socket.addEventListener('error',()=>{clearTimeout(timer);reject(new Error('CDP open failed'));},{once:true});
    });
    let next=0;
    async function send(method,params={}) {
      const id=++next, event={id,method,params};receipt.commands.push(event);save();
      return new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>{socket.removeEventListener('message',handler);reject(new Error(method+' timeout'));},12000);
        function handler(e) {
          let m;try {m=JSON.parse(String(e.data));}catch{return;}
          if(m.id!==id)return;
          clearTimeout(timer);socket.removeEventListener('message',handler);
          event.result=m.result;event.error=m.error;save();
          if(m.error || m.result?.errorText || m.result?.exceptionDetails)reject(new Error(JSON.stringify(m)));
          else resolve(m.result||{});
        }
        socket.addEventListener('message',handler);socket.send(JSON.stringify({id,method,params}));
      });
    }
    await send('Page.enable');
    ({identifier}=await send('Page.addScriptToEvaluateOnNewDocument',{source}));
    await send('Page.navigate',{url:'file:///android_asset/expanded_probe.html'});
    await new Promise(r=>setTimeout(r,1000));
    const observed=await send('Runtime.evaluate',{expression:'({deviceMemory:navigator.deviceMemory,hardwareConcurrency:navigator.hardwareConcurrency})',returnByValue:true});
    receipt.current_runtime_observation=observed.result?.value;
    if(identifier) await send('Page.removeScriptToEvaluateOnNewDocument',{identifier});
    receipt.future_document_script_removed=!!identifier;
    receipt.current_document_rollback='OWNED_APP_PROCESS_EXIT_REQUIRED; verify next clean_post payload';
    receipt.status='COMPLETED';
  } catch(error) {
    receipt.status='FAILED';receipt.error=String(error.stack||error);throw error;
  } finally {
    receipt.finished_at=new Date().toISOString();save();socket?.close();
  }
  return receipt;
}

if (process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href) {
  const [base,path,target]=process.argv.slice(2);
  await run(base,path,target==='noop'?null:Number(target));
}
