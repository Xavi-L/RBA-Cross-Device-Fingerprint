// Existing week10 timezone override, scoped to one owned App WebView target.
// Every phase attaches, clears/applies only timezone, navigates and waits for raw.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';

export const TARGETS = Object.freeze(['UTC', 'America/Los_Angeles']);
export function timezonePlan(target) {
  if (target !== null && !TARGETS.includes(target)) throw new Error('Fixed timezone target required');
  return {apply:{method:'Emulation.setTimezoneOverride',params:{timezoneId:target ?? ''}},
          rollback:{method:'Emulation.setTimezoneOverride',params:{timezoneId:''}}};
}
export const OBSERVE = '({timezone_id:Intl.DateTimeFormat().resolvedOptions().timeZone,timezone_offset:new Date().getTimezoneOffset(),timestamp_ms:Date.now(),device_memory:navigator.deviceMemory,hardware_concurrency:navigator.hardwareConcurrency,user_agent:navigator.userAgent,platform:navigator.platform,language:navigator.language,languages:Array.from(navigator.languages),webdriver:navigator.webdriver,screen_width:screen.width,screen_height:screen.height,dpr:devicePixelRatio,inner_width:innerWidth,inner_height:innerHeight})';

export async function executeFlow(send, target, waitForCollection, pause = ms => new Promise(r => setTimeout(r,ms))) {
  const plan = timezonePlan(target), evidence = {target_timezone:target,rollback_status:'NOT_EXECUTED'};
  try {
    await send('Page.enable');
    await send(plan.apply.method,plan.apply.params);
    evidence.apply_status='COMPLETED';
    await send('Page.navigate',{url:'file:///android_asset/expanded_probe.html'});
    await pause(1000);
    evidence.current_runtime_observation=(await send('Runtime.evaluate',{expression:OBSERVE,returnByValue:true})).result?.value;
    // Never clear before the collector has finished Native/Web acquisition and upload.
    evidence.raw_receipt=await waitForCollection();
  } catch(error) {
    evidence.error=String(error.stack||error);
  } finally {
    try {
      await send(plan.rollback.method,plan.rollback.params);
      evidence.rollback_status='COMPLETED';
      evidence.after_rollback_runtime_observation=(await send('Runtime.evaluate',{expression:OBSERVE,returnByValue:true})).result?.value;
    } catch(error) {
      evidence.rollback_status='FAILED';evidence.rollback_error=String(error.stack||error);
    }
  }
  evidence.status=evidence.error || evidence.rollback_status!=='COMPLETED' ? 'FAILED' : 'COMPLETED';
  return evidence;
}

export async function waitForRaw(path, offset, context, seconds=40) {
  const deadline=Date.now()+seconds*1000;
  while(Date.now()<deadline) {
    if(fs.existsSync(path)) {
      const data=fs.readFileSync(path).subarray(offset).toString('utf8');
      const rows=data.split('\n').slice(0,-1).filter(Boolean).map(line=>JSON.parse(line))
        .filter(row=>row.canonical_received_payload?.collection_manifest?.runtime_context===context);
      if(rows.length>1)throw new Error('Multiple current raw payloads');
      if(rows.length===1)return {session_id:rows[0].session_id,received_before_rollback:true};
    }
    await new Promise(r=>setTimeout(r,250));
  }
  throw new Error('No raw upload received for this planned position');
}

export async function run(baseUrl, receiptPath, target, archive, offset, context) {
  timezonePlan(target);
  const receipt={version:'timezone-only-cdp-v1',status:'STARTED',target_timezone:target,
    changed_domains:target===null?[]:['Web timezone'],started_at:new Date().toISOString(),commands:[]};
  fs.writeFileSync(receiptPath,JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
  const save=()=>fs.writeFileSync(receiptPath,JSON.stringify(receipt,null,2)+'\n');
  let socket;
  try {
    const u=new URL(baseUrl);
    if(u.hostname!=='127.0.0.1'||u.protocol!=='http:')throw new Error('Local CDP only');
    let pages=[];
    for(let i=0;i<30;i++) {
      try {pages=(await fetch(baseUrl+'/json/list',{signal:AbortSignal.timeout(1000)}).then(r=>r.json())).filter(t=>t.type==='page');}catch{}
      if(pages.length)break;
      await new Promise(r=>setTimeout(r,500));
    }
    if(pages.length!==1||pages[0].url!=='about:blank')throw new Error('Expected one waiting owned App page');
    const ws=new URL(pages[0].webSocketDebuggerUrl);
    if(!['127.0.0.1','localhost'].includes(ws.hostname))throw new Error('Nonlocal CDP socket');
    receipt.target={id:pages[0].id,url:pages[0].url};save();
    socket=new WebSocket(ws);
    await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error('CDP open timeout')),10000);
      socket.addEventListener('open',()=>{clearTimeout(timer);resolve();},{once:true});
      socket.addEventListener('error',()=>{clearTimeout(timer);reject(new Error('CDP open failed'));},{once:true});
    });
    let next=0;
    async function send(method,params={}) {
      const id=++next,event={id,method,params};receipt.commands.push(event);save();
      return new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>{socket.removeEventListener('message',handler);reject(new Error(method+' timeout'));},12000);
        function handler(e) {
          let m;try{m=JSON.parse(String(e.data));}catch{return;}
          if(m.id!==id)return;
          clearTimeout(timer);socket.removeEventListener('message',handler);
          event.result=m.result;event.error=m.error;save();
          if(m.error||m.result?.errorText||m.result?.exceptionDetails)reject(new Error(JSON.stringify(m)));
          else resolve(m.result||{});
        }
        socket.addEventListener('message',handler);socket.send(JSON.stringify({id,method,params}));
      });
    }
    Object.assign(receipt,await executeFlow(send,target,()=>waitForRaw(archive,offset,context)));
    receipt.current_document_rollback='CDP empty timezone override; owned App process exits and clean_post is independently collected';
  } catch(error) {
    receipt.status='FAILED';receipt.error=String(error.stack||error);
  } finally {
    receipt.finished_at=new Date().toISOString();save();socket?.close();
  }
  return receipt;
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href) {
  const [base,path,target,archive,offset,context]=process.argv.slice(2);
  const receipt=await run(base,path,target==='noop'?null:target,archive,Number(offset),context);
  if(receipt.status!=='COMPLETED')process.exitCode=1;
}
