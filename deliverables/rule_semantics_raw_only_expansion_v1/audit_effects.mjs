import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { matchesWebviewAutomationProfile, webviewAutomationObservables, webviewObservableTolerance } from './source_snapshot/lib/webview_automation_profiles.mjs';

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'../..');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const lines=p=>fs.existsSync(p)?fs.readFileSync(p,'utf8').split('\n').filter(Boolean).map(JSON.parse):[];
const registry=Object.fromEntries(read(path.join(here,'CONFIGURATIONS.json')).map(c=>[c.id,c]));
const results=[];
function same(a,b,tolerance=0){
  if(a===undefined||b===undefined||a===null||b===null)return false;
  if(tolerance&&typeof a==='number'&&typeof b==='number')return Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=tolerance;
  return JSON.stringify(a)===JSON.stringify(b);
}
function observed(payload,field){
  const matches=Object.entries(payload.web_data||{}).filter(([,layer])=>layer&&typeof layer==='object'&&Object.hasOwn(layer,field));
  return matches.length===1&&payload.collection_status?.fields?.[`web_data.${matches[0][0]}.${field}`]==='observed';
}
for(const registration of read(path.join(here,'RUNS.json'))){
  const run=path.join(root,registration.path);
  const planPath=path.join(run,'plan.json');
  if(!fs.existsSync(planPath)){results.push({...registration,status:'NOT_STARTED',triplets:[]});continue;}
  const plan=read(planPath),sessions=lines(path.join(run,'sessions.jsonl'));
  const byStep=Object.fromEntries(sessions.map(r=>[r.step_id,r]));
  const rawRows=lines(path.join(run,'backend/raw_expanded_payloads.jsonl'));
  const raws=Object.fromEntries(rawRows.map(r=>[r.session_id,r.canonical_received_payload]));
  const triplets=[];
  for(const active of plan.filter(s=>s.phase==='attack')){
    const cfg=registry[active.configuration];
    const steps=plan.filter(s=>s.group===active.group&&s.round===active.round);
    const ordered=['clean_pre','attack','clean_post'].map(p=>steps.find(s=>s.phase===p));
    const saved=ordered.map(s=>s&&byStep[s.step_id]);
    const item={configuration_id:cfg.id,config_id:cfg.configId,round:active.round,
      group:active.group,step_ids:ordered.map(s=>s?.step_id),session_ids:saved.map(s=>s?.observation?.session_id||null),status:'INCOMPLETE'};
    if(saved.every(s=>s?.accepted===true)){
      const payloads=saved.map(s=>raws[s.observation.session_id]);
      const [pre,current,post]=payloads.map(p=>webviewAutomationObservables(p.web_data));
      const fields=cfg.observableFields;
      const statuses=payloads.every(p=>fields.every(f=>observed(p,f)));
      const activeMatches=matchesWebviewAutomationProfile(cfg.id,cfg.name,payloads[1].web_data);
      const changed=fields.filter(f=>!same(pre[f],current[f],webviewObservableTolerance(cfg.id,f)));
      const restored=fields.every(f=>same(pre[f],post[f],webviewObservableTolerance(cfg.id,f)));
      const logDir=path.join(run,'attempts',active.step_id,'automation');
      const logs=fs.readdirSync(logDir).filter(f=>f.endsWith('.json'));
      const receipt=logs.length===1?read(path.join(logDir,logs[0])):null;
      const execution=receipt?.status==='MEASURED'&&receipt?.configId===cfg.configId
        &&receipt?.configurationId===cfg.id&&JSON.stringify(receipt.measuredSessionIds)===JSON.stringify([item.session_ids[1]])
        &&JSON.stringify(receipt.injected)===JSON.stringify(cfg.profile)
        &&JSON.stringify(receipt.declaredObservableFields)===JSON.stringify(fields)
        &&(!cfg.cdpEmulation||receipt?.cdpEmulation?.rollback?.rollback_verified===true);
      Object.assign(item,{status:statuses&&activeMatches&&changed.length>0&&restored&&execution?'PASS':'REVIEW_REQUIRED',
        declared_fields_observed:statuses,active_profile_observed:activeMatches,
        changed_declared_fields:changed,declared_fields_restored:restored,execution_receipt_valid:execution,
        declared_values:{pre:Object.fromEntries(fields.map(f=>[f,pre[f]??null])),active:Object.fromEntries(fields.map(f=>[f,current[f]??null])),post:Object.fromEntries(fields.map(f=>[f,post[f]??null]))},
        tolerances:Object.fromEntries(fields.map(f=>[f,webviewObservableTolerance(cfg.id,f)]))});
    }
    triplets.push(item);
  }
  const attempts=plan.map(s=>path.join(run,'attempts',s.step_id,'attempt.json')).filter(fs.existsSync).map(read);
  results.push({...registration,status:sessions.length===registration.expected_positions&&attempts.every(a=>a.status==='ACCEPTED')?'COLLECTION_COMPLETE':'INCOMPLETE_OR_FAILED',
    saved:sessions.length,raw_saved:rawRows.length,attempted:attempts.length,
    failed_attempts:attempts.filter(a=>a.status==='FAILED').length,
    not_attempted:registration.expected_positions-attempts.length,triplets});
}
const primary=results.filter(r=>r.role==='PRIMARY_PROPOSED');
const assignmentPath=path.join(here,'PRIMARY_ASSIGNMENT.json');
const assignments=fs.existsSync(assignmentPath)?read(assignmentPath):null;
const assigned=assignments?.map(a=>{
  const source=results.find(r=>r.path===a.source_run);
  const triplets=source?.triplets.filter(t=>t.configuration_id===a.configuration_id)||[];
  return {...a,triplets,status:triplets.length===3&&new Set(triplets.map(t=>t.round)).size===3&&triplets.every(t=>t.status==='PASS')?'PASS':'NOT_READY'};
});
const result={scope:'Independent intervention effect and declared-field restoration; no candidate/detector invocation.',
  status:(assigned?assigned.length===42&&assigned.every(a=>a.status==='PASS'):primary.every(r=>r.status==='COLLECTION_COMPLETE'&&r.triplets.every(t=>t.status==='PASS')))?'PRIMARY_EFFECTS_PASS':'PRIMARY_NOT_READY',
  primary_assignments:assigned,runs:results};
if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:result.status,runs:results.map(r=>({api:r.api,kind:r.kind,role:r.role,status:r.status,saved:r.saved,failed:r.failed_attempts,triplet_statuses:r.triplets.reduce((a,t)=>(a[t.status]=(a[t.status]||0)+1,a),{})}))},null,2));
