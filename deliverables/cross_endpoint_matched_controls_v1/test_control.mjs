import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {positions,route} from './collect.mjs';
test('42 unique positions, 14 triplets, 8 intended interventions',()=>{
 const p=positions('test');assert.equal(p.length,42);assert.equal(new Set(p.map(s=>s.sample_id)).size,42);assert.equal(new Set(p.map(s=>s.scenario_group_id)).size,14);assert.equal(p.filter(s=>route(s).kind.startsWith('runtime_')).length,8);
});
test('normal settings use real-setting route; pre/post install no target control',()=>{
 for(const s of positions('test')){const r=route(s);if(s.phase!=='change')assert.equal(r.kind,'none');else if(s.scenario.startsWith('L_'))assert.equal(r.kind,'real_setting');}
});
test('App and Browser endpoints are disjoint; no label depends on detection output',()=>{
 for(const s of positions('test').filter(s=>s.phase==='change'&&s.scenario.startsWith('A_'))){assert.equal(route(s).endpoint,s.scenario.startsWith('A_APP')?'app':'browser');assert.deepEqual(route({...s,detector_output:'T'}),route({...s,detector_output:'F'}));}
});
test('normal settings module has no runtime override mechanism',()=>{
 const s=fs.readFileSync(new URL('settings_control.py',import.meta.url),'utf8');assert(!s.includes('Runtime.evaluate'));assert(!s.includes('Emulation.set'));assert(s.includes("'cmd','alarm','set-timezone'"));
});
