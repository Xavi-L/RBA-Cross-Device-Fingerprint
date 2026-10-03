import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {FAULT_SCRIPT,executeFault} from './fault_cdp.mjs';
test('fault changes only the geometry return, leaves other probe methods and screen alone',()=>{
 const ctx={window:{screen:{width:393}}};vm.runInNewContext(FAULT_SCRIPT,ctx);
 const update=()=>42;ctx.window.HybridGuardProbe={captureWebViewGeometry:()=>({ok:true}),updateResult:update};
 assert.equal(ctx.window.HybridGuardProbe.captureWebViewGeometry(),null);
 assert.equal(ctx.window.__geometryFaultCalls,1);assert.equal(ctx.window.HybridGuardProbe.updateResult,update);
 assert.equal(ctx.window.screen.width,393);
});
test('single bounded fault workflow holds evidence beyond the 5s module timeout',async()=>{
 const calls=[],pauses=[];const send=async(m,p)=>{calls.push([m,p]);return m==='Page.addScriptToEvaluateOnNewDocument'?{identifier:'i'}:{result:{value:{calls:2}}};};
 const r=await executeFault(send,false,async()=>({session_id:'s'}),async ms=>pauses.push(ms));
 assert.equal(r.status,'COMPLETED');assert.deepEqual(pauses,[1000,6000]);
 assert.ok(calls.some(c=>c[0]==='Page.removeScriptToEvaluateOnNewDocument'));
 assert.ok(!calls.some(c=>c[0]==='Emulation.setDeviceMetricsOverride'));
});
