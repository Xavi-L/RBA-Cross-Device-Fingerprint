import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {timezonePlan, executeFlow, waitForRaw, OBSERVE} from './timezone_cdp.mjs';

test('only fixed two targets or no-op use timezone override',()=>{
  for(const target of [null,'UTC','America/Los_Angeles']) {
    const p=timezonePlan(target);
    assert.deepEqual(p.apply,{method:'Emulation.setTimezoneOverride',params:{timezoneId:target??''}});
    assert.deepEqual(p.rollback,{method:'Emulation.setTimezoneOverride',params:{timezoneId:''}});
  }
  for(const bad of ['Asia/Shanghai','',0,undefined,{},'Europe/London'])assert.throws(()=>timezonePlan(bad));
  assert(!OBSERVE.includes('Object.defineProperty'));
});

test('all phases share navigation/read flow, clear only after raw receipt',async()=>{
  for(const target of [null,'UTC','America/Los_Angeles']) {
    const calls=[];
    const send=async(method,params)=>{calls.push({method,params});return {result:{value:{timezone_offset:0}}};};
    const r=await executeFlow(send,target,async()=>{calls.push({method:'RAW_RECEIVED'});return {session_id:'same',received_before_rollback:true};},async()=>{});
    assert.equal(r.status,'COMPLETED');assert.equal(r.rollback_status,'COMPLETED');
    assert.deepEqual(calls.map(c=>c.method),['Page.enable','Emulation.setTimezoneOverride','Page.navigate','Runtime.evaluate','RAW_RECEIVED','Emulation.setTimezoneOverride','Runtime.evaluate']);
    assert.equal(calls[1].params.timezoneId,target??'');assert.equal(calls[5].params.timezoneId,'');
    assert(!calls.some(c=>/addScript|DeviceMetrics|UserAgent|Navigator|Geolocation/.test(c.method)));
  }
});

test('raw upload failure is retained and timezone override still cleared',async()=>{
  const calls=[];
  const r=await executeFlow(async(method,params)=>{calls.push({method,params});return {};},'UTC',async()=>{throw Error('no current receipt');},async()=>{});
  assert.equal(r.status,'FAILED');assert.equal(r.rollback_status,'COMPLETED');
  assert.match(r.error,/no current receipt/);assert.equal(calls.at(-2).params.timezoneId,'');
});

test('rollback errors are distinct from successful collection',async()=>{
  const r=await executeFlow(async(method,params)=>{
    if(method==='Emulation.setTimezoneOverride'&&params.timezoneId==='')throw Error('rollback failed');
    return {};
  },'UTC',async()=>({session_id:'same'}),async()=>{});
  assert.equal(r.apply_status,'COMPLETED');assert.equal(r.raw_receipt.session_id,'same');
  assert.equal(r.status,'FAILED');assert.equal(r.rollback_status,'FAILED');
});

test('raw gate accepts only current context and rejects duplicate sessions',async()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'timezone-cdp-test-')),file=path.join(dir,'raw.jsonl');
  const row=context=>({session_id:context,canonical_received_payload:{collection_manifest:{runtime_context:context}}});
  try {
    fs.writeFileSync(file,JSON.stringify(row('other'))+'\n'+JSON.stringify(row('current'))+'\n');
    const r=await waitForRaw(file,0,'current',1);assert.equal(r.session_id,'current');
    fs.appendFileSync(file,JSON.stringify(row('current'))+'\n');
    await assert.rejects(waitForRaw(file,0,'current',1),/Multiple current raw/);
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});
