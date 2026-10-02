import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {executeFlow,PARAMETERS} from './screen_cdp.mjs';
test('screen parameters exactly reuse saved configuration',()=>{
 const configs=JSON.parse(fs.readFileSync(new URL('../webgl1_fresh_comparison_v1/CONFIGURATIONS.json',import.meta.url)));
 assert.deepEqual(PARAMETERS,configs.find(x=>x.id==='cdp_screen_metrics_only_v1').cdpEmulation.applyCommands[0].params);
});
test('only screen override and flow control, no injected observer; clear after raw',async()=>{
 for(const active of [false,true]){
  const calls=[];let raw=false;
  const send=async(m,p)=>{if(m==='Emulation.clearDeviceMetricsOverride'&&calls.length>2)assert.equal(raw,true);calls.push([m,p]);return {result:{value:{inner_width:393}}};};
  const r=await executeFlow(send,active,async()=>{raw=true;return {session_id:'s'};},async()=>{});
  assert.equal(r.status,'COMPLETED');assert.deepEqual(calls.map(x=>x[0]),['Page.enable',active?'Emulation.setDeviceMetricsOverride':'Emulation.clearDeviceMetricsOverride','Page.navigate','Runtime.evaluate','Emulation.clearDeviceMetricsOverride','Runtime.evaluate']);
 }
});
test('failed observation keeps failure and still rolls back',async()=>{
 const calls=[];const r=await executeFlow(async(m)=>{calls.push(m);return {};},true,async()=>{throw new Error('raw missing');},async()=>{});
 assert.equal(r.status,'FAILED');assert.equal(r.rollback_status,'COMPLETED');assert(calls.includes('Emulation.clearDeviceMetricsOverride'));
});
