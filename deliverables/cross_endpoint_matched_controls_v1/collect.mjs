// One local environment, exact tickets, unchanged B1 probe/backend, no detector imports.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createProbeServer,CdpClient,evaluateChecked,readJsonl,selectNewTicket,
  matchCompletedCapture,validateTarget,managedProbeTarget,waitForChromeReady}
  from '../browser67_pilot_intake_v1/source_reference/run_paired_browser_pilot.mjs';
const HERE=path.dirname(fileURLToPath(import.meta.url)), B1=path.resolve(HERE,'../browser67_pilot_intake_v1');
const exec=promisify(execFile), pause=ms=>new Promise(r=>setTimeout(r,ms)), now=()=>new Date().toISOString();
export const SCENARIOS=['L_SYS_LANG','L_SYS_TZ','L_BROWSER_LANG','A_APP_LANG','A_APP_TZ','A_BROWSER_LANG','A_BROWSER_TZ'];
export function positions(id,rounds=2,scenarios=SCENARIOS){
  return scenarios.flatMap(scenario=>Array.from({length:rounds},(_,i)=>['pre','change','post'].map(phase=>({
    sample_id:`${id}:${scenario}:r${i+1}:${phase}`,scenario_group_id:`${id}:${scenario}:r${i+1}`,
    scenario,round:i+1,phase,collection_round:i+1,runtime_context:`${id}.${scenario}.r${i+1}.${phase}`,
    capture_id:`${id}.${scenario}.r${i+1}.${phase}`}))).flat());
}
export function route(s){
  if(s.phase!=='change')return {kind:'none',endpoint:null};
  if(s.scenario.startsWith('L_'))return {kind:'real_setting',endpoint:s.scenario==='L_BROWSER_LANG'?'browser_preferences':'android_settings'};
  return {kind:s.scenario.endsWith('LANG')?'runtime_language':'runtime_timezone',endpoint:s.scenario.startsWith('A_APP')?'app':'browser'};
}
const OBS="({href:location.href,readyState:document.readyState,coreRevision:globalThis.HybridGuardWebProbe?.REVISION,language:navigator.language,languages:Array.from(navigator.languages),timezone_id:Intl.DateTimeFormat().resolvedOptions().timeZone,timezone_offset:new Date().getTimezoneOffset(),timestamp_ms:Date.now(),languageHasOwn:Object.prototype.hasOwnProperty.call(navigator,'language'),languagesHasOwn:Object.prototype.hasOwnProperty.call(navigator,'languages')})";
const LANG=JSON.parse(fs.readFileSync(path.join(B1,'source_reference/pilot_plan.json'))).controls[0];
export async function run(plan,out){
  if(!path.resolve(out).startsWith(path.join(HERE,'private_runs')+path.sep))throw Error('PRIVATE_RUN_REQUIRED');
  if(plan.serial!=='emulator-5580'||plan.browser_package!=='com.android.chrome')throw Error('OWNED_ENVIRONMENT_REQUIRED');
  const data=path.join(out,'data');if(!fs.existsSync(data))throw Error('START_FRESH_BACKEND_FIRST');
  const capturePath=path.join(out,'captures.jsonl');fs.writeFileSync(capturePath,'',{flag:'wx'});
  let slot=null;
  const record=async row=>fs.appendFileSync(path.join(out,'private_command_events.jsonl'),JSON.stringify({host_time_domain:'host_utc',host_monotonic_ns:String(process.hrtime.bigint()),capture_id:slot?.capture_id,...row})+'\n');
  const adb=async args=>{
    await record({kind:'adb_sent',at:now(),args});
    const r=await exec(plan.adb,['-s',plan.serial,...args],{timeout:20000,maxBuffer:4*1024*1024});
    await record({kind:'adb_received',at:now(),args,...r});return r.stdout.trim();
  };
  const json=async url=>(await fetch(url,{signal:AbortSignal.timeout(1500)})).json();
  const wait=async(fn,ms,code)=>{let last;for(let end=Date.now()+ms;Date.now()<end;){try{const r=await fn();if(r)return r;}catch(e){if(!['TypeError','AbortError','TimeoutError','SyntaxError'].includes(e.name))throw e;last=String(e);}await pause(150);}throw Error(code+(last?':'+last:''));};
  const observe=async c=>(await evaluateChecked(c,{expression:OBS,returnByValue:true})).result.value;
  const setting=async(s,action)=>{
    const result=await exec('python3',[path.join(HERE,'settings_control.py'),s.scenario,action,out],{timeout:150000,maxBuffer:1024*1024});
    return JSON.parse(result.stdout);
  };
  const rows=async file=>readJsonl(path.join(data,file));
  const ref=(file,r)=>({file:`data/${file}`,line:r.line,line_sha256:r.line_sha256});
  const site=await createProbeServer(path.join(B1,'evidence_archive/upstream/browser_probe_site/public'),{record});
  const options={plan};
  await adb(['reverse','tcp:8000','tcp:8000']);await adb(['reverse','tcp:8001','tcp:8001']);
  let unsafe=null;
  try{
    for(const s of plan.positions){
      slot=s;const control=route(s), cap={...s,control_route:control,started_at:now(),result:'FAILED',archives:{},control_installed:false};
      let app=null,browser=null,chrome=null,target=null,ticket=null,script=null,appApplied=false,browserApplied=false;
      try{
        if(unsafe)throw Error('PRIOR_RESTORATION_UNRESOLVED:'+unsafe);
        cap.setting=await setting(s,s.phase==='change'?'apply':s.phase==='post'?'restore':'snapshot');
        if(s.phase==='post'&&cap.setting.status==='FAILED')unsafe=s.sample_id;
        // Unsupported normal preferences still retain the planned pair. Labels are evaluated separately.
        await adb(['shell','am','force-stop',plan.app_package]);await adb(['shell','am','force-stop',plan.browser_package]);
        await adb(['forward','tcp:9340','localabstract:chrome_devtools_remote']);
        const warm=`${plan.static_origin}/pilot-warmup.html?context=${encodeURIComponent(s.runtime_context)}`;
        await adb(['shell','am','start','-W','-a','android.intent.action.VIEW','-d',warm,'-p',plan.browser_package]);
        const discovery=await waitForChromeReady(options,record,warm);cap.chrome_discovery=discovery;
        chrome=await CdpClient.connect(discovery.webSocketDebuggerUrl,row=>record({...row,endpoint:'browser_process'}));
        const targets=await wait(async()=>{const t=await json(plan.cdp_origin+'/json/list');return t.some(x=>x.url===warm)?t:null;},30000,'WARMUP_TIMEOUT');
        for(const t of targets.filter(managedProbeTarget)){
          const closed=await chrome.command('Target.closeTarget',{targetId:t.id});if(!closed.success)throw Error('WARMUP_CLOSE_FAILED');
        }
        const baseline=(await rows('browser_pair_events.jsonl')).at(-1)?.line||0;
        cap.event_baseline_line=baseline;site.gate.arm(s.capture_id);
        const p=plan.app_package;
        await adb(['shell','am','start','-W','-n',plan.app_activity,
          '--es',p+'.DEVICE_MANIFEST_ID',plan.device_manifest_id,'--es',p+'.RUNTIME_CONTEXT',s.runtime_context,
          '--ei',p+'.COLLECTION_ROUND',String(s.collection_round),'--es',p+'.COLLECT_ENDPOINT',plan.collect_endpoint,
          '--ez',p+'.ENABLE_WEBVIEW_DEBUG','true','--ez',p+'.WAIT_FOR_WEBVIEW_CONTROL','true','--el',p+'.PROBE_DELAY_MS','120000']);
        const pid=await adb(['shell','pidof',p]);if(!/^\d+$/.test(pid))throw Error('APP_PID_AMBIGUOUS');
        cap.app_pid=pid;await adb(['forward','tcp:9341',`localabstract:webview_devtools_remote_${pid}`]);
        const at=await wait(async()=>{const t=(await json('http://127.0.0.1:9341/json/list')).filter(t=>t.type==='page');if(t.length>1)throw Error('MULTIPLE_APP_TARGETS');return t[0];},30000,'APP_CDP_TIMEOUT');
        if(at.url!=='about:blank'||!at.webSocketDebuggerUrl.startsWith('ws://127.0.0.1:9341/'))throw Error('APP_TARGET_NOT_FRESH');
        cap.app_target={id:at.id,url:at.url,pid,forward:'webview_devtools_remote_'+pid};
        app=await CdpClient.connect(at.webSocketDebuggerUrl,row=>record({...row,endpoint:'app'}));
        await app.command('Page.enable');await app.command('Runtime.enable');
        cap.app_before=await observe(app);
        if(control.endpoint==='app'){
          cap.control_begin=now();
          if(control.kind==='runtime_language')script=(await app.command('Page.addScriptToEvaluateOnNewDocument',{source:LANG.params.expression})).identifier;
          else await app.command('Emulation.setTimezoneOverride',{timezoneId:'Asia/Tokyo'});
          appApplied=true;cap.control_installed=true;
        }
        cap.app_navigation_begin=now();await app.command('Page.navigate',{url:'file:///android_asset/expanded_probe.html'});
        cap.app_during=await wait(async()=>{const o=await observe(app);return o.href==='file:///android_asset/expanded_probe.html'?o:null;},10000,'APP_NAVIGATION_TIMEOUT');
        ({ticket,target}=await wait(async()=>{
          ticket=selectNewTicket(await rows('browser_pair_events.jsonl'),baseline,plan.browser_package);
          if(site.gate.violation)throw Error(site.gate.violation);
          if(!ticket||!site.gate.pending)return null;
          const t=(await json(plan.cdp_origin+'/json/list')).filter(t=>{try{validateTarget(t,ticket.pair_id);return true;}catch{return false;}});
          if(t.length>1)throw Error('MULTIPLE_PAIR_TARGETS');return t.length===1?{ticket,target:t[0]}:null;
        },60000,'BROWSER_TARGET_TIMEOUT'));
        cap.ticket=ticket;cap.browser_target={id:target.id,pair_id:ticket.pair_id};
        browser=await CdpClient.connect(target.webSocketDebuggerUrl,row=>record({...row,endpoint:'browser'}));
        await browser.command('Page.enable');await browser.command('Runtime.enable');
        cap.browser_before=await wait(async()=>{const o=await observe(browser);if(o.readyState==='complete')throw Error('BROWSER_GATE_TOO_LATE');return o.readyState==='interactive'&&o.coreRevision?o:null;},10000,'BROWSER_REALM_TIMEOUT');
        validateTarget({...target,url:cap.browser_before.href},ticket.pair_id);
        if(control.endpoint==='browser'){
          cap.control_begin=now();
          if(control.kind==='runtime_language'){
            if(cap.browser_before.languageHasOwn||cap.browser_before.languagesHasOwn)throw Error('PREEXISTING_LANGUAGE_OVERRIDE');
            await evaluateChecked(browser,LANG.params);
          }else await browser.command('Emulation.setTimezoneOverride',{timezoneId:'Asia/Tokyo'});
          browserApplied=true;cap.control_installed=true;
        }
        cap.browser_during=await observe(browser);cap.browser_gate_release=now();await site.gate.release();
        const matched=await wait(async()=>{
          if(site.gate.violation)throw Error(site.gate.violation);
          return matchCompletedCapture(s,plan,await rows('raw_expanded_payloads.jsonl'),await rows('browser_pair_provenance.jsonl'),await rows('raw_browser_payloads.jsonl'),ticket);
        },plan.collection_wait_ms,'PAIR_COMPLETION_TIMEOUT');
        cap.pair_completed_at=now();cap.binding=matched.pair.value;
        cap.archives={app:ref('raw_expanded_payloads.jsonl',matched.app),browser:ref('raw_browser_payloads.jsonl',matched.browser),provenance:ref('browser_pair_provenance.jsonl',matched.pair)};
        cap.result='COMPLETED';
      }catch(e){cap.failure=String(e.stack||e);}
      finally{
        // Preserve independently bound endpoints even when the pair did not complete.
        cap.ticket??=ticket;
        try{
          const a=(await rows('raw_expanded_payloads.jsonl')).filter(r=>r.value.canonical_received_payload?.collection_manifest?.runtime_context===s.runtime_context);
          const b=ticket?(await rows('raw_browser_payloads.jsonl')).filter(r=>r.value.pair_id===ticket.pair_id):[];
          if(a.length===1)cap.archives.app=ref('raw_expanded_payloads.jsonl',a[0]);
          if(b.length===1)cap.archives.browser=ref('raw_browser_payloads.jsonl',b[0]);
          cap.endpoint_counts={app:a.length,browser:b.length};
          cap.observation_end=now();
          if(app)cap.app_held_until_end=await observe(app);
          if(browser)cap.browser_held_until_end=await observe(browser);
        }catch(e){cap.final_observation_error=String(e);}
        const restoration=[];
        for(const [endpoint,c,applied] of [['app',app,appApplied],['browser',browser,browserApplied]]){
          if(!c)continue;
          try{
            if(applied){
              if(control.kind==='runtime_language'){
                if(endpoint==='app')await c.command('Page.removeScriptToEvaluateOnNewDocument',{identifier:script});
                await evaluateChecked(c,LANG.restoration);
              }else await c.command('Emulation.setTimezoneOverride',{timezoneId:''});
            }
            const observed=await observe(c);
            const before=cap[endpoint+'_before'];
            if(applied&&(observed.language!==before.language||JSON.stringify(observed.languages)!==JSON.stringify(before.languages)||observed.timezone_offset!==before.timezone_offset||observed.languageHasOwn||observed.languagesHasOwn))throw Error('RUNTIME_RESTORATION_MISMATCH');
            restoration.push({endpoint,at:now(),status:'COMPLETED',applied,observed});
          }catch(e){restoration.push({endpoint,at:now(),status:'FAILED',error:String(e)});unsafe=s.sample_id;}
          c.close();
        }
        cap.control_end=now();cap.restoration=restoration;
        if(site.gate.pending&&site.gate.state==='armed')await site.gate.abort();
        if(chrome&&target){try{cap.target_close=await chrome.command('Target.closeTarget',{targetId:target.id});}catch(e){cap.target_close_error=String(e);}}
        chrome?.close();cap.finished_at=now();
        fs.appendFileSync(capturePath,JSON.stringify(cap)+'\n');
        console.log(JSON.stringify({sample_id:s.sample_id,result:cap.result,setting:cap.setting?.status,restored:restoration.every(r=>r.status==='COMPLETED'),error:cap.failure?.split('\n')[0]}));
      }
    }
  }finally{
    site.server.closeAllConnections();await new Promise(r=>site.server.close(r));
    // Graceful backend stop is performed by the enclosing command after final evidence is read.
    for(const port of ['9340','9341'])await adb(['forward','--remove',`tcp:${port}`]).catch(()=>{});
    for(const port of ['8000','8001'])await adb(['reverse','--remove',`tcp:${port}`]).catch(()=>{});
  }
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const [planPath,out]=process.argv.slice(2);await run(JSON.parse(fs.readFileSync(planPath)),path.resolve(out));
}
