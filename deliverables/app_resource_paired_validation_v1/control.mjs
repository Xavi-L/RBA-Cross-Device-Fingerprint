// Six fixed processes. No detector, learned model, collection or network in this module.
export const SCENARIOS=['A_APP_RESOURCE','A_APP_MEMORY4','A_BROWSER_RESOURCE','A_BROWSER_MEMORY4','N_APP_SHAM','N_BROWSER_SHAM'];
export function route(s){
  if(!SCENARIOS.includes(s.scenario)||!['pre','change','post'].includes(s.phase))throw Error('UNREGISTERED_POSITION');
  const endpoint=s.scenario.includes('_APP_')?'app':'browser';
  return {endpoint,kind:s.phase==='change'&&s.scenario.startsWith('A_')?'resource_override':'sham',
    targets:s.phase==='change'&&s.scenario.startsWith('A_')?(s.scenario.endsWith('RESOURCE')?{deviceMemory:16,hardwareConcurrency:48}:{deviceMemory:4}):{}};
}
export function observe(){
  const resource=k=>{let v,present=k in navigator,error=null;try{v=navigator[k];}catch(e){error=String(e);}
    const own=Object.getOwnPropertyDescriptor(navigator,k),proto=Object.getOwnPropertyDescriptor(Navigator.prototype,k);
    const descriptor=d=>d?{configurable:d.configurable,enumerable:d.enumerable,get:d.get?String(d.get):null,set:d.set?String(d.set):null,value:typeof d.value==='number'?d.value:null}:null;
    return {present,value:typeof v==='number'&&Number.isFinite(v)?v:null,type:typeof v,status:error?'runtime_error':!present?'unsupported':typeof v==='number'&&Number.isFinite(v)&&v>0?'observed':'unavailable',error,own:descriptor(own),prototype:descriptor(proto)};};
  return {href:location.href,origin:location.origin,isSecureContext:globalThis.isSecureContext,readyState:document.readyState,
    coreRevision:globalThis.HybridGuardWebProbe?.REVISION,timestamp_ms:Date.now(),timeOrigin:performance.timeOrigin,
    resources:{deviceMemory:resource('deviceMemory'),hardwareConcurrency:resource('hardwareConcurrency')},
    nontarget:{userAgent:navigator.userAgent,platform:navigator.platform,language:navigator.language,languages:Array.from(navigator.languages),webdriver:navigator.webdriver,timezone_id:Intl.DateTimeFormat().resolvedOptions().timeZone,timezone_offset:new Date().getTimezoneOffset(),screen:{width:screen.width,height:screen.height,colorDepth:screen.colorDepth},dpr:devicePixelRatio},
    control:globalThis.__resourceControl};
}
export const OBS=`(${observe.toString()})()`;
export function controlSource(targets){
  if(Object.entries(targets).some(([k,v])=>!((k==='deviceMemory'&&[4,16].includes(v))||(k==='hardwareConcurrency'&&v===48))))throw Error('UNREGISTERED_TARGET');
  return `(() => {
    const observe=${observe.toString()}, targets=${JSON.stringify(targets)};
    if(globalThis.__resourceControl)throw Error('CONTROL_ALREADY_PRESENT');
    const before=observe(), applied=[], skipped=[], saved=[];
    globalThis.__resourceControl={before,targets,applied,skipped,restored:false};
    globalThis.__restoreResource=()=>{for(const [o,k,d] of saved.reverse()){if(d)Object.defineProperty(o,k,d);else delete o[k];}globalThis.__resourceControl.restored=true;return true;};
    for(const [k,v] of Object.entries(targets)){
      const initial=before.resources[k];
      if(initial.status!=='observed'||(k==='hardwareConcurrency'&&!Number.isInteger(initial.value))){skipped.push({field:k,reason:'ORIGINAL_UNAVAILABLE'});continue;}
      if(initial.own){skipped.push({field:k,reason:'PREEXISTING_OWN_DESCRIPTOR'});continue;}
      for(const o of [Navigator.prototype,navigator]){const d=Object.getOwnPropertyDescriptor(o,k);saved.push([o,k,d]);Object.defineProperty(o,k,{configurable:true,enumerable:d?.enumerable??false,get:()=>v});}
      applied.push(k);
    }
    return globalThis.__resourceControl;
  })()`;
}
export function sameResources(a,b){return !!a&&!!b&&JSON.stringify(a.resources)===JSON.stringify(b.resources);}
