// CDP controls the existing experiment only; the APK owns all geometry observation.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {waitForRaw} from '../timezone_relation_validation_v1/timezone_cdp.mjs';
export const PARAMETERS=Object.freeze({width:393,height:851,deviceScaleFactor:2.75,mobile:true,
  screenWidth:393,screenHeight:851,positionX:0,positionY:0});
export const OBSERVE='({inner_width:innerWidth,inner_height:innerHeight,screen_width:screen.width,screen_height:screen.height,dpr:devicePixelRatio,visual_width:visualViewport?.width,visual_height:visualViewport?.height,visual_scale:visualViewport?.scale,user_agent:navigator.userAgent,hardware_concurrency:navigator.hardwareConcurrency,device_memory:navigator.deviceMemory})';
export async function executeFlow(send,active,wait,pause=ms=>new Promise(r=>setTimeout(r,ms))){
  const evidence={active_screen_override:active,rollback_status:'NOT_EXECUTED'};
  try{
    await send('Page.enable');
    await send(active?'Emulation.setDeviceMetricsOverride':'Emulation.clearDeviceMetricsOverride',active?PARAMETERS:{});
    evidence.apply_status='COMPLETED';
    await send('Page.navigate',{url:'file:///android_asset/expanded_probe.html'});
    await pause(1000);
    evidence.raw_receipt=await wait();
    evidence.current_runtime_observation=(await send('Runtime.evaluate',{expression:OBSERVE,returnByValue:true})).result?.value;
  }catch(error){evidence.error=String(error.stack||error);}
  finally{
    try{
      await send('Emulation.clearDeviceMetricsOverride',{});
      evidence.rollback_status='COMPLETED';
      evidence.after_rollback_runtime_observation=(await send('Runtime.evaluate',{expression:OBSERVE,returnByValue:true})).result?.value;
    }catch(error){evidence.rollback_status='FAILED';evidence.rollback_error=String(error.stack||error);}
  }
  evidence.status=evidence.error||evidence.rollback_status!=='COMPLETED'?'FAILED':'COMPLETED';
  return evidence;
}
export async function run(base,path,active,archive,offset,context){
  const receipt={version:'screen-only-cdp-v1',started_at:new Date().toISOString(),status:'STARTED',
    active_screen_override:active,parameters:active?PARAMETERS:null,commands:[]};
  fs.writeFileSync(path,JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
  const save=()=>fs.writeFileSync(path,JSON.stringify(receipt,null,2)+'\n');let socket;
  try{
    const url=new URL(base);if(url.hostname!=='127.0.0.1'||url.protocol!=='http:')throw new Error('Local owned CDP only');
    let pages=[];
    for(let i=0;i<30;i++){
      try{pages=(await fetch(base+'/json/list',{signal:AbortSignal.timeout(1000)}).then(r=>r.json())).filter(t=>t.type==='page');}catch{}
      if(pages.length)break;await new Promise(r=>setTimeout(r,500));
    }
    if(pages.length!==1||pages[0].url!=='about:blank')throw new Error('One owned waiting App document required');
    const ws=new URL(pages[0].webSocketDebuggerUrl);if(!['127.0.0.1','localhost'].includes(ws.hostname))throw new Error('Nonlocal debugger');
    socket=new WebSocket(ws);await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error('CDP open timeout')),10000);
      socket.addEventListener('open',()=>{clearTimeout(timer);resolve();},{once:true});
      socket.addEventListener('error',()=>{clearTimeout(timer);reject(new Error('CDP open error'));},{once:true});
    });let next=0;
    async function send(method,params={}){
      const event={id:++next,method,params};receipt.commands.push(event);save();
      return new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>{socket.removeEventListener('message',handler);reject(new Error(method+' timeout'));},12000);
        function handler(e){let m;try{m=JSON.parse(String(e.data));}catch{return;}if(m.id!==event.id)return;
          clearTimeout(timer);socket.removeEventListener('message',handler);event.result=m.result;event.error=m.error;save();
          if(m.error||m.result?.errorText||m.result?.exceptionDetails)reject(new Error(JSON.stringify(m)));else resolve(m.result||{});}
        socket.addEventListener('message',handler);socket.send(JSON.stringify(event));
      });
    }
    Object.assign(receipt,await executeFlow(send,active,()=>waitForRaw(archive,offset,context,55)));
  }catch(error){receipt.status='FAILED';receipt.error=String(error.stack||error);}
  finally{receipt.finished_at=new Date().toISOString();save();socket?.close();}
  return receipt;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  const [base,path,active,archive,offset,context]=process.argv.slice(2);
  if(!['active','noop'].includes(active))throw new Error('active or noop required');
  if((await run(base,path,active==='active',archive,Number(offset),context)).status!=='COMPLETED')process.exitCode=1;
}
