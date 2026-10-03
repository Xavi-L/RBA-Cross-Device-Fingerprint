// Engineering only: the current document's geometry function returns null.
// No Android fault switch, no screen-field mutation, no Native exception claim.
import {run, OBSERVE} from '../screen_geometry_observation_v1/screen_cdp.mjs';
import {pathToFileURL} from 'node:url';
export const FAULT_SCRIPT = `(function(){
 var probe; window.__geometryFaultCalls=0;
 Object.defineProperty(window,'HybridGuardProbe',{configurable:true,
  get:function(){return probe;},set:function(value){probe=value;
   if(value && typeof value.captureWebViewGeometry==='function'){
    value.captureWebViewGeometry=function(){window.__geometryFaultCalls++;return null;};
   }
  }});
})();`;
export async function executeFault(send,active,wait,pause=ms=>new Promise(r=>setTimeout(r,ms))){
 if(active)throw new Error('Fault position cannot apply screen intervention');
 const r={active_screen_override:false,fault_target:'Web geometry return value only',rollback_status:'NOT_EXECUTED'};
 let script;
 try{
  await send('Page.enable');await send('Emulation.clearDeviceMetricsOverride',{});
  script=(await send('Page.addScriptToEvaluateOnNewDocument',{source:FAULT_SCRIPT})).identifier;
  await send('Page.navigate',{url:'file:///android_asset/expanded_probe.html'});
  await pause(1000);r.raw_receipt=await wait();
  r.after_upload=(await send('Runtime.evaluate',{expression:'({calls:window.__geometryFaultCalls,screen:'+OBSERVE+'})',returnByValue:true})).result?.value;
  await pause(6000);r.late_observation_seconds=6;
  r.late_raw_receipt=await wait();
  r.after_deadline=(await send('Runtime.evaluate',{expression:'({calls:window.__geometryFaultCalls,screen:'+OBSERVE+'})',returnByValue:true})).result?.value;
 }catch(error){r.error=String(error.stack||error);}
 finally{
  try{
   if(script)await send('Page.removeScriptToEvaluateOnNewDocument',{identifier:script});
   await send('Emulation.clearDeviceMetricsOverride',{});r.rollback_status='COMPLETED';
  }catch(error){r.rollback_status='FAILED';r.rollback_error=String(error);}
 }
 r.status=r.error||r.rollback_status!=='COMPLETED'?'FAILED':'COMPLETED';return r;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 const [base,path,mode,archive,offset,context]=process.argv.slice(2);
 if(mode!=='noop')throw new Error('Only fault-noop allowed');
 const receipt=await run(base,path,false,archive,Number(offset),context,{version:'screen-geometry-web-fault-v1',flow:executeFault});
 if(receipt.status!=='COMPLETED')process.exitCode=1;
}
